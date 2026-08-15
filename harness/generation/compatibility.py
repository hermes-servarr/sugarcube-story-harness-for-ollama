"""Compatibility adapters between legacy ``ModelOutput`` and typed drafts."""
from __future__ import annotations

import re

from ..models import ModelOutput, ParsedChoice
from .contracts import (
    EntityReferencePart,
    FilledChoiceSlot,
    FilledNarrativeSlot,
    NarrativeBlockKind,
    NarrativeFill,
    PassageDraft,
    PassagePlan,
    StateReferencePart,
    TextPart,
    assemble_passage_draft,
)


_REFERENCE_RE = re.compile(r"\{\{(state|entity):([a-z][a-z0-9_]{0,63})\}\}")


def model_output_to_fill(plan: PassagePlan, output: ModelOutput) -> NarrativeFill:
    """Strictly map accepted legacy content into the plan's fixed slots."""
    if len(plan.narrative_slots) == 1:
        prose_blocks = [output.prose.strip()]
    else:
        prose_blocks = [part.strip() for part in re.split(r"\n\s*\n", output.prose) if part.strip()]
    if len(prose_blocks) != len(plan.narrative_slots):
        raise ValueError("legacy prose does not match narrative slot cardinality")
    if len(output.choices) != len(plan.choice_slots):
        raise ValueError("legacy choices do not match choice slot cardinality")

    narrative = tuple(
        FilledNarrativeSlot(
            slot_id=slot.id,
            kind=slot.kind,
            speaker=slot.speaker,
            parts=_parts_from_text(text),
        )
        for slot, text in zip(plan.narrative_slots, prose_blocks, strict=True)
    )
    choices = tuple(
        FilledChoiceSlot(slot_id=slot.id, text=choice.text, hint=choice.hint)
        for slot, choice in zip(plan.choice_slots, output.choices, strict=True)
    )
    summary = output.summary.strip() or _first_sentence(output.prose)
    return NarrativeFill(
        plan_id=plan.plan_id,
        plan_revision=plan.revision,
        narrative=narrative,
        choices=choices,
        summary=summary,
        beats=tuple(output.beats) or (summary,),
    )


def model_output_to_draft(
    plan: PassagePlan,
    output: ModelOutput,
    *,
    draft_id: str | None = None,
    revision: int = 1,
) -> PassageDraft:
    return assemble_passage_draft(
        plan,
        model_output_to_fill(plan, output),
        draft_id=draft_id,
        revision=revision,
    )


def fill_to_model_output(fill: NarrativeFill) -> ModelOutput:
    """Return the readable legacy projection of a typed fill."""
    prose: list[str] = []
    for slot in fill.narrative:
        text = "".join(_part_to_marker(part) for part in slot.parts)
        if slot.kind == NarrativeBlockKind.DIALOGUE:
            prose.append(f'{slot.speaker}: "{text}"')
        elif slot.kind == NarrativeBlockKind.THOUGHT:
            prose.append(f"[{text}]")
        else:
            prose.append(text)
    return ModelOutput(
        prose="\n\n".join(prose),
        choices=[ParsedChoice(text=choice.text, hint=choice.hint) for choice in fill.choices],
        summary=fill.summary,
        beats=list(fill.beats),
    )


def _parts_from_text(text: str):
    parts = []
    cursor = 0
    for match in _REFERENCE_RE.finditer(text):
        if match.start() > cursor:
            parts.append(TextPart(text=text[cursor:match.start()]))
        if match.group(1) == "state":
            parts.append(StateReferencePart(target=match.group(2)))
        else:
            parts.append(EntityReferencePart(target=match.group(2)))
        cursor = match.end()
    if cursor < len(text):
        parts.append(TextPart(text=text[cursor:]))
    if not parts:
        raise ValueError("legacy prose cannot be empty")
    return tuple(parts)


def _part_to_marker(part) -> str:
    if isinstance(part, TextPart):
        return part.text
    kind = "state" if isinstance(part, StateReferencePart) else "entity"
    return f"{{{{{kind}:{part.target}}}}}"


def _first_sentence(prose: str) -> str:
    first = re.split(r"(?<=[.!?])\s", prose.strip())[0].strip()
    if not first:
        raise ValueError("legacy output needs prose or summary")
    return first[:150]


__all__ = ["fill_to_model_output", "model_output_to_draft", "model_output_to_fill"]
