"""Write the body of the Measure speech accuracy PR: what this run measured, and what it planned but did not.

    python3 bench/asr/fleurs/report.py <plan.json> <artifacts-dir> [<validate-output>] > body.md

A planned pair with no `fleurs-<model>-<lang>` artifact is a job that failed or was cancelled.
"""

import json
import sys
from pathlib import Path

from scribekey_models.catalog import accuracy_grade


def report(planned: list[dict], artifacts: Path, validate_output: str | None = None) -> str:
    rows, failed = [], []
    for pair in planned:
        model, lang = pair["model"], pair["lang"]
        file = artifacts / f"fleurs-{model}-{lang}" / f"{model}.json"
        if not file.exists():
            failed.append(f"{model} {lang}")
            continue
        r = json.loads(file.read_text())["languages"][lang]
        rows.append(
            f"| {model} | {lang} | {r['metric']} | {r['errorPercent']} | {accuracy_grade(r['errorPercent'])} |"
        )
    out = ["Measured by the Measure speech accuracy workflow on each model's shipped export.", ""]
    if rows:
        out += [
            "| Model | Language | Metric | Error % | Grade |",
            "| --- | --- | --- | --- | --- |",
            *rows,
            "",
        ]
    else:
        out += ["Nothing was measured.", ""]
    if failed:
        out += ["Failed, not measured:", "", *[f"- {p}" for p in failed], ""]
    if validate_output is not None:
        out += [
            "`scribekey-models validate` fails, so this PR holds partial results:",
            "",
            "```",
            validate_output.strip(),
            "```",
            "",
        ]
    return "\n".join(out)


def cross_check() -> str:
    """Published figures beside ours (bench/asr/references), so a reviewer sees a harness slip."""
    sys.path.insert(0, str(Path(__file__).parents[1] / "references"))
    import compare

    return "## Cross-check against published figures\n\n" + compare.report(compare.RESULTS, compare.REFERENCES)


if __name__ == "__main__":
    plan = json.loads(Path(sys.argv[1]).read_text())["include"]
    validate = Path(sys.argv[3]).read_text() if len(sys.argv) > 3 else None
    print(report(plan, Path(sys.argv[2]), validate))
    print(cross_check())
