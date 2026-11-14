"""Measure a catalogue speech model on the FLEURS test split, the way Handy publishes its numbers.

Recipe (transcribe.cpp `docs/tools/wer.md`): the whole FLEURS test split per language, the
`transcription` field as reference, Whisper's English normaliser for English and the basic one
otherwise, character error for zh/yue/ja/ko/th/km/lo/my, greedy decoding, no gain normalisation.
Two things differ, deliberately: the model is the exact sherpa-onnx export the catalogue ships,
and it is decoded the way the app decodes it (offline or streaming, segment ceiling, tail padding).

    uv run --python 3.12 --with sherpa-onnx==1.13.8 --with jiwer --with whisper-normalizer \
        --with soundfile --with pyarrow --with numpy --with huggingface_hub --with pyyaml \
        bench/asr/fleurs/measure.py <model-id> <lang> [<lang> ...]

Writes bench/asr/fleurs/results/<model-id>.json, merged with earlier runs of other languages.
Audio and model files go under $BENCH_CACHE (default /tmp/scribekey-fleurs) and each language's
parquet is deleted after scoring, so disk use stays at one model plus one language.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

import jiwer
import numpy as np
import pyarrow.parquet as pq
import sherpa_onnx
import soundfile as sf
import yaml
from huggingface_hub import hf_hub_download
from whisper_normalizer.basic import BasicTextNormalizer
from whisper_normalizer.english import EnglishTextNormalizer

ROOT = Path(__file__).resolve().parents[3]
RESULTS = Path(__file__).parent / "results"
CACHE = Path(os.environ.get("BENCH_CACHE", "/tmp/scribekey-fleurs"))
RATE = 16000

# transcribe.cpp scripts/wer/languages.py, for the codes this catalogue uses.
FLEURS = {
    "af": "af_za", "am": "am_et", "ar": "ar_eg", "as": "as_in", "ast": "ast_es", "az": "az_az",
    "be": "be_by", "bg": "bg_bg", "bn": "bn_in", "bs": "bs_ba", "ca": "ca_es", "ceb": "ceb_ph",
    "ckb": "ckb_iq", "cs": "cs_cz", "cy": "cy_gb", "da": "da_dk", "de": "de_de", "el": "el_gr",
    "en": "en_us", "es": "es_419", "et": "et_ee", "fa": "fa_ir", "fi": "fi_fi", "fil": "fil_ph",
    "fr": "fr_fr", "ga": "ga_ie", "gl": "gl_es", "gu": "gu_in", "ha": "ha_ng", "he": "he_il",
    "hi": "hi_in", "hr": "hr_hr", "hu": "hu_hu", "hy": "hy_am", "id": "id_id", "ig": "ig_ng",
    "is": "is_is", "it": "it_it", "ja": "ja_jp", "jv": "jv_id", "ka": "ka_ge", "kk": "kk_kz",
    "km": "km_kh", "kn": "kn_in", "ko": "ko_kr", "ky": "ky_kg", "lb": "lb_lu", "lo": "lo_la",
    "lt": "lt_lt", "lv": "lv_lv", "mi": "mi_nz", "mk": "mk_mk", "ml": "ml_in", "mn": "mn_mn",
    "mr": "mr_in", "ms": "ms_my", "mt": "mt_mt", "my": "my_mm", "nb": "nb_no", "ne": "ne_np",
    "nl": "nl_nl", "pa": "pa_in", "pl": "pl_pl", "ps": "ps_af", "pt": "pt_br", "ro": "ro_ro",
    "ru": "ru_ru", "sd": "sd_in", "sk": "sk_sk", "sl": "sl_si", "sr": "sr_rs", "sv": "sv_se",
    "sw": "sw_ke", "ta": "ta_in", "te": "te_in", "tg": "tg_tj", "th": "th_th", "tr": "tr_tr",
    "uk": "uk_ua", "ur": "ur_pk", "uz": "uz_uz", "vi": "vi_vn", "xh": "xh_za", "yo": "yo_ng",
    "yue": "yue_hant_hk", "zh": "cmn_hans_cn", "zu": "zu_za",
}
CER = {"zh", "yue", "ja", "ko", "th", "km", "lo", "my"}

# The app's own constants: SherpaOnnxTranscriptionProvider.kt, SherpaOfflineRecognizerConfig.kt,
# SherpaOnnxOnlineTranscriptionProvider.kt and RuntimeSherpaOnnxProviderFactory.kt.
MAX_SEGMENT_SECONDS = 30
MOONSHINE_V2_MAX_SEGMENT_SECONDS = 8
QUIET_SEARCH_SECONDS = 3
QUIET_FRAMES_PER_SECOND = 20
ONLINE_TAIL_PADDING_MS = 800
ONLINE_FEED_MS = 100
FEATURE_DIM = {"nemo_transducer": 128, "zipformer_transducer": 80}
THREADS = 2


def entry(model_id: str) -> dict:
    models = yaml.safe_load((ROOT / "catalog/speech.yaml").read_text())["models"]
    return next(m for m in models if m["id"] == model_id)


def fetch_model(model: dict) -> Path:
    folder = CACHE / "models" / model["id"]
    folder.mkdir(parents=True, exist_ok=True)
    for file in model["files"]:
        path = folder / file["name"]
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.stat().st_size != file["sizeBytes"]:
            print(f"download {file['name']}", flush=True)
            urllib.request.urlretrieve(file["downloadUrl"], path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != file["sha256"]:
            raise SystemExit(f"{file['name']}: sha256 {digest} != catalogue {file['sha256']}")
    return folder


def offline(model: dict, d: Path, language: str) -> sherpa_onnx.OfflineRecognizer:
    kind = model["sherpaConfig"]["type"]
    if kind == "moonshine_v2":
        return sherpa_onnx.OfflineRecognizer.from_moonshine_v2(
            encoder=f"{d}/encoder_model.ort", decoder=f"{d}/decoder_model_merged.ort",
            tokens=f"{d}/tokens.txt", num_threads=THREADS)
    if kind == "moonshine":
        return sherpa_onnx.OfflineRecognizer.from_moonshine(
            preprocessor=f"{d}/preprocess.onnx", encoder=f"{d}/encode.int8.onnx",
            uncached_decoder=f"{d}/uncached_decode.int8.onnx", cached_decoder=f"{d}/cached_decode.int8.onnx",
            tokens=f"{d}/tokens.txt", num_threads=THREADS)
    if kind == "nemo_ctc":
        return sherpa_onnx.OfflineRecognizer.from_nemo_ctc(
            model=f"{d}/model.onnx", tokens=f"{d}/tokens.txt", num_threads=THREADS)
    if kind == "canary":
        # The app passes the person's chosen language as both source and target, so it transcribes.
        return sherpa_onnx.OfflineRecognizer.from_nemo_canary(
            encoder=f"{d}/encoder.int8.onnx", decoder=f"{d}/decoder.int8.onnx", tokens=f"{d}/tokens.txt",
            src_lang=language, tgt_lang=language, num_threads=THREADS)
    if kind == "qwen3_asr":
        return sherpa_onnx.OfflineRecognizer.from_qwen3_asr(
            conv_frontend=f"{d}/conv_frontend.onnx", encoder=f"{d}/encoder.int8.onnx",
            decoder=f"{d}/decoder.int8.onnx", tokenizer=f"{d}/tokenizer", num_threads=THREADS)
    if kind == "sense_voice":
        # The app leaves the language blank for detection and turns on inverse text normalisation.
        return sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=f"{d}/model.int8.onnx", tokens=f"{d}/tokens.txt", language="", use_itn=True,
            num_threads=THREADS)
    if kind == "whisper":
        # The app passes no language; an English-only export ignores it either way.
        return sherpa_onnx.OfflineRecognizer.from_whisper(
            encoder=f"{d}/encoder.int8.onnx", decoder=f"{d}/decoder.int8.onnx",
            tokens=f"{d}/tokens.txt", num_threads=THREADS)
    if kind == "omnilingual_ctc":
        return sherpa_onnx.OfflineRecognizer.from_omnilingual_asr_ctc(
            model=f"{d}/model.int8.onnx", tokens=f"{d}/tokens.txt", num_threads=THREADS)
    if kind == "nemo_transducer":
        return sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=f"{d}/encoder.int8.onnx", decoder=f"{d}/decoder.int8.onnx",
            joiner=f"{d}/joiner.int8.onnx", tokens=f"{d}/tokens.txt",
            model_type="nemo_transducer", num_threads=THREADS)
    raise SystemExit(f"{model['id']}: no offline setup for {kind} yet; add it from the app's config")


def online(model: dict, d: Path) -> sherpa_onnx.OnlineRecognizer:
    kind = model["sherpaConfig"]["type"]
    return sherpa_onnx.OnlineRecognizer.from_transducer(
        encoder=f"{d}/encoder.int8.onnx", decoder=f"{d}/decoder.int8.onnx",
        joiner=f"{d}/joiner.int8.onnx", tokens=f"{d}/tokens.txt",
        num_threads=THREADS, sample_rate=RATE, feature_dim=FEATURE_DIM[kind],
        enable_endpoint_detection=False,
        **({"model_type": "nemo_transducer"} if kind == "nemo_transducer" else {}))


def quietest_cut(audio: np.ndarray) -> int:
    frame = RATE // QUIET_FRAMES_PER_SECOND
    frames = min(RATE * QUIET_SEARCH_SECONDS, len(audio) // 2) // frame
    if frames == 0:
        return len(audio)
    start = len(audio) - frames * frame
    energy = [float(np.sum(audio[start + i * frame:start + (i + 1) * frame] ** 2)) for i in range(frames)]
    return start + int(np.argmin(energy)) * frame + frame // 2


def segments(audio: np.ndarray, ceiling_seconds: int) -> list[np.ndarray]:
    """SherpaOnnxTranscriptionProvider: seal at the ceiling, at the quietest point before it."""
    ceiling, out = RATE * ceiling_seconds, []
    while len(audio) > ceiling:
        cut = quietest_cut(audio[:ceiling])
        out.append(audio[:cut])
        audio = audio[cut:]
    return out + [audio]


def transcribe_offline(rec, model: dict, audio: np.ndarray) -> str:
    ceiling = (MOONSHINE_V2_MAX_SEGMENT_SECONDS if model["sherpaConfig"]["type"] == "moonshine_v2"
               else MAX_SEGMENT_SECONDS)
    texts = []
    for part in segments(audio, ceiling):
        stream = rec.create_stream()
        stream.accept_waveform(RATE, part)
        rec.decode_stream(stream)
        texts.append(stream.result.text.strip())
    return " ".join(t for t in texts if t)


def transcribe_online(rec, audio: np.ndarray) -> str:
    """SherpaOnnxOnlineTranscriptionProvider: live 100 ms feeds, 800 ms silence, input finished."""
    stream = rec.create_stream()
    step = RATE * ONLINE_FEED_MS // 1000
    for i in range(0, len(audio), step):
        stream.accept_waveform(RATE, audio[i:i + step])
        while rec.is_ready(stream):
            rec.decode_stream(stream)
    stream.accept_waveform(RATE, np.zeros(RATE * ONLINE_TAIL_PADDING_MS // 1000, dtype=np.float32))
    stream.input_finished()
    while rec.is_ready(stream):
        rec.decode_stream(stream)
    return rec.get_result(stream).strip()


def fleurs_test(language: str) -> list[tuple[str, np.ndarray, str]]:
    config = FLEURS[language]
    path = hf_hub_download("google/fleurs", f"{config}/test/0000.parquet", repo_type="dataset",
                           revision="refs/convert/parquet", cache_dir=CACHE / "hf")
    rows = []
    for row in pq.read_table(path, columns=["path", "audio", "transcription"]).to_pylist():
        audio, rate = sf.read(io.BytesIO(row["audio"]["bytes"]), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if rate != RATE:
            raise SystemExit(f"{language}: FLEURS clip at {rate} Hz")
        rows.append((Path(row["path"] or row["audio"]["path"]).stem, audio, row["transcription"]))
    Path(path).resolve().unlink()  # the blob, not just the cache's symlink to it
    Path(path).unlink()
    return rows


def score(language: str, refs: list[str], hyps: list[str]) -> tuple[float, int]:
    norm = EnglishTextNormalizer() if language == "en" else BasicTextNormalizer()
    pairs = [(norm(r), norm(h)) for r, h in zip(refs, hyps)]
    if language in CER:
        pairs = [("".join(r.split()), "".join(h.split())) for r, h in pairs]
    pairs = [(r, h) for r, h in pairs if r.strip()]
    r, h = zip(*pairs)
    rate = jiwer.cer(list(r), list(h)) if language in CER else jiwer.wer(list(r), list(h))
    return round(rate * 100, 2), len(pairs)


def main() -> None:
    model_id, languages = sys.argv[1], sys.argv[2:]
    model = entry(model_id)
    d = fetch_model(model)
    live = model["transcriptionMode"] == "CACHE_AWARE_ONLINE"
    out_path = RESULTS / f"{model_id}.json"
    RESULTS.mkdir(exist_ok=True)
    result = json.loads(out_path.read_text()) if out_path.exists() else {"model": model_id, "languages": {}}
    run = {
        "export": f"{model['provenance']['exportRepository']}@{model['provenance']['exportRevision']}",
        "mode": "streaming" if live else "offline",
        "sherpaOnnx": sherpa_onnx.__version__,
        "dataset": "google/fleurs test",
    }
    if any(result.get(k) != run[k] for k in ("export", "sherpaOnnx")):
        result["languages"] = {}  # numbers from another export or runtime are not this model's
    result.update(run)
    for language in languages:
        rows = fleurs_test(language)
        rec = online(model, d) if live else offline(model, d, language)
        started, audio_seconds, hyps = time.time(), 0.0, []
        for _, audio, _ in rows:
            audio_seconds += len(audio) / RATE
            hyps.append(transcribe_online(rec, audio) if live else transcribe_offline(rec, model, audio))
        error, clips = score(language, [r for _, _, r in rows], hyps)
        with open(CACHE / f"{model_id}.{language}.hyp.jsonl", "w") as f:  # for reading errors, not committed
            for (clip, audio, ref), hyp in zip(rows, hyps):
                f.write(json.dumps({"id": clip, "peak": float(np.abs(audio).max()), "ref": ref, "hyp": hyp}) + "\n")
        result["languages"][language] = {
            "metric": "cer" if language in CER else "wer", "errorPercent": error, "clips": clips,
            "audioSeconds": round(audio_seconds), "realTimeFactor": round(audio_seconds / (time.time() - started), 1),
            "measuredOn": time.strftime("%Y-%m-%d"),
        }
        print(model_id, language, result["languages"][language], flush=True)
        out_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
