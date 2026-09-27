# Small cleanup models and sherpa-onnx uplift: app plan

Date: 2026-09-27
Scope: replace or back up Quill with a smaller cleanup-only model, give cleanup models speech-level
metadata in the app, and use two sherpa-onnx features the app does not use yet (punctuation and
hotwords). Evidence lives in this repo; the work below lands in `stanvx/scribekey` unless a step
says otherwise.

## Where things stand

Host screen, frozen 240-case CleanBench corpus, raw model output (`bench/results/summary.md`):

| Model | Size | Similarity | Exact | Protected spans | Clean text left alone | Questions and commands |
| --- | --- | --- | --- | --- | --- | --- |
| BitVoice Qwen3 0.6B | 397 MB | 0.927 | 56% | 69% | 100% | 1.00 |
| BitVoice SmolLM2 360M | 271 MB | 0.925 | 57% | 65% | 100% | 1.00 |
| Mumble 2stage | 398 MB | 0.904 | 50% | 61% | 77% | 0.98 |
| OpenWispr 0.6B (thinking off) | 397 MB | 0.890 | 52% | 74% | 87% | 0.77 |
| sherpa punctuation (baseline) | 7 MB | 0.889 | 5% | 56% | 33% | 0.98 |
| Quill (production) | 529 MB | 0.883 | 50% | 74% | 90% | 0.70 |

What that means:

