import dataclasses
import json
from pathlib import Path

import pytest

from harness.ollama_client import OllamaGenerationResult
from model_benchmark import refactor_benchmark
from model_benchmark.config import BenchmarkConfig
from model_benchmark.refactor_benchmark import (
    REFACTOR_CANARY_IDS,
    REFACTOR_ARCHITECTURES,
    build_flat_fill_prompt,
    build_flat_fill_schema,
    build_legacy_json_prompt,
    build_legacy_json_schema,
    RefactorCaseError,
    build_refactor_fill_prompt,
    build_refactor_fill_schema,
    execute_refactor_cases,
    load_refactor_cases,
    parse_refactor_fill,
    parse_flat_fill,
    parse_legacy_json,
    refactor_corpus_checksums,
    refactor_corpus_hash,
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


def _passing_flat_response(case) -> str:
    return json.dumps({
        "plan_id": case.plan.plan_id,
        "plan_revision": case.plan.revision,
        "narrative": {
            "merchant_scene": (
                "The patient merchant opens a cedar case of remedies and "
                "names a fair price. You quietly count {{state:gold}} before "
                "deciding whether the medicine is worth the cost while rain "
                "taps against the canvas roof."
            ),
        },
        "choices": {
            "choice_buy": {
                "text": "Buy the medicine",
                "hint": "Accept the merchant's offer.",
            },
            "choice_leave": {
                "text": "Leave the stall",
                "hint": "Keep searching the market.",
            },
        },
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


def test_flat_fill_uses_fixed_object_keys_and_normalizes_reference_markers():
    case = _state_case()
    schema = build_flat_fill_schema(case)
    prompt = build_flat_fill_prompt(case)
    fill = parse_flat_fill(case, _passing_flat_response(case))

    assert schema["properties"]["narrative"]["required"] == ["merchant_scene"]
    assert schema["properties"]["choices"]["required"] == [
        "choice_buy", "choice_leave",
    ]
    assert "{{state:ID}}" in prompt
    assert fill is not None
    assert any(
        part.kind == "state_ref" and part.target == "gold"
        for part in fill.narrative[0].parts
    )
    assert all(result.passed for result in score_refactor_fill(
        case, _passing_flat_response(case), fill
    ))


def test_execution_compares_architectures_with_same_seed(monkeypatch):
    case = _state_case()
    calls = []

    def fake_call(config, prompt, **kwargs):
        calls.append((kwargs["label"], kwargs["seed"]))
        response = (
            _passing_flat_response(case)
            if "flat_fill" in kwargs["label"]
            else _passing_response(case)
        )
        return OllamaGenerationResult(response=response)

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
        random_seed="42",
    )

    records = execute_refactor_cases(
        cfg, [case], architectures=("typed_fill", "flat_fill")
    )

    assert [seed for _, seed in calls] == [42, 42]
    assert [record.subcategory for record in records] == [
        "typed_fill", "flat_fill",
    ]
    assert [record.category for record in records] == [
        "harness_structure_typed_fill", "harness_structure_flat_fill",
    ]
    assert all(record.status == "PASS" for record in records)


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
    assert records[0].max_score == 7.0


def test_execution_scores_production_and_reports_browser_na(monkeypatch):
    case = _state_case()
    monkeypatch.setattr(
        "model_benchmark.refactor_benchmark.call_ollama_sync_detailed",
        lambda *args, **kwargs: OllamaGenerationResult(response=_passing_response(case)),
    )
    cfg = BenchmarkConfig(
        models=("private-model",), variants=("json",), directions=("A",),
        base_url="http://127.0.0.1:11434", timeout=30, num_predict=640,
        temperature=0.2, runs=1,
    )
    record = execute_refactor_cases(cfg, [case])[0]
    categories = {
        result.name: result for result in record.scored_result.category_results
    }
    assert all(categories[name].passed for name in (
        "draft_assembly",
        "required_component_resolution",
        "state_transaction",
        "compile_success",
    ))
    assert all(not categories[name].applicable for name in (
        "tweego_compile",
        "browser_load",
        "choice_reachability",
        "choice_effect_execution",
        "runtime_state_transaction",
        "continuity_after_navigation",
    ))


def test_execution_accepts_independent_browser_categories(monkeypatch):
    from model_benchmark.scoring import CategoryResult

    case = _state_case()
    monkeypatch.setattr(
        "model_benchmark.refactor_benchmark.call_ollama_sync_detailed",
        lambda *args, **kwargs: OllamaGenerationResult(response=_passing_response(case)),
    )
    cfg = BenchmarkConfig(
        models=("private-model",), variants=("json",), directions=("A",),
        base_url="http://127.0.0.1:11434", timeout=30, num_predict=640,
        temperature=0.2, runs=1,
    )

    def browser(case_value, draft, artifact):
        assert case_value == case
        assert artifact.source_draft_fingerprint == draft.fingerprint()
        return [
            CategoryResult(name, True, 1.0, "fixture runtime passed")
            for name in (
                "tweego_compile",
                "browser_load",
                "choice_reachability",
                "choice_effect_execution",
                "runtime_state_transaction",
                "continuity_after_navigation",
            )
        ]

    record = execute_refactor_cases(
        cfg, [case], browser_evaluator=browser
    )[0]
    categories = {
        result.name: result for result in record.scored_result.category_results
    }
    assert all(categories[name].passed and categories[name].applicable for name in (
        "tweego_compile",
        "browser_load",
        "choice_reachability",
        "choice_effect_execution",
        "runtime_state_transaction",
        "continuity_after_navigation",
    ))


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


# ═══════════════════════════════════════════════════════════════════════════
# Phase 0 — corpus content hash + legacy_json architecture
# ═══════════════════════════════════════════════════════════════════════════


def _passing_legacy_response(case) -> str:
    """A legacy ModelOutput JSON response that adapts to a passing fill."""
    return json.dumps({
        "prose": (
            "The patient merchant opens a cedar case of remedies and names a "
            "fair price. You quietly count {{state:gold}} before deciding "
            "whether the medicine is worth the cost while rain taps against "
            "the canvas roof."
        ),
        "choices": [
            {"text": "Buy the medicine", "hint": "Accept the merchant's offer."},
            {"text": "Leave the stall", "hint": "Keep searching the market."},
        ],
        "summary": "The merchant offers medicine at a price.",
        "beats": ["The offer is made.", "The player weighs the purchase."],
    })


def test_refactor_architectures_includes_legacy_json():
    assert "legacy_json" in REFACTOR_ARCHITECTURES
    assert REFACTOR_ARCHITECTURES == ("typed_fill", "flat_fill", "legacy_json")


def test_corpus_hash_is_deterministic_sha256_hex():
    digest = refactor_corpus_hash()
    assert isinstance(digest, str)
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)
    # Same bytes → same digest.
    assert refactor_corpus_hash() == digest


def test_corpus_hash_changes_with_content(tmp_path):
    original = refactor_corpus_hash()
    src = Path(refactor_benchmark.__file__).with_name("refactor_cases.json")
    tmp = tmp_path / "refactor_cases.json"
    tmp.write_bytes(src.read_bytes())
    assert refactor_corpus_hash(tmp) == original
    # Mutate a copy and confirm the digest changes.
    mutated = tmp_path / "mutated.json"
    mutated.write_bytes(src.read_bytes() + b"\n")
    assert refactor_corpus_hash(mutated) != original


def test_corpus_checksums_returns_single_element_tuple():
    checksums = refactor_corpus_checksums()
    assert isinstance(checksums, tuple)
    assert len(checksums) == 1
    assert checksums[0] == f"sha256:{refactor_corpus_hash()}"


def test_legacy_json_schema_is_object_with_legacy_keys():
    case = _state_case()
    schema = build_legacy_json_schema(case)

    assert schema["type"] == "object"
    required = set(schema["required"])
    assert required == {"prose", "choices", "summary", "beats"}
    assert schema["properties"]["prose"]["type"] == "string"
    assert schema["properties"]["choices"]["type"] == "array"
    assert schema["properties"]["summary"]["type"] == "string"
    assert schema["properties"]["beats"]["type"] == "array"
    assert schema["additionalProperties"] is False
    choices = schema["properties"]["choices"]
    assert choices["minItems"] == choices["maxItems"] == 2


def test_legacy_json_prompt_exposes_immutable_plan_without_slot_ids():
    case = _state_case()
    prompt = build_legacy_json_prompt(case)

    assert "PLAN (IMMUTABLE)" in prompt
    # The legacy prompt must NOT expose trusted slot IDs — the adapter owns
    # the mapping.
    assert "merchant_scene" not in prompt
    assert "choice_buy" not in prompt
    assert "narrative_slot_count" in prompt
    assert "choice_count" in prompt
    # State reference hint appears because the plan allows state refs.
    assert "{{state:ID}}" in prompt


def test_legacy_json_prompt_omits_ref_hint_when_no_refs_allowed():
    case = next(
        case for case in load_refactor_cases()
        if case.id == "R0-ORDINARY-FANTASY"
    )
    prompt = build_legacy_json_prompt(case)
    assert "{{state:ID}}" not in prompt
    assert "{{entity:ID}}" not in prompt


def test_legacy_json_adapter_maps_prose_and_choices_to_fixed_slots():
    case = _state_case()
    fill = parse_legacy_json(case, _passing_legacy_response(case))

    assert fill is not None
    # Exactly one narrative slot, matching the plan — no creation/drop.
    assert [slot.slot_id for slot in fill.narrative] == ["merchant_scene"]
    assert fill.narrative[0].kind == "paragraph"
    # State reference preserved from the model's prose marker.
    assert any(
        part.kind == "state_ref" and part.target == "gold"
        for part in fill.narrative[0].parts
    )
    # Choices mapped positionally to the plan's choice_slots.
    assert [choice.slot_id for choice in fill.choices] == [
        "choice_buy", "choice_leave",
    ]
    assert fill.choices[0].text == "Buy the medicine"
    assert fill.summary == "The merchant offers medicine at a price."
    assert list(fill.beats) == ["The offer is made.", "The player weighs the purchase."]


def test_legacy_json_adapter_scores_passing_with_existing_evaluator():
    case = _state_case()
    raw = _passing_legacy_response(case)
    fill = parse_legacy_json(case, raw)

    results = score_refactor_fill(case, raw, fill)
    assert [result.name for result in results] == [
        "raw_contract",
        "plan_adherence",
        "fill_completeness",
        "semantic_observables",
    ]
    assert all(result.passed for result in results)


def test_legacy_json_adapter_rejects_extra_narrative_slots():
    case = _state_case()
    # Model produces two prose paragraphs but the plan has one narrative slot.
    data = json.loads(_passing_legacy_response(case))
    data["prose"] = (
        "The patient merchant opens a cedar case of remedies and names a fair "
        "price. You quietly count {{state:gold}}.\n\n"
        "A second paragraph the model invented."
    )
    assert parse_legacy_json(case, json.dumps(data)) is None


def test_legacy_json_adapter_rejects_missing_narrative_slots():
    case = next(
        case for case in load_refactor_cases()
        if case.id == "R2-DIALOGUE-THOUGHT"
    )
    # Model produces only one paragraph but the plan has three narrative slots.
    data = {
        "prose": "Detective asks a sharp question.",
        "choices": [
            {"text": "Press harder", "hint": "Push for the truth."},
            {"text": "Release", "hint": "Back off for now."},
        ],
        "summary": "The detective presses the suspect.",
        "beats": ["The detective asks a question."],
    }
    assert parse_legacy_json(case, json.dumps(data)) is None


def test_legacy_json_adapter_rejects_extra_choices():
    case = _state_case()
    data = json.loads(_passing_legacy_response(case))
    data["choices"].append(
        {"text": "Extra choice", "hint": "The model added this."}
    )
    assert parse_legacy_json(case, json.dumps(data)) is None


def test_legacy_json_adapter_rejects_missing_choices():
    case = _state_case()
    data = json.loads(_passing_legacy_response(case))
    data["choices"] = [data["choices"][0]]  # only one choice
    assert parse_legacy_json(case, json.dumps(data)) is None


def test_legacy_json_adapter_rejects_extra_top_level_authority():
    case = _state_case()
    data = json.loads(_passing_legacy_response(case))
    data["state"] = {"gold": 999}

    assert parse_legacy_json(case, json.dumps(data)) is None


def test_legacy_json_adapter_preserves_plan_identity():
    case = _state_case()
    fill = parse_legacy_json(case, _passing_legacy_response(case))

    assert fill is not None
    assert fill.plan_id == case.plan.plan_id
    assert fill.plan_revision == case.plan.revision


def test_legacy_json_parser_returns_none_for_non_json():
    case = _state_case()
    assert parse_legacy_json(case, "not json at all") is None
    assert parse_legacy_json(case, "") is None


def test_execution_accepts_legacy_json_architecture(monkeypatch):
    case = _state_case()
    calls = []

    def fake_call(config, prompt, **kwargs):
        calls.append((kwargs["label"], kwargs["seed"]))
        return OllamaGenerationResult(response=_passing_legacy_response(case))

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
        random_seed="42",
    )

    records = execute_refactor_cases(
        cfg, [case], architectures=("legacy_json",)
    )

    assert len(records) == 1
    assert records[0].subcategory == "legacy_json"
    assert records[0].category == "harness_structure_legacy_json"
    assert records[0].status == "PASS"
    assert records[0].test_id == "private-model:R1-STATE-REFERENCE:legacy_json:1"


