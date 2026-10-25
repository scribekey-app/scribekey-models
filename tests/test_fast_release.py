"""The release evidence must describe the exact evaluated weights and notices."""

import hashlib
import json
from pathlib import Path

from scribekey_models.catalog import load_cleanup_catalog_data

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "cleanup" / "scribekey-fast-v1"


def test_fast_release_evidence_keeps_identity_terms_and_qualification_together() -> None:
    provenance = json.loads((ASSETS / "provenance.json").read_text())
    evaluation = json.loads((ASSETS / "evaluation.json").read_text())
    examples = json.loads((ASSETS / "examples.json").read_text())
    q8 = provenance["artifacts"]["q8_0"]
    assert q8["sha256"] == evaluation["artifact_sha256"] == examples["q8_sha256"]
    assert provenance["model_id"] == "scribekey-cleanup-fast"
    assert provenance["training"]["rows"] == sum(provenance["training"]["source_counts"].values())
    assert provenance["production_promoted"] is False
    assert evaluation["final_artifact_phone"] == evaluation["midrange_phone"] == "not measured"
    assert hashlib.sha256((ASSETS / "LICENSE").read_bytes()).hexdigest() == (
        provenance["licensing"]["lfm_license_snapshot"]["sha256"]
    )
    notice = (ASSETS / "NOTICE").read_text()
    assert "MIT License (applies to the Sotto fine-tune)" in notice
    assert "ductai199x/dictation-speech" in notice and "CC BY-SA 4.0" in notice
    assert "LFM Open License v1.0" in notice


def test_fast_catalogue_pins_the_verified_private_upload() -> None:
    receipt = json.loads((ASSETS / "private-upload-receipt.json").read_text())
    uploaded = next(r for r in receipt["repositories"] if r["repo_id"].endswith("-GGUF"))
    catalogue = load_cleanup_catalog_data()
    model = next(m for m in catalogue["candidates"] if m["modelId"] == "scribekey-cleanup-fast")
    assert model["revision"] == uploaded["commit"] == model["provenance"]["exportRevision"]
    assert model["sha256"] == uploaded["weight_sha256"]
    assert model["sizeBytes"] == uploaded["weight_bytes"]
    assert f"/resolve/{uploaded['commit']}/" in model["downloadUrl"]
    assert model["promptTemplate"] == "InputOutputControlLine"
    assert catalogue["production"]["modelId"] == "sotto"
