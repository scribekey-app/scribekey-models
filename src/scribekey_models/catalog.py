from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError
from referencing import Registry, Resource

from scribekey_models.guardrails import (
    validate_channel_and_release_pointers,
    validate_identities_and_integrity,
    validate_immutable_source_refs,
    validate_model_configuration,
    validate_no_executable_payloads,
    validate_notes_catalog,
    validate_redistribution_clearance,
    validate_release_safety,
    validate_release_snapshot_integrity,
    validate_search_catalog,
    validate_signatures,
    validate_speech_accuracy,
)
from scribekey_models.promotion import build_channel_distribution_manifest

ROOT = Path(__file__).resolve().parents[2]
CATALOG_DIR = ROOT / "catalog"
RELEASES_DIR = CATALOG_DIR / "releases"
CHANNELS_FILE = CATALOG_DIR / "channels.yaml"
SCHEMA_DIR = ROOT / "schemas"
GENERATED_DIR = ROOT / "generated"


@dataclass(frozen=True)
class ValidationIssue:
    source: str
    message: str


@dataclass(frozen=True)
class GenerationArtifact:
    filename: str
    content: str


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"Expected mapping at {path}")
    return data


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"Expected JSON object at {path}")
    return data


def load_speech_catalog_data() -> dict[str, Any]:
    return _load_yaml(CATALOG_DIR / "speech.yaml")


def load_diarization_catalog_data() -> dict[str, Any]:
    return _load_yaml(CATALOG_DIR / "diarization.yaml")


def load_cleanup_catalog_data() -> dict[str, Any]:
    return _load_yaml(CATALOG_DIR / "cleanup.yaml")


def load_notes_catalog_data() -> dict[str, Any]:
    return _load_yaml(CATALOG_DIR / "notes.yaml")


def load_search_catalog_data() -> dict[str, Any]:
    return _load_yaml(CATALOG_DIR / "search.yaml")


CLOUD_TIERS_FILE = CATALOG_DIR / "cloud_tiers.json"
CLOUD_MODELS_SNAPSHOT_FILE = CATALOG_DIR / "models_dev_snapshot.json"
MAX_CLOUD_MODELS_BYTES = 250_000

# Provider API details belong here; model ids and capabilities come only from the snapshot.
CLOUD_PROVIDER_PROTOCOLS: dict[str, dict[str, Any]] = {
    "openai": {
        "modelsDevId": "openai",
        "protocol": {
            "name": "openai-chat-completions",
            "temperatureField": "temperature",
            "reasoningToggleOff": {"reasoning_effort": "none"},
            "reasoningEffortPath": ["reasoning_effort"],
            "reasoningTokenField": "max_completion_tokens",
        },
    },
    "anthropic": {
        "modelsDevId": "anthropic",
        "protocol": {
            "name": "anthropic-messages",
            "temperatureField": "temperature",
            "reasoningToggleOff": {"thinking": {"type": "disabled"}},
            "reasoningEffortPath": ["output_config", "effort"],
            "reasoningTokenField": "max_tokens",
        },
    },
    "gemini": {
        "modelsDevId": "google",
        # The app calls Gemini through its OpenAI-compatible endpoint, not generateContent.
        "protocol": {
            "name": "openai-chat-completions",
            "temperatureField": "temperature",
            "reasoningToggleOff": {"reasoning_effort": "none"},
            "reasoningEffortPath": ["reasoning_effort"],
            "reasoningTokenField": "max_tokens",
        },
    },
    "groq": {
        "modelsDevId": "groq",
        "protocol": {
            "name": "openai-chat-completions",
            "temperatureField": "temperature",
            "reasoningToggleOff": {"reasoning_effort": "none"},
            "reasoningEffortPath": ["reasoning_effort"],
            "reasoningTokenField": "max_tokens",
        },
    },
    "cerebras": {
        "modelsDevId": "cerebras",
        "protocol": {
            "name": "openai-chat-completions",
            "temperatureField": "temperature",
            "reasoningToggleOff": {"reasoning_effort": "none"},
            "reasoningEffortPath": ["reasoning_effort"],
            "reasoningTokenField": "max_tokens",
        },
    },
    "openrouter": {
        "modelsDevId": "openrouter",
        "protocol": {
            "name": "openai-chat-completions",
            "temperatureField": "temperature",
            "reasoningToggleOff": {"reasoning": {"enabled": False}},
            "reasoningEffortPath": ["reasoning", "effort"],
            "reasoningTokenField": "max_tokens",
        },
    },
    "mistral": {
        "modelsDevId": "mistral",
        "protocol": {
            "name": "openai-chat-completions",
            "temperatureField": "temperature",
            "reasoningToggleOff": {"reasoning_effort": "none"},
            "reasoningEffortPath": ["reasoning_effort"],
            "reasoningTokenField": "max_tokens",
        },
    },
    "alibabacloud": {
        "modelsDevId": "alibaba",
        "protocol": {
            "name": "openai-chat-completions",
            "temperatureField": "temperature",
            "reasoningToggleOff": {"enable_thinking": False},
            "reasoningTokenField": "max_tokens",
        },
    },
    "nvidia": {
        "modelsDevId": "nvidia",
        "protocol": {
            "name": "openai-chat-completions",
            "temperatureField": "temperature",
            "reasoningToggleOff": {"chat_template_kwargs": {"enable_thinking": False}},
            "reasoningTokenField": "max_tokens",
        },
    },
    "foundry": {
        "modelsDevId": "azure",
        "protocol": {
            "name": "openai-chat-completions",
            "temperatureField": "temperature",
            "reasoningToggleOff": {"reasoning_effort": "none"},
            "reasoningEffortPath": ["reasoning_effort"],
            "reasoningTokenField": "max_completion_tokens",
        },
    },
}


