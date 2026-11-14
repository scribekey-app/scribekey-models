"""Re-fetch the Open ASR Leaderboard entries of references.yaml at one pinned leaderboard version.

    python3 bench/asr/references/fetch.py           # print the leaderboard entries
    python3 bench/asr/references/fetch.py --write   # replace them in references.yaml

The leaderboard's source datasets (hf-audio/multilingual_evals, hf-audio/open-asr-leaderboard-results)
are private: anonymous huggingface_hub downloads return 404 at every revision. So this reads the same
tables through the Space's public Gradio API, asking for VERSION, which the Space resolves to the dataset
revisions its init.py pins (recorded below for traceability). Only entries whose source starts with
"open-asr-leaderboard" are replaced; Handy and model-card entries are hand-curated and kept as they are.
Standard library and PyYAML only.
"""

import argparse
import json
import math
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

import yaml

HERE = Path(__file__).parent
REFERENCES = HERE / "references.yaml"

SPACE = "https://hf-audio-open-asr-leaderboard.hf.space"
SPACE_REPO = "https://huggingface.co/spaces/hf-audio/open_asr_leaderboard"
# hf-audio/open_asr_leaderboard commit whose init.py was read; VERSION is its latest entry (v1.16.0),
# which pins hf-audio/multilingual_evals and hf-audio/open-asr-leaderboard-results at these revisions.
SPACE_REVISION = "3b5317f4e49b6cb40502b95065b29fbfe08284ce"
VERSION = "13-11-2026"
MULTILINGUAL_REVISION = "7aa0b0918a319f8f1b66a0b32d24ddd4342b54fb"
ENGLISH_REVISION = "5f5053c3bbae932f547bf8ebb82f90673541d859"

# Leaderboard row name -> catalogue ids. Exact names only: "(fast-gpu-asr)" rows are another runtime.
MODELS = {
    "nvidia/parakeet-tdt-0.6b-v2": ["parakeet-0.6b-v2"],
    "nvidia/parakeet-tdt-0.6b-v3": ["parakeet-0.6b-v3"],
    "Qwen/Qwen3-ASR-0.6B-hf": ["qwen3-asr-0.6b"],
    "nvidia/nemotron-speech-streaming-en-0.6b": ["nemotron-en-0.6b"],
    "nvidia/nemotron-3.5-asr-streaming-0.6b": ["nemotron-3.5-0.6b-560ms"],
}
# Multilingual breakdown label -> language code. Hindi is left out: the leaderboard has no FLEURS Hindi.
LANGUAGES = {
    "🇫🇷 French": "fr",
    "🇩🇪 German": "de",
    "🇪🇸 Spanish": "es",
    "🇮🇹 Italian": "it",
    "🇵🇹 Portuguese": "pt",
    "🇳🇱 Dutch": "nl",
    "🇦🇲 Armenian": "hy",
    "🇨🇳 Chinese": "zh",
}
ENGLISH_COLUMNS = [
    "RTFx ⬆️️",
    "AMI-Cleaned",
    "Earnings22-Cleaned-AA-chunked",
    "Gigaspeech-Cleaned",
    "SPGISpeech",
    "URGENT24",
    "Voice Arena Monsoon",
    "Voxpopuli-AA-Cleaned",
    "Private (scripted)",
    "Private (conversational)",
]
BUILD = "checkpoint as submitted to the leaderboard; precision and hardware not stated"
NORMALISER = "Open ASR Leaderboard normaliser, Whisper-style (huggingface/open_asr_leaderboard)"


def call(fn: str, data: list) -> list:
    url = f"{SPACE}/gradio_api/call/{fn}"
    body = json.dumps({"data": data}).encode()
    request = urllib.request.Request(url, body, {"Content-Type": "application/json"})
    event = json.load(urllib.request.urlopen(request, timeout=60))["event_id"]
    stream = urllib.request.urlopen(f"{url}/{event}", timeout=300).read().decode()
    last = [line for line in stream.splitlines() if line.startswith(("event:", "data:"))][-2:]
    if not last or last[0] != "event: complete":
        raise SystemExit(f"{fn} did not complete: {last}")
    return json.loads(last[1].removeprefix("data:"))


def rows(table: dict, name_column: int) -> dict[str, dict[str, float]]:
    """Leaderboard rows by bare model name, as {column header: number}."""
    out = {}
    for row in table["data"]:
        name = re.sub(r"<[^>]+>", "", str(row[name_column])).replace("🤗", "").strip()
        out[name] = dict(zip(table["headers"], row))
    return out


