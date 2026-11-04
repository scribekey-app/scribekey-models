from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from scribekey_models import catalog, cloud_refresh
from scribekey_models.cli import main

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/models_dev_snapshot.json").read_text(encoding="utf-8"))


def api_response(snapshot: dict) -> bytes:
    return json.dumps(
        {
            provider: snapshot["providers"][provider]
            for provider in {config["modelsDevId"] for config in catalog.CLOUD_PROVIDER_PROTOCOLS.values()}
        }
    ).encode("utf-8")


def setup_catalog(tmp_path: Path, monkeypatch, snapshot: dict = FIXTURE) -> tuple[Path, Path]:
    snapshot_path = tmp_path / "catalog/models_dev_snapshot.json"
    generated_dir = tmp_path / "generated"
    snapshot_path.parent.mkdir(parents=True)
    generated_dir.mkdir()
    snapshot_path.write_text(catalog._render_json(snapshot), encoding="utf-8")
    profiles_path = generated_dir / "cloud_models.json"
    profiles_path.write_text(catalog._render_json(catalog.generate_cloud_models(snapshot)), encoding="utf-8")
    monkeypatch.setattr(catalog, "CLOUD_MODELS_SNAPSHOT_FILE", snapshot_path)
    monkeypatch.setattr(catalog, "GENERATED_DIR", generated_dir)
    return snapshot_path, profiles_path


def test_unchanged_snapshot_prints_no_change_and_writes_nothing(tmp_path, monkeypatch, capsys) -> None:
    raw = api_response(FIXTURE)
    snapshot = copy.deepcopy(FIXTURE)
    snapshot["source"]["sha256"] = hashlib.sha256(raw).hexdigest()
    snapshot_path, profiles_path = setup_catalog(tmp_path, monkeypatch, snapshot)
    before = snapshot_path.read_bytes(), profiles_path.read_bytes()
    monkeypatch.setattr(cloud_refresh, "fetch_models_dev_api", lambda: raw)
    monkeypatch.setattr(sys, "argv", ["scribekey-models", "cloud", "refresh"])

    main()

    assert capsys.readouterr().out.strip() == "no change"
    assert (snapshot_path.read_bytes(), profiles_path.read_bytes()) == before


def test_added_model_and_profile_field_changes_are_summarized(tmp_path, monkeypatch) -> None:
    snapshot = copy.deepcopy(FIXTURE)
    upstream = json.loads(api_response(snapshot))
    upstream["openai"]["models"]["new-model"] = copy.deepcopy(upstream["openai"]["models"]["reason-effort"])
    upstream["openai"]["models"] = dict(reversed(list(upstream["openai"]["models"].items())))
    upstream["openai"]["models"]["reason-effort"]["temperature"] = False
    upstream["openai"]["models"]["reason-effort"]["cost"]["output"] = 2.5
    upstream["openai"]["models"]["reason-effort"]["limit"]["output"] = 101
    upstream["openai"]["models"]["reason-effort"]["reasoning_options"][0]["values"] = ["low"]
    snapshot_path, _ = setup_catalog(tmp_path, monkeypatch)
    monkeypatch.setattr(cloud_refresh, "fetch_models_dev_api", lambda: json.dumps(upstream).encode())

    result = cloud_refresh.refresh_cloud_models()

    assert result is not None
    summary, _ = result
    assert "Added models: `new-model`" in summary
    assert "reasoningOff:" in summary
    assert "temperature:" in summary
    assert "price:" in summary
    assert "outputLimit:" in summary
    assert json.loads(snapshot_path.read_text())["providers"]["openai"]["models"]["new-model"]
    generated_models = json.loads((catalog.GENERATED_DIR / "cloud_models.json").read_text())["providers"]["openai"]["models"]
    assert list(generated_models) == [
        *catalog.generate_cloud_models(FIXTURE)["providers"]["openai"]["models"],
        "new-model",
    ]


