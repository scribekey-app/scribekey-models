"""Merge downloaded workflow results into results/, then write each model's numbers into catalog/speech.yaml.

    gh run download <run-id> --dir /tmp/fleurs-artifacts
    python3 bench/asr/fleurs/collect.py /tmp/fleurs-artifacts

Each artifact is one model's result file holding the language its job measured (plus any committed
before). A language is taken from the artifact named for it, so two jobs never overwrite each other.
An artifact measured on another export or sherpa-onnx than the result file replaces the file.
The YAML is edited line by line, replacing or inserting only the `accuracy:` block, so comments and
layout survive.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
SPEECH = ROOT / "catalog/speech.yaml"


def merge(artifacts: Path) -> set[str]:
    touched = set()
    (HERE / "results").mkdir(exist_ok=True)
    for folder in sorted(artifacts.glob("fleurs-*")):
        for file in folder.glob("*.json"):
            incoming = json.loads(file.read_text())
            model, lang = incoming["model"], folder.name.removeprefix(f"fleurs-{incoming['model']}-")
            target = HERE / "results" / f"{model}.json"
            current = json.loads(target.read_text()) if target.exists() else {}
            if any(current.get(k) != incoming[k] for k in ("export", "sherpaOnnx")):
                current = {"languages": {}}  # a stale result keeps none of the old export's numbers
            current.update({k: v for k, v in incoming.items() if k != "languages"})
            current["languages"][lang] = incoming["languages"][lang]
            target.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
            touched.add(model)
    return touched


def write_accuracy() -> None:
    results = {p.stem: json.loads(p.read_text())["languages"] for p in (HERE / "results").glob("*.json")}
    lines, out, model = SPEECH.read_text().split("\n"), [], None
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("  - id: "):
            model = line.removeprefix("  - id: ").strip()
        if line == "    accuracy:":  # drop the old block; it is rewritten before `files:`
            i += 1
            while i < len(lines) and lines[i].startswith("      "):
                i += 1
            continue
        if line == "    files:" and model in results:
            out.append("    accuracy:")
            out += [f"      {lang}: {r['errorPercent']}" for lang, r in sorted(results[model].items())]
        out.append(line)
        i += 1
    SPEECH.write_text("\n".join(out))


if __name__ == "__main__":
    print("merged:", ", ".join(sorted(merge(Path(sys.argv[1])))) if len(sys.argv) > 1 else "nothing")
    write_accuracy()
