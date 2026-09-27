# Hotword vocabularies

`bpe.vocab` files for the NeMo transducer speech models, so sherpa-onnx can turn Dictionary words
into tokens for hotword biasing (`modelingUnit = "bpe"`). The sherpa exports ship only
`tokens.txt`, so each file is built by `scribekey-models bpe-vocab` from the SentencePiece
tokenizer inside the pinned upstream `.nemo`, and checked piece by piece against the export's
`tokens.txt`. `SOURCE` records the exact upstream file, SHA-256 and size.

Only offline (segmented) transducers are here. sherpa-onnx 1.13.6 decodes the streaming NeMo
transducers greedily, which has no hotword support.

Derived from NVIDIA's Parakeet tokenizers, CC-BY-4.0:
[parakeet-tdt-0.6b-v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3),
[parakeet-unified-en-0.6b](https://huggingface.co/nvidia/parakeet-unified-en-0.6b).