def number(value) -> float | None:
    return None if value is None or (isinstance(value, float) and math.isnan(value)) else value


def check_version() -> None:
    config = json.load(urllib.request.urlopen(f"{SPACE}/config", timeout=60))
    for component in config["components"]:
        if component["props"].get("label") == "Version":
            if VERSION not in [choice[1] for choice in component["props"]["choices"]]:
                raise SystemExit(f"leaderboard no longer offers version {VERSION}")
            break
    else:
        raise SystemExit("leaderboard has no Version selector")
    # The Space serves VERSION from its live init.py: refuse if that entry no longer pins our revisions.
    init = urllib.request.urlopen(f"{SPACE_REPO}/raw/main/init.py", timeout=60).read().decode()
    start = init.find(f'"{VERSION}": {{')
    end = re.compile(r'\n    "\d\d-\d\d-\d{4}": \{').search(init, start + 1) if start >= 0 else None
    block = init[start : end.start() if end else len(init)] if start >= 0 else ""
    for revision in (MULTILINGUAL_REVISION, ENGLISH_REVISION):
        if revision not in block:
            raise SystemExit(f"init.py version {VERSION} no longer pins {revision}")


def entry(model: str, name: str, source: str, dataset: str, revision: str, languages: dict) -> dict:
    return {
        "model": model,
        "source": source,
        "url": f"{SPACE_REPO}?version={VERSION}",
        "revision": f"leaderboard {VERSION}; space {SPACE_REVISION}; dataset {revision}",
        "fetched": date.today().isoformat(),
        "upstream": f"{name} (the leaderboard names no revision)",
        "build": BUILD,
        "dataset": dataset,
        "normaliser": NORMALISER,
        "languages": languages,
    }


def leaderboard() -> list[dict]:
    check_version()
    found: dict[str, dict] = {name: {} for name in MODELS}
    for label, code in LANGUAGES.items():
        table = call("_render_multilingual_combined", [VERSION, "", True, [label], label])[0][
            "value"
        ]
        column = next((h for h in table["headers"] if h.startswith("FLEURS")), None)
        if column is None:
            raise SystemExit(f"{label}: no FLEURS column in {table['headers']}")
        metric = "cer" if "CER" in column else "wer"
        for name, values in rows(table, 1).items():
            if name in found and number(values[column]) is not None:
                found[name][code] = {"metric": metric, "errorPercent": values[column]}
    english = call("_main_table_update", [VERSION, "", True, False, ENGLISH_COLUMNS, 33.7])[0][
        "value"
    ]
    english_rows = rows(english, 2)

    out = []
    for name, models in MODELS.items():
        for model in models:
            if found[name]:
                languages = dict(sorted(found[name].items()))
                out.append(
                    entry(
                        model,
                        name,
                        "open-asr-leaderboard",
                        "FLEURS test, as aggregated in nithinraok/asr-leaderboard-datasets",
                        MULTILINGUAL_REVISION,
                        languages,
                    )
                )
            average = number(english_rows.get(name, {}).get("Average WER ⬇️"))
            if average is not None:
                out.append(
                    entry(
                        model,
                        name,
                        "open-asr-leaderboard-english",
                        "Open ASR Leaderboard English short-form average (not FLEURS; "
                        + ", ".join(ENGLISH_COLUMNS[1:])
                        + ")",
                        ENGLISH_REVISION,
                        {"en": {"metric": "wer", "errorPercent": average}},
                    )
                )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--write", action="store_true", help="replace the leaderboard entries in place"
    )
    args = parser.parse_args()
    fresh = leaderboard()
    if not args.write:
        yaml.safe_dump(
            {"references": fresh}, sys.stdout, sort_keys=False, allow_unicode=True, width=120
        )
        return 0
    current = yaml.safe_load(REFERENCES.read_text()) if REFERENCES.exists() else {"references": []}
    kept = [e for e in current["references"] if not e["source"].startswith("open-asr-leaderboard")]
    merged = sorted(kept + fresh, key=lambda e: (e["model"], e["source"]))
    REFERENCES.write_text(
        yaml.safe_dump({"references": merged}, sort_keys=False, allow_unicode=True, width=120)
    )
    print(f"{REFERENCES}: {len(fresh)} leaderboard entries, {len(kept)} kept")
    return 0


if __name__ == "__main__":
    sys.exit(main())
