import importlib.util
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
_PATH = ROOT / "bench/asr/references/compare.py"
_SPEC = importlib.util.spec_from_file_location("references_compare", _PATH)
compare = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(compare)

FLEURS = "FLEURS test"


def _ref(model, source, languages, dataset=FLEURS):
    return {
        "model": model,
        "source": source,
        "dataset": dataset,
        "languages": {
            lang: {"metric": metric, "errorPercent": value}
            for lang, (metric, value) in languages.items()
        },
    }


def test_comparisons_skip_other_metrics_and_non_fleurs_sets() -> None:
    results = {"a": {"en": ("wer", 5.0), "zh": ("cer", 9.0)}}
    rows = compare.comparisons(
        results,
        [
            _ref("a", "s", {"en": ("wer", 4.0), "zh": ("wer", 3.0)}),
            _ref("a", "board-en", {"en": ("wer", 1.0)}, dataset="English short-form average"),
        ],
    )
    assert [(r["lang"], r["source"], r["delta"]) for r in rows] == [("en", "s", 1.0)]
    assert rows[0]["relative"] == 0.25


def test_above_reference_needs_both_thresholds_against_the_best_reference() -> None:
    results = {
        "both": {"en": ("wer", 9.0)},  # +5 points, +125% vs best 4.0
        "relative-only": {"en": ("wer", 3.0)},  # +1.5 points, +100%
        "points-only": {"en": ("wer", 43.0)},  # +3 points, +7.5%
    }
    refs = [
        _ref("both", "s1", {"en": ("wer", 4.0)}),
        _ref("both", "s2", {"en": ("wer", 8.0)}),  # within thresholds of this one; best is s1
        _ref("relative-only", "s1", {"en": ("wer", 1.5)}),
        _ref("points-only", "s1", {"en": ("wer", 40.0)}),
    ]
    flagged = compare.above_reference(compare.comparisons(results, refs))
    assert [(r["model"], r["source"]) for r in flagged] == [("both", "s1")]


def test_non_fleurs_reference_is_never_flagged() -> None:
    results = {"a": {"en": ("wer", 20.0)}}
    refs = [_ref("a", "board-en", {"en": ("wer", 2.0)}, dataset="Open ASR English average")]
    rows = compare.comparisons(results, refs)
    assert rows == []
    assert compare.above_reference(rows) == [] and compare.order_flips(rows) == []


def test_order_flips_are_per_source_and_ignore_ties() -> None:
    results = {"a": {"en": ("wer", 5.0)}, "b": {"en": ("wer", 6.0)}, "c": {"en": ("wer", 7.0)}}
    refs = [
        _ref("a", "s1", {"en": ("wer", 4.0)}),
        _ref("b", "s1", {"en": ("wer", 3.0)}),  # a < b ours, a > b here: flip
        _ref("c", "s1", {"en": ("wer", 3.0)}),  # b == c here: tie, no flip; a vs c flips
        _ref("a", "s2", {"en": ("wer", 1.0)}),
        _ref("b", "s2", {"en": ("wer", 2.0)}),  # agrees with ours
    ]
    flips = compare.order_flips(compare.comparisons(results, refs))
    assert [(f["source"], f["a"]["model"], f["b"]["model"]) for f in flips] == [
        ("s1", "a", "b"),
        ("s1", "a", "c"),
    ]


def test_report_lists_flags_and_unreferenced_measurements(tmp_path: Path) -> None:
    results = tmp_path / "results"
    results.mkdir()
    for model, langs in {"a": {"en": 9.0, "de": 4.0}, "b": {"en": 6.0}}.items():
        data = {
            "model": model,
            "languages": {
                lang: {"metric": "wer", "errorPercent": value} for lang, value in langs.items()
            },
        }
        (results / f"{model}.json").write_text(json.dumps(data))
    refs = tmp_path / "references.yaml"
    refs.write_text(
        yaml.safe_dump(
            {
                "references": [
                    _ref("a", "s", {"en": ("wer", 4.0)}),
                    _ref("b", "s", {"en": ("wer", 5.0)}),
                ]
            }
        )
    )
    text = compare.report(results, refs)
    assert "| a | 9.00 | s | 4.00 | +5.00 | +125% |" in text
    assert "- above reference: a en measures 9.00" in text
    assert "- order flip in en (s): ours a 9.00 vs b 6.00; reference 4.00 vs 5.00" in text
    assert "No published FLEURS figure to compare: a de." in text


def test_report_runs_on_the_committed_data() -> None:
    assert compare.report().startswith("## Measured FLEURS error")


def test_references_parse_and_name_catalogue_models() -> None:
    catalogue = yaml.safe_load((ROOT / "catalog/speech.yaml").read_text())
    ids = {model["id"] for model in catalogue["models"]}
    references = compare.load_references(compare.REFERENCES)
    assert references
    seen = set()
    for ref in references:
        assert ref["model"] in ids, ref["model"]
        assert (ref["model"], ref["source"]) not in seen
        seen.add((ref["model"], ref["source"]))
        for field in ("url", "revision", "fetched", "build", "dataset", "normaliser"):
            assert ref[field], (ref["model"], ref["source"], field)
        assert ref["languages"]
        for lang, value in ref["languages"].items():
            assert value["metric"] in {"wer", "cer"}, (ref["model"], lang)
            assert isinstance(value["errorPercent"], (int, float)), (ref["model"], lang)
