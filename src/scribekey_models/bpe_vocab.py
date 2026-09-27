"""Build the sherpa-onnx ``bpe.vocab`` a NeMo transducer needs for hotwords.

sherpa-onnx turns hotword text into tokens with ``modelingUnit = "bpe"`` and a ``bpe.vocab``
(``piece<TAB>score`` per line), but the sherpa exports in ``catalog/speech.yaml`` ship only
``tokens.txt``. The vocabulary cannot be rebuilt from ``tokens.txt`` alone: how many leading pieces
score 0 is known only to the original SentencePiece model. So this reads ``tokenizer.model`` out of
the pinned upstream ``.nemo`` (a tar, sometimes gzipped) by streaming from the start and stopping
at the tokenizer, which NeMo writes before the weights, then refuses the result unless every piece
matches the export's ``tokens.txt`` in order.
"""

from __future__ import annotations

import hashlib
import tarfile
import urllib.request
from pathlib import Path
from typing import Any

import yaml

from scribekey_models.catalog import CATALOG_DIR

# NeMo archives put the tokenizer in the first few hundred kilobytes; never stream the weights.
MAX_STREAM_BYTES = 50_000_000
BLANK_TOKEN = "<blk>"


class _CappedReader:
    def __init__(self, response: Any, cap: int) -> None:
        self._response = response
        self._cap = cap
        self.read_bytes = 0

    def read(self, size: int = -1) -> bytes:
        if self.read_bytes > self._cap:
            raise ValueError(f"tokenizer.model not found in the first {self._cap} bytes")
        chunk = self._response.read(size)
        self.read_bytes += len(chunk)
        return chunk


def extract_tokenizer(nemo_url: str, cap: int = MAX_STREAM_BYTES) -> bytes:
    with urllib.request.urlopen(nemo_url) as response:
        reader = _CappedReader(response, cap)
        with tarfile.open(fileobj=reader, mode="r|*") as archive:
            for member in archive:
                if member.name.endswith("tokenizer.model"):
                    extracted = archive.extractfile(member)
                    if extracted is None:
                        break
                    return extracted.read()
    raise ValueError(f"{nemo_url} has no tokenizer.model")


def vocab_from_tokenizer(tokenizer_model: bytes) -> list[tuple[str, float]]:
    import sentencepiece as spm  # optional [bench] extra

    processor = spm.SentencePieceProcessor(model_proto=tokenizer_model)
    return [
        (processor.id_to_piece(index), processor.get_score(index))
        for index in range(processor.get_piece_size())
    ]


def check_against_tokens(vocab: list[tuple[str, float]], tokens_txt: str) -> None:
    """The export's tokens.txt is the tokenizer's pieces in order, plus NeMo's blank."""
    tokens = [line.rsplit(" ", 1)[0] for line in tokens_txt.splitlines() if line]
    pieces = [piece for piece, _ in vocab]
    if [token for token in tokens if token != BLANK_TOKEN] != pieces:
        raise ValueError("tokenizer.model pieces do not match the export's tokens.txt")


def render_vocab(vocab: list[tuple[str, float]]) -> str:
    """Same format as sherpa-onnx scripts/export_bpe_vocab.py."""
    return "".join(f"{piece}\t{score}\n" for piece, score in vocab)


def speech_model(model_id: str) -> dict[str, Any]:
    models = yaml.safe_load((CATALOG_DIR / "speech.yaml").read_text(encoding="utf-8"))["models"]
    model = next((m for m in models if m["id"] == model_id), None)
    if model is None:
        raise ValueError(f"No speech model '{model_id}'")
    if model["sherpaConfig"]["type"] != "nemo_transducer":
        raise ValueError(f"'{model_id}' is not a NeMo transducer; hotwords need one")
    return model


def build(model_id: str, upstream_revision: str, nemo_file: str, out_dir: Path) -> Path:
    model = speech_model(model_id)
    source = model["provenance"]["sourceModel"]
    tokens_url = next(f["downloadUrl"] for f in model["files"] if f["name"] == "tokens.txt")
    nemo_url = f"https://huggingface.co/{source}/resolve/{upstream_revision}/{nemo_file}"

    vocab = vocab_from_tokenizer(extract_tokenizer(nemo_url))
    with urllib.request.urlopen(tokens_url) as response:
        check_against_tokens(vocab, response.read().decode("utf-8"))

    target = out_dir / model_id / "bpe.vocab"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_vocab(vocab), encoding="utf-8")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (target.parent / "SOURCE").write_text(
        f"{source}@{upstream_revision}/{nemo_file}\nsha256 {digest}\nsizeBytes {target.stat().st_size}\n",
        encoding="utf-8",
    )
    return target
