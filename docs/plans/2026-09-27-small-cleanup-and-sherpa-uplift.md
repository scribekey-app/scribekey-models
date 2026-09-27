# Small cleanup models and sherpa-onnx uplift: app plan

Date: 2026-09-27
Scope: check whether a smaller cleanup-only model can replace Quill, give cleanup models
speech-level metadata in the app, and use two sherpa-onnx features the app does not use yet
(punctuation and hotwords). Evidence lives in this repo; the work below lands in
`stanvx/scribekey` unless a step says otherwise.

## Where things stand

Host screen, frozen 240-case CleanBench corpus, raw model output (`bench/results/summary.md`):

| Model | Size | Similarity | Exact | Protected spans | Clean text left alone | Questions and commands |
| --- | --- | --- | --- | --- | --- | --- |
| Mumble 2stage | 398 MB | 0.904 | 50% | 61% | 77% | 0.98 |
| OpenWispr 0.6B (thinking off) | 397 MB | 0.890 | 52% | 74% | 87% | 0.77 |
| sherpa punctuation (baseline) | 7 MB | 0.889 | 5% | 56% | 33% | 0.98 |
| Quill (production) | 529 MB | 0.883 | 50% | 74% | 90% | 0.70 |

What that means:

- **Quill stays.** No smaller cleanup-only model is clearly better. Mumble rewrites 23% of
  already-clean inputs; OpenWispr has no documented prompt, adds content on 18 cases, and under
  the app's current template does not work at all (below). Re-screen with
  `scribekey-models cleanbench` when a new small cleanup model appears.
- **No model passes the 95% protected-span bar on raw output, and that is expected.** Most misses
  are spoken numbers left as words ("twenty five", "seven thirty pm"), which `TextNormaliser`
  fixes in the app before `FidelityGuard` runs.
- **Similarity is lenient.** It is character similarity to one expected answer, which is why a
  punctuation-only model scores close to Quill. Use it to rank, never to accept.

Two app bugs found on the way:

1. **OpenWispr thinks instead of cleaning.** It is a Qwen3 fine-tune, and `QwenChatMl` does not
   disable Qwen3 thinking, so 232/240 cases filled the budget with a `<think>` block
   (`bench/results/openwispr-cleanup-0.6b.app-template.jsonl`). Device qualification of the
   current `SmartCleanupCandidateCatalog` entry would fail the same way.
2. **The punctuation hook is dead.** `SherpaOnnxTranscriptionProvider` accepts a
   `punctuationModel`, but `RuntimeSherpaOnnxProviderFactory` never passes one.

Hotwords, end to end (`bench/hotwords/results.txt`): Parakeet v3 with per-stream hotwords recognised
7 of 12 target words in five synthesised jargon sentences, against 4 of 12 greedy and 4 of 12 with
beam search alone. "Email Siobhan Nguyen about the ScribeKey rollout" went from "Shival New Yan…
scribe key" to exact. Words already right stayed right. Irish names did not improve, probably
because the synthetic voice mispronounces them; that needs real recordings (Phase 3).

## Phase 0: this repo (about 2 hours)

1. **Cleanup metadata (done).** `catalog/cleanup.yaml` entries carry `description`, `bestFor`,
   `info` and `provenance`, validated like speech entries.
2. **Never add a file to an existing speech entry.** `LocalModelReadiness` compares an install's
   metadata with the catalogue's `files`, so one extra file marks every existing install of that
   model invalid, on every app version that reads the remote catalogue. Optional companions go
   in the APK or need their own optional-download field first.
3. **Hotword vocabularies ship in the app (done).** `assets/bpe-vocab/*/bpe.vocab` (12 and 117 KB)
   are copied into the app as `assets/hotwords/<model-id>.bpe.vocab`. The app uses one only when
   its pieces equal the installed `tokens.txt`, so a re-pinned export falls back to greedy
   decoding instead of mis-tokenising hotwords. Rebuild with `scribekey-models bpe-vocab` and
   copy again whenever a Parakeet export is re-pinned.
4. **Punctuation model hosting (open decision).** Upstream publishes `model.int8.onnx` (7.5 MB)
   and `bpe.vocab` only inside a GitHub release archive, and this repo forbids model binaries.
   Choose one: bundle both in the APK like `silero_vad.onnx` (+7.6 MB for everyone), or mirror them
   to a Hugging Face repo under the ScribeKey account and add an optional-download field that
   `LocalModelReadiness` ignores (see step 2).
5. `scribekey-models generate`, `validate`, `pytest`; freeze a release; promote to QA only after
   the app release in Phase 1 is on the QA channel.

## Phase 1: cleanup catalogue in the app (done, pending device check)

1. Delete the OpenWispr entry from `SmartCleanupCandidateCatalog`. It cannot work under
   `QwenChatMl`, and with thinking off it still ranks below Quill.
2. Give `ProductCleanupModelManifest` optional `description`, `bestFor`, `info`, `provenance`,
   `deprecated`, `retired` and `replacementId` (defaults keep old catalogues parsing), and show them
   on `SmartCleanupModelCard` by reusing the speech pattern: `LocalModelCard` puts `bestFor` (or
   `description`) under the name.
3. Update the screenshot baselines for the card. Run the full local gate from `CLAUDE.md`.

## Phase 2: sherpa punctuation (app code done; needs the Phase 0 hosting decision and a device)

1. Change the provider's `punctuationModel` from `OfflinePunctuation` (the Chinese–English
   CT-Transformer, 65 MB) to `OnlinePunctuation` with `addPunctuationWithCase`, the 7.5 MB English
   model screened here. Wrap it in a small interface so tests can fake it.
2. In `RuntimeSherpaOnnxProviderFactory`, create it only when the model has
   `supportsPunctuation: false`, is offline, and `punct-model.int8.onnx` and `punct-bpe.vocab` are
   installed. Release it with the recogniser.
3. Never run it on text that already has punctuation: it title-cases words ("The Front Gate is
   locked.").
4. Journey: dictate with Moonshine and check the inserted text is punctuated and capitalised.
   Measure added latency on device; about 10 ms per sentence on the host.

## Phase 3: hotwords from the Dictionary (app code done; needs a device)

1. In `nemoTransducerConfig`, when `bpe.vocab` is installed: `decodingMethod =
   "modified_beam_search"`, `modelingUnit = "bpe"`, `bpeVocab = "$modelDir/bpe.vocab"`. Without it,
   stay on greedy. Only Parakeet v3 and Parakeet Unified: sherpa-onnx 1.13.6 decodes the streaming
   NeMo transducers greedily.
2. For each recording, build the hotwords from the Dictionary: vocabulary words and manual
   replacements first, then learned ones, de-duplicated and capped at 100, joined with `/`, and
   pass them to
   `recognizer.createStream(hotwords)`. No file to keep in sync, and an edit applies on the next
   recording.
3. Measure beam search against greedy on device (p95 per utterance). If beam search costs too
   much, keep greedy when the Dictionary is empty.
4. Re-run `bench/hotwords/hotword_test.py` with real recordings of names and jargon. Also check
   that hotwords do not insert Dictionary words into speech that does not contain them, and tune
   `hotwordsScore` (default 1.5; the test used 2.0).
5. Journey: add a Dictionary word, dictate it with Parakeet v3, check it is spelled right before
   any cleanup runs.

## Not now

- **Speech denoiser (GTCRN, 0.5 MB).** Possible later spike; denoising can hurt recognition on
  clean audio, so it needs its own measurement.
- **Number rules as FSTs, homophone replacer.** sherpa-onnx ships these for Chinese only, and
  `TextNormaliser` already covers English numbers, times and dates.
