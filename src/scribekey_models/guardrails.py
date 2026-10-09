from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scribekey_models.signing import verify_file

ROOT = Path(__file__).resolve().parents[2]
CATALOG_DIR = ROOT / "catalog"
RELEASES_DIR = CATALOG_DIR / "releases"
CHANNELS_FILE = CATALOG_DIR / "channels.yaml"
GENERATED_DIR = ROOT / "generated"

HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
MUTABLE_REFS = {"main", "master", "head", "latest", "trunk", "dev", "develop"}
BINARY_EXTENSIONS = {
    ".onnx",
    ".bin",
    ".safetensors",
    ".pt",
    ".pth",
    ".gguf",
    ".tflite",
    ".ckpt",
    ".tar.gz",
    ".zip",
    ".h5",
}
EXECUTABLE_PAYLOAD_EXTENSIONS = {
    ".apk",
    ".dex",
    ".so",
    ".jar",
    ".class",
    ".sh",
    ".bash",
    ".exe",
    ".elf",
    ".bat",
    ".cmd",
    ".ps1",
    ".dylib",
    ".dll",
}
KNOWN_RUNTIME_FAMILIES = {"sherpa-onnx", "gguf", "pyannote"}
KNOWN_CONFIG_FAMILIES = {
    "speech-model-catalog",
    "cleanup-model-catalog",
    "speaker-diarization-manifest",
}
PERMISSIVE_LICENSES = {
    "MIT",
    "Apache-2.0",
    "BSD-3-Clause",
    "BSD-2-Clause",
    "ISC",
    "CC0-1.0",
    "Unlicense",
}
MAX_TRACKED_FILE_BYTES = 2 * 1024 * 1024  # 2MB maximum for any metadata/tooling file
REQUIRED_RUNTIME_FILES: dict[str, tuple[str, ...]] = {
    "moonshine": (
        "preprocess.onnx",
        "encode.int8.onnx",
        "uncached_decode.int8.onnx",
        "cached_decode.int8.onnx",
        "tokens.txt",
    ),
    "moonshine_v2": (
        "encoder_model.ort",
        "decoder_model_merged.ort",
        "tokens.txt",
    ),
    "nemo_ctc": (
        "model.onnx",
        "tokens.txt",
    ),
    "nemo_transducer": (
        "encoder.int8.onnx",
        "decoder.int8.onnx",
        "joiner.int8.onnx",
        "tokens.txt",
    ),
    "whisper": (
        "encoder.int8.onnx",
        "decoder.int8.onnx",
        "tokens.txt",
    ),
    "canary": (
        "encoder.int8.onnx",
        "decoder.int8.onnx",
        "tokens.txt",
    ),
    "omnilingual_ctc": (
        "model.int8.onnx",
        "tokens.txt",
    ),
    # The app punctuates this model's text with sherpa-onnx's English punctuation model, so its
    # two files are part of the install (SherpaPunctuation.kt in the app).
    "zipformer_transducer": (
        "encoder.int8.onnx",
        "decoder.int8.onnx",
        "joiner.int8.onnx",
        "tokens.txt",
        "punct-model.int8.onnx",
        "punct-bpe.vocab",
    ),
    "qwen3_asr": (
        "conv_frontend.onnx",
        "encoder.int8.onnx",
        "decoder.int8.onnx",
        "tokenizer/merges.txt",
        "tokenizer/tokenizer_config.json",
        "tokenizer/vocab.json",
    ),
}
RUNTIME_TO_FAMILY: dict[str, str] = {
    "moonshine": "MOONSHINE",
    "moonshine_v2": "MOONSHINE",
    "nemo_ctc": "PARAKEET",
    "nemo_transducer": "PARAKEET",
    "whisper": "DISTIL_WHISPER",
    "canary": "CANARY",
    "omnilingual_ctc": "OMNILINGUAL",
    "qwen3_asr": "QWEN3_ASR",
    "zipformer_transducer": "ZIPFORMER",
}
# sherpa-onnx's English punctuation model, as published in k2-fsa's `punctuation-models` release
# (sherpa-onnx-online-punct-en-2024-08-06, Apache-2.0). Upstream ships it only as an archive, so a
# model may fetch these files from any host: the digest, not the URL, says they are those bytes.
PUNCTUATION_FILE_SHA256: dict[str, str] = {
    "punct-model.int8.onnx": "9d611f445fe4a46186080fe161be6059d87d72eb88d3a8cb00c1a06e83a6067e",
    "punct-bpe.vocab": "e118b7ad88c54db562517df49e1cffd4836d166c34fb190fd311d7f34eb238f5",
}
# Runtimes the app drives through sherpa-onnx's online recogniser.
STREAMING_RUNTIMES = frozenset({"nemo_transducer", "zipformer_transducer"})
STREAMING_ONLY_RUNTIMES = frozenset({"zipformer_transducer"})


@dataclass(frozen=True)
class GuardrailIssue:
    source: str
    message: str


