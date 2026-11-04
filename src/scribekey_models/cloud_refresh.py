from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from scribekey_models import catalog

MODELS_DEV_URL = "https://models.dev/api.json"
APP_REGISTRY = Path("app/src/main/java/app/scribekey/enhancement/provider/EnhancementProviderRegistry.kt")
# Upstream fields the generator reads; a refresh that dropped one would silently change protocols.
PROVIDER_FIELDS = ("id", "name", "npm", "api", "env")
PROFILE_FIELDS = ("reasoningOff", "temperature", "price", "outputLimit")


def fetch_models_dev_api() -> bytes:
    request = urllib.request.Request(
        MODELS_DEV_URL,
        headers={"User-Agent": "scribekey-models/0.1.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def build_snapshot(raw: bytes, previous_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    upstream = json.loads(raw)
    providers: dict[str, Any] = {}
    for config in catalog.CLOUD_PROVIDER_PROTOCOLS.values():
        provider_id = config["modelsDevId"]
        models = upstream[provider_id]["models"]
        projected = {model_id: _snapshot_model(model) for model_id, model in models.items()}
        previous = (previous_snapshot or {}).get("providers", {}).get(provider_id, {}).get("models", {})
        ordered = {model_id: projected[model_id] for model_id in previous if model_id in projected}
        ordered.update({model_id: model for model_id, model in projected.items() if model_id not in previous})
        provider = {key: upstream[provider_id][key] for key in PROVIDER_FIELDS if key in upstream[provider_id]}
        providers[provider_id] = {**provider, "models": ordered}
    return {
        "schemaVersion": 1,
        "source": {
            "url": MODELS_DEV_URL,
            "fetchedAt": datetime.datetime.now(datetime.UTC).date().isoformat(),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "upstreamRepo": "anomalyco/models.dev",
            "license": "MIT",
            "attribution": "Data from models.dev, maintained by anomalyco/models.dev; MIT licensed.",
            "upstreamCommit": None,
        },
        "providers": providers,
    }


def _snapshot_model(model: dict[str, Any]) -> dict[str, Any]:
    projected = {}
    for field in ("type", "provider", "modalities", "cost", "limit", "temperature", "reasoning", "reasoning_options"):
        if field not in model:
            continue
        value = model[field]
        if field in {"provider", "modalities", "cost", "limit"}:
            keys = {
                "provider": ("npm", "api", "shape"),
                "modalities": ("output",),
                "cost": ("input", "output"),
                "limit": ("output",),
            }[field]
            projected[field] = (
                {key: value[key] for key in keys if key in value}
                if isinstance(value, dict)
                else value
            )
        elif field == "reasoning_options":
            projected[field] = [
                {key: value for key, value in option.items() if key in {"type", "values", "min", "max"}}
                if isinstance(option, dict)
                else option
                for option in value
            ] if isinstance(value, list) else value
        else:
            projected[field] = value
    return projected


def validate_candidates(snapshot: dict[str, Any], profiles: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for filename, data in (
        ("models_dev_snapshot.schema.json", snapshot),
        ("cloud_models.schema.json", profiles),
    ):
        schema = catalog._load_json(catalog.SCHEMA_DIR / filename)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        problems.extend(f"{filename}: {error.message}" for error in validator.iter_errors(data))
    problems.extend(catalog.validate_cloud_models(profiles))
    return problems


def load_app_defaults(app_dir: str | None) -> dict[str, list[str]]:
    if not app_dir:
        return {}
    registry = Path(app_dir) / APP_REGISTRY
    source = registry.read_text(encoding="utf-8")
    defaults = {}
    for provider, constant, models in re.findall(
        r'id\s*=\s*(?:"([^\"]+)"|([A-Z][A-Z0-9_]*_PROVIDER_ID)).*?defaultModels\s*=\s*listOf\((.*?)\)',
        source,
        flags=re.DOTALL,
    ):
        provider = provider or constant.removesuffix("_PROVIDER_ID").lower()
        defaults[provider] = re.findall(r'"([^\"]+)"', models)
    if not defaults:
        raise ValueError(f"No defaultModels listOf entries found in {registry}")
    return defaults


def summarize_changes(
    old_profiles: dict[str, Any],
    new_profiles: dict[str, Any],
    defaults: dict[str, list[str]],
) -> str:
    lines = [
        "# Cloud model profile refresh",
        "",
        f"models.dev sha256: `{old_profiles['snapshot']['sha256']}` → `{new_profiles['snapshot']['sha256']}`",
        "",
    ]
    old_providers = old_profiles.get("providers", {})
    new_providers = new_profiles.get("providers", {})
    for provider in new_providers:
        old_models = old_providers.get(provider, {}).get("models", {})
        new_models = new_providers[provider].get("models", {})
        added = sorted(new_models.keys() - old_models.keys())
        removed = sorted(old_models.keys() - new_models.keys())
        changed = []
        for model_id in sorted(old_models.keys() & new_models.keys()):
            fields = []
            for field in PROFILE_FIELDS:
                old_value = old_models[model_id].get(field, _MISSING)
                new_value = new_models[model_id].get(field, _MISSING)
                if old_value != new_value:
                    fields.append(f"{field}: {_format_value(old_value)} → {_format_value(new_value)}")
            if fields:
                changed.append(f"`{model_id}` ({'; '.join(fields)})")
        missing_defaults = sorted(model for model in defaults.get(provider, []) if model not in new_models)
        lines.extend(
            [
                f"### {provider}",
                f"- Added models: {_format_ids(added)}",
                f"- Removed models: {_format_ids(removed)}",
                f"- Changed models: {'; '.join(changed) if changed else 'none'}",
                f"- ⚠ Default models missing: {_format_ids(missing_defaults)}",
                "",
            ]
        )
    return "\n".join(lines)


def _format_ids(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "none"


_MISSING = object()


def _format_value(value: Any) -> str:
    return "absent" if value is _MISSING else f"`{json.dumps(value, ensure_ascii=False, sort_keys=True)}`"


def refresh_cloud_models() -> tuple[str, str] | None:
    raw = fetch_models_dev_api()
    old_snapshot = catalog._load_json(catalog.CLOUD_MODELS_SNAPSHOT_FILE)
    if hashlib.sha256(raw).hexdigest() == old_snapshot["source"]["sha256"]:
        return None
    snapshot = build_snapshot(raw, old_snapshot)

    old_profiles = catalog.generate_cloud_models(old_snapshot)
    profiles = catalog.generate_cloud_models(snapshot)
    problems = validate_candidates(snapshot, profiles)
    if problems:
        raise ValueError("Refusing to write invalid cloud refresh:\n" + "\n".join(problems))

    defaults = load_app_defaults(os.environ.get("SCRIBEKEY_APP_DIR"))
    summary = summarize_changes(old_profiles, profiles, defaults)
    snapshot_path = catalog.CLOUD_MODELS_SNAPSHOT_FILE
    profiles_path = catalog.GENERATED_DIR / "cloud_models.json"
    snapshot_path.write_text(catalog._render_json(snapshot), encoding="utf-8")
    profiles_path.write_text(catalog._render_json(profiles), encoding="utf-8")
    return summary, snapshot["source"]["sha256"]