- **Take BitVoice SmolLM2 360M and BitVoice Qwen3 0.6B forward.** Both leave clean text alone
  and never answered a question or obeyed a command. Quill answers some ("I can't answer that
  question.") and is the largest.
- **No model passes the 95% protected-span bar on raw output, and that is expected.** Most misses
  are spoken numbers left as words ("twenty five", "seven thirty pm"). In the app,
  `SmartCleanupCleaner.acceptSmartResult` runs `TextNormaliser` on the model output and
  `FidelityGuard` before anything is inserted, so the raw score understates the product. Phase 1
  measures the product path.
- **BitVoice does not resolve self-corrections** ("the blue folder is please put the blue folder…"
  comes back unchanged). Standard cleanup's correction handling and the guard must cover it.
- **Drop Mumble and OpenWispr.** Mumble rewrites 23% of already-clean inputs. OpenWispr has no
  documented prompt, and under the app's current template it does not work at all (below).
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
because the synthetic voice mispronounces them; that needs real recordings (Phase 6).

## Phase 0: this repo (about 2 hours, plus the licence wait)

1. **Clear the BitVoice licence.** The repository metadata says `license: other` and there is no
   LICENSE file; only the card table says Apache 2.0 per file. Ask the author to add a LICENSE,
   or get it in writing. Nothing is mirrored or promoted before that.
2. **Add both BitVoice models to `catalog/cleanup.yaml` `candidates`** with the new metadata
   (`description`, `bestFor`, `info`, `provenance`), exact `sizeBytes` and `sha256`, and the card's
   system prompt. SmolLM2 uses the existing `QwenChatMl` template. Qwen3 needs a new
   `Qwen3NoThinkChatMl` value, and **must wait for an app release that knows it**: the app decodes
   `promptTemplate` as an enum, so an unknown value fails the whole remote catalogue and the app
   silently falls back to its bundled copy.
3. **Publish the hotword vocabularies.** Add `bpe.vocab` to the `files` of `parakeet-0.6b-v3` and
   `parakeet-unified-0.6b` (sizes and SHA-256 are in `assets/bpe-vocab/*/SOURCE`), hosted at an
   immutable URL: a commit-pinned raw URL in this repo, or a mirror repo. Add an optional
   `sherpaConfig.hotwords: {modelingUnit: bpe, bpeVocab: bpe.vocab}`. Older apps ignore the key
   and download 12–117 KB they do not use.
4. **Decide how the punctuation model ships.** Recommended: attach `punct/model.int8.onnx` (7.5 MB)
   and `punct/bpe.vocab` to the English speech entries with `supportsPunctuation: false` (Moonshine
   and Distil-Whisper) plus an optional `sherpaConfig.punctuation` key, so it downloads with the
   model that needs it and needs no new config family. The alternative, bundling it in the APK
   like `silero_vad.onnx`, adds 7.6 MB for everyone.
5. `scribekey-models generate`, `validate`, `pytest`; freeze a release; promote to QA only after
   the app release in Phase 2 is on the QA channel.

## Phase 1: product-path scores without a device (about 3 hours)

1. Copy the committed `bench/results/*.jsonl` into `app/src/test/resources/cleanbench/`.
2. Add a JVM test beside `CleanBenchTest` that feeds each raw output through the same steps as
   `SmartCleanupCleaner.acceptSmartResult`: `TextNormaliser.normalise`, then the safety guard with
   the Standard result as the fallback. Report what would be inserted.
3. Gate with the research doc's safety rules: 100% protected-span retention in inserted text,
   zero accepted answer-like outputs, under 5% material change on already-clean inputs.
4. Keep the two best of BitVoice SmolLM2, BitVoice Qwen3 and Quill. If neither BitVoice model
   beats Quill here, stop: Quill stays and only Phases 5–6 go ahead.

## Phase 2: app plumbing (about 1 day)

1. Add `SmartCleanupPromptTemplate.Qwen3NoThinkChatMl`
   (`…<|im_start|>assistant\n<think>\n\n</think>\n\n`, system turn only when non-empty) and a unit
   test pinning the exact string, as `quill_chatml` is pinned in `tests/test_cleanbench.py`.
2. Move OpenWispr to that template or delete the entry. Recommended: delete it (Phase 1 already
   ranks it out).
3. Add the two BitVoice entries to `SmartCleanupCandidateCatalog` with the pinned artifacts from
   `bench/cleanup_candidates.yaml`, and to `CleanBenchCandidate`.
4. Give `ProductCleanupModelManifest` optional `description`, `bestFor`, `info`, `provenance`,
   `deprecated`, `retired` and `replacementId` (defaults keep old catalogues parsing), and show them
   on `SmartCleanupModelCard` by reusing the speech pattern: `LocalModelCard` puts `bestFor` (or
   `description`) under the name, and the info sheet carries the parameter badge, size, languages,
   source and licence.
5. Update the cleanup journey under `journeys/` and the screenshot baselines for the card. Run the
   full local gate from `CLAUDE.md`.

## Phase 3: device qualification (about half a day of device time)

1. `scripts/tests/run_smart_cleanup_qualification.sh --mode core` then `--mode warm` for each
   finalist and Quill, on the Galaxy (`SM-S938B`) and one midrange phone.
2. Warm targets from the research doc: under 1.5 s p95 on the flagship and 2.5 s midrange, with
   peak memory recorded alongside Sherpa.
3. Blinded two-reviewer review through `CleanBench.humanReviewGate`: each finalist must beat Quill
   by 3 points with no loss on semantic fidelity or voice. Add a `CleanBenchComparison` entry per
   finalist against Quill first; today it only knows Quill vs Standard and Meeko vs Quill.

## Phase 4: promote (about 1 hour)

1. Make the winner `production` in `catalog/cleanup.yaml`. Keep Quill as a candidate with
   `deprecated: true` and `replacementId`, so existing installs keep working.
2. Freeze a release, promote to QA, ship a QA build with `scripts/firebase/distribute_qa.sh`, then
   promote stable.

## Phase 5: sherpa punctuation (about 1 day)

1. Change the provider's `punctuationModel` from `OfflinePunctuation` (the Chinese–English
   CT-Transformer, 65 MB) to `OnlinePunctuation` with `addPunctuationWithCase`, the 7.5 MB English
   model screened here. Wrap it in a small interface so tests can fake it.
2. In `RuntimeSherpaOnnxProviderFactory`, create it only when the model has
   `supportsPunctuation: false`, is English, and its `punct/` files are installed. Release it with
   the recogniser.
3. Never run it on text that already has punctuation: it title-cases words ("The Front Gate is
   locked.").
4. Journey: dictate with Moonshine and check the inserted text is punctuated and capitalised.
   Measure added latency on device; about 10 ms per sentence on the host.

## Phase 6: hotwords from the Dictionary (1 to 2 days)

1. In `nemoTransducerConfig`, when `bpe.vocab` is installed: `decodingMethod =
   "modified_beam_search"`, `modelingUnit = "bpe"`, `bpeVocab = "$modelDir/bpe.vocab"`. Without it,
   stay on greedy. Only Parakeet v3 and Parakeet Unified: sherpa-onnx 1.13.6 decodes the streaming
   NeMo transducers greedily.
2. For each recording, build the hotwords from the Dictionary's replacement words (manual and
   learned rules), de-duplicated and capped at 100, joined with `/`, and pass them to
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