def validate_download_url(source: str, url: str, model_id: str) -> list[GuardrailIssue]:
    issues: list[GuardrailIssue] = []
    if not url:
        return [GuardrailIssue(source, f"Model '{model_id}' has empty downloadUrl")]

    if not url.startswith("https://"):
        issues.append(
            GuardrailIssue(source, f"Model '{model_id}' download source must use HTTPS: {url}")
        )

    for ref in MUTABLE_REFS:
        if f"/resolve/{ref}/" in url or f"/{ref}/" in url:
            issues.append(
                GuardrailIssue(
                    source,
                    f"Model '{model_id}' URL uses mutable ref '{ref}': {url}",
                )
            )

    if "huggingface.co" in url and "/resolve/" in url:
        parts = url.split("/resolve/")[1].split("/")
        revision = parts[0]
        if not HEX40_RE.match(revision):
            issues.append(
                GuardrailIssue(
                    source,
                    f"Model '{model_id}' HuggingFace URL must use a 40-character commit hash, got '{revision}'",
                )
            )

    return issues


def validate_immutable_source_refs(
    speech_data: dict[str, Any],
    cleanup_data: dict[str, Any],
    diarization_data: dict[str, Any],
) -> list[GuardrailIssue]:
    issues: list[GuardrailIssue] = []

    # Check speech models
    for model in speech_data.get("models", []):
        model_id = model.get("id", "unknown")
        for f in model.get("files", []):
            urls = [f.get("downloadUrl", ""), *f.get("downloadUrls", [])]
            for url in urls:
                issues.extend(validate_download_url("catalog/speech.yaml", url, model_id))
        for build in model.get("npuBuilds", []):
            issues.extend(validate_download_url("catalog/speech.yaml", build.get("downloadUrl", ""), model_id))

    # Check cleanup models
    prod = cleanup_data.get("production")
    if prod:
        model_id = prod.get("modelId", "production")
        rev = prod.get("revision", "")
        if rev.lower() in MUTABLE_REFS:
            issues.append(
                GuardrailIssue("catalog/cleanup.yaml", f"Cleanup model '{model_id}' revision cannot be mutable ref '{rev}'")
            )
        urls = [prod.get("downloadUrl", ""), *prod.get("downloadUrls", [])]
        for url in urls:
            issues.extend(validate_download_url("catalog/cleanup.yaml", url, model_id))

    for cand in cleanup_data.get("candidates", []):
        model_id = cand.get("modelId", "candidate")
        rev = cand.get("revision", "")
        if rev.lower() in MUTABLE_REFS:
            issues.append(
                GuardrailIssue("catalog/cleanup.yaml", f"Cleanup candidate '{model_id}' revision cannot be mutable ref '{rev}'")
            )
        urls = [cand.get("downloadUrl", ""), *cand.get("downloadUrls", [])]
        for url in urls:
            issues.extend(validate_download_url("catalog/cleanup.yaml", url, model_id))

    # Check diarization models
    for model in diarization_data.get("models", []):
        role = model.get("role", "unknown")
        rev = model.get("sourceRevision", "")
        if rev.lower() in MUTABLE_REFS:
            issues.append(
                GuardrailIssue("catalog/diarization.yaml", f"Diarization model '{role}' sourceRevision cannot be mutable ref '{rev}'")
            )
        urls = [model.get("downloadUrl", ""), *model.get("downloadUrls", [])]
        for url in urls:
            issues.extend(validate_download_url("catalog/diarization.yaml", url, role))

    return issues


def validate_identities_and_integrity(
    speech_data: dict[str, Any],
    cleanup_data: dict[str, Any],
    diarization_data: dict[str, Any],
) -> list[GuardrailIssue]:
    issues: list[GuardrailIssue] = []

    # Speech IDs and digests
    seen_speech_ids: set[str] = set()
    all_speech_ids: set[str] = set()
    for model in speech_data.get("models", []):
        m_id = model.get("id")
        if not m_id:
            issues.append(GuardrailIssue("catalog/speech.yaml", "Speech model missing id"))
            continue
        if m_id in seen_speech_ids:
            issues.append(GuardrailIssue("catalog/speech.yaml", f"Duplicate speech model id: '{m_id}'"))
        seen_speech_ids.add(m_id)
        all_speech_ids.add(m_id)

        for f in model.get("files", []):
            sha = f.get("sha256", "")
            if not HEX64_RE.match(sha):
                issues.append(GuardrailIssue("catalog/speech.yaml", f"Model '{m_id}' invalid sha256: '{sha}'"))
            size = f.get("sizeBytes")
            if not isinstance(size, int) or size <= 0:
                issues.append(GuardrailIssue("catalog/speech.yaml", f"Model '{m_id}' invalid sizeBytes: '{size}'"))

    for model in speech_data.get("models", []):
        repl = model.get("replacementId")
        if repl and repl not in all_speech_ids:
            issues.append(GuardrailIssue("catalog/speech.yaml", f"Model '{model.get('id')}' replacementId '{repl}' not found in catalogue"))

    issues.extend(_validate_speech_presentation(speech_data.get("models", [])))

    # Diarization digests
    for model in diarization_data.get("models", []):
        role = model.get("role", "unknown")
        sha = model.get("sha256", "")
        if not HEX64_RE.match(sha):
            issues.append(GuardrailIssue("catalog/diarization.yaml", f"Diarization model '{role}' invalid sha256: '{sha}'"))
        size = model.get("sizeBytes")
        if not isinstance(size, int) or size <= 0:
            issues.append(GuardrailIssue("catalog/diarization.yaml", f"Diarization model '{role}' invalid sizeBytes: '{size}'"))

    # Cleanup digests
    all_cleanup = []
    if cleanup_data.get("production"):
        all_cleanup.append(cleanup_data["production"])
    all_cleanup.extend(cleanup_data.get("candidates", []))

    for model in all_cleanup:
        m_id = model.get("modelId", "unknown")
        sha = model.get("sha256", "")
        if not HEX64_RE.match(sha):
            issues.append(GuardrailIssue("catalog/cleanup.yaml", f"Cleanup model '{m_id}' invalid sha256: '{sha}'"))
        size = model.get("sizeBytes")
        if not isinstance(size, int) or size <= 0:
            issues.append(GuardrailIssue("catalog/cleanup.yaml", f"Cleanup model '{m_id}' invalid sizeBytes: '{size}'"))
        issues.extend(_validate_cleanup_examples(model))

    return issues