def test_execution_pairs_all_three_architectures_with_same_seed(monkeypatch):
    case = _state_case()
    calls = []

    def fake_call(config, prompt, **kwargs):
        calls.append((kwargs["label"], kwargs["seed"]))
        arch = "legacy_json" if "legacy_json" in kwargs["label"] else (
            "flat_fill" if "flat_fill" in kwargs["label"] else "typed_fill"
        )
        if arch == "legacy_json":
            response = _passing_legacy_response(case)
        elif arch == "flat_fill":
            response = _passing_flat_response(case)
        else:
            response = _passing_response(case)
        return OllamaGenerationResult(response=response)

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
        random_seed="42",
    )

    records = execute_refactor_cases(
        cfg, [case],
        architectures=("typed_fill", "flat_fill", "legacy_json"),
    )

    # All three architectures use the same per-case seed.
    assert [seed for _, seed in calls] == [42, 42, 42]
    # One result record per original request.
    assert len(records) == 3
    assert [record.subcategory for record in records] == [
        "typed_fill", "flat_fill", "legacy_json",
    ]
    assert [record.category for record in records] == [
        "harness_structure_typed_fill",
        "harness_structure_flat_fill",
        "harness_structure_legacy_json",
    ]
    assert all(record.status == "PASS" for record in records)


def test_execution_rejects_unknown_architecture():
    case = _state_case()
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
    with pytest.raises(RefactorCaseError, match="unknown refactor architectures"):
        execute_refactor_cases(cfg, [case], architectures=("typed_fill", "bogus"))


def test_execution_legacy_json_uses_json_schema(monkeypatch):
    case = _state_case()
    captured = {}

    def fake_call(config, prompt, **kwargs):
        captured["format_spec"] = kwargs["format_spec"]
        captured["prompt"] = prompt
        return OllamaGenerationResult(response=_passing_legacy_response(case))

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

    records = execute_refactor_cases(
        cfg, [case], architectures=("legacy_json",)
    )

    assert captured["format_spec"]["type"] == "object"
    assert "PLAN (IMMUTABLE)" in captured["prompt"]
    assert len(records) == 1
    assert records[0].status == "PASS"
