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

from dataclasses import dataclass
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


# ── Fixture contexts (P1 §3.3 + benchmark expansion 2026-07-30) ───────────
# Each context is a controlled INPUT, not prompt template text (INV-3).
# The real prompt templates come from build_*_passage_prompt in harness.prompts.
# Multiple contexts test whether models generalize SugarCube compliance across
# genres, not just one fantasy scenario.

@dataclass(frozen=True)
class FixtureContext:
    """A fixed story context used to build controlled benchmark prompts."""
    id: str
    premise: str
    story_points: str
    arc_md: str
    snapshot: str
    entities: str
    parent_prose: str
    inspiration: str
    mode: str = "standard"


# Original fantasy context
FIXTURE_FANTASY = FixtureContext(
    id="fantasy",
    premise="A young apprentice discovers a magical tome in the dusty attic of their mentor's tower.",
    story_points="The apprentice must decide whether to read the forbidden book or return it.",
    arc_md="## Chapter 1: The Discovery\nThe apprentice finds a mysterious artifact.",
    snapshot="Location: Mentor's tower attic. Time: Late evening. $gold = 15, $hasMetKing = false.",
    entities="Characters: apprentice (protagonist), mentor (wise old wizard)",
    parent_prose="The apprentice climbed the creaking stairs to the attic, dust motes dancing in the moonlight.",
    inspiration="Classic fantasy discovery trope with moral choices.",
)

# Sci-fi context
FIXTURE_SCIFI = FixtureContext(
    id="scifi",
    premise="A shuttle pilot discovers an alien artifact hidden in the cargo bay of a derelict station.",
    story_points="The pilot must decide whether to activate the artifact or report it to Central Command.",
    arc_md="## Chapter 1: The Signal\nA faint energy reading draws the pilot to the cargo bay.",
    snapshot="Location: Derelict station cargo bay. Time: Ship night cycle. $fuel = 40, $hasMetAliens = false.",
    entities="Characters: pilot (protagonist), ARIA (ship AI companion)",
    parent_prose="The pilot floated through the zero-g corridor, emergency lights flickering in the darkness.",
    inspiration="Hard sci-fi first-contact trope with isolation and trust themes.",
)

# Horror context
FIXTURE_HORROR = FixtureContext(
    id="horror",
    premise="A journalist enters an abandoned asylum following anonymous tips about missing persons.",
    story_points="The journalist must decide whether to descend into the basement or leave and call for help.",
    arc_md="## Chapter 1: The Tip\nAnonymous source describes sounds coming from the old asylum basement.",
    snapshot="Location: Asylum main hall. Time: 2 AM. $sanity = 80, $hasFlashlight = true.",
    entities="Characters: journalist (protagonist), entity (unknown presence)",
    parent_prose="The journalist pushed open the rusted door, the smell of decay hitting like a wall.",
    inspiration="Psychological horror with unreliable perception and isolation.",
)

# Modern detective context
FIXTURE_MODERN = FixtureContext(
    id="modern",
    premise="A detective interviews a suspect in a downtown precinct over a missing person case.",
    story_points="The detective must decide whether to press the suspect harder or let them go and follow them.",
    arc_md="## Chapter 1: The Interview\nThe suspect arrived with a lawyer, but something feels off.",
    snapshot="Location: Precinct interview room. Time: 11 PM. $evidence = 3, $hasConfession = false.",
    entities="Characters: detective (protagonist), suspect (nervous, evasive), lawyer (silent observer)",
    parent_prose="The detective studied the suspect across the metal table, fluorescent lights buzzing overhead.",
    inspiration=" Noir detective procedural with tension and psychological maneuvering.",
)