def _validate_cleanup_examples(model: dict[str, Any]) -> list[GuardrailIssue]:
    """Recorded examples are shown in the app as what this model does, so they must be reproducible.

    That holds only for deterministic decoding and only for the revision they were recorded with.
    A revision bump that keeps the old examples would show output the new model never produced.
    """
    examples = model.get("examples") or []
    if not examples:
        return []
    m_id = model.get("modelId", "unknown")
    issues: list[GuardrailIssue] = []
    if not model.get("deterministicDecoding", True) or float(model.get("temperature", 0.0)) != 0.0:
        issues.append(
            GuardrailIssue("catalog/cleanup.yaml", f"Cleanup model '{m_id}' has examples but samples its output")
        )
    seen_inputs: set[str] = set()
    for example in examples:
        recorded = example.get("recordedWith") or {}
        if recorded.get("modelRevision") != model.get("revision"):
            issues.append(
                GuardrailIssue(
                    "catalog/cleanup.yaml",
                    f"Cleanup model '{m_id}' example was recorded with revision "
                    f"'{recorded.get('modelRevision')}', not '{model.get('revision')}'; re-record it",
                )
            )
        text = str(example.get("input", "")).strip()
        if text in seen_inputs:
            issues.append(GuardrailIssue("catalog/cleanup.yaml", f"Cleanup model '{m_id}' repeats example '{text}'"))
        seen_inputs.add(text)
        if len(text) > int(model.get("maxInputCharacters", 0) or 0):
            issues.append(
                GuardrailIssue("catalog/cleanup.yaml", f"Cleanup model '{m_id}' example exceeds maxInputCharacters")
            )
    return issues


def _validate_speech_presentation(models: list[dict[str, Any]]) -> list[GuardrailIssue]:
    """Checks the facts Android shows side by side, where a clash reads as one model twice.

    A legacy entry that shares its replacement's display name makes Settings say "Moonshine Base"
    for two different downloads, so names are unique. The card shows ``bestFor`` under the name
    and the info sheet shows ``description`` beneath it; the same sentence twice is noise.
    A counterpart is the same job in the other mode (live versus final), so the pairing must be
    mutual and must cross modes, or the app would offer a "live version" that is not live.
    """
    issues: list[GuardrailIssue] = []
    by_id = {m.get("id"): m for m in models if m.get("id")}
    seen_names: dict[str, str] = {}
    for model in models:
        mid = model.get("id", "unknown")
        name = str(model.get("displayName", "")).strip().casefold()
        if name and name in seen_names:
            issues.append(
                GuardrailIssue(
                    "catalog/speech.yaml",
                    f"Speech model '{mid}' reuses display name of '{seen_names[name]}'",
                )
            )
        elif name:
            seen_names[name] = mid

        # The badge is copy and ``experimental`` is the gate; Android hides on the flag alone, so
        # a card that says "Experimental" must be one the gate actually hides, and vice versa.
        experimental = bool(model.get("experimental"))
        if (str(model.get("badge", "")).strip().casefold() == "experimental") != experimental:
            issues.append(
                GuardrailIssue(
                    "catalog/speech.yaml",
                    f"Speech model '{mid}' badge and experimental flag disagree",
                )
            )
        if experimental and (model.get("retired") or model.get("deprecated")):
            issues.append(
                GuardrailIssue(
                    "catalog/speech.yaml",
                    f"Speech model '{mid}' is experimental and also retired or deprecated",
                )
            )

        best_for = str(model.get("bestFor", "")).strip().casefold()
        description = str(model.get("description", "")).strip().casefold()
        if best_for and best_for == description:
            issues.append(
                GuardrailIssue("catalog/speech.yaml", f"Speech model '{mid}' repeats description as bestFor")
            )

        counterpart_id = model.get("counterpartId")
        if not counterpart_id:
            continue
        counterpart = by_id.get(counterpart_id)
        if counterpart is None:
            issues.append(
                GuardrailIssue(
                    "catalog/speech.yaml",
                    f"Speech model '{mid}' counterpartId '{counterpart_id}' not found in catalogue",
                )
            )
            continue
        if counterpart.get("counterpartId") != mid:
            issues.append(
                GuardrailIssue(
                    "catalog/speech.yaml",
                    f"Speech model '{mid}' counterpart '{counterpart_id}' does not point back",
                )
            )
        if counterpart.get("transcriptionMode", "SEGMENTED") == model.get("transcriptionMode", "SEGMENTED"):
            issues.append(
                GuardrailIssue(
                    "catalog/speech.yaml",
                    f"Speech model '{mid}' counterpart '{counterpart_id}' uses the same transcription mode",
                )
            )
        if counterpart.get("retired") or counterpart.get("deprecated"):
            issues.append(
                GuardrailIssue(
                    "catalog/speech.yaml",
                    f"Speech model '{mid}' counterpart '{counterpart_id}' is retired or deprecated",
                )
            )
    return issues