def load_cloud_tiers_data() -> dict[str, Any] | None:
    """Optional: copied from scribekey-model-research tiers/cloud-tiers.json by its routine."""
    return _load_json(CLOUD_TIERS_FILE) if CLOUD_TIERS_FILE.exists() else None


def generate_cloud_tiers() -> dict[str, Any] | None:
    return load_cloud_tiers_data()


def load_cloud_models_snapshot_data() -> dict[str, Any]:
    return _load_json(CLOUD_MODELS_SNAPSHOT_FILE)


def _cloud_probe_params(provider: str, qualifications_dir: Path) -> dict[str, str]:
    records = sorted((qualifications_dir / provider).glob("*.json"))
    if not records:
        return {}

    latest_key = ""
    latest_params: dict[str, str] = {}
    for path in records:
        try:
            record = _load_json(path)
        except (OSError, ValueError, TypeError) as exc:
            raise ValueError(f"Invalid cloud probe record {path}: {exc}") from exc
        params = record.get("params")
        if not isinstance(params, dict) or any(
            not isinstance(field, str)
            or not isinstance(status, str)
            or status not in {"accepted", "rejected", "ignored"}
            for field, status in params.items()
        ):
            raise ValueError(f"Invalid params in cloud probe record {path}")
        timestamp = next(
            (record[key] for key in ("verifiedAt", "recordedAt", "createdAt", "timestamp") if isinstance(record.get(key), str)),
            path.name,
        )
        if timestamp >= latest_key:
            latest_key, latest_params = timestamp, params
    return latest_params


def _path_is_rejected(path: list[str], rejected: set[str]) -> bool:
    dotted = ".".join(path)
    return any(field == dotted or dotted.startswith(f"{field}.") or field.startswith(f"{dotted}.") for field in rejected)


def _put_path(path: list[str], value: Any) -> dict[str, Any]:
    result: Any = value
    for part in reversed(path):
        result = {part: result}
    return result


def _reasoning_floor(model: dict[str, Any], protocol: dict[str, Any]) -> dict[str, Any] | None:
    options = model.get("reasoning_options", [])
    toggle = any(option.get("type") == "toggle" for option in options)
    if toggle and "reasoningToggleOff" in protocol:
        return protocol["reasoningToggleOff"]

    effort = next((option for option in options if option.get("type") == "effort"), None)
    path = protocol.get("reasoningEffortPath")
    if not effort or not path:
        return None
    values = effort.get("values", [])
    priority = ["none", "minimal", "low", "medium", "high", "xhigh", "max"]
    selected = min(values, key=lambda value: (priority.index(value) if value in priority else len(priority), str(value))) if values else None
    if selected is None:
        return None
    return _put_path(path, selected)


def _protocol_config(name: str, provider_config: dict[str, Any]) -> dict[str, Any]:
    """Return the request-parameter rules for one canonical protocol."""
    if name == "anthropic-messages":
        return CLOUD_PROVIDER_PROTOCOLS["anthropic"]["protocol"]
    if name == "openai-chat-completions":
        return {**provider_config["protocol"], "name": name}
    return {"name": name}


