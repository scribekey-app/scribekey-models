"""Host-side screening benchmark for Smart cleanup candidates.

Runs each GGUF in ``bench/cleanup_candidates.yaml`` through llama.cpp on the frozen CleanBench
corpus the app's device qualification uses, and scores the raw model output. It is a cheap first
filter for deciding which models earn a device qualification run; it is not release evidence.
Host CPU latency says nothing absolute about a phone, only how candidates compare with each other.

Entries with ``runtime: sherpa-online-punct`` are non-LLM baselines: sherpa-onnx's punctuation and
casing model, which the app can already host. They are scored the same way but never advance.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import tarfile
import time
import urllib.request
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import yaml

from scribekey_models.catalog import ROOT

BENCH_DIR = ROOT / "bench"
CANDIDATES_FILE = BENCH_DIR / "cleanup_candidates.yaml"
CORPUS_FILE = BENCH_DIR / "cleanbench_corpus_v1.jsonl"
# Same identity the app's run_smart_cleanup_qualification.sh pins for the frozen corpus.
CORPUS_SHA256 = "aecd44a0d037776935b438431782466cd8f9a33d5887119639fc448ee1dab699"

CONTROL_CATEGORY = "already_clean_controls"
STOP_SEQUENCES = ["<|im_end|>", "<|endoftext|>"]
CONTEXT_TOKENS = 4096
MIN_OUTPUT_TOKENS = 64
MAX_OUTPUT_TOKENS = 1024
# An output this much longer than the expected text has added something the speaker did not say.
ADDED_CONTENT_RATIO = 1.3
ADDED_CONTENT_SLACK_CHARS = 20
# Screening gate: a model that drops protected spans more often than this is not worth a device run.
MIN_PROTECTED_RETENTION = 0.95
# Admission ceiling for a phone: a small cleanup model, not a general assistant.
MAX_CANDIDATE_BYTES = 600_000_000
LLAMA_RUNTIME = "llama.cpp"
SHERPA_PUNCT_RUNTIME = "sherpa-online-punct"
ARCHIVE_CACHE = Path.home() / ".cache" / "scribekey-cleanbench"


@dataclass(frozen=True)
class Candidate:
    id: str
    repo: str
    revision: str
    file: str
    size_bytes: int
    license: str
    template: str
    system_prompt: str
    runtime: str = LLAMA_RUNTIME
    archive_url: str = ""
    archive_sha256: str = ""
    vocab_file: str = ""

    @property
    def is_baseline(self) -> bool:
        return self.runtime != LLAMA_RUNTIME

    def prompt_for(self, text: str) -> str:
        system = self.system_prompt.strip()
        if self.template == "quill_chatml":
            return (
                f"<|im_start|>system\n{system}<|im_end|>\n"
                f"<|im_start|>user\n{text}<|im_end|>\n"
                "<|im_start|>assistant\n<think>\n\n</think>\n"
            )
        if self.template == "qwen3_nothink":
            return (
                f"<|im_start|>system\n{system}<|im_end|>\n"
                f"<|im_start|>user\n{text}<|im_end|>\n"
                "<|im_start|>assistant\n<think>\n\n</think>\n\n"
            )
        if self.template == "chatml":
            head = f"<|im_start|>system\n{system}<|im_end|>\n" if system else ""
            return f"{head}<|im_start|>user\n{text}<|im_end|>\n<|im_start|>assistant\n"
        if self.template == "meeko_chatml":
            return f"<|startoftext|><|im_start|>user\n{text}<|im_end|>\n<|im_start|>assistant\n"
        if self.template == "lfm2_chatml":
            return (
                f"<|startoftext|><|im_start|>system\n{system}<|im_end|>\n"
                f"<|im_start|>user\n{text}\n<|im_end|>\n<|im_start|>assistant\n"
            )
        raise ValueError(f"Unknown prompt template {self.template!r} for {self.id}")


def load_candidates(path: Path = CANDIDATES_FILE) -> list[Candidate]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [
        Candidate(
            id=entry["id"],
            repo=entry.get("repo", ""),
            revision=entry.get("revision", ""),
            file=entry["file"],
            size_bytes=entry["sizeBytes"],
            license=entry["license"],
            template=entry.get("template", ""),
            system_prompt=entry.get("systemPrompt", ""),
            runtime=entry.get("runtime", LLAMA_RUNTIME),
            archive_url=entry.get("archiveUrl", ""),
            archive_sha256=entry.get("archiveSha256", ""),
            vocab_file=entry.get("vocabFile", ""),
        )
        for entry in raw["candidates"]
    ]


def load_corpus(path: Path = CORPUS_FILE) -> list[dict[str, Any]]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != CORPUS_SHA256:
        raise ValueError(f"Frozen corpus identity changed: {digest}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def canonical(value: str) -> str:
    """Mirror of canonical() in SmartCleanupQualificationTest."""
    lines = value.strip().replace("\r\n", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines)


def _find_bounded(text: str, token: str, start: int) -> int:
    search_from = start
    while token and search_from <= len(text) - len(token):
        index = text.find(token, search_from)
        if index < 0:
            return -1
        after = index + len(token)
        left_ok = not token[0].isalnum() or index == 0 or not text[index - 1].isalnum()
        right_ok = not token[-1].isalnum() or after == len(text) or not text[after].isalnum()
        if left_ok and right_ok:
            return index
        search_from = index + 1
    return -1


def _count_bounded(text: str, token: str) -> int:
    count, search_from = 0, 0
    while (index := _find_bounded(text, token, search_from)) >= 0:
        count += 1
        search_from = index + len(token)
    return count


def retains_protected_tokens(output: str, tokens: list[str]) -> bool:
    """Mirror of retainsProtectedTokensExactly(): in order, word-bounded, exact multiplicity."""
    search_from = 0
    for token in tokens:
        index = _find_bounded(output, token, search_from)
        if index < 0:
            return False
        search_from = index + len(token)
    return all(_count_bounded(output, token) == tokens.count(token) for token in set(tokens))


def score_case(case: dict[str, Any], output: str) -> dict[str, Any]:
    out, expected = canonical(output), canonical(case["expected"])
    added = len(out) > ADDED_CONTENT_RATIO * len(expected) + ADDED_CONTENT_SLACK_CHARS
    return {
        "exact": out == expected,
        "similarity": round(SequenceMatcher(None, out, expected, autojunk=False).ratio(), 4),
        "protectedRetained": retains_protected_tokens(out, case["protectedTokens"]),
        "controlKept": out == canonical(case["input"])
        if case["category"] == CONTROL_CATEGORY
        else None,
        "addedContent": added,
        "empty": not out,
    }


def output_budget(input_tokens: int) -> int:
    """One budget formula for every model, so a tight per-model cap cannot hide truncation."""
    return max(MIN_OUTPUT_TOKENS, min(MAX_OUTPUT_TOKENS, math.ceil(1.5 * input_tokens) + 32))


def run_candidate(
    candidate: Candidate,
    cases: list[dict[str, Any]],
    threads: int,
    log: Any = print,
) -> list[dict[str, Any]]:
    generate = (
        _sherpa_punct_generator(candidate, threads)
        if candidate.runtime == SHERPA_PUNCT_RUNTIME
        else _llama_generator(candidate, threads)
    )
    rows = []
    for index, case in enumerate(cases, start=1):
        started = time.perf_counter()
        generation = generate(case["input"])
        latency_ms = round((time.perf_counter() - started) * 1000)
        rows.append(
            {
                "model": candidate.id,
                "id": case["id"],
                "category": case["category"],
                "lengthBucket": case["lengthBucket"],
                "protectedTokenCount": len(case["protectedTokens"]),
                "input": case["input"],
                "expected": case["expected"],
                "latencyMs": latency_ms,
                **generation,
                **score_case(case, generation["output"]),
            }
        )
        if index % 20 == 0 or index == len(cases):
            log(f"{candidate.id}: {index}/{len(cases)}")
    return rows


def _llama_generator(candidate: Candidate, threads: int) -> Any:
    # Imported here so the catalogue tooling does not need the optional [bench] extra.
    from huggingface_hub import hf_hub_download
    from llama_cpp import Llama

    model_path = hf_hub_download(candidate.repo, candidate.file, revision=candidate.revision)
    llm = Llama(model_path=model_path, n_ctx=CONTEXT_TOKENS, n_threads=threads, seed=42, verbose=False)

    def generate(transcript: str) -> dict[str, Any]:
        llm.reset()  # fresh conversation per case, as on device
        transcript_tokens = len(llm.tokenize(transcript.encode(), add_bos=False))
        prompt = llm.tokenize(candidate.prompt_for(transcript).encode(), add_bos=False, special=True)
        result = llm.create_completion(
            prompt,
            max_tokens=output_budget(transcript_tokens),
            temperature=0.0,
            top_k=1,
            top_p=1.0,
            repeat_penalty=1.0,
            stop=STOP_SEQUENCES,
        )
        choice = result["choices"][0]
        return {
            "output": choice["text"].strip(),
            "truncated": choice["finish_reason"] == "length",
            "promptTokens": result["usage"]["prompt_tokens"],
            "generatedTokens": result["usage"]["completion_tokens"],
        }

    return generate


def _sherpa_punct_generator(candidate: Candidate, threads: int) -> Any:
    import sherpa_onnx

    model_dir = _fetch_archive(candidate)
    punct = sherpa_onnx.OnlinePunctuation(
        sherpa_onnx.OnlinePunctuationConfig(
            model_config=sherpa_onnx.OnlinePunctuationModelConfig(
                cnn_bilstm=str(model_dir / candidate.file),
                bpe_vocab=str(model_dir / candidate.vocab_file),
                num_threads=threads,
            )
        )
    )

    def generate(transcript: str) -> dict[str, Any]:
        output = punct.add_punctuation_with_case(transcript).strip()
        return {"output": output, "truncated": False, "promptTokens": 0, "generatedTokens": 0}

    return generate


def _fetch_archive(candidate: Candidate) -> Path:
    """Download a release archive once, refuse it on a SHA-256 mismatch, and extract it."""
    target = ARCHIVE_CACHE / candidate.archive_sha256
    archive = target.with_suffix(".tar.bz2")
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists():
            urllib.request.urlretrieve(candidate.archive_url, archive)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if digest != candidate.archive_sha256:
            archive.unlink()
            raise ValueError(f"{candidate.id}: archive SHA-256 {digest} is not the pinned one")
        with tarfile.open(archive) as tar:
            tar.extractall(target, filter="data")
    return next(path.parent for path in target.rglob(candidate.file))


def _percentile(values: list[int], pct: int) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(pct / 100 * len(ordered)) - 1)]


def summarize_model(rows: list[dict[str, Any]]) -> dict[str, Any]:
    protected = [r for r in rows if r["protectedTokenCount"]]
    controls = [r for r in rows if r["controlKept"] is not None]
    gen_ms = sum(r["latencyMs"] for r in rows)
    gen_tokens = sum(r["generatedTokens"] for r in rows)
    return {
        "cases": len(rows),
        "exact": _share(rows, "exact"),
        "similarity": round(statistics.mean(r["similarity"] for r in rows), 3),
        "protectedRetention": _share(protected, "protectedRetained") if protected else None,
        "controlsKept": _share(controls, "controlKept") if controls else None,
        "addedContent": sum(r["addedContent"] for r in rows),
        "truncated": sum(r["truncated"] for r in rows),
        "empty": sum(r["empty"] for r in rows),
        "p50Ms": _percentile([r["latencyMs"] for r in rows], 50),
        "p95Ms": _percentile([r["latencyMs"] for r in rows], 95),
        "tokensPerSecond": round(gen_tokens / (gen_ms / 1000), 1) if gen_ms and gen_tokens else None,
        "byCategory": {
            category: round(statistics.mean(r["similarity"] for r in group), 3)
            for category, group in _group(rows, "category").items()
        },
    }


def _share(rows: list[dict[str, Any]], key: str) -> float:
    return round(sum(bool(r[key]) for r in rows) / len(rows), 3)


def _group(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(row[key], []).append(row)
    return groups


def render_report(
    candidates: list[Candidate],
    results: dict[str, list[dict[str, Any]]],
) -> str:
    summaries = {c.id: summarize_model(results[c.id]) for c in candidates if results.get(c.id)}
    ranked = sorted(summaries, key=lambda model: summaries[model]["similarity"], reverse=True)
    by_id = {c.id: c for c in candidates}
    advancing = [
        model
        for model in ranked
        if not by_id[model].is_baseline
        and (summaries[model]["protectedRetention"] or 0) >= MIN_PROTECTED_RETENTION
    ][:2]
    lines = [
        "# CleanBench host screen",
        "",
        (
            "Raw model output on the frozen 240-case CleanBench corpus, llama.cpp on host CPU, "
            "greedy decoding, one output budget for every model. No fidelity guard is applied, "
            "so these numbers are stricter than what a user would see. Latency is host CPU and "
            "only ranks models against each other. Rows marked *baseline* are not language "
            "models and never advance."
        ),
        "",
        (
            f"Advance to device qualification: {', '.join(advancing) or 'none'} (highest mean "
            f"similarity with protected-span retention ≥ {MIN_PROTECTED_RETENTION:.0%})."
        ),
        "",
        (
            "| Model | Size | Similarity | Exact | Protected spans | Controls kept "
            "| Added content | Truncated | Host p50 / p95 ms | Tokens/s |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for model in ranked:
        s = summaries[model]
        label = f"{model} *baseline*" if by_id[model].is_baseline else model
        lines.append(
            f"| {label} | {by_id[model].size_bytes / 1e6:.0f} MB | {s['similarity']:.3f} | {_pct(s['exact'])} | "
            f"{_pct(s['protectedRetention'])} | {_pct(s['controlsKept'])} | {s['addedContent']} | "
            f"{s['truncated']} | {s['p50Ms']} / {s['p95Ms']} | {s['tokensPerSecond'] or 'n/a'} |"
        )
    categories = sorted({c for s in summaries.values() for c in s["byCategory"]})
    lines += ["", "## Mean similarity by category", ""]
    lines.append("| Category | " + " | ".join(ranked) + " |")
    lines.append("| --- |" + " --- |" * len(ranked))
    for category in categories:
        cells = [f"{summaries[m]['byCategory'].get(category, 0):.3f}" for m in ranked]
        lines.append(f"| {category} | " + " | ".join(cells) + " |")
    lines += ["", "## Artefacts", ""]
    for model in ranked:
        c = by_id[model]
        source = c.archive_url if c.is_baseline else f"{c.repo}@{c.revision[:12]}"
        lines.append(f"- `{model}`: `{source}` `{c.file}`, {c.size_bytes / 1e6:.0f} MB ({c.license})")
    return "\n".join(lines) + "\n"


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def run(
    out_dir: Path,
    model_ids: list[str] | None,
    limit: int | None,
    threads: int,
    report_only: bool,
) -> Path:
    candidates = load_candidates()
    if model_ids:
        unknown = set(model_ids) - {c.id for c in candidates}
        if unknown:
            raise ValueError(f"Unknown candidates: {', '.join(sorted(unknown))}")
        candidates = [c for c in candidates if c.id in model_ids]
    cases = load_corpus()[:limit] if limit else load_corpus()
    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        path = out_dir / f"{candidate.id}.jsonl"
        if path.exists():
            results[candidate.id] = [json.loads(line) for line in path.read_text().splitlines()]
        if report_only or len(results.get(candidate.id, [])) >= len(cases):
            continue
        rows = run_candidate(candidate, cases, threads)
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        results[candidate.id] = rows
    report = out_dir / "summary.md"
    report.write_text(render_report(candidates, results), encoding="utf-8")
    return report