def _validate_cleanup_presentation(models: list[dict[str, Any]]) -> list[GuardrailIssue]:
    """The same presentation rules as speech: unique names, distinct guidance, real replacements."""
    issues: list[GuardrailIssue] = []
    ids = {m.get("modelId") for m in models}
    seen_names: dict[str, str] = {}
    for model in models:
        mid = model.get("modelId", "unknown")
        name = str(model.get("displayName", "")).strip().casefold()
        if name and name in seen_names:
            issues.append(
                GuardrailIssue(
                    "catalog/cleanup.yaml",
                    f"Cleanup model '{mid}' reuses display name of '{seen_names[name]}'",
                )
            )
        elif name:
            seen_names[name] = mid
        best_for = str(model.get("bestFor", "")).strip().casefold()
        if best_for and best_for == str(model.get("description", "")).strip().casefold():
            issues.append(
                GuardrailIssue("catalog/cleanup.yaml", f"Cleanup model '{mid}' repeats description as bestFor")
            )
        replacement = model.get("replacementId")
        if replacement and replacement not in ids:
            issues.append(
                GuardrailIssue(
                    "catalog/cleanup.yaml",
                    f"Cleanup model '{mid}' replacementId '{replacement}' not found in catalogue",
                )
            )
    return issues


def validate_no_executable_payloads(
    speech_data: dict[str, Any],
    cleanup_data: dict[str, Any],
    diarization_data: dict[str, Any],
    releases_data: dict[str, dict[str, Any]] | None = None,
) -> list[GuardrailIssue]:
    """Ensure no model payload is an executable binary or script rejected by Android."""
    issues: list[GuardrailIssue] = []

    def _check(source: str, filename: str, entity_id: str) -> None:
        ext = Path(filename).suffix.lower()
        if ext in EXECUTABLE_PAYLOAD_EXTENSIONS:
            issues.append(
                GuardrailIssue(
                    source,
                    f"Entity '{entity_id}' references executable payload '{filename}' ({ext}) "
                    f"which is rejected by Android runtime guardrails",
                )
            )

    for model in speech_data.get("models", []):
        m_id = model.get("id", "unknown")
        for f in model.get("files", []):
            _check("catalog/speech.yaml", f.get("name", ""), m_id)

    prod = cleanup_data.get("production")
    if prod:
        m_id = prod.get("modelId", "production")
        url = prod.get("downloadUrl", "")
        if url:
            _check("catalog/cleanup.yaml", Path(url).name, m_id)

    for cand in cleanup_data.get("candidates", []):
        m_id = cand.get("modelId", "candidate")
        url = cand.get("downloadUrl", "")
        if url:
            _check("catalog/cleanup.yaml", Path(url).name, m_id)

    for model in diarization_data.get("models", []):
        role = model.get("role", "unknown")
        url = model.get("downloadUrl", "")
        if url:
            _check("catalog/diarization.yaml", Path(url).name, role)

    if releases_data:
        for rel_id, rel_data in releases_data.items():
            recovery = rel_data.get("recoveryAssets", {})
            for model in recovery.get("clearedModels", []):
                m_id = model.get("modelId", "unknown")
                for f in model.get("files", []):
                    _check(f"catalog/releases/{rel_id}.yaml", f.get("name", ""), m_id)

    return issues


def validate_release_safety(root: Path = ROOT) -> list[GuardrailIssue]:
    issues: list[GuardrailIssue] = []

    # Excluded directories
    excluded_dirs = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache", "fixtures"}

    for path in root.rglob("*"):
        if any(part in excluded_dirs for part in path.parts):
            continue
        if not path.is_file():
            continue

        # Check binary extensions
        if path.suffix.lower() in BINARY_EXTENSIONS:
            issues.append(GuardrailIssue(str(path.relative_to(root)), f"Forbidden model binary file tracked in repo: {path.name}"))

        # Check file size limit
        try:
            stat = path.stat()
            if stat.st_size > MAX_TRACKED_FILE_BYTES:
                issues.append(GuardrailIssue(str(path.relative_to(root)), f"File exceeds maximum allowed size ({stat.st_size} > {MAX_TRACKED_FILE_BYTES} bytes)"))
        except OSError:
            pass

        # Check for accidentally committed secrets or tokens (only in non-code text/config files)
        if path.suffix in {".yaml", ".yml", ".json", ".md", ".txt", ".toml", ".env", ".key"}:
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                pem_markers = [
                    "-----" + "BEGIN " + "PRIVATE KEY-----",
                    "-----" + "BEGIN " + "OPENSSH PRIVATE KEY-----",
                    "-----" + "BEGIN " + "EC PRIVATE KEY-----",
                    "-----" + "BEGIN " + "RSA PRIVATE KEY-----",
                ]
                if any(marker in content for marker in pem_markers):
                    issues.append(GuardrailIssue(str(path.relative_to(root)), "Private signing key found in file! Private keys must only live in CI secrets."))
                # Detect HuggingFace user tokens: hf_ followed by 34 alphanumeric chars
                if re.search(r"\bhf_[A-Za-z0-9]{34}\b", content):
                    issues.append(GuardrailIssue(str(path.relative_to(root)), "Potential Hugging Face authentication token found! Tokens must not be committed."))
                # Detect GitHub PATs: ghp_ followed by 36 alphanumeric chars
                if re.search(r"\bghp_[A-Za-z0-9]{36}\b", content):
                    issues.append(GuardrailIssue(str(path.relative_to(root)), "Potential GitHub Personal Access Token found! Tokens must not be committed."))
            except (OSError, UnicodeDecodeError):
                continue

    return issues


