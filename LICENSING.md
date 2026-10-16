# Licensing

This file says which parts of this repository are meant to be shared, on what terms, and which
parts are meant to stay under ScribeKey's control. It records intent. It does not change the
licence anything is distributed under.

**Today everything in this repository is distributed under the MIT licence** (`LICENSE`,
`pyproject.toml`), and has been since the repository was published on 15 September 2026. Anything
already obtained under MIT stays under MIT for whoever obtained it. The target licences below would
apply only to releases made after a change, and no change has been made yet.

This is not legal advice. Items marked **(lawyer)** need a lawyer's answer before anyone acts on
them.

## The four categories

| Category | Target terms | Why |
| --- | --- | --- |
| Tooling | Apache 2.0 | Open for anyone to use, including commercially. Adds an explicit patent grant and a NOTICE file that carries attribution forward. |
| Benchmark data and model metadata | ODbL 1.0 | Public, reusable data. Publicly used derivative databases must be shared under the same terms and credit the source. |
| Recommendations | Controlled | The rankings and tier picks are the expensive, continuously updated part. |
| Recommendations API and scoring | Controlled, not in this repository | Lives in private repositories and services. FSL 1.1 is the option to evaluate if any of it is ever published. |

ODbL and Apache 2.0 both allow a competitor to use the material commercially. That is the price of
an open licence. Stopping a competing service needs a source-available licence (FSL 1.1, PolyForm
Perimeter) or keeping the material out of public view.

## Where each path belongs

### Tooling: Apache 2.0

| Path | What it is |
| --- | --- |
| `src/scribekey_models/` | Catalogue generation, validation, guardrails, promotion, signing, mirroring, CleanBench runner |
| `schemas/` | JSON schemas for canonical inputs, generated catalogues and signatures |
| `tests/` | Unit, reproducibility and guardrail tests and their fixtures |
| `tools/record_cleanup_examples/` | Cleanup example recorder |
| `bench/asr/*.py`, `bench/asr/zipformer/*.py`, `bench/asr/zipformer/*.sh` | ASR benchmark runners and scorers |
| `bench/hotwords/hotword_test.py` | Hotword benchmark runner |
| `.github/workflows/` | CI and promotion workflows |
| `docs/` | Operator guide, compatibility contract, contribution notes, plans |
| `README.md`, `pyproject.toml` | Project metadata |

### Benchmark data and model metadata: ODbL 1.0

| Path | What it is |
| --- | --- |
| `bench/cleanbench_corpus_v1.jsonl` | The frozen 240-case CleanBench corpus |
| `bench/cleanup_candidates.yaml` | Cleanup candidates and their pinned revisions |
| `bench/results/` | Per-model CleanBench output and `summary.md` |
| `bench/asr/zipformer/bench_out*.json`, `bench/hotwords/results.txt` | ASR and hotword results |
| `catalog/speech.yaml`, `catalog/cleanup.yaml`, `catalog/diarization.yaml` | Canonical model metadata |
| `catalog/releases/`, `catalog/channels.yaml` | Release and channel records |
| `generated/model_catalog.json`, `generated/cleanup_model_catalog.json`, `generated/speaker_diarization_manifest.json` | Runtime catalogues built from the metadata |
| `generated/releases/*/` (except `cloud_model_tiers.json`), `generated/channels/` | Immutable release snapshots and signed channel manifests |

Benchmark scores are factual measurements. Facts are generally not protected by copyright, and in
Australia effort spent gathering data does not by itself create copyright in it. ODbL rests on
copyright, database rights and contract, so its reach over individual scores may be thin. Someone
who runs the same models and gets the same numbers is not copying them. **(lawyer)**: how much of
this collection ODbL can actually protect in Australia and in the countries ScribeKey ships to.

### Recommendations: controlled

| Path | What it is |
| --- | --- |
| `catalog/cloud_tiers.json` | Recommended cloud model per provider and task, with tiers |
| `generated/cloud_model_tiers.json`, `generated/releases/*/cloud_model_tiers.json` | The same picks, shipped to the app |

These files are the recommendations. They are public today under MIT: they ship in every release
snapshot here, and the app bundles a copy. The scoring that produces them stays in the private
`scribekey-model-research` repository. Making new versions controlled means either publishing them
under a source-available licence or serving them from somewhere other than this public repository.
That is the open decision below.

### Recommendations API and scoring: not in this repository

The scoring pipeline, raw research results and any recommendations API are not here. Access to a
hosted service is governed by its terms of service (authentication, rate limits, no bulk
extraction, no resale), not by a repository licence. Those terms cover the service, not copies of
data already published here under an open licence.

## Not ours to license

| Path | Terms |
| --- | --- |
| `assets/bpe-vocab/` | Derived from NVIDIA's Parakeet tokenizers, CC-BY-4.0. Attribution in `assets/bpe-vocab/README.md` and each `SOURCE`. |
| `.agents/skills/`, `.claude/skills/` | Third-party agent skills, under their upstream terms. |
| Model weights | Not in this repository. Each model's `licenseId` and `licenseUrl` in `catalog/` govern its weights. |
| `keys/release-signing.pub` | A public key. Publishing it grants no right to sign releases. |

The ScribeKey name and logo are not licensed by any of the above. A fork can reuse the tooling and
data on their terms but cannot present itself as ScribeKey. **(lawyer)**: whether to register the
mark, which is the main protection against a rebranded copy.

## Open decisions

1. Relicense tooling from MIT to Apache 2.0 for future releases. Low risk: Apache 2.0 is also
   permissive. Needs `LICENSE`, `pyproject.toml` and a `NOTICE` file.
2. Put benchmark data and model metadata under ODbL 1.0 for future releases.
3. Choose how the recommendations stay controlled: keep publishing them under MIT, move them under
   FSL 1.1 or PolyForm Perimeter, or serve them outside this repository.
4. **(lawyer)**: confirm ScribeKey holds the rights to relicense everything it would relicense. Git
   history shows no outside contributors besides Dependabot.
5. **(lawyer)**: check that FSL 1.1 or PolyForm Perimeter fits data files, since both are written
   for software.
