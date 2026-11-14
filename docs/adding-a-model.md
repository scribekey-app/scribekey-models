# Adding a model

The canonical model definitions live in `catalog/`. Generated JSON in `generated/` should not be edited by hand.

For a new model:

1. Add or update the relevant YAML file in `catalog/`.
2. Pin the upstream artifact to an immutable revision where the provider supports it.
3. Record the expected file size and SHA-256 digest.
4. Include upstream licence and attribution information.
5. Run `scribekey-models generate`.
6. Run `scribekey-models validate` and `pytest`.

Model weights are not added to Git history. Mirroring is handled separately and only for artifacts whose licence permits redistribution.

Compatibility metadata should describe what ScribeKey actually supports rather than what an upstream runtime might support in theory.


## How the app presents a speech model

Android shows these fields directly, so write them as screen copy (sentence case, no internal names).
`model-copy-style-guide.md` covers wording: one benefit, no unmeasured ranking, no "offline" for one model.

| Field | Where it appears | Rule |
| --- | --- | --- |
| `displayName` | Card title, Settings summary | Unique across the catalogue. A legacy entry never shares its replacement's name — suffix it (`Moonshine Base v1`). |
| `bestFor` | The one line under the card title, and the counterpart row in the sheet | A phrase of 48 characters or fewer, no full stop. Why someone picks this model. Never a timing, size or language the app already shows. |
| `description` | The info sheet, under the title | One or two sentences saying what the model does. Never a copy of `bestFor`. |
| `languageCodes` | Language names on the card and in the sheet; search | ISO 639 codes, when the languages can be listed. Leave it out for models whose coverage is a count (`1600+ languages`). |
| `counterpartId` | "Want words as you speak?" / "Prefer text after speaking?" link in the sheet | The same job in the other transcription mode. Must be mutual, cross modes, and point at a selectable model. |
| `accuracy` | The grade tag on the model card (`A-`), and the grades by language in the sheet | Required. Error percent by ISO 639 language code on the FLEURS test split, for every listed language FLEURS has. Run `bench/asr/fleurs/run_all.sh <id>` and copy each `errorPercent` from `bench/asr/fleurs/results/<id>.json`; `validate` fails a number that differs from that file. Never copy a published figure. The generator derives each grade (`A` under 5%, `B` under 10%, `C` under 20%, `D` under 30%, each `+`/`-` a factor of ∛2), so never write a grade by hand. |
| `provenance` | Model card and licence links in the sheet | Every entry, legacy ones included. |
| `experimental` | The `Experimental` badge on the model card. Android lists the model only in debug and QA builds with Settings → Advanced → Feature toggles → Extra speech models on; a release build lists it only while it is in use or downloaded | `true` for a model still being qualified, and only then give it `badge: Experimental`. Promote it by deleting the flag and the badge in a new release; the app needs no update. Never on a retired or deprecated entry. |

Retired and deprecated entries stay in the catalogue so existing installs keep working. Give them
`bestFor: Existing installs only` and a `replacementId`; the app groups them under older models,
which, like experimental models, only debug and QA builds with Extra speech models on list for
anyone who does not already have the model.
`scribekey-models validate` enforces the unique-name, distinct-guidance, wording, counterpart, and experimental-badge rules.

## NPU builds

`npuBuilds` lists a model compiled for one Snapdragon NPU each, so the app can run it there instead
of on the CPU. Only segmented Parakeet TDT (`nemo_transducer`) qualifies, because that is the only
NPU path the app's sherpa-onnx bindings reach. Each build is a context-binary archive from a
sherpa-onnx `asr-models-qnn-binary-N` release, pinned by `sizeBytes` and `sha256`, with:

- `soc`: the chip's `Build.SOC_MODEL`, such as `SM8750`. One build per chip.
- `runtime`: `qnn`.
- `windowSeconds`: the fixed audio length the graph was compiled for; the app splits longer audio.
- `archiveRoot`: the archive's top folder, which the download URL's file name must match.

The archives hold model data only. Qualcomm's runtime libraries are code, so they ship inside the
app and never appear in the catalogue. `scribekey-models validate` enforces the source, chip and hash rules.

## Recorded cleanup examples

A cleanup model may carry `examples`: a few inputs and the output this exact revision produced.
The app shows them as what the model does, so they have to be real and reproducible:

