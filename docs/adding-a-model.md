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

Android shows these fields directly, so write them as screen copy (sentence case, no internal names):

| Field | Where it appears | Rule |
| --- | --- | --- |
| `displayName` | Card title, Settings summary | Unique across the catalogue. A legacy entry never shares its replacement's name — suffix it (`Moonshine Base v1`). |
| `bestFor` | The one line under the card title | A phrase of 48 characters or fewer, no full stop. Why someone picks this model. |
| `description` | The info sheet, under the title | One or two sentences saying what the model does. Never a copy of `bestFor`. |
| `languageCodes` | Language names on the card and in the sheet; search | ISO 639 codes, when the languages can be listed. Leave it out for models whose coverage is a count (`1600+ languages`). |
| `counterpartId` | "Live version" / "Final text version" link in the sheet | The same job in the other transcription mode. Must be mutual, cross modes, and point at a selectable model. |
| `provenance` | Model card and licence links in the sheet | Every entry, legacy ones included. |
| `experimental` | Nowhere by default: the model is listed only once its Advanced Labs toggle is on | `true` for a model still being qualified, and only then give it `badge: Experimental`. Promote it by deleting the flag and the badge in a new release; the app needs no update. Never on a retired or deprecated entry. |

Retired and deprecated entries stay in the catalogue so existing installs keep working. Give them
`bestFor: Existing installs only` and a `replacementId`; the app groups them under older models.
`scribekey-models validate` enforces the unique-name, distinct-guidance, counterpart, and experimental-badge rules.

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