def test_removed_default_model_is_flagged_from_app_registry(tmp_path, monkeypatch) -> None:
    upstream = json.loads(api_response(FIXTURE))
    del upstream["openai"]["models"]["reason-effort"]
    app_dir = tmp_path / "app-checkout"
    registry = app_dir / cloud_refresh.APP_REGISTRY
    registry.parent.mkdir(parents=True)
    registry.write_text(
        'id = "openai", defaultModels = listOf(\n    "reason-effort",\n)\n'
        'id = FOUNDRY_PROVIDER_ID, defaultModels = listOf("deployment")\n',
        encoding="utf-8",
    )
    setup_catalog(tmp_path, monkeypatch)
    monkeypatch.setenv("SCRIBEKEY_APP_DIR", str(app_dir))
    monkeypatch.setattr(cloud_refresh, "fetch_models_dev_api", lambda: json.dumps(upstream).encode())

    result = cloud_refresh.refresh_cloud_models()

    assert result is not None
    assert "Removed models: `reason-effort`" in result[0]
    assert "Default models missing: `reason-effort`" in result[0]
    assert "Default models missing: `deployment`" in result[0]


def test_size_budget_refuses_both_writes(tmp_path, monkeypatch) -> None:
    upstream = json.loads(api_response(FIXTURE))
    upstream["openai"]["models"]["new-model"] = copy.deepcopy(upstream["openai"]["models"]["reason-effort"])
    snapshot_path, profiles_path = setup_catalog(tmp_path, monkeypatch)
    before = snapshot_path.read_bytes(), profiles_path.read_bytes()
    monkeypatch.setattr(catalog, "MAX_CLOUD_MODELS_BYTES", 1)
    monkeypatch.setattr(cloud_refresh, "fetch_models_dev_api", lambda: json.dumps(upstream).encode())

    with pytest.raises(ValueError, match="Refusing to write invalid cloud refresh"):
        cloud_refresh.refresh_cloud_models()

    assert (snapshot_path.read_bytes(), profiles_path.read_bytes()) == before


def test_open_pr_dry_run_prints_commands_without_running_them(tmp_path, monkeypatch, capsys) -> None:
    upstream = json.loads(api_response(FIXTURE))
    upstream["openai"]["models"]["new-model"] = copy.deepcopy(upstream["openai"]["models"]["reason-effort"])
    setup_catalog(tmp_path, monkeypatch)
    monkeypatch.setattr(cloud_refresh, "fetch_models_dev_api", lambda: json.dumps(upstream).encode())
    monkeypatch.setattr(sys, "argv", ["scribekey-models", "cloud", "refresh", "--open-pr"])
    monkeypatch.setattr("scribekey_models.cli.ROOT", tmp_path)
    subprocess_run = Mock()
    monkeypatch.setattr("scribekey_models.cli.subprocess.run", subprocess_run)

    main()

    output = capsys.readouterr().out
    subprocess_run.assert_not_called()
    assert "git switch -c cloud-profiles-refresh-" in output
    assert "git commit --only" in output
    assert "gh pr create --draft" in output
    assert list(tmp_path.glob("cloud-refresh-summary-*.md"))


def test_open_pr_yes_runs_only_the_printed_git_and_gh_commands(tmp_path, monkeypatch) -> None:
    upstream = json.loads(api_response(FIXTURE))
    upstream["openai"]["models"]["new-model"] = copy.deepcopy(upstream["openai"]["models"]["reason-effort"])
    setup_catalog(tmp_path, monkeypatch)
    monkeypatch.setattr(cloud_refresh, "fetch_models_dev_api", lambda: json.dumps(upstream).encode())
    monkeypatch.setattr(sys, "argv", ["scribekey-models", "cloud", "refresh", "--open-pr", "--yes"])
    monkeypatch.setattr("scribekey_models.cli.ROOT", tmp_path)
    subprocess_run = Mock()
    monkeypatch.setattr("scribekey_models.cli.subprocess.run", subprocess_run)

    main()

    commands = [call.args[0] for call in subprocess_run.call_args_list]
    assert [command[0] for command in commands] == ["git", "git", "gh"]
    assert commands[0][:3] == ["git", "switch", "-c"]
    assert commands[1][1:3] == ["commit", "--only"]
    assert commands[2][1:4] == ["pr", "create", "--draft"]
    assert all(call.kwargs == {"cwd": tmp_path, "check": True} for call in subprocess_run.call_args_list)
