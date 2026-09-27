"""Record cleanup examples from the production model, the way the Android app would run it.

Usage:
    python tools/record_cleanup_examples/record.py \
        --recorder build/recorder --model quill.gguf --runtime <llama.cpp commit> \
        "um i think we should ship it today" "..."

Each input runs twice; a difference between runs is an error, because an example that is not
reproducible cannot be shown as what the model does. Prints YAML to paste under `examples:`.
"""

from __future__ import annotations

import argparse
import datetime
import subprocess
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def prompt_for(template: str, system_prompt: str, text: str) -> str:
    # Mirrors SmartCleanupRuntime.promptFor in the app. Only the templates in production are here.
    if template == "QuillChatMl":
        return (
            f"<|im_start|>system\n{system_prompt.strip()}<|im_end|>\n"
            f"<|im_start|>user\n{text}<|im_end|>\n"
            "<|im_start|>assistant\n<think>\n\n</think>\n"
        )
    raise SystemExit(f"Prompt template {template} is not supported by the recorder yet")


def token_cap(profile: dict, text: str) -> int:
    # Mirrors SmartCleanupCleaner: min(profile cap, 256, max(64, words * 2 + 32)).
    return min(int(profile["maxOutputTokens"]), 256, max(64, len(text.split()) * 2 + 32))


def run(recorder: str, model: str, prompt: str, context: int, cap: int) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as handle:
        handle.write(prompt)
    raw = subprocess.run(
        [recorder, model, handle.name, str(context), str(cap)], check=True, capture_output=True, text=True
    ).stdout
    # Mirrors SmartCleanupRuntime.cleanOutput for ChatML templates.
    return raw.split("<|im_end|>")[0].split("<|endoftext|>")[0].strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recorder", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--runtime", required=True, help="llama.cpp commit the recorder was built from")
    parser.add_argument("inputs", nargs="+")
    args = parser.parse_args()

    profile = yaml.safe_load((ROOT / "catalog" / "cleanup.yaml").read_text())["production"]
    if not profile.get("deterministicDecoding") or float(profile.get("temperature", 0.0)) != 0.0:
        raise SystemExit("Examples need deterministic decoding")
    examples = []
    for text in args.inputs:
        prompt = prompt_for(profile["promptTemplate"], profile["systemPrompt"], text)
        cap = token_cap(profile, text)
        first = run(args.recorder, args.model, prompt, int(profile["contextTokens"]), cap)
        second = run(args.recorder, args.model, prompt, int(profile["contextTokens"]), cap)
        if first != second:
            raise SystemExit(f"Output for {text!r} differs between runs")
        examples.append(
            {
                "input": text,
                "output": first,
                "recordedWith": {
                    "modelRevision": profile["revision"],
                    "runtime": f"llama.cpp@{args.runtime}",
                    "recordedAt": datetime.date.today().isoformat(),
                },
            }
        )
    print(yaml.safe_dump({"examples": examples}, sort_keys=False, allow_unicode=True))


if __name__ == "__main__":
    main()
