"""The release evidence must describe the exact evaluated weights and notices."""

import hashlib
import json
import re
from pathlib import Path

from scribekey_models.catalog import load_cleanup_catalog_data

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "cleanup" / "scribekey-fast-v1.1"


def test_fast_release_evidence_keeps_identity_terms_and_qualification_together() -> None:
    provenance = json.loads((ASSETS / "provenance.json").read_text())
    evaluation = json.loads((ASSETS / "evaluation.json").read_text())
    examples = json.loads((ASSETS / "examples.json").read_text())
    q8 = provenance["artifacts"]["q8_0"]
    assert q8["sha256"] == evaluation["artifact_sha256"] == examples["q8_sha256"]
    assert provenance["model_id"] == "scribekey-cleanup-fast"
    assert all(m["rows"] > provenance["training"]["replay_mix_rows"] for m in provenance["training"]["members"])
    assert provenance["production_promoted"] is False
    assert evaluation["final_artifact_phone"] == evaluation["midrange_phone"] == "not measured"
    assert hashlib.sha256((ASSETS / "LICENSE").read_bytes()).hexdigest() == (
        provenance["licensing"]["lfm_license_snapshot"]["sha256"]
    )
    notice = (ASSETS / "NOTICE").read_text()
    assert "MIT License (applies to the Sotto fine-tune)" in notice
    assert "ductai199x/dictation-speech" in notice and "CC BY-SA 4.0" in notice
    assert "LFM Open License v1.0" in notice


def test_fast_is_production_and_pins_the_verified_upload() -> None:
    receipt = json.loads((ASSETS / "upload-receipt.json").read_text())
    uploaded = next(r for r in receipt["repositories"] if r["repo_id"].endswith("-GGUF"))
    catalogue = load_cleanup_catalog_data()
    model = catalogue["production"]
    assert model["modelId"] == "scribekey-cleanup-fast"
    assert "experimental" not in model
    assert re.fullmatch(r"[0-9a-f]{40}", model["revision"])
    assert model["revision"] == model["provenance"]["exportRevision"]
    assert model["sha256"] == uploaded["weight_sha256"]
    assert model["sizeBytes"] == uploaded["weight_bytes"]
    assert f"/{uploaded['repo_id']}/resolve/{model['revision']}/" in model["downloadUrl"]
    sotto = next(m for m in catalogue["candidates"] if m["modelId"] == "sotto")
    assert sotto["retired"] is True and sotto["replacementId"] == model["modelId"]
    for gate in ("minDeviceMemoryGb", "minimumApiLevel", "supportedAbis", "supportedLanguages"):
        assert model[gate] == sotto[gate], gate
    assert model["promptTemplate"] == "InputOutputControlLine"
    assert model["license"] == "ScribeKey Fast + LFM v1.0"
    assert model["licenseUrl"].endswith(f"/{model['revision']}/ADDITIONAL_TERMS.md")
    assert "Derived from ScribeKey Fast by ScribeKey" in (ASSETS / "ADDITIONAL_TERMS.md").read_text()
    app_examples = json.loads((ASSETS / "app-examples.json").read_text())
    assert app_examples["artifact_sha256"] == model["sha256"]
    assert app_examples["examples"] == model["examples"]
    assert len(model["examples"]) == 4
    # The owner dropped the list demos; the cards show corrections, fillers, numbers, questions.
    assert all("\n" not in example["output"] for example in model["examples"])
    assert "$45" in model["examples"][2]["output"]
    assert model["examples"][3]["output"].endswith("?")