def validate_redistribution_clearance(release_data: dict[str, Any]) -> list[GuardrailIssue]:
    issues: list[GuardrailIssue] = []
    recovery = release_data.get("recoveryAssets")
    if not recovery:
        return issues

    for item in recovery.get("clearedModels", []):
        model_id = item.get("modelId", "unknown")
        if not item.get("cleared"):
            issues.append(GuardrailIssue("recoveryAssets", f"Model '{model_id}' is listed in recoveryAssets but cleared is false"))
        lic = item.get("licenseId", "")
        if lic not in PERMISSIVE_LICENSES:
            issues.append(
                GuardrailIssue(
                    "recoveryAssets",
                    f"Model '{model_id}' license '{lic}' is not in redistribution-cleared permissive licenses ({', '.join(sorted(PERMISSIVE_LICENSES))})",
                )
            )

        for f in item.get("files", []):
            fname = f.get("name", "")
            sha = f.get("sha256", "")
            if not HEX64_RE.match(sha):
                issues.append(GuardrailIssue("recoveryAssets", f"Model '{model_id}' file '{fname}' invalid sha256: '{sha}'"))
            url = f.get("upstreamUrl", "")
            issues.extend(validate_download_url("recoveryAssets", url, f"{model_id}:{fname}"))

    return issues


def validate_release_snapshot_integrity(
    release_id: str,
    release_data: dict[str, Any],
    generated_dir: Path = GENERATED_DIR,
) -> list[GuardrailIssue]:
    issues: list[GuardrailIssue] = []
    release_dir = generated_dir / "releases" / release_id
    for catalog_name, declared in release_data.get("catalogs", {}).items():
        filename = declared.get("filename")
        if not filename:
            issues.append(GuardrailIssue(catalog_name, "Release catalogue is missing filename"))
            continue
        snapshot = release_dir / str(filename)
        if not snapshot.is_file():
            issues.append(
                GuardrailIssue(catalog_name, f"Immutable release snapshot is missing: {snapshot}")
            )
            continue
        content = snapshot.read_bytes()
        actual_sha256 = hashlib.sha256(content).hexdigest()
        actual_size = len(content)
        if actual_sha256 != declared.get("sha256"):
            issues.append(
                GuardrailIssue(
                    catalog_name,
                    f"Immutable release snapshot digest changed for {filename}",
                )
            )
        if actual_size != declared.get("sizeBytes"):
            issues.append(
                GuardrailIssue(
                    catalog_name,
                    f"Immutable release snapshot size changed for {filename}",
                )
            )
    return issues


