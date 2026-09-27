# Cleanup model screening

A cheap first filter for Smart cleanup candidates. It decides which models earn a run of the
app's device qualification (`scripts/tests/run_smart_cleanup_qualification.sh` in
`stanvx/scribekey`); it never decides what ships.

```bash
python -m pip install -e '.[bench]'                  # llama-cpp-python builds from source, 3–10 min
scribekey-models cleanbench                          # every candidate, all 240 cases
scribekey-models cleanbench --models quill,mumble-cleanup-2stage --limit 40   # quick look
scribekey-models cleanbench --report-only            # rebuild summary.md from saved results
```

Results go to `bench/results/`: one JSONL per model (every case with input, expected, output and
scores) and `summary.md`. A model whose JSONL is complete is not re-run, so an interrupted run
resumes; delete its JSONL to run it again.

## What it does

- Runs each GGUF in `cleanup_candidates.yaml` at its pinned revision with llama.cpp on the host
  CPU, using the prompt template the app uses, greedy decoding and a fresh context per case.
- Uses the frozen `cleanbench_corpus_v1.jsonl`, a byte-identical copy of the app's
  `app/src/androidTest/assets/smart_cleanup/` corpus. The loader refuses it if the SHA-256 differs
  from the identity the device script pins.
- Gives every model the same output budget (1.5 × input tokens + 32, between 64 and 1024), so a
  tight per-model cap cannot hide truncation.

## How to read the summary

| Column | Meaning |
| --- | --- |
| Similarity | Mean character similarity to the expected text, 0–1. The ranking score. |
| Exact | Share of outputs identical to the expected text, the device test's pass bar. |
| Protected spans | Share of cases with protected spans (numbers, URLs, names) that kept them all exactly. |
| Controls kept | Share of already-clean inputs returned unchanged. |
| Added content | Outputs more than 1.3× the expected length: answers, additions, rambling. |
| Truncated | Outputs that hit the token budget. |

**Advance to device qualification** names the two best-similarity models that keep protected
spans in at least 95% of cases.

## What it does not tell you

- **Phone latency or memory.** Host CPU numbers only rank models against each other.
- **What a user sees.** The app's fidelity guard rejects many bad outputs and falls back to
  Standard cleanup. This screen scores the raw model, so it is stricter than the product.
- **Voice and readability.** Similarity to one expected answer penalises valid alternatives. The
  blinded two-reviewer gate in the app's `CleanBench` covers that for finalists.

## Adding a candidate

Add an entry to `cleanup_candidates.yaml` with an immutable revision, the exact GGUF path, the
licence as the source states it, and the model card's prompt format. Run it with
`--models <id>`, then `--report-only` to refresh the summary.