def _model_protocol(
    provider_config: dict[str, Any], source_provider: dict[str, Any], model: dict[str, Any]
) -> tuple[str, str | None]:
    """Resolve an upstream per-model adapter and account-scoped URL, if supplied."""
    model_provider = model.get("provider")
    if not isinstance(model_provider, dict):
        return provider_config["protocol"]["name"], None
    upstream = {
        key: source_provider.get(key)
        for key in ("npm", "api", "shape")
        if source_provider.get(key) is not None
    }
    upstream.update(model_provider)
    npm = upstream.get("npm")
    shape = upstream.get("shape")
    api = upstream.get("api")
    if shape == "responses":
        protocol = "openai-responses"
    elif shape == "completions":
        protocol = "openai-chat-completions"
    elif npm in {"@ai-sdk/anthropic", "@ai-sdk/google-vertex/anthropic"}:
        protocol = "anthropic-messages"
    elif npm in {"@ai-sdk/google", "@ai-sdk/google-vertex"}:
        protocol = "google-generative-ai"
    elif npm in {
        "@ai-sdk/openai",
        "@ai-sdk/openai-compatible",
        "@openrouter/ai-sdk-provider",
        "@ai-sdk/azure",
        "@ai-sdk/mistral",
        "@ai-sdk/alibaba",
    }:
        protocol = "openai-chat-completions"
    elif api is not None:
        protocol = "unknown"
    else:
        protocol = provider_config["protocol"]["name"]
    base_url = api if isinstance(api, str) and (api.startswith("https://") or "${" in api) else None
    return protocol, base_url


def generate_cloud_models(
    snapshot: dict[str, Any] | None = None,
    qualifications_dir: Path | None = None,
) -> dict[str, Any]:
    snapshot = snapshot or load_cloud_models_snapshot_data()
    qualifications_dir = qualifications_dir or ROOT / "qualifications" / "cloud"
    providers: dict[str, Any] = {}
    for app_id, provider_config in CLOUD_PROVIDER_PROTOCOLS.items():
        source_provider = snapshot["providers"][provider_config["modelsDevId"]]
        source = source_provider["models"]
        probe_params = _cloud_probe_params(app_id, qualifications_dir)
        rejected = {field for field, status in probe_params.items() if status == "rejected"}
        protocol = dict(provider_config["protocol"])
        if "temperature" in rejected:
            protocol.pop("temperatureField", None)
        for key in ("reasoningToggleOff", "reasoningEffortPath"):
            value = protocol.get(key)
            path = list(value) if isinstance(value, list) else []
            if key == "reasoningToggleOff" and isinstance(value, dict):
                def walk(node: dict[str, Any], prefix: list[str]) -> list[list[str]]:
                    leaves: list[list[str]] = []
                    for name, child in node.items():
                        child_path = [*prefix, name]
                        leaves.extend(walk(child, child_path) if isinstance(child, dict) else [child_path])
                    return leaves
                if any(_path_is_rejected(field_path, rejected) for field_path in walk(value, [])):
                    protocol.pop(key, None)
            elif path and _path_is_rejected(path, rejected):
                protocol.pop(key, None)
        token_field = protocol.get("reasoningTokenField")
        if token_field in rejected:
            protocol.pop("reasoningTokenField", None)
        if probe_params:
            protocol["verifiedParams"] = probe_params

        models: dict[str, Any] = {}
        for model_id, model in source.items():
            output_modalities = model.get("modalities", {}).get("output", [])
            cost = model.get("cost")
            output_limit = model.get("limit", {}).get("output")
            if (
                "text" not in output_modalities
                or not isinstance(cost, dict)
                or not isinstance(output_limit, int)
                or isinstance(output_limit, bool)
                or output_limit <= 0
                or model.get("type") in {"embedding", "reranking", "reranker"}
            ):
                continue
            output_price = cost.get("output")
            if not isinstance(output_price, (int, float)) or isinstance(output_price, bool):
                continue
            # Charging for input but not output means it generates nothing (embeddings, rerankers,
            # speech); free models price both at zero and stay.
            input_price = cost.get("input")
            if output_price == 0 and isinstance(input_price, (int, float)) and input_price > 0:
                continue

            protocol_name, base_url = _model_protocol(provider_config, source_provider, model)
            supported = protocol_name in {"openai-chat-completions", "anthropic-messages"}
            model_protocol = _protocol_config(protocol_name, provider_config)
            token_field = (
                model_protocol.get("reasoningTokenField")
                if model.get("reasoning") is True
                else None
            )
            token_field = token_field or "max_tokens"
            if token_field in rejected:
                if token_field == "max_completion_tokens":
                    token_field = "max_tokens"
                if token_field in rejected:
                    supported = False
            profile: dict[str, Any] = {
                "text": supported,
                "protocol": protocol_name,
                "tokenField": token_field,
                "outputLimit": output_limit,
                "temperature": model.get("temperature") is True and "temperature" not in rejected,
                "price": {"input": cost.get("input"), "output": output_price},
            }
            if base_url is not None:
                profile["baseUrl"] = base_url
            if model.get("reasoning") is True:
                floor = _reasoning_floor(model, model_protocol)
                if floor is not None and any(
                    _path_is_rejected(path, rejected)
                    for path in _payload_paths(floor)
                ):
                    floor = None
                profile["reasoningOff"] = floor
            models[model_id] = profile
        providers[app_id] = {"protocol": protocol, "models": models}
    return {"schemaVersion": 1, "snapshot": snapshot["source"], "providers": providers}


