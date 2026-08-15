import json

import pytest
from pydantic import ValidationError

from harness.generation import (
    build_flat_fill_schema,
    build_strategy_request,
    build_typed_fill_schema,
    normalize_flat_fill,
    normalize_typed_fill,
)
from harness.generation.contracts import NarrativeSlot, PassagePlan
from harness.models import HarnessConfig


def _plan(with_refs=True):
    return PassagePlan(
        plan_id="strategy_plan",
        revision=2,
        passage_mode="normal",
        narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),),
        choice_slots=("accept", "decline"),
        allowed_state_refs=("gold",) if with_refs else (),
    )


def _typed_payload(plan):
    return {
        "schema_version": 1,
        "plan_id": plan.plan_id,
        "plan_revision": plan.revision,
        "revision": 1,
        "narrative": [{
            "slot_id": "body", "kind": "paragraph", "speaker": "",
            "parts": [{"kind": "text", "text": "You count "}, {"kind": "state_ref", "target": "gold"}],
        }],
        "choices": [
            {"slot_id": "accept", "text": "Accept", "hint": ""},
            {"slot_id": "decline", "text": "Decline", "hint": ""},
        ],
        "summary": "A choice is offered.",
        "beats": ["The player chooses."],
        "continuity_proposals": [],
        "media_proposals": [],
    }


def test_existing_configuration_stays_on_explicit_legacy_defaults():
    cfg = HarnessConfig()
    assert cfg.generation_strategy == "legacy_delimited"
    assert cfg.typed_shadow_generation is False
    assert cfg.experience_mode == "story_driven"
    with pytest.raises(ValidationError):
        HarnessConfig(generation_strategy="unknown")


def test_typed_schema_omits_unavailable_reference_branches():
    schema = build_typed_fill_schema(_plan(with_refs=False))
    variants = schema["properties"]["narrative"]["items"]["oneOf"][0]["properties"]["parts"]["items"]["oneOf"]
    assert [item["properties"]["kind"]["const"] for item in variants] == ["text"]
    proposals = schema["properties"]["continuity_proposals"]
    assert proposals["maxItems"] == 4
    assert proposals["items"]["properties"]["evidence_slot_ids"]["items"]["enum"] == ["body"]


def test_flat_schema_freezes_exact_slot_keys():
    schema = build_flat_fill_schema(_plan())
    assert schema["properties"]["narrative"]["required"] == ["body"]
    assert schema["properties"]["choices"]["required"] == ["accept", "decline"]
    assert schema["additionalProperties"] is False


def test_typed_and_flat_normalize_to_the_same_fill():
    plan = _plan()
    typed = normalize_typed_fill(plan, json.dumps(_typed_payload(plan)))
    flat = normalize_flat_fill(plan, json.dumps({
        "plan_id": plan.plan_id,
        "plan_revision": plan.revision,
        "narrative": {"body": "You count {{state:gold}}"},
        "choices": {
            "accept": {"text": "Accept", "hint": ""},
            "decline": {"text": "Decline", "hint": ""},
        },
        "summary": "A choice is offered.",
        "beats": ["The player chooses."],
    }))
    assert typed == flat


def test_normalization_rejects_unknown_slots_and_references():
    plan = _plan()
    payload = _typed_payload(plan)
    payload["narrative"][0]["parts"][1]["target"] = "health"
    with pytest.raises(ValueError):
        normalize_typed_fill(plan, json.dumps(payload))
    with pytest.raises(ValueError, match="slot keys"):
        normalize_flat_fill(plan, json.dumps({
            "plan_id": plan.plan_id,
            "plan_revision": plan.revision,
            "narrative": {"model_added": "Bad"},
            "choices": {},
            "summary": "Bad.",
            "beats": ["Bad."],
        }))


def test_strategy_prompts_expose_immutable_plan_not_sugarcube_authoring():
    plan = _plan()
    for strategy in ("typed_fill", "flat_fill"):
        request = build_strategy_request(
            strategy, plan, context="Trusted story context.", author_task="Write the scene.",
        )
        assert "PLAN (IMMUTABLE)" in request.prompt
        assert "harness owns mechanics and topology" in request.prompt
        assert "PROSE:" not in request.prompt
        assert request.schema["type"] == "object"
