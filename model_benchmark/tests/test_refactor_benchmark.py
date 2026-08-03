import dataclasses
import json

import pytest

from harness.ollama_client import OllamaGenerationResult
from model_benchmark.config import BenchmarkConfig
from model_benchmark.refactor_benchmark import (
    REFACTOR_CANARY_IDS,
    RefactorCaseError,
    build_refactor_fill_prompt,
    build_refactor_fill_schema,
    execute_refactor_cases,
    load_refactor_cases,
    parse_refactor_fill,
    score_refactor_fill,
    select_refactor_cases,
    validate_refactor_case,
)


def _state_case():
    return next(
        case for case in load_refactor_cases()
        if case.id == "R1-STATE-REFERENCE"
    )


def _passing_response(case) -> str:
    return json.dumps({
        "plan_id": case.plan.plan_id,
        "plan_revision": case.plan.revision,
        "narrative": [{
            "slot_id": "merchant_scene",
            "kind": "paragraph",
            "speaker": "",
            "parts": [
                {
                    "kind": "text",
                    "text": (
                        "The patient merchant opens a cedar case of remedies "
                        "and names a fair price. You quietly count "
                    ),
                },
                {"kind": "state_ref", "target": "gold"},
                {
                    "kind": "text",
                    "text": (
                        " before deciding whether the medicine is worth the "
                        "cost while rain taps against the canvas roof."
                    ),
                },
            ],
        }],
        "choices": [
            {
                "slot_id": "choice_buy",
                "text": "Buy the medicine",
                "hint": "Accept the merchant's offer.",
            },
            {
                "slot_id": "choice_leave",
                "text": "Leave the stall",
                "hint": "Keep searching the market.",
            },
        ],
        "summary": "The merchant offers medicine at a price.",
        "beats": ["The offer is made.", "The player weighs the purchase."],
    })


def test_refactor_corpus_has_fixed_core_and_canary_sizes():
    cases = load_refactor_cases()

    assert len(cases) == 24
    assert len(select_refactor_cases(cases, "refactor-canary")) == 10
    assert len(select_refactor_cases(cases, "refactor-core")) == 24
    assert len(REFACTOR_CANARY_IDS) == len(set(REFACTOR_CANARY_IDS))


def test_case_validation_rejects_plan_authority_ambiguity():
    case = _state_case()
    raw = {
        "schema_version": 1,
        "id": case.id,
        "tier": case.tier,
        "context_ref": case.context_ref,
        "context_size": case.context_size,
        "distractor_density": case.distractor_density,
        "task": case.task,
        "plan": {
            "plan_id": case.plan.plan_id,
            "revision": case.plan.revision,
            "passage_mode": case.plan.passage_mode,
            "narrative_slots": [
                dataclasses.asdict(slot) for slot in case.plan.narrative_slots
            ],
            "choice_slots": ["choice_buy", "choice_buy"],
            "allowed_state_refs": list(case.plan.allowed_state_refs),
            "allowed_entity_refs": list(case.plan.allowed_entity_refs),
            "required_components": list(case.plan.required_components),
        },
        "expected": dataclasses.asdict(case.expected),
    }

    with pytest.raises(RefactorCaseError, match="duplicates"):
        validate_refactor_case(raw)


def test_dynamic_schema_freezes_slots_and_reference_ids():
    case = _state_case()
    schema = build_refactor_fill_schema(case)

    narrative = schema["properties"]["narrative"]
    assert narrative["minItems"] == narrative["maxItems"] == 1
    assert narrative["items"]["properties"]["slot_id"]["enum"] == [
        "merchant_scene"
    ]
    part_variants = narrative["items"]["properties"]["parts"]["items"][
        "oneOf"
    ]
    state_variant = next(
        item for item in part_variants
        if item["properties"]["kind"].get("const") == "state_ref"
    )
    assert state_variant["properties"]["target"]["enum"] == ["gold"]


def test_prompt_exposes_immutable_plan_not_markup_authoring():
    prompt = build_refactor_fill_prompt(_state_case())

    assert "PLAN (IMMUTABLE)" in prompt
    assert "You write narrative and choice copy; the harness owns mechanics." in prompt
    assert '"choice_guard:gold_gte_5"' in prompt
    assert "PROSE:" not in prompt
    assert "CHOICES:" not in prompt