def _payload_paths(payload: dict[str, Any], prefix: list[str] | None = None) -> list[list[str]]:
    prefix = prefix or []
    paths: list[list[str]] = []
    for key, value in payload.items():
        path = [*prefix, key]
        paths.extend(_payload_paths(value, path) if isinstance(value, dict) else [path])
    return paths


def validate_cloud_models(data: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    size = len(_render_cloud_models(data).encode("utf-8"))
    if size >= MAX_CLOUD_MODELS_BYTES:
        problems.append(f"generated/cloud_models.json is {size} bytes; limit is {MAX_CLOUD_MODELS_BYTES - 1}")
    for provider, entry in data.get("providers", {}).items():
        for model, profile in entry.get("models", {}).items():
            price = profile.get("price", {})
            if profile.get("text") is True and (
                profile.get("protocol") not in {"openai-chat-completions", "anthropic-messages"}
                or not isinstance(profile.get("outputLimit"), int)
                or profile["outputLimit"] <= 0
                or (price.get("output", 0) == 0 and price.get("input", 0) > 0)
            ):
                problems.append(f"{provider}.{model}: profile must be a text generator, not input-priced only")
    return problems


def validate_cloud_tiers(data: dict[str, Any]) -> list[str]:
    """What the schema cannot say: each provider's recommended tier must exist, and no tier may
    name a model that provider has retired."""
    problems = []
    retired = data.get("retired", {})
    for task, block in data.get("tasks", {}).items():
        for provider, entry in block.get("providers", {}).items():
            if entry["recommended"] not in entry["tiers"]:
                problems.append(f"{task}.{provider}: recommended tier '{entry['recommended']}' is missing")
            for name, tier in entry["tiers"].items():
                if tier["model"] in retired.get(provider, []):
                    problems.append(f"{task}.{provider}.{name}: '{tier['model']}' is retired")
    return problems


def load_channels_data() -> dict[str, Any]:
    return _load_yaml(CHANNELS_FILE)


def load_all_releases_data() -> dict[str, dict[str, Any]]:
    releases: dict[str, dict[str, Any]] = {}
    if not RELEASES_DIR.exists():
        return releases
    for rel_file in sorted(RELEASES_DIR.glob("*.yaml")):
        data = _load_yaml(rel_file)
        # Ensure releaseId matches filename stem
        rel_id = str(data.get("releaseId", rel_file.stem))
        releases[rel_id] = data
    return releases


def accuracy_grade(error_percent: float) -> str:
    """Handy's display bands: A under 5% error, B under 10, C under 20, D under 30, F beyond.

    Within A to C each +/- step is a factor of the cube root of 2, so a grade means the same
    proportional change in error wherever it sits.
    """
    if error_percent >= 30:
        return "F"
    if error_percent >= 20:
        return "D"
    letter, ceiling = next((g, c) for g, c in (("A", 5), ("B", 10), ("C", 20)) if error_percent < c)
    step = 2 ** (1 / 3)
    if error_percent < ceiling / step**2:
        return letter + "+"
    return letter if error_percent < ceiling / step else letter + "-"


def generate_speech_catalog() -> dict[str, Any]:
    raw = load_speech_catalog_data()
    models: list[dict[str, Any]] = []
    for model in raw.get("models", []):
        entry: dict[str, Any] = {"id": model["id"]}
        if model.get("outcome") is not None:
            entry["outcome"] = model["outcome"]
        entry.update(
            {
                "family": model["family"],
                "displayName": model["displayName"],
                "badge": model.get("badge", ""),
                "diskMb": model["diskMb"],
                "minRamMb": model["minRamMb"],
                "minApiLevel": model["minApiLevel"],
                "transcriptionMode": model.get("transcriptionMode", "SEGMENTED"),
                "supportsTimestamps": model.get("supportsTimestamps", False),
                "supportsPunctuation": model.get("supportsPunctuation", False),
                "supportsLanguageDetection": model.get("supportsLanguageDetection", False),
            }
        )
        for field in ("description", "bestFor"):
            if model.get(field) is not None:
                entry[field] = model[field]
        # Always present, so Android can tell "not experimental" from a catalogue that predates
        # the field and fall back to the model ids it gated before.
        entry["experimental"] = bool(model.get("experimental", False))
        if model.get("retired"):
            entry["retired"] = True
        if model.get("deprecated"):
            entry["deprecated"] = True
        if model.get("replacementId"):
            entry["replacementId"] = model["replacementId"]
        if model.get("streamLanguage"):
            entry["streamLanguage"] = model["streamLanguage"]
        if model.get("counterpartId"):
            entry["counterpartId"] = model["counterpartId"]
        if model.get("languageCodes"):
            entry["languageCodes"] = list(model["languageCodes"])
        if model.get("accuracy"):
            entry["accuracy"] = {
                language: {"grade": accuracy_grade(error), "errorPercent": error}
                for language, error in model["accuracy"].items()
            }
        entry["files"] = [
            {
                "name": file["name"],
                "downloadUrl": file["downloadUrl"],
                "sizeBytes": file["sizeBytes"],
                "sha256": file["sha256"],
                **(
                    {"downloadUrls": file["downloadUrls"]}
                    if file.get("downloadUrls")
                    else {}
                ),
            }
            for file in model["files"]
        ]
        if model.get("npuBuilds"):
            entry["npuBuilds"] = [
                {
                    "soc": build["soc"],
                    "runtime": build["runtime"],
                    "windowSeconds": build["windowSeconds"],
                    "downloadUrl": build["downloadUrl"],
                    "sizeBytes": build["sizeBytes"],
                    "sha256": build["sha256"],
                    "archiveRoot": build["archiveRoot"],
                }
                for build in model["npuBuilds"]
            ]
        entry["sherpaConfig"] = {
            "type": model["sherpaConfig"]["type"],
            "modelDir": model["sherpaConfig"].get("modelDir", ""),
        }
        entry["info"] = {
            "paramsBadge": model["info"]["paramsBadge"],
            "architecture": model["info"]["architecture"],
            "languages": model["info"]["languages"],
        }
        if model.get("languageTiers"):
            entry["languageTiers"] = model["languageTiers"]
        if model.get("provenance"):
            entry["provenance"] = model["provenance"]
        models.append(entry)
    return {"models": models}


def generate_diarization_manifest() -> dict[str, Any]:
    raw = load_diarization_catalog_data()
    return {
        "packageId": raw["packageId"],
        "runtime": {
            "name": raw["runtime"]["name"],
            "version": str(raw["runtime"]["version"]),
            "revision": raw["runtime"]["revision"],
        },
        "models": [
            {
                "role": model["role"],
                "fileName": model["fileName"],
                "downloadUrl": model["downloadUrl"],
                **(
                    {"downloadUrls": model["downloadUrls"]}
                    if model.get("downloadUrls")
                    else {}
                ),
                "sizeBytes": model["sizeBytes"],
                "sha256": model["sha256"],
                "sourceRepository": model["sourceRepository"],
                "sourceRevision": model["sourceRevision"],
                "licenseId": model["licenseId"],
                "licenseUrl": model["licenseUrl"],
            }
            for model in raw["models"]
        ],
    }


def _cleanup_entry(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "modelId": model["modelId"],
        "displayName": model["displayName"],
        "description": model["description"],
        "bestFor": model["bestFor"],
        "info": model["info"],
        "provenance": model["provenance"],
        **{
            field: model[field]
            for field in ("deprecated", "retired", "replacementId")
            if field in model
        },
        **({"version": model["version"]} if "version" in model else {}),
        "revision": model["revision"],
        "bundleFileName": model["bundleFileName"],
        "downloadUrl": model["downloadUrl"],
        **(
            {"downloadUrls": model["downloadUrls"]}
            if model.get("downloadUrls")
            else {}
        ),
        "sizeBytes": model["sizeBytes"],
        "sha256": model["sha256"],
        "minDeviceMemoryGb": model["minDeviceMemoryGb"],
        "minimumApiLevel": model.get("minimumApiLevel", 28),
        "supportedAbis": model.get("supportedAbis", ["arm64-v8a", "x86_64"]),
        "supportedLanguages": model.get("supportedLanguages", ["en"]),
        "systemPrompt": model["systemPrompt"],
        "promptTemplate": model["promptTemplate"],
        "maxInputCharacters": model["maxInputCharacters"],
        "maxOutputCharacters": model["maxOutputCharacters"],
        "maxOutputTokens": model["maxOutputTokens"],
        "contextTokens": model["contextTokens"],
        "topK": model.get("topK", 1),
        "topP": float(model.get("topP", 1.0)),
        "temperature": float(model.get("temperature", 0.0)),
        "repetitionPenalty": (
            float(model["repetitionPenalty"])
            if model.get("repetitionPenalty") is not None
            else None
        ),
        "deterministicDecoding": model.get("deterministicDecoding", True),
        "samplerSeed": model.get("samplerSeed", 42),
        "license": model["license"],
        "attribution": model["attribution"],
        "licenseUrl": model["licenseUrl"],
        "privacyDisclosure": model.get(
            "privacyDisclosure", "Transcript text stays on this device."
        ),
        **(
            {"examples": [_cleanup_example(example) for example in model["examples"]]}
            if model.get("examples")
            else {}
        ),
    }


def _cleanup_example(example: dict[str, Any]) -> dict[str, Any]:
    recorded = example["recordedWith"]
    return {
        "input": example["input"],
        "output": example["output"],
        "recordedWith": {
            "modelRevision": recorded["modelRevision"],
            "runtime": recorded["runtime"],
            "recordedAt": str(recorded["recordedAt"]),
        },
    }


def generate_cleanup_catalog() -> dict[str, Any]:
    raw = load_cleanup_catalog_data()
    production = raw.get("production")
    return {
        "production": _cleanup_entry(production) if production else None,
        "candidates": [_cleanup_entry(candidate) for candidate in raw.get("candidates", [])],
    }


def generate_notes_catalog() -> dict[str, Any]:
    # experimental and badge are always present, so Android can tell "not experimental" from absent.
    return {
        "schemaVersion": 1,
        "models": [
            {**model, "experimental": bool(model.get("experimental", False)), "badge": model.get("badge", "")}
            for model in load_notes_catalog_data().get("models", [])
        ],
    }


def generate_search_catalog() -> dict[str, Any]:
    # Same projection as notes: experimental and badge always present.
    return {
        "schemaVersion": 1,
        "models": [
            {**model, "experimental": bool(model.get("experimental", False)), "badge": model.get("badge", "")}
            for model in load_search_catalog_data().get("models", [])
        ],
    }


def _render_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _render_cloud_models(data: dict[str, Any]) -> str:
    # The model map is large; compact JSON keeps the signed catalogue below its 250 KB budget.
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False) + "\n"


