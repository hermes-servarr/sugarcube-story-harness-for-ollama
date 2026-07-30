"""Load a constrained, data-only prompt overlay for optimization runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_OVERLAY_PATH = Path("model_benchmark/prompt_overrides.json")
MAX_FRAGMENT_LENGTH = 8_000
ALLOWED_VARIANTS = {"compact", "full", "json", "thinking"}
ALLOWED_DIRECTIONS = set("ABCDEFGH")


class PromptOverlayError(ValueError):
    """Raised when the candidate prompt overlay is malformed or unsafe."""


def _string_map(value: Any, *, allowed: set[str], field: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise PromptOverlayError(f"{field} must be an object")
    result: dict[str, str] = {}
    for key, fragment in value.items():
        if key not in allowed:
            raise PromptOverlayError(f"unsupported {field} key: {key}")
        if not isinstance(fragment, str):
            raise PromptOverlayError(f"{field}.{key} must be a string")
        if len(fragment) > MAX_FRAGMENT_LENGTH:
            raise PromptOverlayError(f"{field}.{key} exceeds the length limit")
        result[key] = fragment.strip()
    return result


def load_prompt_overlay(path: str | Path = DEFAULT_OVERLAY_PATH) -> dict[str, Any]:
    overlay_path = Path(path)
    if not overlay_path.exists():
        return {"global_suffix": "", "variants": {}, "directions": {}}
    try:
        data = json.loads(overlay_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PromptOverlayError("could not load prompt overlay") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise PromptOverlayError("prompt overlay must use schema_version 1")
    unknown = set(data) - {
        "schema_version",
        "global_suffix",
        "variants",
        "directions",
    }
    if unknown:
        raise PromptOverlayError(f"unknown prompt overlay fields: {sorted(unknown)}")
    global_suffix = data.get("global_suffix", "")
    if not isinstance(global_suffix, str):
        raise PromptOverlayError("global_suffix must be a string")
    if len(global_suffix) > MAX_FRAGMENT_LENGTH:
        raise PromptOverlayError("global_suffix exceeds the length limit")
    return {
        "global_suffix": global_suffix.strip(),
        "variants": _string_map(
            data.get("variants"),
            allowed=ALLOWED_VARIANTS,
            field="variants",
        ),
        "directions": _string_map(
            data.get("directions"),
            allowed=ALLOWED_DIRECTIONS,
            field="directions",
        ),
    }


def apply_prompt_overlay(
    prompt: str,
    *,
    variant: str,
    direction: str,
    path: str | Path = DEFAULT_OVERLAY_PATH,
) -> str:
    overlay = load_prompt_overlay(path)
    fragments = [
        overlay["global_suffix"],
        overlay["variants"].get(variant, ""),
        overlay["directions"].get(direction, ""),
    ]
    additions = [fragment for fragment in fragments if fragment]
    if not additions:
        return prompt
    return f"{prompt.rstrip()}\n\nOPTIMIZATION GUIDANCE:\n" + "\n\n".join(additions) + "\n"