- Record them with `tools/record_cleanup_examples`, built against the llama.cpp commit the app
  pins (`SCRIBEKEY_LLAMA_CPP_REVISION` in the app's `app/src/main/cpp/CMakeLists.txt`). The recorder
  mirrors the app's native wrapper, prompt template and output clean-up, and runs every input
  twice; a difference between runs stops it.
- Only a model with deterministic decoding (`temperature: 0`) may have examples.
- Every example names the `modelRevision` it came from. Changing `revision` without re-recording
  fails `scribekey-models validate`.
- Keep only examples the app's `AiCleanupSafetyGuard` accepts. A rejected output falls back to
  Standard cleanup on a phone, so it is not what the model does there; the app drops such examples
  at display time too. On 2026-09-27 the guard rejected Quill's questions ("can you review it" →
  "…?", as invented question intent) and spoken self-corrections ("no wait", as lost polarity).

```bash
cmake -S tools/record_cleanup_examples -B build -DLLAMA_CPP_DIR=../scribekey/third_party/llama.cpp
cmake --build build --target recorder
python tools/record_cleanup_examples/record.py --recorder build/recorder --model quill.gguf \
    --runtime <llama.cpp commit> "um i think we should ship it today"
```

## How the app presents a cleanup model

Cleanup entries in `catalog/cleanup.yaml` carry the same presentation fields as speech, under the
same rules: `displayName`, `bestFor` (48 characters or fewer, no full stop), `description` (one or
two sentences, never a copy of `bestFor`), `info` (`paramsBadge`, `architecture`, `languages`) and
`provenance` (source model, the exact Hugging Face repository and revision the GGUF comes from, the
quantisation as `exportVariant`, and the SPDX licence). A replaced model stays in the catalogue with
`deprecated: true` and a `replacementId`, so existing installs keep working.

Before a cleanup model is added, screen it with `scribekey-models cleanbench` (see
`bench/README.md`). Only small, cleanup-only models qualify.

## Notes models

`catalog/notes.yaml` lists the models that write notes from a transcript on the phone: Summary,
action items and Ask. Entries take cleanup's identity, download, decoding and licence fields under the
same names and rules. They also take `experimental` and `badge: Experimental` as speech does. Instead
of character limits, each entry carries its own token limits, so a weaker or stronger model can
change what the app does without an app update:

| Field | Unit | What the app does with it |
| --- | --- | --- |
| `capabilities` | `summary`, `action_items`, `ask` | Offers only the listed features with this model. |
| `pieceTokens` | tokens | Splits a transcript into pieces of this size; each piece is one request. |
| `maxInputTokens` | tokens | The longest transcript it offers notes on. Keep it within the Summary budget: today 8 pieces, the most for which 16 lines still give each piece 2. |
| `maxOutputTokens` | tokens | The most one request may write. |
| `contextTokens` | tokens | The context window it opens. |
| `maxAskPassages` | passages | The most transcript passages one Ask request reads. Required with `ask`. |
| `askPassageTokens` | tokens | The size of one Ask passage. Required with `ask`. |

`scribekey-models validate` checks that the id and name are unique, the revision is a pinned commit,
size and SHA-256 are present, every limit is positive and `maxInputTokens` is at least `pieceTokens`.
It also checks that `pieceTokens + maxOutputTokens`, and for Ask `maxAskPassages × askPassageTokens +
maxOutputTokens`, leave 1,024 tokens of `contextTokens` for the prompt.

The app reads `generated/notes_model_catalog.json`. A release made after this file existed carries it
as the optional `notes` catalogue.

## Search models

`catalog/search.yaml` lists the embedding models behind Search by meaning. Each turns a passage of a
transcript, or a query, into one vector, and the app ranks passages by how close their vectors are
to the query's. Entries take notes' identity, download, licence and `experimental` fields under the
same names and rules, without decoding or token budgets. They add:

| Field | Value | What the app does with it |
| --- | --- | --- |
| `bundleFileName` | `*.litertlm` | The one file it downloads and loads. |
| `runtimeFamily` | `litert-lm` | The runtime that loads it. Nothing else is accepted. |
| `backends` | `cpu` | The LiteRT-LM backends it may use. |
| `embeddingDimensions` | 128, 256, 512 or 768 | The length of every stored vector, for queries and passages alike. |
| `normalizeEmbeddings` | boolean | Whether it asks for unit-length vectors. |
| `passageTokens` | 128 to 8192, as the model publishes | The input size it loads for a passage. |

Changing `embeddingDimensions` or `normalizeEmbeddings` makes every stored vector unusable, so the
app has to index again. Give the replacement a new `modelId`.

`scribekey-models validate` checks that the id and name are unique, the revision is a pinned commit,
the download URL names that revision, the repository in `provenance` and the `bundleFileName`, size
and SHA-256 are present, and the runtime family is `litert-lm`.

The app reads `generated/search_model_catalog.json`. A release made after this file existed carries
it as the optional `search` catalogue, and promoting that release declares `litert-lm` on the channel.
