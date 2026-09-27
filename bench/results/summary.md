# CleanBench host screen

Raw model output on the frozen 240-case CleanBench corpus, llama.cpp on host CPU, greedy decoding, one output budget for every model. No fidelity guard is applied, so these numbers are stricter than what a user would see. Latency is host CPU and only ranks models against each other. Rows marked *baseline* are not language models and never advance.

Advance to device qualification: none (highest mean similarity with protected-span retention ≥ 95%).

| Model | Size | Similarity | Exact | Protected spans | Controls kept | Added content | Truncated | Host p50 / p95 ms | Tokens/s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bitvoice-qwen3-0.6b | 397 MB | 0.927 | 56% | 69% | 100% | 5 | 0 | 730 / 2561 | 19.5 |
| bitvoice-smollm2-360m | 271 MB | 0.925 | 57% | 65% | 100% | 4 | 0 | 638 / 2024 | 23.2 |
| mumble-cleanup-2stage | 398 MB | 0.904 | 50% | 61% | 77% | 5 | 5 | 713 / 3231 | 19.7 |
| openwispr-cleanup-0.6b | 397 MB | 0.890 | 52% | 74% | 87% | 18 | 7 | 368 / 2228 | 29.7 |
| sherpa-punct-en *baseline* | 7 MB | 0.889 | 5% | 56% | 33% | 5 | 0 | 6 / 12 | n/a |
| quill | 529 MB | 0.883 | 50% | 74% | 90% | 11 | 1 | 592 / 3289 | 20.9 |

## Mean similarity by category

| Category | bitvoice-qwen3-0.6b | bitvoice-smollm2-360m | mumble-cleanup-2stage | openwispr-cleanup-0.6b | sherpa-punct-en | quill |
| --- | --- | --- | --- | --- | --- | --- |
| already_clean_controls | 1.000 | 1.000 | 0.953 | 0.961 | 0.975 | 0.946 |
| dates_numbers_money | 0.792 | 0.793 | 0.888 | 0.903 | 0.751 | 0.903 |
| false_starts_corrections | 0.808 | 0.781 | 0.759 | 0.805 | 0.726 | 0.772 |
| fillers_stutters | 0.973 | 0.976 | 0.948 | 0.946 | 0.907 | 0.953 |
| identifiers_urls_emails | 0.924 | 0.965 | 0.922 | 0.795 | 0.897 | 0.865 |
| negations_hedges_contrasts | 0.991 | 0.990 | 0.945 | 0.989 | 0.980 | 0.976 |
| questions_commands | 1.000 | 1.000 | 0.984 | 0.769 | 0.978 | 0.703 |
| run_ons_formatting | 0.926 | 0.895 | 0.834 | 0.951 | 0.903 | 0.943 |

## Artefacts

- `bitvoice-qwen3-0.6b`: `dhanr4j/bitvoice-dictation@572820f65a5a` `gguf/qwen3-0.6b-v2-Q4_K_M.gguf`, 397 MB (Apache 2.0 per model card table; repository metadata says "other")
- `bitvoice-smollm2-360m`: `dhanr4j/bitvoice-dictation@572820f65a5a` `gguf/smollm2-360m-v2-Q4_K_M.gguf`, 271 MB (Apache 2.0 per model card table; repository metadata says "other")
- `mumble-cleanup-2stage`: `amitashwini/mumble-cleanup-2stage@e7ce94746f0e` `mumble-cleanup-2stage-q4km.gguf`, 398 MB (Apache 2.0)
- `openwispr-cleanup-0.6b`: `rohitag13/openwispr-cleanup-qwen3-0.6b-GGUF@42c2c2e8beb0` `qwen3-0.6b.Q4_K_M.gguf`, 397 MB (Apache 2.0 claimed by the source model; GGUF repository metadata needs review)
- `sherpa-punct-en`: `https://github.com/k2-fsa/sherpa-onnx/releases/download/punctuation-models/sherpa-onnx-online-punct-en-2024-08-06.tar.bz2` `model.int8.onnx`, 7 MB (Apache 2.0 (upstream frankyoujian/Edge-Punct-Casing))
- `quill`: `Quobi/Quill@4cc2cc3c8e7e` `quill-0.8b-Q4_K_M.gguf`, 529 MB (Apache 2.0)
