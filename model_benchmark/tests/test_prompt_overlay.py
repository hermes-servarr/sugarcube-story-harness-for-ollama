import json
import re
from pathlib import Path

import pytest

from harness.parsers import parse_model_output
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


def test_applies_thinking_variant_fragment(tmp_path):
    path = tmp_path / "overlay.json"
    _write(
        path,
        {
            "schema_version": 1,
            "variants": {
                "thinking": "Finish planning, then emit a complete passage."
            },
        },
    )

    result = apply_prompt_overlay(
        "BASE",
        variant="thinking",
        direction="H",
        path=path,
    )

    assert "Finish planning, then emit a complete passage." in result


def test_repository_overlay_uses_parser_section_contract():
    path = Path(__file__).parents[1] / "prompt_overrides.json"
    overlay = load_prompt_overlay(path)
    assert overlay["global_suffix"] == ""
    assert overlay["variants"]["json"] == ""
    assert overlay["directions"]["H"] == ""

    for variant in ("compact", "full", "thinking"):
        fragment = overlay["variants"][variant]
        assert not re.search(r"===(?:PROSE|CHOICES|SUMMARY)===", fragment)
        headers = re.findall(r"(?m)^(PROSE|CHOICES|SUMMARY):$", fragment)
        assert headers == ["PROSE", "CHOICES", "SUMMARY"]

        parsed = parse_model_output(
            "\n".join(f"{header}:\nplaceholder" for header in headers)
        )
        assert not any(
            warning.startswith("Required section")
            for warning in parsed.parse_warnings
        )

    assert apply_prompt_overlay(
        "BASE",
        variant="json",
        direction="H",
        path=path,
    ) == "BASE"


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