def test_scoring_passes_valid_fill_and_rejects_extra_slot():
    case = _state_case()
    raw = _passing_response(case)
    fill = parse_refactor_fill(raw)

    results = score_refactor_fill(case, raw, fill)
    assert [result.name for result in results] == [
        "raw_contract",
        "plan_adherence",
        "fill_completeness",
        "semantic_observables",
    ]
    assert all(result.passed for result in results)
    assert results[0].gating is False

    assert fill is not None
    extra_slot = dataclasses.replace(
        fill.narrative[0],
        slot_id="model_added_mechanic",
    )
    invalid = dataclasses.replace(fill, narrative=(*fill.narrative, extra_slot))
    invalid_results = score_refactor_fill(case, raw, invalid)
    assert invalid_results[1].passed is False


def test_scoring_rejects_empty_text_and_cross_typed_reference():
    case = _state_case()
    raw = _passing_response(case)
    fill = parse_refactor_fill(raw)
    assert fill is not None

    empty_parts = tuple(
        dataclasses.replace(part, text="")
        if part.kind == "text"
        else part
        for part in fill.narrative[0].parts
    )
    empty_fill = dataclasses.replace(
        fill,
        narrative=(
            dataclasses.replace(fill.narrative[0], parts=empty_parts),
        ),
    )
    assert score_refactor_fill(case, raw, empty_fill)[2].passed is False

    wrong_ref_parts = tuple(
        dataclasses.replace(part, kind="entity_ref")
        if part.kind == "state_ref"
        else part
        for part in fill.narrative[0].parts
    )
    wrong_ref_fill = dataclasses.replace(
        fill,
        narrative=(
            dataclasses.replace(fill.narrative[0], parts=wrong_ref_parts),
        ),
    )
    assert score_refactor_fill(case, raw, wrong_ref_fill)[1].passed is False


def test_parser_rejects_fields_outside_the_fill_contract():
    case = _state_case()
    data = json.loads(_passing_response(case))
    data["mechanics"] = [{"operation": "set", "target": "gold"}]

    assert parse_refactor_fill(json.dumps(data)) is None


def test_execution_uses_json_schema_and_request_level_record(monkeypatch):
    case = _state_case()
    captured = {}

    def fake_call(config, prompt, **kwargs):
        captured["prompt"] = prompt
        captured["format_spec"] = kwargs["format_spec"]
        return OllamaGenerationResult(
            response=_passing_response(case),
            prompt_eval_count=120,
            eval_count=45,
            done_reason="stop",
        )

    monkeypatch.setattr(
        "model_benchmark.refactor_benchmark.call_ollama_sync_detailed",
        fake_call,
    )
    cfg = BenchmarkConfig(
        models=("private-model",),
        variants=("json",),
        directions=("A",),
        base_url="http://127.0.0.1:11434",
        timeout=30,
        num_predict=640,
        temperature=0.2,
        runs=1,
    )
    progress = []

    records = execute_refactor_cases(
        cfg,
        [case],
        progress_callback=lambda completed, total, model: progress.append(
            (completed, total, model)
        ),
    )

    assert captured["format_spec"]["type"] == "object"
    assert "PLAN (IMMUTABLE)" in captured["prompt"]
    assert progress == [(1, 1, "private-model")]
    assert len(records) == 1
    assert records[0].status == "PASS"
    assert records[0].test_id == (
        "private-model:R1-STATE-REFERENCE:typed_fill:1"
    )
    assert records[0].dataset == "refactor_core"
    assert records[0].input_tokens == 120
    assert records[0].output_tokens == 45
    assert records[0].max_score == 3.0


def test_execution_repeats_requests_with_incremented_seeds(monkeypatch):
    case = _state_case()
    seeds = []

    def fake_call(config, prompt, **kwargs):
        seeds.append(kwargs["seed"])
        return OllamaGenerationResult(response=_passing_response(case))

    monkeypatch.setattr(
        "model_benchmark.refactor_benchmark.call_ollama_sync_detailed",
        fake_call,
    )
    cfg = BenchmarkConfig(
        models=("private-model",),
        variants=("json",),
        directions=("A",),
        base_url="http://127.0.0.1:11434",
        timeout=30,
        num_predict=640,
        temperature=0.2,
        runs=2,
        random_seed="42",
    )

    records = execute_refactor_cases(cfg, [case])

    assert seeds == [42, 43]
    assert [record.repetition for record in records] == [1, 2]
    assert [record.random_seed for record in records] == ["42", "43"]
    assert records[1].test_id.endswith(":typed_fill:2")
