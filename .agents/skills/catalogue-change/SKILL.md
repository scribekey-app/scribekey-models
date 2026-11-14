---
name: catalogue-change
description: Change a ScribeKey model catalogue and carry it through to the Android app. Use whenever catalog/*.yaml, a schema, generated/, a release or a channel is touched, when a speech model is added, measured, graded, promoted from experimental or retired, when accuracy grades, FLEURS or benchmark numbers come up, and when someone asks why the app does not show a catalogue change yet.
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

**Every speech model must have one, measured by `bench/asr/fleurs/`.** `validate` fails a model
with no `accuracy`, a listed language FLEURS has but `accuracy` lacks, or a number that differs from
`bench/asr/fleurs/results/<id>.json`. So the only way to a number is to run the harness and commit
its result file with the YAML. `bench/asr/fleurs/README.md` has the method and the commands.

Measuring is automatic. Add or change a model on main or a `measure/**` branch, and **Measure speech
accuracy** measures what `plan.py` says is missing or stale, then opens a PR from `accuracy/<branch>`
with the numbers and grades. Review it and merge. `run_all.sh` and `collect.py` stay as the local route.

- The harness runs the exact export the entry downloads, in the mode the app runs it, with the app's
  segment ceiling or live feed. A new export revision or a new pinned sherpa-onnx makes a result stale,
  and the whole model is measured again. A change to how the app decodes a family does not: delete the
  language from the result file and rerun.
- Do not copy Handy's or any other published figure. Handy measures a Q8 GGUF build of the source
  model, not the int8 export the app ships. The recipe is Handy's, credited in `catalog/speech.yaml`,
  so the grade bands mean the same, with one change: each clip is scaled to a 0.5 peak first, because
  FLEURS is far quieter than a phone mic and the int8 exports lose accuracy on quiet input.
- A model with no `languageCodes` is measured on every language any catalogue model is graded in.
- Measuring needs 1 to 2 GB free per model; check `df -h /` first.

The grade ranks models against each other on a desktop and read speech. It is not a phone
measurement, and no copy may say it is.

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
