"""Immutable, fingerprinted context passed to generation strategies."""
from __future__ import annotations

import json

from .contracts import StrictFrozenModel


class ContextPack(StrictFrozenModel):
    """Bounded story context with explicit trusted and untrusted sections."""

    premise: str = ""
    parent_passage_id: str = ""
    parent_summary: str = ""
    parent_prose: str = ""
    world_facts: tuple[str, ...] = ()
    entity_facts: tuple[str, ...] = ()
    open_threads: tuple[str, ...] = ()
    inspiration: str = ""
    story_recall: str = ""

    def render(self) -> str:
        """Render stable JSON; strategy prompts still label it untrusted data."""
        return json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )


__all__ = ["ContextPack"]
