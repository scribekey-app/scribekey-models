# Speech accuracy on FLEURS

Every speech model in `catalog/speech.yaml` carries an `accuracy` block, and every number in it comes
from this harness. `scribekey-models validate` fails a model with no block, a listed FLEURS language
with no number, or a number that differs from `results/<model-id>.json`.

## Method

Handy's publication recipe (transcribe.cpp `docs/tools/wer.md`), so grades mean the same as theirs:

- the whole FLEURS test split for each language (`google/fleurs`, parquet conversion);
- the `transcription` field as the reference;
- Whisper's English normaliser for English, the basic normaliser otherwise;
- character error for zh, yue, ja, ko, th, km, lo and my, word error for the rest;
- greedy decoding, no gain normalisation.

Two things differ, on purpose. The model is the exact sherpa-onnx export the catalogue ships, checked
against its `sha256`, run in sherpa-onnx at the version the app pins. And it is decoded the way the app
decodes it: offline models in segments of at most 30 s (8 s for Moonshine v2) split at the quietest
50 ms, live models fed in 100 ms steps with 800 ms of tail silence and no endpointing. The constants are
copied from the app and named in `measure.py`.

The two differences matter. On 2026-11-14 the shipped int8 export of Parakeet English measured 5.75%
on FLEURS English, where Handy's Q8 GGUF build measured 3.99%. That is a grade lower for the same source
model. Handy's figures are therefore not copied into the catalogue: a grade describes what the app runs.

A model is measured on its `languageCodes`. Qwen3 ASR and Nemotron 3.5 list none, so they keep the
languages they are already graded in. Omnilingual lists none and has no grades, so it is measured on
every language any catalogue model lists or is graded in, which is every language the app can grade. A listed
language FLEURS does not have cannot be measured and is not required.

This is a desktop measurement on read speech. It ranks models against each other; it is not a
measurement of a phone, and no copy may say it is.

## Run

The whole catalogue takes about a day of CPU, so it runs on GitHub. Push to a `measure/**` branch, or
dispatch **Measure speech accuracy** from main with model ids. One job measures one pair from
`plan.py`, which lists every pair not yet in `results/`. Then:

```bash
gh run download <run-id> --dir /tmp/fleurs-artifacts
python3 bench/asr/fleurs/collect.py /tmp/fleurs-artifacts   # merges results/, rewrites each accuracy block
uv run --extra dev scribekey-models generate
```

Locally, `bench/asr/fleurs/run_all.sh [<model-id> ...]` runs the same pairs one at a time, keeping one
model and one language on disk under `$BENCH_CACHE` (`/tmp/scribekey-fleurs`). To measure a language
again, delete it from the result file.

A new runtime family needs its recogniser setup in `offline()` or `online()`, copied from the app's
`SherpaOfflineRecognizerConfig.kt` or `RuntimeSherpaOnnxProviderFactory.kt`.