def generate_all_artifacts() -> list[GenerationArtifact]:
    artifacts: list[GenerationArtifact] = []

    speech_json = _render_json(generate_speech_catalog())
    diarization_json = _render_json(generate_diarization_manifest())
    cleanup_json = _render_json(generate_cleanup_catalog())

    # Root runtime catalogues
    artifacts.append(GenerationArtifact("model_catalog.json", speech_json))
    artifacts.append(GenerationArtifact("speaker_diarization_manifest.json", diarization_json))
    artifacts.append(GenerationArtifact("cleanup_model_catalog.json", cleanup_json))
    cloud_tiers = generate_cloud_tiers()
    if cloud_tiers is not None:
        artifacts.append(GenerationArtifact("cloud_model_tiers.json", _render_json(cloud_tiers)))
    artifacts.append(GenerationArtifact("cloud_models.json", _render_cloud_models(generate_cloud_models())))
    artifacts.append(GenerationArtifact("notes_model_catalog.json", _render_json(generate_notes_catalog())))
    artifacts.append(GenerationArtifact("search_model_catalog.json", _render_json(generate_search_catalog())))

    # Release manifests are derived metadata. The catalogue files below each release are
    # deliberately NOT generated here: `release create` freezes them once and validation checks
    # their declared hashes. Re-generating them from the live catalogue would mutate history.
    releases = load_all_releases_data()
    for rel_id, rel_data in releases.items():
        rel_dir = f"releases/{rel_id}"
        artifacts.append(GenerationArtifact(f"{rel_dir}/release.json", _render_json(rel_data)))

    # Channel distribution manifests
    if CHANNELS_FILE.exists():
        channels_data = load_channels_data()
        for chan_name in ["qa", "stable"]:
            chan_info = channels_data.get("channels", {}).get(chan_name)
            if chan_info:
                rel_id = str(chan_info["targetRelease"])
                if rel_id in releases:
                    manifest = build_channel_distribution_manifest(
                        chan_name,
                        releases[rel_id],
                        sequence=int(chan_info.get("sequence", 1)),
                        issued_at=chan_info.get("issuedAt"),
                        compatibility=chan_info.get("compatibility"),
                        notes=chan_info.get("notes"),
                    )
                    artifacts.append(
                        GenerationArtifact(f"channels/{chan_name}.json", _render_json(manifest))
                    )

    return artifacts


