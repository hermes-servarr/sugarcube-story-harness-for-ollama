"""Plan-derived model-facing JSON schemas."""
from __future__ import annotations

from typing import Any

from .contracts import PassagePlan


def build_typed_fill_schema(plan: PassagePlan) -> dict[str, Any]:
    part_variants: list[dict[str, Any]] = [
        _strict_object(
            {"kind": {"const": "text"}, "text": {"type": "string", "minLength": 1}},
            ("kind", "text"),
        )
    ]
    if plan.allowed_state_refs:
        part_variants.append(_strict_object(
            {
                "kind": {"const": "state_ref"},
                "target": {"type": "string", "enum": list(plan.allowed_state_refs)},
            },
            ("kind", "target"),
        ))
    if plan.allowed_entity_refs:
        part_variants.append(_strict_object(
            {
                "kind": {"const": "entity_ref"},
                "target": {"type": "string", "enum": list(plan.allowed_entity_refs)},
            },
            ("kind", "target"),
        ))

    narrative_variants = [
        _strict_object(
            {
                "slot_id": {"const": slot.id},
                "kind": {"const": slot.kind.value},
                "speaker": {"const": slot.speaker},
                "parts": {"type": "array", "items": {"oneOf": part_variants}, "minItems": 1},
            },
            ("slot_id", "kind", "speaker", "parts"),
        )
        for slot in plan.narrative_slots
    ]
    choice_variants = [
        _strict_object(
            {
                "slot_id": {"const": slot.id},
                "text": {"type": "string", "minLength": 1},
                "hint": {"type": "string"},
            },
            ("slot_id", "text", "hint"),
        )
        for slot in plan.choice_slots
    ]
    return _strict_object(
        {
            "plan_id": {"const": plan.plan_id},
            "plan_revision": {"const": plan.revision},
            "revision": {"const": 1},
            "narrative": {
                "type": "array",
                "items": {"oneOf": narrative_variants},
                "minItems": len(plan.narrative_slots),
                "maxItems": len(plan.narrative_slots),
            },
            "choices": {
                "type": "array",
                "items": {"oneOf": choice_variants},
                "minItems": len(plan.choice_slots),
                "maxItems": len(plan.choice_slots),
            },
            "summary": {"type": "string", "minLength": 1},
            "beats": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "continuity_proposals": {
                "type": "array",
                "items": _strict_object(
                    {
                        "key": {"type": "string", "pattern": "^[a-z][a-z0-9_]{0,63}$"},
                        "value": {"type": "string", "minLength": 1},
                        "evidence_slot_ids": {
                            "type": "array",
                            "items": {"enum": [slot.id for slot in plan.narrative_slots]},
                            "uniqueItems": True,
                            "maxItems": len(plan.narrative_slots),
                        },
                    },
                    ("key", "value", "evidence_slot_ids"),
                ),
                "maxItems": 4,
            },
            "media_proposals": {"type": "array", "maxItems": 0},
        },
        (
            "plan_id", "plan_revision", "revision", "narrative", "choices",
            "summary", "beats", "continuity_proposals", "media_proposals",
        ),
    )


def build_flat_fill_schema(plan: PassagePlan) -> dict[str, Any]:
    narrative = {slot.id: {"type": "string", "minLength": 1} for slot in plan.narrative_slots}
    choices = {
        slot.id: _strict_object(
            {"text": {"type": "string", "minLength": 1}, "hint": {"type": "string"}},
            ("text", "hint"),
        )
        for slot in plan.choice_slots
    }
    return _strict_object(
        {
            "plan_id": {"const": plan.plan_id},
            "plan_revision": {"const": plan.revision},
            "narrative": _strict_object(narrative, tuple(narrative)),
            "choices": _strict_object(choices, tuple(choices)),
            "summary": {"type": "string", "minLength": 1},
            "beats": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        },
        ("plan_id", "plan_revision", "narrative", "choices", "summary", "beats"),
    )


def _strict_object(properties: dict[str, Any], required: tuple[str, ...]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


__all__ = ["build_flat_fill_schema", "build_typed_fill_schema"]
