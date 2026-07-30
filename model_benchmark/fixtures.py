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
    build_thinking_passage_prompt,
)
from model_benchmark.prompt_overlay import apply_prompt_overlay

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

# Complex state context (designed for thinking models)
# Multiple state variables, complex interdependencies that benefit from planning
FIXTURE_COMPLEX_STATE = FixtureContext(
    id="complex_state",
    premise="A rebel leader must coordinate three factions in a besieged city while managing dwindling supplies.",
    story_points="The leader must decide which faction to trust with a critical mission: the military, the scholars, or the underground.",
    arc_md="## Chapter 3: The Siege\nThree factions demand action. Supplies run low. Trust is currency.",
    snapshot="Location: Rebel HQ, besieged city. Time: Dawn. $militaryTrust = 40, $scholarTrust = 60, $undergroundTrust = 20, $supplies = 25, $hasMetGeneral = true, $hasMetScholar = true, $hasMetBroker = false.",
    entities="Characters: leader (protagonist), general (military faction, pragmatic), scholar (knowledge faction, idealistic), broker (underground faction, opportunistic, not yet met)",
    parent_prose="The rebel leader stared at the map, three faction markers glowing in the dim light of the command tent. Artillery fire echoed in the distance.",
    inspiration="Political thriller with multi-faction resource management and trust mechanics.",
)

# Multi-NPC social context (designed for thinking models)
# Requires reasoning about character motivations and relationships
FIXTURE_SOCIAL = FixtureContext(
    id="social",
    premise="A diplomat at a gala must navigate a web of alliances, secrets, and hidden agendas to secure a trade deal.",
    story_points="The diplomat must decide whether to confront a rival about a stolen document or use it as leverage quietly.",
    arc_md="## Chapter 2: The Gala\nThree nobles hold pieces of the puzzle. One of them is lying.",
    snapshot="Location: Palace ballroom. Time: Midnight. $hasMetDuke = true, $hasMetCountess = true, $hasMetBaron = false, $knowsSecret = false, $reputation = 70.",
    entities="Characters: diplomat (protagonist), duke (wealthy, suspicious), countess (charming, secretive), baron (ambitious, dangerous, not yet met)",
    parent_prose="The diplomat swirled their wine, watching the duke and countess exchange glances across the crowded ballroom. Something was being hidden.",
    inspiration="Court intrigue with social deduction and relationship tracking.",
)

# Puzzle context (designed for thinking models)
# Requires logical reasoning about state and consequences
FIXTURE_PUZZLE = FixtureContext(
    id="puzzle",
    premise="An archaeologist in an ancient temple must solve a sequence puzzle to unlock a chamber, but each wrong attempt triggers a trap.",
    story_points="The archaeologist must decide which combination of three runes to press based on clues found in the previous rooms.",
    arc_md="## Chapter 4: The Sealed Chamber\nThree runes. Three clues. One wrong move means death.",
    snapshot="Location: Temple inner chamber. Time: Unknown. $hasRuneClue1 = true, $hasRuneClue2 = true, $hasRuneClue3 = false, $trapArmed = true, $health = 80, $attempts = 0.",
    entities="Characters: archaeologist (protagonist), guardian spirit (ancient, enigmatic, bound to the temple)",
    parent_prose="The archaeologist knelt before the three rune slots, their torch casting flickering shadows on the ancient stone walls. Two clues were deciphered. One was still missing.",
    inspiration="Tomb Raider style puzzle-adventure with state-dependent consequences and logical deduction.",
)

# Registry: all available fixture contexts
FIXTURE_CONTEXTS: dict[str, FixtureContext] = {
    ctx.id: ctx for ctx in [
        FIXTURE_FANTASY,
        FIXTURE_SCIFI,
        FIXTURE_HORROR,
        FIXTURE_MODERN,
        FIXTURE_CYBERPUNK,
        FIXTURE_COMPLEX_STATE,
        FIXTURE_SOCIAL,
        FIXTURE_PUZZLE,
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
        prompt = build_compact_passage_prompt(
            premise=ctx.premise,
            story_points=ctx.story_points,
            arc_notes=ctx.arc_md,
            entities_text=ctx.entities,
            parent_prose=ctx.parent_prose,
            snapshot_text=ctx.snapshot,
            human_prompt=human_prompt,
        )
    elif variant == "full":
        prompt = build_full_passage_prompt(
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
        prompt = build_json_passage_prompt(
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
    elif variant == "thinking":
        prompt = build_thinking_passage_prompt(
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
    else:
        raise ValueError(f"Unknown variant: {variant}")
    return apply_prompt_overlay(prompt, variant=variant, direction=direction)


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

# ── Thinking variant dry-run fixture ──────────────────────────────────
# A response with chain-of-thought reasoning before the formatted output,
# separated by ===PASSAGE===. Tests the thinking extraction and scoring.
_THINKING_DRY_RUN_RESPONSE = """Let me analyze this scene before writing.

1. State analysis: The apprentice has $gold = 15 and $hasMetKing = false. The direction asks me to check inventory and set a flag, so I need to use <<set>> to update a variable. I'll set $hasReadBook to true since the scene involves discovering a tome.

2. Character motivations: The apprentice is curious but cautious. The mentor is absent but their influence is felt. The moral choice is between knowledge (read) and obedience (return).

3. SugarCube decisions: I need <<set $hasReadBook to true>> for the state change. I'll use ''italic'' for emphasis (not markdown). No <<if>> needed for this direction, just a straightforward state set.

4. Direction plan: The direction says "check inventory and set a flag". I'll reference $gold in the prose (naked interpolation) and use <<set>> for the flag.

5. Draft plan:
- Sensory: dust, moonlight, old leather smell
- Choice: read vs return (risk vs safety)
- Summary: discovery + moral choice

===PASSAGE===
PROSE:
The apprentice examined the tome carefully. ''This is remarkable!'' they whispered.
$gold glinted in their pouch as they weighed the decision.

<<set $hasReadBook to true>>

CHOICES:
- Open the book and read | A dangerous choice
- Return it to the mentor | The safe path

SUMMARY:
The apprentice discovered a magical tome and faced a moral choice.
"""
