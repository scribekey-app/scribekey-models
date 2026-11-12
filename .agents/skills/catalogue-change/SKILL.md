---
name: catalogue-change
description: Change a ScribeKey model catalogue and carry it through to the Android app. Use whenever catalog/*.yaml, a schema, generated/, a release or a channel is touched, when a speech model is added, graded, promoted from experimental or retired, when accuracy grades or Handy benchmark numbers come up, and when someone asks why the app does not show a catalogue change yet.
---

# Changing a catalogue

`catalog/` is the only place a person edits. `generated/` is output, and `generated/releases/<id>/`
is frozen once created. `docs/adding-a-model.md` lists every field and where Android shows it;
`docs/model-copy-style-guide.md` covers wording; `docs/operator-guide.md` covers releases and signing.

## The loop

```bash
uv run --extra dev scribekey-models generate
uv run --extra dev scribekey-models validate
uv run --extra dev pytest -q
uv run --extra dev ruff check src tests
```

`uv run` writes an untracked `uv.lock`. Delete it before committing; the repo does not track one.
This checkout's shell aliases `rm` and `cp` to their interactive forms, so use `command rm -f` and
`command cp -f` in scripts or the step silently does nothing.

Work in a worktree off `origin/main` (`git worktree add ../<name> -b <branch> origin/main`). The
main checkout is often parked on an old branch.

## A new field

A field reaches the app only when all four of these change together:

1. `schemas/<catalogue>.schema.json` accepts it in the YAML.
2. The `generate_*_catalog` function in `src/scribekey_models/catalog.py` projects it. The generator
   copies fields by name, so a field it does not name is dropped without an error.
3. A test in `tests/test_catalog.py` pins the projected shape.
4. `docs/adding-a-model.md` gets a row saying where Android shows it.

Add fields as optional. Android decodes with `ignoreUnknownKeys`, so an older app skips a new field,
but a field that becomes required breaks every app that predates it.

## Speech accuracy grades

`accuracy` on a speech model is error percent by ISO 639 language code, on the FLEURS test split.
`accuracy_grade()` turns each into the grade the app shows: A under 5%, B under 10%, C under 20%,
D under 30%, F beyond, with each `+`/`-` a factor of the cube root of 2. Never write a grade by hand.

The numbers come from Handy's published benchmark (`@handy-computer/models` on npm, `catalog.json`,
`results.<model>.accuracy.<lang>.error`), credited in the comment at the top of `catalog/speech.yaml`.
Keep that credit, and update the version in it when the numbers are refreshed.

Give a model an `accuracy` block only when both hold:

- Handy measured the same source model (`provenance.sourceModel`), not a sibling or a successor.
- It was measured in the mode this entry runs in. Parakeet English Live preview has none, because
  the measurement is of the after-speaking model.

Handy measured a Q8 GGUF build on a desktop. The grade ranks models against each other; it is not a
phone measurement, and no copy may say it is. Unmeasured as of 2026.11.5: Distil-Whisper, Omnilingual,
Parakeet Redux, Zipformer English Live, both Moonshine v2 models, Parakeet English Live preview.

## Choosing a model to add

- The app runs sherpa-onnx only. A candidate needs a sherpa-onnx ONNX export that exists today; a
  model that needs another runtime is out of scope. Check the export repository and its file sizes
  on Hugging Face, and read the licence from the source model card, not from a third-party list.
- Pin `downloadUrl` to an immutable revision and record `sizeBytes` and `sha256` per file.
- A model still being qualified ships with `experimental: true` and `badge: Experimental`.
- A phone timing comes before admission. Desktop speed says little about a phone.

## Release and delivery

A merged catalogue change reaches nobody by itself. In order:

1. Merge the change to `main`.
2. On a branch off the new `main`: `scribekey-models release create --id <YYYY.MM.N> --description "..."`,
   commit `catalog/releases/<id>.yaml` and `generated/releases/<id>/`, and merge that.
3. In the Android repo, copy the release's files over `app/src/main/assets/` (see that repo's
   `speech-model-catalogue` skill). The app's check compares them byte for byte with the newest release.
4. Promotion to `qa` or `stable` is the **Prepare Release Promotion** workflow. It signs with a key
   held in a protected environment and needs a person to approve it. Never promote from a laptop,
   and never merge a promotion PR without the owner asking.

Until step 4, an app that has a verified channel keeps showing the channel's older catalogue.
