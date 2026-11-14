"""Print what still needs measuring: one `<model-id> <lang>` line per pair, or a JSON matrix with --json.

A model is measured on its languageCodes; without them, on the languages it already has a grade in
(Qwen3 ASR, Nemotron 3.5); with neither (Omnilingual), on every language any catalogue model lists or
is graded in, which is every language the app can grade. A pair already in results/ is skipped, unless
the result is stale: measured on another export than the catalogue ships, or another sherpa-onnx than
requirements.txt pins. Then every language of that model is planned again.

    python3 bench/asr/fleurs/plan.py [--json] [<model-id> ...]
"""

import json
import re
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
FLEURS = set(re.findall(r'"([a-z]{2,3})": "[a-z0-9_]+"', (HERE / "measure.py").read_text()))


def pinned_sherpa() -> str:
    return re.search(r"^sherpa-onnx==(\S+)", (HERE / "requirements.txt").read_text(), re.MULTILINE).group(1)


def export(model: dict) -> str:
    """The `export` measure.py records, so a result can be matched against what the catalogue ships."""
    return f"{model['provenance']['exportRepository']}@{model['provenance']['exportRevision']}"


def plan(wanted: list[str]) -> list[tuple[str, str]]:
    models = yaml.safe_load((ROOT / "catalog/speech.yaml").read_text())["models"]
    every = {lang for m in models for lang in (m.get("languageCodes") or []) + list(m.get("accuracy") or {})}
    runtime, pairs = pinned_sherpa(), []
    for m in models:
        if wanted and m["id"] not in wanted:
            continue
        result = HERE / "results" / f"{m['id']}.json"
        current = json.loads(result.read_text()) if result.exists() else {}
        fresh = current.get("export") == export(m) and current.get("sherpaOnnx") == runtime
        done = current.get("languages", {}) if fresh else {}
        languages = set(m.get("languageCodes") or m.get("accuracy") or every) & FLEURS
        pairs += [(m["id"], lang) for lang in sorted(languages) if lang not in done]
    return pairs


if __name__ == "__main__":
    args = sys.argv[1:]
    as_json = "--json" in args
    pairs = plan([a for a in args if a != "--json"])
    if as_json:
        print(json.dumps({"include": [{"model": m, "lang": lang} for m, lang in pairs]}))
    else:
        print("\n".join(f"{m} {lang}" for m, lang in pairs))
