import json

import pytest

from harness.ingestion_profiles import (
    IngestionEnvelopeError,
    PROFILE_IDS,
    load_ingestion_envelopes,
    render_ingestion,
)
from harness.models import HarnessConfig
from harness.ollama_client import _ollama_payload
from model_benchmark.ingestion_routing import load_ingestion_routing
from model_benchmark.benchmark import run_single_model
from model_benchmark.config import BenchmarkConfig


@pytest.mark.parametrize("profile_id", PROFILE_IDS)
def test_profiles_render_deterministically_without_generic_persona(profile_id):
    first = render_ingestion(profile_id, "Keep  spaces\nand lines.")
    second = render_ingestion(profile_id, "Keep  spaces\nand lines.")

    assert first == second
    assert "Keep  spaces\nand lines." in first.prompt
    assert "helpful assistant" not in first.prompt.lower()
    assert "you are" not in first.prompt.lower()


def test_family_framing_and_thinking_tiers_are_exact():
    assert render_ingestion("llama3-neutral", "P").prompt == (
        "<|begin_of_text|>"
        "<|start_header_id|>user<|end_header_id|>\n\nP<|eot_id|>"
        "<|start_header_id|>assistant<|end_header_id|>\n\n"
    )
    assert render_ingestion("llama2-chat-neutral", " P ").prompt == (
        "<s>[INST] P [/INST]"
    )
    assert render_ingestion("gemma-instruct-neutral", " P ").prompt == (
        "<bos><start_of_turn>user\nP<end_of_turn>\n"
        "<start_of_turn>model\n"
    )
    assert render_ingestion("mistral-neutral", " P ").prompt == "<s>[INST] P[/INST]"
    assert render_ingestion("qwen3-thinking", "P").prompt.endswith(
        "<|im_start|>assistant\n"
    )
    assert render_ingestion("qwen3-nonthinking", "P").prompt.endswith(
        "<|im_start|>assistant\n<think>\n\n</think>\n\n"
    )
    assert render_ingestion("deepseek-r1-thinking", "P").prompt == (
        "<｜begin▁of▁sentence｜><｜User｜>P<｜Assistant｜><think>\n"
    )


def test_payload_uses_raw_profile_and_signed_stop_markers():
    cfg = HarnessConfig(ollama_model="private", model_mode="standard")

    payload = _ollama_payload(
        cfg,
        "P",
        ingestion_profile="deepseek-r1-thinking",
    )

    assert payload["raw"] is True
    assert payload["prompt"] == (
        "<｜begin▁of▁sentence｜><｜User｜>P<｜Assistant｜><think>\n"
    )
    assert "<｜end▁of▁sentence｜>" in payload["options"]["stop"]


def test_payload_sends_sampling_seed_to_ollama():
    cfg = HarnessConfig(ollama_model="private", model_mode="standard")

    payload = _ollama_payload(cfg, "P", seed_override=42)

    assert payload["options"]["seed"] == 42


def test_native_profile_preserves_ollama_template_behavior():
    cfg = HarnessConfig(ollama_model="private", model_mode="standard")

    payload = _ollama_payload(cfg, "P", ingestion_profile="ollama-native")

    assert payload["prompt"] == "P"
    assert "raw" not in payload


def test_harness_generate_profile_matches_production_request_framing():
    cfg = HarnessConfig(ollama_model="private", model_mode="standard")

    payload = _ollama_payload(
        cfg,
        "Complete self-contained harness prompt",
        ingestion_profile="harness-generate-neutral",
    )

    assert payload["prompt"] == "Complete self-contained harness prompt"
    assert "raw" not in payload
    assert "system" not in payload
    assert "template" not in payload


def test_live_harness_config_can_select_story_profile_without_call_override():
    cfg = HarnessConfig(
        ollama_model="private",
        model_mode="standard",
        ingestion_profile="llama3-story",
    )

    payload = _ollama_payload(cfg, "Write the next passage")

    assert payload["raw"] is True
    assert payload["prompt"].startswith(
        "<|begin_of_text|><|start_header_id|>user<|end_header_id|>"
    )
    assert "STORY GENERATION TASK" in payload["prompt"]


def test_private_routing_requires_exact_models_and_closed_profiles(tmp_path):
    path = tmp_path / "routing.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "model_profiles": {"private-a": "llama3-neutral"},
            }
        ),
        encoding="utf-8",
    )

    assert load_ingestion_routing(
        path,
        expected_models=("private-a",),
    ) == {"private-a": "llama3-neutral"}
    with pytest.raises(ValueError, match="exactly match"):
        load_ingestion_routing(path, expected_models=("private-b",))

    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "model_profiles": {"private-a": "unsigned-template"},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid entry"):
        load_ingestion_routing(path)


def test_unknown_profile_fails_closed_without_echoing_identifier():
    with pytest.raises(ValueError, match="unknown ingestion profile") as exc:
        render_ingestion("private-family-name", "P")

    assert "private-family-name" not in str(exc.value)


def test_optimized_and_story_profiles_apply_only_bounded_semantic_envelopes():
    optimized = render_ingestion("llama3-optimized", "ORIGINAL TASK")
    story = render_ingestion("gemma-instruct-story", "ORIGINAL TASK")
    official = render_ingestion("llama3-official", "ORIGINAL TASK")

    assert "Execute the complete request above" in optimized.prompt
    assert "STORY GENERATION TASK" in story.prompt
    assert "preserve continuity" in story.prompt
    assert "Execute the complete request above" not in official.prompt


def test_envelope_rejects_protocol_and_jinja_syntax(tmp_path):
    path = tmp_path / "envelopes.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "envelopes": {
                    "optimized": {
                        "user_prefix": "{{ unsafe }}",
                        "user_suffix": "",
                    },
                    "story": {"user_prefix": "", "user_suffix": ""},
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(IngestionEnvelopeError, match="reserved protocol"):
        load_ingestion_envelopes(path)


def test_matrix_execution_uses_private_profile_selection(tmp_path, monkeypatch):
    routing = tmp_path / "routing.json"
    routing.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "model_profiles": {"private-a": "mistral-neutral"},
            }
        ),
        encoding="utf-8",
    )
    captured = {}

    def fake_call(*args, **kwargs):
        captured["profile"] = kwargs["ingestion_profile"]
        return "PROSE:\nText\n\nCHOICES:\n- Go | Continue\n- Wait | Stay\n\nSUMMARY:\nDone."

    monkeypatch.setattr("model_benchmark.benchmark.call_ollama_sync", fake_call)
    config = BenchmarkConfig(
        models=("private-a",),
        variants=("compact",),
        directions=("A",),
        base_url="http://127.0.0.1:11434",
        timeout=30,
        num_predict=640,
        temperature=0.2,
        runs=1,
        ingestion_routing_path=str(routing),
    )

    run_single_model("private-a", "compact", "A", config)

    assert captured["profile"] == "mistral-neutral"
