"""Normalize model strategy responses into one production NarrativeFill."""
from __future__ import annotations

import re

from ..parsers import parse_json_object
from .contracts import (
    EntityReferencePart,
    NarrativeFill,
    PassagePlan,
    StateReferencePart,
)


_REFERENCE_RE = re.compile(r"\{\{(state|entity):([a-z][a-z0-9_]{0,63})\}\}")


def normalize_typed_fill(plan: PassagePlan, raw: str) -> NarrativeFill:
    data = parse_json_object(raw)
    if not isinstance(data, dict):
        raise ValueError("typed_fill response contained no JSON object")
    fill = NarrativeFill.model_validate(data)
    _verify_identity(plan, fill)
    return fill


def normalize_flat_fill(plan: PassagePlan, raw: str) -> NarrativeFill:
    data = parse_json_object(raw)
    if not isinstance(data, dict) or set(data) != {
        "plan_id", "plan_revision", "narrative", "choices", "summary", "beats",
    }:
        raise ValueError("flat_fill fields do not match the contract")
    narrative = data["narrative"]
    choices = data["choices"]
    if not isinstance(narrative, dict) or not isinstance(choices, dict):
        raise ValueError("flat_fill narrative and choices must be objects")
    expected_narrative = {slot.id for slot in plan.narrative_slots}
    expected_choices = {slot.id for slot in plan.choice_slots}
    if set(narrative) != expected_narrative or set(choices) != expected_choices:
        raise ValueError("flat_fill slot keys do not match the plan")
    payload = {
        "plan_id": data["plan_id"],
        "plan_revision": data["plan_revision"],
        "narrative": [
            {
                "slot_id": slot.id,
                "kind": slot.kind.value,
                "speaker": slot.speaker,
                "parts": _parts(narrative[slot.id]),
            }
            for slot in plan.narrative_slots
        ],
        "choices": [
            {"slot_id": slot.id, **choices[slot.id]}
            for slot in plan.choice_slots
        ],
        "summary": data["summary"],
        "beats": data["beats"],
    }
    fill = NarrativeFill.model_validate(payload)
    _verify_identity(plan, fill)
    return fill


def _parts(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("flat narrative slot must be non-empty text")
    parts = []
    cursor = 0
    for match in _REFERENCE_RE.finditer(value):
        if match.start() > cursor:
            parts.append({"kind": "text", "text": value[cursor:match.start()]})
        parts.append({"kind": f"{match.group(1)}_ref", "target": match.group(2)})
        cursor = match.end()
    if cursor < len(value):
        parts.append({"kind": "text", "text": value[cursor:]})
    return parts


def _verify_identity(plan: PassagePlan, fill: NarrativeFill) -> None:
    if fill.plan_id != plan.plan_id or fill.plan_revision != plan.revision:
        raise ValueError("fill references a stale or different plan")

    expected_narrative = {slot.id: slot for slot in plan.narrative_slots}
    actual_narrative = {slot.slot_id: slot for slot in fill.narrative}
    if (
        len(actual_narrative) != len(fill.narrative)
        or set(actual_narrative) != set(expected_narrative)
    ):
        raise ValueError("narrative slots do not match the plan")
    for slot_id, value in actual_narrative.items():
        authority = expected_narrative[slot_id]
        if value.kind != authority.kind or value.speaker != authority.speaker:
            raise ValueError(f"narrative slot {slot_id} metadata does not match the plan")
        for part in value.parts:
            if (
                isinstance(part, StateReferencePart)
                and part.target not in plan.allowed_state_refs
            ):
                raise ValueError(f"unauthorized state reference: {part.target}")
            if (
                isinstance(part, EntityReferencePart)
                and part.target not in plan.allowed_entity_refs
            ):
                raise ValueError(f"unauthorized entity reference: {part.target}")

    expected_choices = {slot.id for slot in plan.choice_slots}
    actual_choices = [slot.slot_id for slot in fill.choices]
    if len(set(actual_choices)) != len(actual_choices) or set(actual_choices) != expected_choices:
        raise ValueError("choice slots do not match the plan")


__all__ = ["normalize_flat_fill", "normalize_typed_fill"]
