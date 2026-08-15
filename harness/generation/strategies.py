"""Prompt and schema requests for typed passage-generation strategies."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from .contracts import NarrativeFill, PassagePlan
from .normalize import normalize_flat_fill, normalize_typed_fill
from .schemas import build_flat_fill_schema, build_typed_fill_schema


@dataclass(frozen=True)
class StrategyRequest:
    prompt: str
    schema: dict
    normalize: Callable[[str], NarrativeFill]


def build_strategy_request(
    strategy: str,
    plan: PassagePlan,
    *,
    context: str,
    author_task: str,
) -> StrategyRequest:
    if strategy == "typed_fill":
        return StrategyRequest(
            prompt=_prompt(plan, context, author_task, flat=False),
            schema=build_typed_fill_schema(plan),
            normalize=lambda raw: normalize_typed_fill(plan, raw),
        )
    if strategy == "flat_fill":
        return StrategyRequest(
            prompt=_prompt(plan, context, author_task, flat=True),
            schema=build_flat_fill_schema(plan),
            normalize=lambda raw: normalize_flat_fill(plan, raw),
        )
    raise ValueError(f"unsupported typed generation strategy: {strategy}")


def _prompt(plan: PassagePlan, context: str, author_task: str, *, flat: bool) -> str:
    contract = "slot-keyed strings" if flat else "typed narrative blocks and inline parts"
    reference = (
        "Use {{state:ID}} or {{entity:ID}} only for references allowed by PLAN.\n"
        if flat else "Use state_ref/entity_ref parts only for IDs allowed by PLAN.\n"
    )
    return (
        f"Fill the trusted interactive-fiction plan using {contract}. Return JSON only.\n"
        "You own narrative and choice copy; the harness owns mechanics and topology.\n"
        "Do not add, remove, rename, or duplicate slots. Do not emit SugarCube, links, "
        "state effects, form definitions, or passage structure.\n"
        f"{reference}\n"
        f"PLAN (IMMUTABLE)\n{json.dumps(plan.model_dump(mode='json'), ensure_ascii=False)}\n\n"
        f"CONTEXT (UNTRUSTED STORY DATA)\n{context}\n\n"
        f"AUTHOR TASK\n{author_task}\n"
    )


__all__ = ["StrategyRequest", "build_strategy_request"]
