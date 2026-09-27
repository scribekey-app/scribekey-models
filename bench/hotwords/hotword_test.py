"""End-to-end check: do per-stream hotwords with a generated bpe.vocab change Parakeet v3 output?

Synthesises jargon-heavy sentences with a Piper voice, then transcribes each three ways:
greedy (what the app does today), beam search with no hotwords, and beam search with the
sentence's hotwords passed to create_stream(hotwords) - the Kotlin createStream(hotwords) path.

Run from a directory holding the Parakeet v3 int8 export (encoder/decoder/joiner saved with a
pv3- prefix), parakeet-0.6b-v3/ with tokens.txt and the bpe.vocab from
scribekey-models bpe-vocab, and the vits-piper-en_US-lessac-medium release. Results: results.txt.
"""

import sherpa_onnx

TTS_DIR = "vits-piper-en_US-lessac-medium"
SENTENCES = [
    ("Deploy the Kubernetes cluster with Terraform before Friday.", ["Kubernetes", "Terraform"]),
    ("Email Siobhan Nguyen about the ScribeKey rollout.", ["Siobhan", "Nguyen", "ScribeKey"]),
    ("The Grafana dashboard shows Prometheus alerts from Wednesday.", ["Grafana", "Prometheus"]),
    ("Ask Aoife to review the Qdrant migration.", ["Aoife", "Qdrant"]),
    ("Book a table at Nobu for Saoirse and Tadhg.", ["Nobu", "Saoirse", "Tadhg"]),
]

tts = sherpa_onnx.OfflineTts(
    sherpa_onnx.OfflineTtsConfig(
        model=sherpa_onnx.OfflineTtsModelConfig(
            vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                model=f"{TTS_DIR}/en_US-lessac-medium.onnx",
                tokens=f"{TTS_DIR}/tokens.txt",
                data_dir=f"{TTS_DIR}/espeak-ng-data",
            ),
            num_threads=4,
        )
    )
)


def recognizer(method: str, bpe_vocab: str = "") -> sherpa_onnx.OfflineRecognizer:
    return sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder="pv3-encoder.int8.onnx",
        decoder="pv3-decoder.int8.onnx",
        joiner="pv3-joiner.int8.onnx",
        tokens="parakeet-0.6b-v3/tokens.txt",
        num_threads=4,
        decoding_method=method,
        model_type="nemo_transducer",
        modeling_unit="bpe" if bpe_vocab else "cjkchar",
        bpe_vocab=bpe_vocab,
        hotwords_score=2.0,
    )


greedy = recognizer("greedy_search")
beam = recognizer("modified_beam_search", "parakeet-0.6b-v3/bpe.vocab")


def transcribe(rec: sherpa_onnx.OfflineRecognizer, audio, hotwords: str | None = None) -> str:
    stream = rec.create_stream(hotwords) if hotwords else rec.create_stream()
    stream.accept_waveform(audio.sample_rate, audio.samples)
    rec.decode_stream(stream)
    return stream.result.text.strip()


hits = {"greedy": 0, "beam": 0, "beam+hotwords": 0}
total = 0
for sentence, words in SENTENCES:
    audio = tts.generate(sentence, sid=0, speed=1.0)
    outputs = {
        "greedy": transcribe(greedy, audio),
        "beam": transcribe(beam, audio),
        # Hotwords are "/"-separated in create_stream; each is BPE-encoded with bpe.vocab.
        "beam+hotwords": transcribe(beam, audio, "/".join(words)),
    }
    total += len(words)
    print(f"\nSAID : {sentence}")
    for name, text in outputs.items():
        found = sum(word in text for word in words)
        hits[name] += found
        print(f"{name:14}: {text}   [{found}/{len(words)}]")

print("\nTarget words recognised exactly:", {k: f"{v}/{total}" for k, v in hits.items()})
