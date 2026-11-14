"""Set our FLEURS measurements beside published figures for the same models, and flag disagreements.

    python3 bench/asr/references/compare.py [results-dir] [references.yaml]

A report, never a gate: it always exits 0. `report()` returns the same markdown for a PR body.
Published figures measure other builds, so they never become grades (README.md).

Flags:
- above reference: our error exceeds the best (lowest) reference for that model and language by more
  than REL_THRESHOLD relative AND ABS_THRESHOLD points. Both, so a 1.5 -> 2.4 gap on a strong model and a
  40 -> 43 gap on a weak language stay quiet; together they mean a harness or export problem worth a look.
- order flip: two models we measured in a language, both in one reference source, rank the other way
  round there. Ties on either side are not flips.

Only FLEURS references with the same metric as ours (wer or cer) are compared.
"""

import json
import sys
from itertools import combinations
from pathlib import Path

import yaml

HERE = Path(__file__).parent
RESULTS = HERE.parent / "fleurs" / "results"
REFERENCES = HERE / "references.yaml"
REL_THRESHOLD = 0.5
ABS_THRESHOLD = 2.0


def load_results(results_dir: Path) -> dict[str, dict[str, tuple[str, float]]]:
    """{model: {lang: (metric, errorPercent)}} from results/*.json."""
    out = {}
    for path in sorted(Path(results_dir).glob("*.json")):
        data = json.loads(path.read_text())
        out[data["model"]] = {
            lang: (v["metric"], v["errorPercent"]) for lang, v in data["languages"].items()
        }
    return out


def load_references(references_path: Path) -> list[dict]:
    return yaml.safe_load(Path(references_path).read_text())["references"]


def is_fleurs(reference: dict) -> bool:
    return reference["dataset"].startswith("FLEURS")


def comparisons(results: dict, references: list[dict]) -> list[dict]:
    """One row per (model, language, reference) where the reference is FLEURS and the metric matches."""
    out = []
    for ref in references:
        if not is_fleurs(ref):
            continue
        ours = results.get(ref["model"], {})
        for lang, value in ref["languages"].items():
            if lang not in ours or ours[lang][0] != value["metric"]:
                continue
            measured, published = ours[lang][1], value["errorPercent"]
            out.append(
                {
                    "model": ref["model"],
                    "lang": lang,
                    "metric": value["metric"],
                    "source": ref["source"],
                    "ours": measured,
                    "reference": published,
                    "delta": round(measured - published, 2),
                    "relative": (measured - published) / published if published else None,
                }
            )
    return out


def above_reference(
    rows: list[dict], rel: float = REL_THRESHOLD, points: float = ABS_THRESHOLD
) -> list[dict]:
    """The best reference per (model, lang) when ours exceeds it by more than both thresholds."""
    best: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row["model"], row["lang"])
        if key not in best or row["reference"] < best[key]["reference"]:
            best[key] = row
    return [
        row
        for row in best.values()
        if row["ours"] - row["reference"] > points and row["ours"] > row["reference"] * (1 + rel)
    ]


def order_flips(rows: list[dict]) -> list[dict]:
    """Pairs of models whose order in one source and language differs from ours."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        groups.setdefault((row["source"], row["lang"]), []).append(row)
    flips = []
    for (source, lang), group in sorted(groups.items()):
        for a, b in combinations(sorted(group, key=lambda r: r["model"]), 2):
            if (a["ours"] - b["ours"]) * (a["reference"] - b["reference"]) < 0:
                flips.append({"source": source, "lang": lang, "a": a, "b": b})
    return flips


def _pct(value: float | None) -> str:
    return "" if value is None else f"{value * 100:+.0f}%"


def report(results_dir: Path = RESULTS, references_path: Path = REFERENCES) -> str:
    results = load_results(results_dir)
    rows = comparisons(results, load_references(references_path))
    lines = ["## Measured FLEURS error against published figures", ""]
    for lang in sorted({r["lang"] for r in rows}):
        lines += [
            f"### {lang}",
            "",
            "| model | ours % | source | reference % | delta (points) | delta (relative) |",
            "|---|---|---|---|---|---|",
        ]
        for r in sorted(
            (r for r in rows if r["lang"] == lang),
            key=lambda r: (r["ours"], r["model"], r["source"]),
        ):
            lines.append(
                f"| {r['model']} | {r['ours']:.2f} | {r['source']} | {r['reference']:.2f} | "
                f"{r['delta']:+.2f} | {_pct(r['relative'])} |"
            )
        lines.append("")
    compared = {(r["model"], r["lang"]) for r in rows}
    missing = sorted(
        f"{model} {lang}"
        for model, langs in results.items()
        for lang in langs
        if (model, lang) not in compared
    )
    if missing:
        lines += ["No published FLEURS figure to compare: " + ", ".join(missing) + ".", ""]

    lines += [
        f"### Flags (above reference: > {REL_THRESHOLD:.0%} relative and > {ABS_THRESHOLD:g} "
        + "points over the best reference)",
        "",
    ]
    above = above_reference(rows)
    flips = order_flips(rows)
    for r in above:
        lines.append(
            f"- above reference: {r['model']} {r['lang']} measures {r['ours']:.2f}, "
            f"best reference {r['reference']:.2f} ({r['source']}), {r['delta']:+.2f} points"
        )
    for f in flips:
        a, b = f["a"], f["b"]
        lines.append(
            f"- order flip in {f['lang']} ({f['source']}): ours {a['model']} {a['ours']:.2f} vs "
            f"{b['model']} {b['ours']:.2f}; reference {a['reference']:.2f} vs {b['reference']:.2f}"
        )
    if not above and not flips:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = sys.argv[1:]
    results_dir = Path(args[0]) if args else RESULTS
    references_path = Path(args[1]) if len(args) > 1 else REFERENCES
    print(report(results_dir, references_path), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
