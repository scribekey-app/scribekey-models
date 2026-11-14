from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import yaml

FLEURS_DIR = Path(__file__).resolve().parents[1] / "bench/asr/fleurs"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"fleurs_{name}", FLEURS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plan = _load("plan")
collect = _load("collect")
report = _load("report")

EXPORT = "owner/export@abc123"


def _result(langs: dict[str, float], export: str = EXPORT, sherpa: str = "1.0.0") -> dict:
    return {
        "model": "m",
        "export": export,
        "sherpaOnnx": sherpa,
        "mode": "offline",
        "dataset": "google/fleurs test",
        "languages": {
            lang: {"metric": "wer", "errorPercent": e, "clips": 1, "audioSeconds": 1}
            for lang, e in langs.items()
        },
    }


@pytest.fixture
def bench(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "catalog").mkdir()
    (tmp_path / "results").mkdir()
    model = {
        "id": "m",
        "languageCodes": ["en", "de"],
        "provenance": {"exportRepository": "owner/export", "exportRevision": "abc123"},
    }
    (tmp_path / "catalog/speech.yaml").write_text(yaml.safe_dump({"models": [model]}))
    (tmp_path / "requirements.txt").write_text("sherpa-onnx==1.0.0\njiwer==4.0.0\n")
    monkeypatch.setattr(plan, "ROOT", tmp_path)
    monkeypatch.setattr(plan, "HERE", tmp_path)
    monkeypatch.setattr(collect, "HERE", tmp_path)
    return tmp_path


def _write(bench: Path, result: dict) -> None:
    (bench / "results/m.json").write_text(json.dumps(result))


def test_plan_lists_missing_languages(bench: Path) -> None:
    _write(bench, _result({"en": 5.0}))
    assert plan.plan([]) == [("m", "de")]


def test_plan_replans_whole_model_on_stale_export(bench: Path) -> None:
    _write(bench, _result({"en": 5.0, "de": 6.0}, export="owner/export@old"))
    assert plan.plan([]) == [("m", "de"), ("m", "en")]


def test_plan_replans_whole_model_on_stale_runtime(bench: Path) -> None:
    _write(bench, _result({"en": 5.0, "de": 6.0}, sherpa="0.9.0"))
    assert plan.plan([]) == [("m", "de"), ("m", "en")]


def test_plan_skips_up_to_date_model(bench: Path) -> None:
    _write(bench, _result({"en": 5.0, "de": 6.0}))
    assert plan.plan([]) == []


def _artifact(root: Path, lang: str, result: dict) -> None:
    folder = root / f"fleurs-m-{lang}"
    folder.mkdir(parents=True)
    (folder / "m.json").write_text(json.dumps(result))


def test_merge_adds_language_to_current_export(bench: Path, tmp_path: Path) -> None:
    _write(bench, _result({"en": 5.0}))
    _artifact(tmp_path / "art", "de", _result({"en": 5.0, "de": 6.0}))
    collect.merge(tmp_path / "art")
    merged = json.loads((bench / "results/m.json").read_text())
    assert {k: v["errorPercent"] for k, v in merged["languages"].items()} == {"en": 5.0, "de": 6.0}


@pytest.mark.parametrize("stale", [{"export": "owner/export@old"}, {"sherpa": "0.9.0"}])
def test_merge_replaces_stale_result(bench: Path, tmp_path: Path, stale: dict) -> None:
    _write(bench, _result({"en": 5.0, "de": 6.0}, **stale))
    # measure.py may carry the old file's languages into its artifact; only the job's language counts
    _artifact(tmp_path / "art", "de", _result({"en": 5.0, "de": 7.5}))
    collect.merge(tmp_path / "art")
    merged = json.loads((bench / "results/m.json").read_text())
    assert merged["export"] == EXPORT and merged["sherpaOnnx"] == "1.0.0"
    assert {k: v["errorPercent"] for k, v in merged["languages"].items()} == {"de": 7.5}


def test_report_tables_measured_pairs_and_lists_failed(tmp_path: Path) -> None:
    _artifact(tmp_path, "en", _result({"en": 3.0}))
    body = report.report(
        [{"model": "m", "lang": "en"}, {"model": "m", "lang": "de"}], tmp_path, "boom"
    )
    assert "| m | en | wer | 3.0 | A+ |" in body
    assert "- m de" in body
    assert "boom" in body and "partial results" in body


def test_report_without_validate_failure_has_no_warning(tmp_path: Path) -> None:
    _artifact(tmp_path, "en", _result({"en": 12.0}))
    body = report.report([{"model": "m", "lang": "en"}], tmp_path)
    assert "| m | en | wer | 12.0 | C+ |" in body
    assert "Failed" not in body and "partial" not in body