def validate_channel_and_release_pointers(
    channels_data: dict[str, Any],
    releases_dir: Path = RELEASES_DIR,
    generated_dir: Path = GENERATED_DIR,
) -> list[GuardrailIssue]:
    issues: list[GuardrailIssue] = []

    channels = channels_data.get("channels", {})
    for chan_name in ["qa", "stable"]:
        chan = channels.get(chan_name)
        if not chan:
            issues.append(GuardrailIssue("catalog/channels.yaml", f"Missing channel pointer for '{chan_name}'"))
            continue
        rel_id = chan.get("targetRelease")
        if not rel_id:
            issues.append(GuardrailIssue("catalog/channels.yaml", f"Channel '{chan_name}' missing targetRelease"))
            continue

        rel_file = releases_dir / f"{rel_id}.yaml"
        if not rel_file.exists():
            issues.append(
                GuardrailIssue(
                    "catalog/channels.yaml",
                    f"Channel '{chan_name}' points to non-existent release definition: {rel_file}",
                )
            )

        seq = chan.get("sequence")
        if seq is None or not isinstance(seq, int) or seq < 1:
            issues.append(
                GuardrailIssue(
                    "catalog/channels.yaml",
                    f"Channel '{chan_name}' has invalid anti-rollback sequence '{seq}' (must be integer >= 1)",
                )
            )

        issued_at = chan.get("issuedAt")
        if not issued_at:
            issues.append(
                GuardrailIssue(
                    "catalog/channels.yaml",
                    f"Channel '{chan_name}' missing required 'issuedAt' timestamp",
                )
            )

        comp = chan.get("compatibility")
        if not comp or not isinstance(comp, dict):
            issues.append(
                GuardrailIssue(
                    "catalog/channels.yaml",
                    f"Channel '{chan_name}' missing required 'compatibility' metadata",
                )
            )
        else:
            api_level = comp.get("minAndroidApiLevel")
            if not isinstance(api_level, int) or api_level < 21:
                issues.append(
                    GuardrailIssue(
                        "catalog/channels.yaml",
                        f"Channel '{chan_name}' compatibility.minAndroidApiLevel must be integer >= 21, got '{api_level}'",
                    )
                )

            app_version = comp.get("minAppVersionCode")
            if not isinstance(app_version, int) or app_version < 1:
                issues.append(
                    GuardrailIssue(
                        "catalog/channels.yaml",
                        f"Channel '{chan_name}' compatibility.minAppVersionCode must be integer >= 1, got '{app_version}'",
                    )
                )

            schema_ver = comp.get("catalogsSchemaVersion")
            if not isinstance(schema_ver, int) or schema_ver < 1:
                issues.append(
                    GuardrailIssue(
                        "catalog/channels.yaml",
                        f"Channel '{chan_name}' compatibility.catalogsSchemaVersion must be integer >= 1, got '{schema_ver}'",
                    )
                )

            families = comp.get("supportedRuntimeFamilies")
            if not isinstance(families, list) or not families:
                issues.append(
                    GuardrailIssue(
                        "catalog/channels.yaml",
                        f"Channel '{chan_name}' compatibility.supportedRuntimeFamilies must be non-empty list",
                    )
                )
            else:
                unknown = set(families) - KNOWN_RUNTIME_FAMILIES
                if unknown:
                    issues.append(
                        GuardrailIssue(
                            "catalog/channels.yaml",
                            f"Channel '{chan_name}' contains unknown runtime families: {unknown} "
                            f"(known: {KNOWN_RUNTIME_FAMILIES})",
                        )
                    )

            configs = comp.get("supportedConfigFamilies")
            if not isinstance(configs, list) or not configs:
                issues.append(
                    GuardrailIssue(
                        "catalog/channels.yaml",
                        f"Channel '{chan_name}' compatibility.supportedConfigFamilies must be non-empty list",
                    )
                )
            else:
                unknown_cfg = set(configs) - KNOWN_CONFIG_FAMILIES
                if unknown_cfg:
                    issues.append(
                        GuardrailIssue(
                            "catalog/channels.yaml",
                            f"Channel '{chan_name}' contains unknown config families: {unknown_cfg} "
                            f"(known: {KNOWN_CONFIG_FAMILIES})",
                        )
                    )

    return issues


def validate_signatures(
    generated_dir: Path = GENERATED_DIR,
    public_key_path: Path = ROOT / "keys" / "release-signing.pub",
) -> list[GuardrailIssue]:
    issues: list[GuardrailIssue] = []
    if not public_key_path.exists():
        issues.append(GuardrailIssue("keys/release-signing.pub", "Public key file not found"))
        return issues

    # Validate signatures on channels and releases
    for sig_file in generated_dir.rglob("*.sig"):
        target_name = sig_file.name[:-4] if sig_file.name.endswith(".sig") else sig_file.stem
        target_file = sig_file.with_name(target_name)
        if not target_file.exists():
            issues.append(GuardrailIssue(str(sig_file.relative_to(ROOT)), f"Orphaned signature file without target: {target_file.name}"))
            continue

        ok, msg = verify_file(target_file, sig_file, public_key=public_key_path)
        if not ok:
            issues.append(GuardrailIssue(str(sig_file.relative_to(ROOT)), f"Signature verification failed for {target_file.name}: {msg}"))

    return issues


def _is_safe_relative_path(path: str) -> bool:
    if not path or "\0" in path or "\\" in path or path.startswith(("/", "./")):
        return False
    parts = path.split("/")
    for part in parts:
        if part in ("", ".", ".."):
            return False
    return True


def _is_safe_filename(name: str) -> bool:
    if not name or "\0" in name or "/" in name or "\\" in name:
        return False
    return name not in (".", "..")


# NPU builds are context binaries compiled for one Snapdragon chip by sherpa-onnx's own release job.
# Only an offline Parakeet TDT runs on the NPU through the app's sherpa-onnx bindings.
NPU_RELEASE_URL_RE = re.compile(
    r"^https://github\.com/k2-fsa/sherpa-onnx/releases/download/asr-models-qnn-binary-[0-9]+/([^/]+)$"
)
NPU_RUNTIMES = frozenset({"nemo_transducer"})


