"""Deterministic passage-plan constructors used by compatibility facades."""
from __future__ import annotations

import re
from collections.abc import Sequence

from ..models import ModelOutput
from .contracts import (
    ChoiceSlot,
    ExperienceProfile,
    NarrativeSlot,
    PassageMode,
    PassagePlan,
    StateEffect,
    StateOperation,
)


_MARKER_RE = re.compile(r"\{\{(state|entity):([a-z][a-z0-9_]{0,63})\}\}")


def build_legacy_passage_plan(
    output: ModelOutput,
    *,
    plan_id: str,
    revision: int = 1,
    passage_mode: PassageMode | str = PassageMode.NORMAL,
    choice_destinations: Sequence[str] = (),
    context_fingerprint: str = "",
    experience_profile: ExperienceProfile | None = None,
) -> PassagePlan:
    """Create a trusted compatibility plan from already-accepted legacy data.

    This adapter is deliberately not used for new model responses: it exists so
    historical ``ModelOutput`` values can cross the typed compiler boundary.
    """
    state_refs = [_state_id(name) for name in output.state]
    entity_refs: list[str] = []
    for kind, target in _MARKER_RE.findall(output.prose):
        bucket = state_refs if kind == "state" else entity_refs
        if target not in bucket:
            bucket.append(target)

    fixed_effects = tuple(
        StateEffect(
            component_id=f"scene_set_{index}",
            target=_state_id(target),
            operation=StateOperation.SET,
            value=value,
        )
        for index, (target, value) in enumerate(output.state.items())
    )
    choice_slots: list[ChoiceSlot] = []
    for index, choice in enumerate(output.choices):
        effects = tuple(
            StateEffect(
                component_id=f"choice_{index}_set_{effect_index}",
                target=_state_id(target),
                operation=StateOperation.SET,
                value=value,
            )
            for effect_index, (target, value) in enumerate(choice.state_writes.items())
        )
        for effect in effects:
            if effect.target not in state_refs:
                state_refs.append(effect.target)
        choice_slots.append(ChoiceSlot(
            id=f"choice_{index}",
            destination=(choice_destinations[index] if index < len(choice_destinations) else ""),
            effects=effects,
        ))

    profile = experience_profile or ExperienceProfile.story_driven()
    return PassagePlan(
        plan_id=plan_id,
        revision=revision,
        passage_mode=passage_mode,
        narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),),
        choice_slots=tuple(choice_slots),
        allowed_state_refs=tuple(state_refs),
        allowed_entity_refs=tuple(entity_refs),
        fixed_effects=fixed_effects,
        context_fingerprint=context_fingerprint,
        experience_profile_fingerprint=profile.fingerprint(),
    )


def _state_id(value: str) -> str:
    value = value.strip()
    return value[1:] if value.startswith("$") else value


__all__ = ["build_legacy_passage_plan"]
