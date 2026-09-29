# Speech model comparison, 2026-09-29

Parakeet Ultra int8 (`mldecode/parakeet-ultra-onnx-int8` at `3282a6e3`) against the Parakeet v3
int8 the catalogue shipped (`csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8` at `2bda32ec`).
Host: macOS, sherpa-onnx 1.13.8, `nemo_transducer`, greedy decoding, 2 threads. Speed figures are
host times; the ratio, not the absolute value, is what carries over to a phone.

Data: 150 LibriSpeech test-other clips and 100 FLEURS test clips each in `en_us`, `de_de`, `es_419`
and `fr_fr`, taken at an even stride through the first parquet shard. Text is normalised with
`whisper-normalizer` (English normaliser for English, basic for the rest) and scored with `jiwer`.
The noisy condition adds the sum of three other clips from the same set, scaled to 5 dB below the
target clip. It is a stress test, not a model of any real room.

| Set | Clips | Audio (s) | v3 WER % | Ultra WER % | Ultra better / worse |
|---|---|---|---|---|---|
| LibriSpeech test-other, clean | 150 | 1018 | 4.48 | 3.43 | 25 / 2 |
| LibriSpeech test-other, babble | 150 | 1018 | 61.50 | 21.92 | 116 / 8 |
| FLEURS en_us, clean | 100 | 994 | 8.88 | 7.20 | 32 / 10 |
| FLEURS en_us, babble | 100 | 994 | 38.38 | 18.29 | 63 / 8 |
| FLEURS de_de, clean | 100 | 1377 | 6.88 | 6.26 | 23 / 19 |
| FLEURS de_de, babble | 100 | 1377 | 55.38 | 28.09 | 80 / 10 |
| FLEURS es_419, clean | 100 | 1218 | 5.49 | 4.33 | 28 / 8 |
| FLEURS es_419, babble | 100 | 1218 | 30.00 | 10.45 | 74 / 10 |
| FLEURS fr_fr, clean | 100 | 1024 | 8.13 | 6.59 | 30 / 12 |
| FLEURS fr_fr, babble | 100 | 1024 | 54.04 | 24.57 | 84 / 5 |

Speed was within 3% on every set (about 27 to 30x real time on the host for both). Ultra's files
total 629,512,715 bytes against 670,478,772 for v3.

Not measured: a phone, and any language beyond these four.

Reproduce: `extract.py <parquet> <name> <n>` writes `clips/<name>.json`, then `bench.py` scores both
bundles from directories named `v3/` and `ultra/`. Needs `sherpa-onnx==1.13.8`, `soundfile`,
`pyarrow`, `jiwer`, `whisper-normalizer`.
