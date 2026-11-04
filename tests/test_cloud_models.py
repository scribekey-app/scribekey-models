from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from scribekey_models.catalog import (
    MAX_CLOUD_MODELS_BYTES,
    generate_cloud_models,
    validate_cloud_models,
)
from scribekey_models.promotion import build_channel_distribution_manifest, create_release_manifest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "models_dev_snapshot.json").read_text(encoding="utf-8"))
SNAPSHOT_SCHEMA = json.loads((ROOT / "schemas" / "models_dev_snapshot.schema.json").read_text(encoding="utf-8"))
PROFILE_SCHEMA = json.loads((ROOT / "schemas" / "cloud_models.schema.json").read_text(encoding="utf-8"))


def errors(schema: dict[str, Any], doc: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [error.message for error in validator.iter_errors(doc)]


def test_trimmed_snapshot_generates_generic_profiles() -> None:
    assert errors(SNAPSHOT_SCHEMA, FIXTURE) == []
    generated = generate_cloud_models(FIXTURE)
    assert errors(PROFILE_SCHEMA, generated) == []
    assert validate_cloud_models(generated) == []
    assert len(json.dumps(generated).encode("utf-8")) < MAX_CLOUD_MODELS_BYTES
    assert set(generated["providers"]) == {
        "openai", "anthropic", "gemini", "groq", "cerebras", "openrouter", "mistral", "alibabacloud", "nvidia", "foundry"
    }
    assert generated["providers"]["openai"]["models"] == {
        "reason-effort": {
            "text": True,
            "temperature": True,
            "price": {"input": 1, "output": 2},
            "outputLimit": 100,
            "reasoningOff": {"reasoning_effort": "none"},
        },
        # Free models price both input and output at zero and stay.
        "free-text": {"text": True, "temperature": True, "price": {"input": 0, "output": 0}},
    }
    assert generated["providers"]["anthropic"]["models"]["reason-toggle"]["reasoningOff"] == {
        "thinking": {"type": "disabled"}
    }
    assert generated["providers"]["gemini"]["models"]["reason-minimal"]["reasoningOff"] == {
        "reasoning_effort": "minimal"
    }
    assert generated["providers"]["openrouter"]["models"]["reason-low"]["reasoningOff"] == {
        "reasoning": {"effort": "low"}
    }
    assert generated["providers"]["groq"]["models"]["plain"]["temperature"] is False
    assert "reasoningOff" not in generated["providers"]["groq"]["models"]["plain"]
    assert generated["providers"]["alibabacloud"]["models"]["reason-toggle"]["reasoningOff"] == {
        "enable_thinking": False
    }
    # Image output and an input-priced embedding (output 0) are not text generators.
    assert set(generated["providers"]["openai"]["models"]) == {"reason-effort", "free-text"}


def test_latest_probe_rejection_drops_parameter_for_provider(tmp_path: Path) -> None:
    provider_dir = tmp_path / "openai"
    provider_dir.mkdir()
    (provider_dir / "older.json").write_text(
        json.dumps({"verifiedAt": "2026-11-01T00:00:00Z", "params": {"reasoning_effort": "accepted"}}),
        encoding="utf-8",
    )
    (provider_dir / "newer.json").write_text(
        json.dumps({
            "verifiedAt": "2026-11-03T00:00:00Z",
            "params": {
                "reasoning_effort": "rejected",
                "temperature": "rejected",
                "max_completion_tokens": "rejected",
            },
        }),
        encoding="utf-8",
    )
    generated = generate_cloud_models(FIXTURE, tmp_path)
    openai = generated["providers"]["openai"]
    assert "reasoningEffortPath" not in openai["protocol"]
    assert "reasoningToggleOff" not in openai["protocol"]
    assert "temperatureField" not in openai["protocol"]
    assert "reasoningTokenField" not in openai["protocol"]
    assert openai["models"]["reason-effort"]["reasoningOff"] is None
    assert openai["models"]["reason-effort"]["temperature"] is False
    assert openai["protocol"]["verifiedParams"] == {
        "reasoning_effort": "rejected",
        "temperature": "rejected",
        "max_completion_tokens": "rejected",
    }


def test_release_and_channel_include_cloud_models_reference() -> None:
    content = json.dumps(generate_cloud_models(FIXTURE), indent=2) + "\n"
    release = create_release_manifest(
        "2026.11.2",
        "cloud profiles",
        speech_content="{}\n",
        diarization_content="{}\n",
        cleanup_content="{}\n",
        cloud_models_content=content,
    )
    assert release["catalogs"]["cloudModels"]["filename"] == "cloud_models.json"
    channel = build_channel_distribution_manifest("qa", release, sequence=1)
    assert channel["catalogs"]["cloudModels"]["path"] == "../releases/2026.11.2/cloud_models.json"
    assert "cloud-model-profiles" in channel["compatibility"]["supportedConfigFamilies"]
