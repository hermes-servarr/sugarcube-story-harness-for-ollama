"""Named workload profiles for the built-in SugarCube benchmark."""
from __future__ import annotations

from itertools import product
from typing import Sequence


PROFILE_NAMES = ("canary", "core", "full")
ALL_VARIANTS = ("compact", "full", "json", "thinking")
ALL_DIRECTIONS = tuple("ABCDEFGH")

CANARY_MATRIX_CASES = (
    ("compact", "A"),
    ("full", "B"),
    ("json", "C"),
    ("thinking", "D"),
    ("compact", "E"),
    ("full", "F"),
    ("json", "G"),
    ("thinking", "H"),
)

CANARY_CAPABILITY_IDS = (
    "T0-MARKUP",
    "T1-STATE-READ-WRITE",
    "T2-BRANCH-STATE",
    "T3-SWITCH",
    "T4-LOOP-CAPTURE",
    "T5-FORM",
    "T6-RETRIEVE-S",
    "T6-RETRIEVE-XL",
    "T2-CONVERSATION-COMPACT",
    "T5-CONVERSATION-JSON",
    "T2-STYLE-CANT-COMPACT",
    "T9-THINKING-XL",
)


def resolve_matrix_cases(
    profile: str,
    variants: Sequence[str],
    directions: Sequence[str],
) -> tuple[tuple[str, str], ...]:
    """Return ordered variant/direction pairs for a named or custom run."""
    if profile == "canary":
        return CANARY_MATRIX_CASES
    if profile in {"core", "full"}:
        return tuple(product(ALL_VARIANTS, ALL_DIRECTIONS))
    return tuple(product(variants, directions))
