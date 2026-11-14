# Published FLEURS figures, as a cross-check

`references.yaml` lists published FLEURS error rates for the upstream models behind catalogue entries,
one entry per catalogue id and source: where the number came from (URL and revision), when it was
fetched, what build and runtime were measured, the dataset, the normaliser, and `{lang: {metric,
errorPercent}}`.

These numbers never become grades. A grade describes the export the app runs, measured by
`bench/asr/fleurs/`. Published figures measure other builds (NeMo checkpoints on a GPU, Q8 GGUF in
transcribe.cpp, a Photon runtime), so they are only a check on the harness. When our ranking disagrees
badly with them, look for a harness or export bug before trusting the grade.

Sources:

- **Open ASR Leaderboard** (`open-asr-leaderboard` for its FLEURS columns, `open-asr-leaderboard-english`
  for its English short-form average, which is not FLEURS and is never compared). Its datasets are not
  downloadable anonymously, so `fetch.py` reads the Space's public API at one pinned version.
- **Handy / transcribe.cpp** (`handy-transcribe-cpp`): Q8_0 results from its `catalog/<model>.json`, on
  the full FLEURS test split with the recipe our harness copies. The closest comparison.
- **Model cards** (`model-card:<repo>`), only where a card states per-language FLEURS figures.

## Refresh

```bash
uv venv /tmp/ref-env -p 3.12 && uv pip install -p /tmp/ref-env pyyaml
/tmp/ref-env/bin/python bench/asr/references/fetch.py --write
```

`fetch.py` replaces only the leaderboard entries, at the version pinned as `VERSION`. To move to a newer
leaderboard version, read the Space's `init.py`, update `VERSION` and the revisions next to it, and
re-run. Handy and model-card entries are curated by hand: edit them in the YAML with the new revision.

## Read the report

```bash
python3 bench/asr/references/compare.py
```

It prints, per language, our measurement beside every reference with the same metric, then two kinds
of flag. It always exits 0, and `report(results_dir, references_path)` returns the same markdown.

- **above reference**: our error exceeds the best reference for that model by more than 50% relative
  *and* more than 2 points. Both are needed: small models on hard languages differ by a few points
  between builds, and strong models differ by large ratios over fractions of a point.
- **order flip**: two models we measured rank the other way round in one source. One flip between two
  close models is noise. Several flips around one model point at that model's harness setup.

Some real gaps stay under the thresholds. Parakeet Unified English measures 5.75% against Handy's
3.99% (+44%, +1.76 points), a grade lower for the same model, and is not flagged. The flags catch broken
runs; read the deltas too.