def _validate_npu_builds(model: dict[str, Any]) -> list[GuardrailIssue]:
    builds = model.get("npuBuilds") or []
    if not builds:
        return []
    mid = model.get("id", "unknown")
    issues: list[GuardrailIssue] = []
    runtime = model.get("sherpaConfig", {}).get("type")
    if runtime not in NPU_RUNTIMES or model.get("transcriptionMode", "SEGMENTED") != "SEGMENTED":
        issues.append(
            GuardrailIssue(
                "catalog/speech.yaml",
                f"Speech model '{mid}' lists NPU builds but only segmented {sorted(NPU_RUNTIMES)} models run on the NPU",
            )
        )
    seen_socs: set[str] = set()
    for build in builds:
        soc = build.get("soc", "")
        if soc in seen_socs:
            issues.append(GuardrailIssue("catalog/speech.yaml", f"Speech model '{mid}' lists NPU build {soc} twice"))
        seen_socs.add(soc)
        match = NPU_RELEASE_URL_RE.match(build.get("downloadUrl", ""))
        if not match:
            issues.append(
                GuardrailIssue(
                    "catalog/speech.yaml",
                    f"Speech model '{mid}' NPU build {soc} must come from a sherpa-onnx asr-models-qnn-binary release",
                )
            )
        elif match.group(1) != f"{build.get('archiveRoot')}.tar.bz2":
            issues.append(
                GuardrailIssue(
                    "catalog/speech.yaml",
                    f"Speech model '{mid}' NPU build {soc} archive name does not match its archiveRoot",
                )
            )
        elif f"-{soc}-" not in match.group(1):
            issues.append(
                GuardrailIssue(
                    "catalog/speech.yaml",
                    f"Speech model '{mid}' NPU build {soc} points at an archive for another chip",
                )
            )
        if not HEX64_RE.match(build.get("sha256", "")):
            issues.append(
                GuardrailIssue("catalog/speech.yaml", f"Speech model '{mid}' NPU build {soc} needs a sha256")
            )
    return issues


