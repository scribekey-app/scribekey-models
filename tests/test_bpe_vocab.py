import io
import tarfile
from pathlib import Path

import pytest

from scribekey_models.bpe_vocab import (
    check_against_tokens,
    extract_tokenizer,
    render_vocab,
    speech_model,
)


def _nemo(path: Path, compression: str) -> str:
    """A .nemo-shaped tar: config and tokenizer first, then a weights member."""
    mode = "w:gz" if compression == "gz" else "w"
    with tarfile.open(path, mode) as archive:
        for name, data in [
            ("./model_config.yaml", b"cfg"),
            ("./abc_tokenizer.model", b"TOKENIZER"),
            ("./model_weights.ckpt", b"W" * 4096),
        ]:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return path.as_uri()


@pytest.mark.parametrize("compression", ["plain", "gz"])
def test_extracts_the_tokenizer_from_plain_and_gzipped_nemo(tmp_path: Path, compression) -> None:
    assert extract_tokenizer(_nemo(tmp_path / "m.nemo", compression)) == b"TOKENIZER"


def test_stops_streaming_when_the_tokenizer_is_not_near_the_start(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not found in the first"):
        extract_tokenizer(_nemo(tmp_path / "m.nemo", "plain"), cap=10)


def test_vocab_must_match_tokens_txt_apart_from_the_blank() -> None:
    vocab = [("<unk>", 0.0), ("▁s", -1.0), ("er", -2.0)]

    check_against_tokens(vocab, "<unk> 0\n▁s 1\ner 2\n<blk> 3\n")
    with pytest.raises(ValueError, match="do not match"):
        check_against_tokens(vocab, "<unk> 0\ner 1\n▁s 2\n<blk> 3\n")


def test_vocab_uses_the_sherpa_export_format() -> None:
    assert render_vocab([("<unk>", 0.0), ("▁s", -1.0)]) == "<unk>\t0.0\n▁s\t-1.0\n"


def test_only_nemo_transducers_take_hotwords() -> None:
    assert speech_model("parakeet-0.6b-v3")["sherpaConfig"]["type"] == "nemo_transducer"
    with pytest.raises(ValueError, match="not a NeMo transducer"):
        speech_model("parakeet-110m")
