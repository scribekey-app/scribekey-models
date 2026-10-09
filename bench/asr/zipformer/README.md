# Streaming Zipformer against Nemotron English Live, 2026-10-09

For #921: every live model needs 6 GB, so 4 GB phones show no words while speaking. Two English
streaming Zipformer transducers from sherpa-onnx were scored against Nemotron English Live, the
app's current live model, on the same data and method as the 2026-09-29 Parakeet comparison.

Models, all INT8, decoded streaming with sherpa-onnx 1.13.8, greedy, 2 threads, 0.1 s chunks,
0.66 s tail padding, no endpointing:

| Name | Export | Training data | Disk |
|---|---|---|---|
| Nemotron | `csukuangfj2/sherpa-onnx-nemotron-speech-streaming-en-0.6b-560ms-int8-2026-04-25` @ `52056fdc` | NVIDIA | 662 MB |
| zip0626 | `csukuangfj/sherpa-onnx-streaming-zipformer-en-2023-06-26` @ `672fbf1b` (chunk 16, left 128) | LibriSpeech | 73 MB |
| zip0621 | `csukuangfj/sherpa-onnx-streaming-zipformer-en-2023-06-21` @ `9a65b6ea` | GigaSpeech + LibriSpeech | 189 MB |

Data: 150 LibriSpeech test-other clips and 100 FLEURS en_us test clips at an even stride through
the first parquet shard; English Whisper normaliser; `jiwer`. Babble adds three other clips from
the same set at 5 dB below the target.

## Word error rate, %

| Set | Clips | Audio (s) | Nemotron | zip0626 | zip0621 |
|---|---|---|---|---|---|
| LibriSpeech test-other, clean | 150 | 1018 | 5.71 | 8.13 | 6.14 |
| LibriSpeech test-other, babble | 150 | 1018 | 27.92 | 32.65 | 31.85 |
| FLEURS en_us, clean | 100 | 994 | 12.46 | 72.39 | 62.23 |
| FLEURS en_us, babble | 100 | 994 | 34.36 | 83.70 | 58.39 |
| FLEURS en_us, clean, peak-normalised | 100 | 994 | 6.89 | 17.93 | 9.58 |
| FLEURS en_us, babble, peak-normalised | 100 | 994 | 21.91 | 42.05 | 34.63 |

Many FLEURS clips are very quiet (one peaks at 0.011 of full scale). On those both Zipformers
return nothing or stop early, while Nemotron transcribes them, so the raw FLEURS rows mostly
measure recording level. The peak-normalised rows scale each clip to 0.9 peak after mixing. A
phone's microphone level is the open question this leaves: the Galaxy S8 run has to check quiet
speech.

Speed: both Zipformers decoded about 3 to 4 times faster than Nemotron on this shared 4-vCPU host
(Intel Xeon 2.8 GHz); the absolute real-time factors drifted between runs. Host peak RSS after
loading and decoding one clip: Nemotron 966 MB, zip0626 171 MB, zip0621 277 MB (each includes
about 36 MB of Python).

## Choice

zip0621 ships as Zipformer English Live. On clean audio it is close to Nemotron (6.14 against 5.71
on LibriSpeech, 9.58 against 6.89 on normalised FLEURS), where zip0626, trained on LibriSpeech
alone, has nearly twice the error on FLEURS. It is 189 MB rather than the 130 MB the issue
guessed, and needs about 100 MB more memory, which the S8 run must confirm stays under 400 MB.
Neither Zipformer beats Nemotron anywhere, so it stays the live model from 6 GB.

Not chosen: the Kroko English Zipformers. Their licence is unclear (`Banafo/Kroko-ASR` has an
empty LICENSE file and points production use to paid models), so they need Banafo's written
confirmation first.

Not measured: a phone. Scripts and raw results: scribekey-models `bench/asr/zipformer/`.

## Reproduce

The scripts expect to sit in `scripts/` under a working directory. Needs `sherpa-onnx==1.13.8`,
`soundfile`, `pyarrow`, `jiwer`, `whisper-normalizer`, `numpy`.

```bash
mkdir -p work/scripts && cp bench/asr/zipformer/*.py bench/asr/zipformer/*.sh work/scripts/ && cd work
scripts/download_models.sh
mkdir -p data/libri_other.parquet.d data/fl_en_us.parquet.d
curl -fL -o data/libri_other.parquet.d/0.parquet https://huggingface.co/api/datasets/openslr/librispeech_asr/parquet/all/test.other/0.parquet
curl -fL -o data/fl_en_us.parquet.d/0.parquet https://huggingface.co/api/datasets/google/fleurs/parquet/en_us/test/0.parquet
python3 -I scripts/extract.py data/libri_other.parquet.d/0.parquet libri_other 150 data
python3 -I scripts/extract.py data/fl_en_us.parquet.d/0.parquet fl_en_us 100 data
scripts/run_all.sh        # about 45 min on a 4-vCPU host
scripts/run_peaknorm.sh   # the peak-normalised FLEURS rows
```