def validate_model_configuration(
    speech_data: dict[str, Any],
    cleanup_data: dict[str, Any],
    diarization_data: dict[str, Any],
) -> list[GuardrailIssue]:
    issues: list[GuardrailIssue] = []

    for model in speech_data.get("models", []):
        issues.extend(_validate_npu_builds(model))

    # 1. Speech model configuration
    for model in speech_data.get("models", []):
        mid = model.get("id", "unknown")
        runtime = model.get("sherpaConfig", {}).get("type")
        family = model.get("family")
        files = model.get("files", [])

        # Runtime layout required files
        if runtime in REQUIRED_RUNTIME_FILES:
            file_names = {f.get("name") for f in files if "name" in f}
            missing = [req for req in REQUIRED_RUNTIME_FILES[runtime] if req not in file_names]
            if missing:
                issues.append(
                    GuardrailIssue(
                        "catalog/speech.yaml",
                        f"Speech model '{mid}' with runtime '{runtime}' is missing required files: {', '.join(missing)}",
                    )
                )

        # Family alignment
        if runtime in RUNTIME_TO_FAMILY and family != RUNTIME_TO_FAMILY[runtime]:
            issues.append(
                GuardrailIssue(
                    "catalog/speech.yaml",
                    f"Speech model '{mid}' family '{family}' does not match expected family '{RUNTIME_TO_FAMILY[runtime]}' for runtime '{runtime}'",
                )
            )

        # CACHE_AWARE_ONLINE support
        if model.get("transcriptionMode") != "CACHE_AWARE_ONLINE" and runtime in STREAMING_ONLY_RUNTIMES:
            issues.append(
                GuardrailIssue(
                    "catalog/speech.yaml",
                    f"Speech model '{mid}' with runtime '{runtime}' must use transcriptionMode CACHE_AWARE_ONLINE",
                )
            )
        if model.get("transcriptionMode") == "CACHE_AWARE_ONLINE" and runtime not in STREAMING_RUNTIMES:
            issues.append(
                GuardrailIssue(
                    "catalog/speech.yaml",
                    f"Speech model '{mid}' has transcriptionMode CACHE_AWARE_ONLINE which is not supported for runtime '{runtime}'",
                )
            )

        # Total size rounding up to diskMb
        if "diskMb" in model:
            total_bytes = sum(f.get("sizeBytes", 0) for f in files)
            expected_disk_mb = math.ceil(total_bytes / (1024 * 1024))
            if model["diskMb"] != expected_disk_mb:
                issues.append(
                    GuardrailIssue(
                        "catalog/speech.yaml",
                        f"Speech model '{mid}' diskMb {model['diskMb']} does not match expected {expected_disk_mb} MB (totalBytes={total_bytes})",
                    )
                )

        # File path safety and duplicate checks
        seen_names = set()
        for f in files:
            name = f.get("name", "")
            if not _is_safe_relative_path(name):
                issues.append(
                    GuardrailIssue(
                        "catalog/speech.yaml",
                        f"Speech model '{mid}' has unsafe install path '{name}'",
                    )
                )
            if name in seen_names:
                issues.append(
                    GuardrailIssue(
                        "catalog/speech.yaml",
                        f"Speech model '{mid}': Duplicate install path '{name}'",
                    )
                )
            seen_names.add(name)

        for f in files:
            expected = PUNCTUATION_FILE_SHA256.get(f.get("name", ""))
            if expected and f.get("sha256") != expected:
                issues.append(
                    GuardrailIssue(
                        "catalog/speech.yaml",
                        f"Speech model '{mid}' file '{f.get('name')}' is not k2-fsa's English punctuation model",
                    )
                )

        # Provenance matching Hugging Face artifacts
        provenance = model.get("provenance")
        if isinstance(provenance, dict):
            export_repo = provenance.get("exportRepository")
            export_rev = provenance.get("exportRevision")
            for f in files:
                url = f.get("downloadUrl", "")
                if f.get("name") in PUNCTUATION_FILE_SHA256:
                    continue
                hf_match = re.match(r"^https://huggingface\.co/([^/]+/[^/]+)/resolve/([^/]+)/", url)
                if hf_match:
                    url_repo, url_rev = hf_match.group(1), hf_match.group(2)
                    if (export_repo and url_repo != export_repo) or (export_rev and url_rev != export_rev):
                        issues.append(
                            GuardrailIssue(
                                "catalog/speech.yaml",
                                f"Speech model '{mid}' file '{f.get('name')}' download URL does not match Hugging Face provenance ({url_repo}@{url_rev} vs {export_repo}@{export_rev})",
                            )
                        )

    # 2. Cleanup model configuration
    cleanup_models: list[dict[str, Any]] = []
    prod_cleanup = cleanup_data.get("production")
    if isinstance(prod_cleanup, dict):
        cleanup_models.append(prod_cleanup)
    for cand in cleanup_data.get("candidates", []):
        if isinstance(cand, dict):
            cleanup_models.append(cand)

    issues.extend(_validate_cleanup_presentation(cleanup_models))

    seen_cleanup_ids = set()
    for cm in cleanup_models:
        cm_id = cm.get("modelId", "unknown")
        if cm_id in seen_cleanup_ids:
            issues.append(
                GuardrailIssue(
                    "catalog/cleanup.yaml",
                    f"Duplicate cleanup model id '{cm_id}'",
                )
            )
        seen_cleanup_ids.add(cm_id)

        bundle_file = cm.get("bundleFileName", "")
        if not _is_safe_filename(bundle_file):
            issues.append(
                GuardrailIssue(
                    "catalog/cleanup.yaml",
                    f"Cleanup model '{cm_id}' has unsafe install path '{bundle_file}'",
                )
            )

        rev = cm.get("revision")
        url = cm.get("downloadUrl", "")
        hf_match = re.match(r"^https://huggingface\.co/([^/]+/[^/]+)/resolve/([^/]+)/", url)
        if hf_match and rev:
            url_rev = hf_match.group(2)
            if url_rev != rev:
                issues.append(
                    GuardrailIssue(
                        "catalog/cleanup.yaml",
                        f"Cleanup model '{cm_id}' download URL does not match Hugging Face revision ({url_rev} vs {rev})",
                    )
                )

        provenance = cm.get("provenance")
        if hf_match and isinstance(provenance, dict):
            url_repo, url_rev = hf_match.group(1), hf_match.group(2)
            export_repo = provenance.get("exportRepository")
            export_rev = provenance.get("exportRevision")
            if url_repo != export_repo or url_rev != export_rev:
                issues.append(
                    GuardrailIssue(
                        "catalog/cleanup.yaml",
                        f"Cleanup model '{cm_id}' download URL does not match Hugging Face provenance ({url_repo}@{url_rev} vs {export_repo}@{export_rev})",
                    )
                )

        ctx_tokens = cm.get("contextTokens")
        max_out_tokens = cm.get("maxOutputTokens")
        if ctx_tokens is not None and max_out_tokens is not None and ctx_tokens <= max_out_tokens:
            issues.append(
                GuardrailIssue(
                    "catalog/cleanup.yaml",
                    f"Cleanup model '{cm_id}': contextTokens must exceed maxOutputTokens ({ctx_tokens} <= {max_out_tokens})",
                )
            )

        if cm.get("deterministicDecoding") is True:
            top_k = cm.get("topK")
            top_p = cm.get("topP")
            temp = cm.get("temperature")
            rep_pen = cm.get("repetitionPenalty")
            if top_k != 1 or top_p != 1.0 or temp != 0.0 or rep_pen is not None:
                issues.append(
                    GuardrailIssue(
                        "catalog/cleanup.yaml",
                        f"Cleanup model '{cm_id}': deterministicDecoding requires topK=1, topP=1.0, temperature=0.0, repetitionPenalty=None",
                    )
                )

    # 3. Diarization configuration
    diarization_models = diarization_data.get("models", [])
    roles = [m.get("role") for m in diarization_models]
    seg_count = roles.count("SEGMENTATION")
    emb_count = roles.count("EMBEDDING")
    if seg_count != 1:
        issues.append(
            GuardrailIssue(
                "catalog/diarization.yaml",
                f"Diarization catalog must have exactly one SEGMENTATION model, found {seg_count}",
            )
        )
    if emb_count != 1:
        issues.append(
            GuardrailIssue(
                "catalog/diarization.yaml",
                f"Diarization catalog must have exactly one EMBEDDING model, found {emb_count}",
            )
        )

    for dm in diarization_models:
        file_name = dm.get("fileName", "")
        if not _is_safe_filename(file_name):
            issues.append(
                GuardrailIssue(
                    "catalog/diarization.yaml",
                    f"Diarization model has unsafe install path '{file_name}'",
                )
            )

        src_repo = dm.get("sourceRepository")
        src_rev = dm.get("sourceRevision")
        url = dm.get("downloadUrl", "")
        hf_match = re.match(r"^https://huggingface\.co/([^/]+/[^/]+)/resolve/([^/]+)/", url)
        if hf_match:
            url_repo, url_rev = hf_match.group(1), hf_match.group(2)
            if (src_repo and url_repo != src_repo) or (src_rev and url_rev != src_rev):
                issues.append(
                    GuardrailIssue(
                        "catalog/diarization.yaml",
                        f"Diarization model download URL does not match Hugging Face source identity ({url_repo}@{url_rev} vs {src_repo}@{src_rev})",
                    )
                )

    return issues