# Cyberpunk context
FIXTURE_CYBERPUNK = FixtureContext(
    id="cyberpunk",
    premise="A netrunner finds an unguarded corporate data vault while browsing the grid.",
    story_points="The netrunner must decide whether to steal the data or report the vulnerability for a bounty.",
    arc_md="## Chapter 1: The Vault\nAn unencrypted node pulses in the corporate grid.",
    snapshot="Location: Corporate grid node. Time: 3 AM real-time. $credsticks = 200, $heat = 15.",
    entities="Characters: netrunner (protagonist), fixer (contact, not present), daemons (IC programs)",
    parent_prose="The netrunner jacked in, neon data streams erupting around them as they entered the corporate grid.",
    inspiration="Cyberpunk heist trope with corporate espionage and moral ambiguity.",
)

# Registry: all available fixture contexts
FIXTURE_CONTEXTS: dict[str, FixtureContext] = {
    ctx.id: ctx for ctx in [
        FIXTURE_FANTASY,
        FIXTURE_SCIFI,
        FIXTURE_HORROR,
        FIXTURE_MODERN,
        FIXTURE_CYBERPUNK,
    ]
}

# Default context for backward compatibility
_DEFAULT_CONTEXT = FIXTURE_FANTASY


_DIRECTION_PROMPTS = {
    # Original directions A-C (basic SugarCube features)
    "A": "The protagonist checks their inventory and sets a flag",
    "B": "Include a conditional: if the player has met the king, reference it",
    "C": "Show the player's gold count and a complex stat",
    # New directions D-H (advanced SugarCube features, added 2026-07-30)
    "D": "Include a shared scene using the <<include>> macro to reference another passage",
    "E": "Use a <<capture>> block inside a <<for>> loop iterating over a list of items",
    "F": "Create a form passage with input macros: <<textbox>> for a name and <<radiobutton>> for a choice",
    "G": "Iterate over the player's inventory using a <<for>> loop and display each item with <<print>>",
    "H": "Use <<switch>> and <<case>> to branch on the player's current location variable",
}


def build_fixture_prompt(
    variant: PromptVariant,
    direction: DirectionKey,
    context_id: str = "fantasy",
) -> str:
    """Build a fixed-context prompt for the given variant using the real build_*_passage_prompt builder.

    Args:
        variant: Prompt variant (compact, full, json).
        direction: Direction key (A-H).
        context_id: Fixture context ID (fantasy, scifi, horror, modern, cyberpunk).
                   Defaults to "fantasy" for backward compatibility.
    """
    # TODO(benchmark-upgrade): fixtures.py — build_fixture_prompt is a PRESERVED
    # signature (P3 §2.2, verified against benchmark.py L627).  No changes needed;
    # this is the correct home module.  The implementation is complete and
    # conforms to INV-3 (delegates to real harness.prompts builders).
    ctx = FIXTURE_CONTEXTS.get(context_id, _DEFAULT_CONTEXT)
    # INV-3: delegates to the real harness.prompts builders — no inline prompt text.
    human_prompt = _DIRECTION_PROMPTS[direction]
    if variant == "compact":
        return build_compact_passage_prompt(
            premise=ctx.premise,
            story_points=ctx.story_points,
            arc_notes=ctx.arc_md,
            entities_text=ctx.entities,
            parent_prose=ctx.parent_prose,
            snapshot_text=ctx.snapshot,
            human_prompt=human_prompt,
        )
    elif variant == "full":
        return build_full_passage_prompt(
            premise=ctx.premise,
            story_points=ctx.story_points,
            arc_md=ctx.arc_md,
            snapshot_text=ctx.snapshot,
            entities_text=ctx.entities,
            inspiration=ctx.inspiration,
            parent_prose=ctx.parent_prose,
            human_prompt=human_prompt,
            mode=ctx.mode,
        )
    elif variant == "json":
        return build_json_passage_prompt(
            premise=ctx.premise,
            story_points=ctx.story_points,
            arc_md=ctx.arc_md,
            snapshot_text=ctx.snapshot,
            entities_text=ctx.entities,
            inspiration=ctx.inspiration,
            parent_prose=ctx.parent_prose,
            human_prompt=human_prompt,
            mode=ctx.mode,
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
