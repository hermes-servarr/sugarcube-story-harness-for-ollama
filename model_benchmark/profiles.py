"""Named workload profiles for the built-in SugarCube benchmark."""
from __future__ import annotations

from itertools import product
from typing import Sequence


REFACTOR_PROFILE_NAMES = ("refactor-canary", "refactor-core")
PROFILE_NAMES = ("canary", "core", "full", *REFACTOR_PROFILE_NAMES)
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

CORE_MATRIX_CASES = (
    ("compact", "A"),
    ("compact", "C"),
    ("compact", "E"),
    ("compact", "G"),
    ("full", "A"),
    ("full", "B"),
    ("full", "D"),
    ("full", "F"),
    ("json", "B"),
    ("json", "C"),
    ("json", "F"),
    ("json", "H"),
    ("thinking", "D"),
    ("thinking", "E"),
    ("thinking", "G"),
    ("thinking", "H"),
)

CANARY_CAPABILITY_IDS = (
    "T0-HARNESS-COMPACT",
    "T0-HARNESS-JSON",
    "T1-HARNESS-STATE-FULL",
    "T2-HARNESS-FORM-JSON",
    "T3-HARNESS-CONTINUITY-M",
    "T3-HARNESS-CONVERSATION",
    "T7-HARNESS-DISTRACTOR",
    "T9-HARNESS-THINKING-XL",
)


def resolve_matrix_cases(
    profile: str,
    variants: Sequence[str],
    directions: Sequence[str],
) -> tuple[tuple[str, str], ...]:
    """Return ordered variant/direction pairs for a named or custom run."""
    if profile == "canary":
        return CANARY_MATRIX_CASES
    if profile == "core":
        return CORE_MATRIX_CASES
    if profile == "full":
        return tuple(product(ALL_VARIANTS, ALL_DIRECTIONS))
    if profile in REFACTOR_PROFILE_NAMES:
        return ()
    return tuple(product(variants, directions))
