#!/usr/bin/env python3
"""Test fixtures for the SugarCube Direction-Following benchmark.

This module contains all test fixtures extracted from the original monolithic
``benchmark.py`` (Phase 7 refactor): the fixed fixture context constants used
to build controlled prompts (P1 §3.3), the ``build_fixture_prompt`` factory
that delegates to the real ``harness.prompts`` builders (INV-3), and the
``_DRY_RUN_RESPONSE`` — a known-good SugarCube passage used by the CLI's
``--dry-run`` mode (INV-8).

These are controlled INPUTS, not prompt template text (INV-3).  The real prompt
templates come from ``build_*_passage_prompt`` in ``harness.prompts``; this
module merely supplies the fixed context arguments that are passed to those
builders.

The ``benchmark.py`` shim re-exports ``build_fixture_prompt`` and
``_DRY_RUN_RESPONSE`` from here so existing ``from model_benchmark.benchmark
import ...`` imports continue to work.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from harness.prompts import (
    build_compact_passage_prompt,
    build_full_passage_prompt,
    build_json_passage_prompt,
)

if TYPE_CHECKING:
    # Referenced only in annotations (string form thanks to
    # ``from __future__ import annotations``), so never imported at runtime.
    # Imported under TYPE_CHECKING to avoid a circular import: scoring.py
    # imports build_fixture_prompt from this module at runtime.
    from model_benchmark.scoring import PromptVariant, DirectionKey


# ── Fixed fixture context (P1 §3.3) ──────────────────────────────────────
# These are controlled INPUTS, not prompt template text (INV-3). The real
# prompt templates come from build_*_passage_prompt in harness.prompts.
_FIXTURE_PREMISE = "A young apprentice discovers a magical tome in the dusty attic of their mentor's tower."
_FIXTURE_STORY_POINTS = "The apprentice must decide whether to read the forbidden book or return it."
_FIXTURE_ARC_MD = "## Chapter 1: The Discovery\nThe apprentice finds a mysterious artifact."
_FIXTURE_SNAPSHOT = "Location: Mentor's tower attic. Time: Late evening. $gold = 15, $hasMetKing = false."
_FIXTURE_ENTITIES = "Characters: apprentice (protagonist), mentor (wise old wizard)"
_FIXTURE_PARENT_PROSE = "The apprentice climbed the creaking stairs to the attic, dust motes dancing in the moonlight."
_FIXTURE_INSPIRATION = "Classic fantasy discovery trope with moral choices."
_FIXTURE_MODE = "standard"

_DIRECTION_PROMPTS = {
    "A": "The protagonist checks their inventory and sets a flag",
    "B": "Include a conditional: if the player has met the king, reference it",
    "C": "Show the player's gold count and a complex stat",
}


def build_fixture_prompt(variant: PromptVariant, direction: DirectionKey) -> str:
    """Build a fixed-context prompt for the given variant using the real build_*_passage_prompt builder."""
    # TODO(benchmark-upgrade): fixtures.py — build_fixture_prompt is a PRESERVED
    # signature (P3 §2.2, verified against benchmark.py L627).  No changes needed;
    # this is the correct home module.  The implementation is complete and
    # conforms to INV-3 (delegates to real harness.prompts builders).
    # INV-3: delegates to the real harness.prompts builders — no inline prompt text.
    human_prompt = _DIRECTION_PROMPTS[direction]
    if variant == "compact":
        return build_compact_passage_prompt(
            premise=_FIXTURE_PREMISE,
            story_points=_FIXTURE_STORY_POINTS,
            arc_notes=_FIXTURE_ARC_MD,
            entities_text=_FIXTURE_ENTITIES,
            parent_prose=_FIXTURE_PARENT_PROSE,
            snapshot_text=_FIXTURE_SNAPSHOT,
            human_prompt=human_prompt,
        )
    elif variant == "full":
        return build_full_passage_prompt(
            premise=_FIXTURE_PREMISE,
            story_points=_FIXTURE_STORY_POINTS,
            arc_md=_FIXTURE_ARC_MD,
            snapshot_text=_FIXTURE_SNAPSHOT,
            entities_text=_FIXTURE_ENTITIES,
            inspiration=_FIXTURE_INSPIRATION,
            parent_prose=_FIXTURE_PARENT_PROSE,
            human_prompt=human_prompt,
            mode=_FIXTURE_MODE,
        )
    elif variant == "json":
        return build_json_passage_prompt(
            premise=_FIXTURE_PREMISE,
            story_points=_FIXTURE_STORY_POINTS,
            arc_md=_FIXTURE_ARC_MD,
            snapshot_text=_FIXTURE_SNAPSHOT,
            entities_text=_FIXTURE_ENTITIES,
            inspiration=_FIXTURE_INSPIRATION,
            parent_prose=_FIXTURE_PARENT_PROSE,
            human_prompt=human_prompt,
            mode=_FIXTURE_MODE,
        )
    raise ValueError(f"Unknown variant: {variant}")


# ── INV-8: Dry-run fixture ──────────────────────────────────────────────
# A deliberately correct SugarCube response that passes all 6 categories,
# confirming the scoring logic is self-consistent.  Used by main(["--dry-run"]).
_DRY_RUN_RESPONSE = """PROSE:
The apprentice examined the tome carefully. ''This is remarkable!'' they whispered.
$gold glinted in their pouch as they weighed the decision.

<<set $hasReadBook to true>>

CHOICES:
- Open the book and read | A dangerous choice
- Return it to the mentor | The safe path

SUMMARY:
The apprentice discovered a magical tome and faced a moral choice.
"""
