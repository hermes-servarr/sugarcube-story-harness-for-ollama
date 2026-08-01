"""Load the private model-to-ingestion-profile routing document."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from harness.ingestion_profiles import PROFILE_IDS

MAX_ROUTING_BYTES = 64 * 1024


def load_ingestion_routing(
    path: str | Path,
    *,
    expected_models: tuple[str, ...] | list[str] | None = None,
) -> dict[str, str]:
    """Load and strictly validate a PC-private routing document."""
    if not path:
        return {}
    target = Path(path)
    if not target.is_file() or target.is_symlink():
        raise ValueError("ingestion routing must be a regular file")
    if target.stat().st_size > MAX_ROUTING_BYTES:
        raise ValueError("ingestion routing exceeds the size limit")
    with target.open("r", encoding="utf-8") as handle:
        payload: Any = json.load(handle)
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "model_profiles",
    }:
        raise ValueError("invalid ingestion routing document")
    if payload["schema_version"] != 1:
        raise ValueError("unsupported ingestion routing schema")
    mapping = payload["model_profiles"]
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError("model_profiles must be a non-empty object")
    if not all(
        isinstance(model, str)
        and model.strip()
        and isinstance(profile, str)
        and profile in PROFILE_IDS
        for model, profile in mapping.items()
    ):
        raise ValueError("model_profiles contains an invalid entry")
    if expected_models is not None and set(mapping) != set(expected_models):
        raise ValueError("model_profiles must exactly match configured models")
    return dict(mapping)


def profile_for_model(model: str, routing_path: str) -> str:
    """Return a model's selected profile; empty means legacy Ollama behavior."""
    if not routing_path:
        return ""
    mapping = _cached_routing(routing_path)
    try:
        return mapping[model]
    except KeyError as exc:
        raise ValueError("configured model has no ingestion profile") from exc


@lru_cache(maxsize=8)
def _cached_routing(path: str) -> dict[str, str]:
    """Keep one immutable routing snapshot for the duration of a run."""
    return load_ingestion_routing(path)
