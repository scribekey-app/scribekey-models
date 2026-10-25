# ScribeKey Fast v1: private staging and publication plan

25 October 2026. Owner request: prepare the release, upload privately, and obtain confirmation before public publication.

## Agreed release

- Product name: **ScribeKey Fast** by ScribeKey; model ID `scribekey-cleanup-fast`.
- Selected candidate: `v7-replay-tgt`, continuing Sotto v6 on 2,000 pilot rows, 2,000 Sotto replay rows and 350 targeted rows. Naming and the Sotto-derived route were accepted on research #45; evidence is in #79/#80 and PR #82. The broader shipping decision #81 and release bar #44 remain open.
- Hugging Face destinations: `scribekey/scribekey-cleanup-fast` (merged BF16/tokenizer) and `scribekey/scribekey-cleanup-fast-GGUF` (evaluated Q8_0). Create **private**. Tag reviewed commits `v1-rc1`; reserve `v1` for an approved release.
- Q8_0: 379,219,904 bytes, SHA-256 `bbce6fe5dc52080366ea65768f96e8d6265c45c1925d9a2e3d03de32856295cc`.
- BF16: 708,984,464 bytes, SHA-256 `4ece194d955bc3abc2a96a02bb81c3e37e79cc672d99d07e172537b52c636fbf` (checked on the VM and after transfer). The export manifest's `merged_sha256` (`566a1069…`) hashes the entire original checkpoint directory, not this file.
- Rename the download file, keeping evaluated GGUF bytes intact. Internal experiment identifiers are provenance, not the display name.

## Package and checks

1. Verify the two weight files against the export manifest; upload only an explicit file list. Keep training/evaluation rows, credentials, adapters and logs outside upload directories.
2. Include a model card, exact prompt, greedy generation settings, compatible tokenizer template, original LFM licence, inherited Sotto notice/MIT text, training-source attributions, modification notices, checksums and machine-readable provenance/evaluation summaries.
3. Use the S1-mini card as an editorial reference for overview, quickstart, controls, measured examples, integration and terms. Do not copy its naming clause or imply S1-mini ancestry. Preserve LFM Open License v1.0 obligations and explain its commercial revenue condition. Dataset licences remain distinct from the weights' licence.
4. Verify the Transformers chat template renders the app's exact `InputOutputControlLine` prompt, including BOS and whitespace. Check generation is greedy. Record fresh public-input outputs from this Q8_0; retain only observed examples.
5. Keep measured Q8_0 quality separate from BF16 inference smoke checks. Prior S25 Ultra timings are for **v7-replay**, not this final candidate. Do not claim final-artifact or midrange qualification.
6. Upload both destinations privately, pin commit IDs, create private RC tags, verify remote file sizes/hashes and anonymously inaccessible status, and record a private staging receipt without credentials.

## Catalogue preparation

Prepare a local branch in the public `scribekey-models` repository with the ScribeKey Fast candidate, immutable Q8_0 URL, exact size/hash, correct LFM/Sotto attribution and `InputOutputControlLine` runtime profile. Generate and validate metadata, run the existing tests and lint, and check that signed QA/stable pointers and immutable historical releases remain unchanged.

Do not push to the public repository, merge, promote a channel or retire Sotto during private staging. After approval, publish the HF repositories and prepare the public catalogue PR. A new signed release must require an app build containing scribekey#1415/#1397/#1413; older apps cannot use the new prompt template safely. Review the model-aware “Match the app” subtitle before activation.

## Outstanding gates before production/default promotion

- Owner approval of public HF visibility and public `scribekey-models` publication.
- Phone recheck of this exact Q8_0 plus a midrange phone run; settings journey on a compatible app build.
- Final release-bar/default decisions on research #44/#81 and recorded follow-through on #79/#80/#83. Do not close these just because files were uploaded.
- Dataset provenance is inherited in part from Sotto's published declarations, not independently reconstructed. Research #52 accepts the unresolved reach of CC BY-SA training-data obligations as a risk for weights that do not reproduce the text. Carry that caveat forward; do not describe this as a legal opinion or complete provenance audit.
- No new model training, teacher spend, new naming restriction, lower-bit release or automatic stable promotion is part of this staging task.