def export_generated(output_dir: Path = GENERATED_DIR, *, check: bool = False) -> list[str]:
    drift: list[str] = []
    for artifact in generate_all_artifacts():
        target = output_dir / artifact.filename
        if check:
            if not target.exists():
                drift.append(f"Missing generated file: {target}")
            elif target.read_text(encoding="utf-8") != artifact.content:
                drift.append(f"Generated file is stale: {target}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(artifact.content, encoding="utf-8")
    return drift


def validate() -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    # 1. Validate canonical YAML sources with JSON schemas
    canonical_sources = [
        (CATALOG_DIR / "speech.yaml", SCHEMA_DIR / "speech.schema.json"),
        (CATALOG_DIR / "cleanup.yaml", SCHEMA_DIR / "cleanup.schema.json"),
        (CATALOG_DIR / "diarization.yaml", SCHEMA_DIR / "diarization.schema.json"),
        (CATALOG_DIR / "notes.yaml", SCHEMA_DIR / "notes.schema.json"),
        (CATALOG_DIR / "search.yaml", SCHEMA_DIR / "search.schema.json"),
    ]
    if CHANNELS_FILE.exists():
        canonical_sources.append((CHANNELS_FILE, SCHEMA_DIR / "channels.schema.json"))
    if CLOUD_TIERS_FILE.exists():
        canonical_sources.append((CLOUD_TIERS_FILE, SCHEMA_DIR / "cloud_tiers.schema.json"))
    canonical_sources.append((CLOUD_MODELS_SNAPSHOT_FILE, SCHEMA_DIR / "models_dev_snapshot.schema.json"))

    if RELEASES_DIR.exists():
        for rel_file in RELEASES_DIR.glob("*.yaml"):
            canonical_sources.append((rel_file, SCHEMA_DIR / "release.schema.json"))

    for source, schema in canonical_sources:
        try:
            validator = Draft202012Validator(_load_json(schema), format_checker=FormatChecker())
            for error in validator.iter_errors(_load_yaml(source)):
                location = ".".join(str(part) for part in error.absolute_path)
                prefix = f"{location}: " if location else ""
                issues.append(ValidationIssue(str(source.relative_to(ROOT)), prefix + error.message))
        except (OSError, TypeError, ValueError, yaml.YAMLError, SchemaError) as exc:
            issues.append(ValidationIssue(str(source.relative_to(ROOT)), str(exc)))

    # Semantic checks and generation require schema-valid inputs.
    if issues:
        return issues

    cloud_tiers = load_cloud_tiers_data()
    if cloud_tiers is not None:
        for problem in validate_cloud_tiers(cloud_tiers):
            issues.append(ValidationIssue(str(CLOUD_TIERS_FILE.relative_to(ROOT)), problem))

    cloud_models = generate_cloud_models()
    for problem in validate_cloud_models(cloud_models):
        issues.append(ValidationIssue("generated/cloud_models.json", problem))
    cloud_models_schema = _load_json(SCHEMA_DIR / "cloud_models.schema.json")
    cloud_models_validator = Draft202012Validator(cloud_models_schema)
    for error in cloud_models_validator.iter_errors(cloud_models):
        location = ".".join(str(part) for part in error.absolute_path)
        prefix = f"{location}: " if location else ""
        issues.append(ValidationIssue("generated/cloud_models.json", prefix + error.message))

    for name, generated, guardrail_issues in (
        ("notes", generate_notes_catalog(), validate_notes_catalog(load_notes_catalog_data())),
        ("search", generate_search_catalog(), validate_search_catalog(load_search_catalog_data())),
    ):
        entry_schema = _load_json(SCHEMA_DIR / f"{name}.schema.json")
        generated_validator = Draft202012Validator(
            _load_json(SCHEMA_DIR / f"{name}_model_catalog.schema.json"),
            registry=Registry().with_resource(entry_schema["$id"], Resource.from_contents(entry_schema)),
        )
        for error in generated_validator.iter_errors(generated):
            location = ".".join(str(part) for part in error.absolute_path)
            prefix = f"{location}: " if location else ""
            issues.append(ValidationIssue(f"generated/{name}_model_catalog.json", prefix + error.message))
        for g_issue in guardrail_issues:
            issues.append(ValidationIssue(g_issue.source, g_issue.message))

    # 2. Guardrails: source refs, identities, safety, pointers, redistribution
    speech_data = load_speech_catalog_data()
    cleanup_data = load_cleanup_catalog_data()
    diarization_data = load_diarization_catalog_data()

    for g_issue in validate_immutable_source_refs(speech_data, cleanup_data, diarization_data):
        issues.append(ValidationIssue(g_issue.source, g_issue.message))

    for g_issue in validate_speech_accuracy(speech_data):
        issues.append(ValidationIssue(g_issue.source, g_issue.message))

    for g_issue in validate_identities_and_integrity(speech_data, cleanup_data, diarization_data):
        issues.append(ValidationIssue(g_issue.source, g_issue.message))

    for g_issue in validate_model_configuration(speech_data, cleanup_data, diarization_data):
        issues.append(ValidationIssue(g_issue.source, g_issue.message))

    for g_issue in validate_release_safety(ROOT):
        issues.append(ValidationIssue(g_issue.source, g_issue.message))

    releases_data = load_all_releases_data()
    for g_issue in validate_no_executable_payloads(speech_data, cleanup_data, diarization_data, releases_data):
        issues.append(ValidationIssue(g_issue.source, g_issue.message))

    if CHANNELS_FILE.exists():
        channels_data = load_channels_data()
        for g_issue in validate_channel_and_release_pointers(channels_data, RELEASES_DIR, GENERATED_DIR):
            issues.append(ValidationIssue(g_issue.source, g_issue.message))

    for rel_id, rel_data in load_all_releases_data().items():
        for g_issue in validate_release_snapshot_integrity(rel_id, rel_data, GENERATED_DIR):
            issues.append(ValidationIssue(f"generated/releases/{rel_id}", g_issue.message))
        for g_issue in validate_redistribution_clearance(rel_data):
            issues.append(ValidationIssue(f"catalog/releases/{rel_id}.yaml", g_issue.message))

    # 3. Validate generated channel manifests with distribution schema
    dist_schema_path = SCHEMA_DIR / "channel_distribution.schema.json"
    if dist_schema_path.exists():
        dist_validator = Draft202012Validator(_load_json(dist_schema_path))
        for chan_file in (GENERATED_DIR / "channels").glob("*.json"):
            try:
                for error in dist_validator.iter_errors(_load_json(chan_file)):
                    location = ".".join(str(part) for part in error.absolute_path)
                    prefix = f"{location}: " if location else ""
                    issues.append(ValidationIssue(str(chan_file.relative_to(ROOT)), prefix + error.message))
            except (OSError, json.JSONDecodeError, TypeError, SchemaError) as exc:
                issues.append(ValidationIssue(str(chan_file.relative_to(ROOT)), str(exc)))

    # 4. Check generated file freshness
    for message in export_generated(check=True):
        issues.append(ValidationIssue("generated", message))

    # 5. Validate existing signatures against public key
    for g_issue in validate_signatures(GENERATED_DIR):
        issues.append(ValidationIssue(g_issue.source, g_issue.message))

    return issues
