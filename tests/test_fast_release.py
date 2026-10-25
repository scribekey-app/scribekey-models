"""The release evidence must describe the exact evaluated weights and notices."""

import hashlib
import json
from pathlib import Path

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
