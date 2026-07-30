import json

import pytest

from model_benchmark.prompt_overlay import (
    PromptOverlayError,
    apply_prompt_overlay,
    load_prompt_overlay,
)


def _write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def test_applies_global_variant_and_direction_fragments(tmp_path):
    path = tmp_path / "overlay.json"
    _write(
        path,
        {
            "schema_version": 1,
            "global_suffix": "Always follow the requested format.",
            "variants": {"json": "Return one JSON object."},
            "directions": {"D": "Use the include macro exactly once."},
        },
    )

    result = apply_prompt_overlay(
        "BASE",
        variant="json",
        direction="D",
        path=path,
    )

    assert result.startswith("BASE\n\nOPTIMIZATION GUIDANCE:")
    assert "Return one JSON object." in result
    assert "Use the include macro exactly once." in result


def test_rejects_unknown_fields(tmp_path):
    path = tmp_path / "overlay.json"
    _write(path, {"schema_version": 1, "run_command": "anything"})

    with pytest.raises(PromptOverlayError, match="unknown"):
        load_prompt_overlay(path)


def test_rejects_non_string_and_oversized_fragments(tmp_path):
    path = tmp_path / "overlay.json"
    _write(path, {"schema_version": 1, "variants": {"json": ["not", "text"]}})
    with pytest.raises(PromptOverlayError, match="must be a string"):
        load_prompt_overlay(path)

    _write(path, {"schema_version": 1, "global_suffix": "x" * 8_001})
    with pytest.raises(PromptOverlayError, match="length"):
        load_prompt_overlay(path)
