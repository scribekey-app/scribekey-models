from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from scribekey_models.catalog import validate_cloud_tiers
from scribekey_models.promotion import build_channel_distribution_manifest, create_release_manifest

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "cloud_tiers.schema.json").read_text(encoding="utf-8"))


def tiers(**overrides: Any) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "schemaVersion": 1,
        "version": "2026.10.09",
        "generatedAt": "2026-10-09",
        "tasks": {
            "enhance": {
                "providers": {
                    "openai": {
                        "recommended": "balanced",
                        "tiers": {
                            "balanced": {"model": "gpt-5.6-luna", "score": 0.99, "p50Seconds": 1.1, "usdPer1k": 0.2},
                            "budget": {"model": "gpt-6-luna", "score": 0.97, "p50Seconds": 1.1, "usdPer1k": 0.1},
                        },
                    }
                }
            }
        },
    }
    doc.update(overrides)
    return doc


def errors(doc: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
    return [e.message for e in validator.iter_errors(doc)]


def test_valid_tiers_pass() -> None:
    assert errors(tiers()) == []
    assert validate_cloud_tiers(tiers()) == []


def test_unknown_provider_and_odd_model_ids_are_rejected() -> None:
    doc = tiers()
    doc["tasks"]["enhance"]["providers"]["evil"] = doc["tasks"]["enhance"]["providers"]["openai"]
    assert errors(doc)
    doc = tiers()
    doc["tasks"]["enhance"]["providers"]["openai"]["tiers"]["budget"]["model"] = "gpt 6; rm -rf"
    assert errors(doc)


def test_recommended_tier_must_exist() -> None:
    doc = tiers()
    doc["tasks"]["enhance"]["providers"]["openai"]["recommended"] = "best"
    assert validate_cloud_tiers(doc) == ["enhance.openai: recommended tier 'best' is missing"]


def test_release_and_channel_carry_cloud_tiers_only_when_present() -> None:
    common = {"speech_content": "{}\n", "diarization_content": "{}\n", "cleanup_content": "{}\n"}
    without = create_release_manifest("2026.10.1", "x", **common)
    assert "cloudTiers" not in without["catalogs"]
    assert "cloudTiers" not in build_channel_distribution_manifest("qa", without, sequence=1)["catalogs"]

    content = json.dumps(tiers(), indent=2) + "\n"
    release = create_release_manifest("2026.10.1", "x", cloud_tiers_content=content, **common)
    assert release["catalogs"]["cloudTiers"]["filename"] == "cloud_model_tiers.json"
    channel = build_channel_distribution_manifest("qa", release, sequence=1)
    assert channel["catalogs"]["cloudTiers"]["path"] == "../releases/2026.10.1/cloud_model_tiers.json"
    assert "cloud-model-tiers" in channel["compatibility"]["supportedConfigFamilies"]
