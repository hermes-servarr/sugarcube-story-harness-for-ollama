"""Issue detection: 8 pure-function detectors.

All detectors are pure functions — they take data, not Playwright objects.
Each returns a ``PlaytestIssue | None`` (one issue or none).
"""
from __future__ import annotations

import re

from harness.playtest.models import (
    ChoiceInfo, ConsoleMessage, IssueCategory, IssueSeverity, PlaytestIssue,
)


def detect_console_errors(
    messages: list[ConsoleMessage], passage: str, step_number: int
) -> PlaytestIssue | None:
    """Return an issue if any error-level console messages were captured."""
    errors = [m for m in messages if m.type == "error"]
    if not errors:
        return None
    return PlaytestIssue(
        id=f"{step_number:03d}_console_error",
        category=IssueCategory.console_error,
        severity=IssueSeverity.major,
        passage=passage,
        step_number=step_number,
        description=f"{len(errors)} error-level console message(s) detected",
        console_output=[m.text for m in errors],
        reproduction_steps=[
            f"Navigate to passage '{passage}'",
            "Observe the browser console for error messages",
        ],
        suggested_fix_area="story.html / SugarCube macros",
    )


def detect_broken_navigation(
    before_passage: str, after_passage: str, choice: ChoiceInfo, step_number: int
) -> PlaytestIssue | None:
    """Return an issue if clicking a choice did not change the current passage."""
    if before_passage == after_passage:
        return PlaytestIssue(
            id=f"{step_number:03d}_broken_nav",
            category=IssueCategory.broken_nav,
            severity=IssueSeverity.major,
            passage=before_passage,
            step_number=step_number,
            description=(
                f"Clicking choice '{choice.text}' did not navigate away from "
                f"passage '{before_passage}'"
            ),
            reproduction_steps=[
                f"Navigate to passage '{before_passage}'",
                f"Click the choice '{choice.text}'",
                "Observe that the current passage remains unchanged",
            ],
            suggested_fix_area="harness/passage.py (link rendering) / story.json",
        )
    return None


def detect_dead_end(
    passage_id: str, passage_type: str, choices: list[ChoiceInfo], step_number: int
) -> PlaytestIssue | None:
    """Return an issue if a non-ending passage has no clickable choices."""
    internal_choices = [c for c in choices if not c.is_external]
    if internal_choices:
        return None
    if passage_type == "ending":
        return None
    return PlaytestIssue(
        id=f"{step_number:03d}_dead_end",
        category=IssueCategory.dead_end,
        severity=IssueSeverity.major,
        passage=passage_id,
        step_number=step_number,
        description=(
            f"Passage '{passage_id}' has no internal choices and is not typed "
            f"as 'ending' (type='{passage_type or 'unknown'}')"
        ),
        reproduction_steps=[
            f"Navigate to passage '{passage_id}'",
            "Observe that no clickable choices are available",
            "The passage is not marked as an ending — likely a dead end bug",
        ],
        suggested_fix_area="story.json / harness/passage.py",
    )


# Pattern for unrendered SugarCube macros: <<set>>, <<if>>, <<print>>, etc.
_RAW_MACRO_RE = re.compile(r"<<\s*/?\s*(set|if|print|goto|link|actions|switch|case|for|capture|silently|nobr|widget|button|textarea|textbox|checkbox|radio|listbox|number|dropdown|action|return|script|include|nobr)[^>]*>>", re.IGNORECASE)


def detect_raw_macros(
    page_text: str, passage_id: str, step_number: int
) -> PlaytestIssue | None:
    """Return an issue if unrendered SugarCube macro text is visible in passage content."""
    if not page_text:
        return None
    matches = _RAW_MACRO_RE.findall(page_text)
    if not matches:
        return None
    return PlaytestIssue(
        id=f"{step_number:03d}_raw_macro",
        category=IssueCategory.raw_macro,
        severity=IssueSeverity.major,
        passage=passage_id,
        step_number=step_number,
        description=(
            f"Unrendered SugarCube macro text detected in passage '{passage_id}': "
            + ", ".join(sorted(set(matches)))
        ),
        reproduction_steps=[
            f"Navigate to passage '{passage_id}'",
            "Observe raw macro syntax (e.g. <<set>>, <<if>>) visible in the rendered text",
        ],
        suggested_fix_area="harness/passage.py / story.json (macro syntax)",
    )


def detect_blank_passage(
    page_text: str, passage_id: str, step_number: int
) -> PlaytestIssue | None:
    """Return an issue if the passage body is empty or whitespace-only."""
    if page_text and page_text.strip():
        return None
    return PlaytestIssue(
        id=f"{step_number:03d}_blank_passage",
        category=IssueCategory.blank_passage,
        severity=IssueSeverity.major,
        passage=passage_id,
        step_number=step_number,
        description=f"Passage '{passage_id}' body is empty or whitespace-only",
        reproduction_steps=[
            f"Navigate to passage '{passage_id}'",
            "Observe that the passage content area is blank",
        ],
        suggested_fix_area="story.json (passage content) / harness/passage.py",
    )


def detect_broken_media(
    failed_media: list[str], passage_id: str, step_number: int
) -> PlaytestIssue | None:
    """Return an issue if any img/audio/video elements failed to load."""
    if not failed_media:
        return None
    return PlaytestIssue(
        id=f"{step_number:03d}_broken_media",
        category=IssueCategory.broken_media,
        severity=IssueSeverity.minor,
        passage=passage_id,
        step_number=step_number,
        description=(
            f"{len(failed_media)} broken media element(s) in passage "
            f"'{passage_id}': " + "; ".join(failed_media[:5])
        ),
        reproduction_steps=[
            f"Navigate to passage '{passage_id}'",
            "Observe that media elements (img/audio/video) fail to load",
        ],
        suggested_fix_area="harness/media.py / story.json (media paths)",
    )


def detect_sugarcube_errors(
    messages: list[ConsoleMessage], passage: str, step_number: int
) -> PlaytestIssue | None:
    """Return an issue if SugarCube runtime errors appear in console messages."""
    sc_errors = [
        m for m in messages
        if m.type == "error" and "sugarcube" in m.text.lower()
    ]
    if not sc_errors:
        return None
    return PlaytestIssue(
        id=f"{step_number:03d}_sc_runtime_error",
        category=IssueCategory.sc_runtime_error,
        severity=IssueSeverity.blocker,
        passage=passage,
        step_number=step_number,
        description=(
            f"SugarCube runtime error(s) detected in passage '{passage}': "
            + "; ".join(m.text[:80] for m in sc_errors[:3])
        ),
        console_output=[m.text for m in sc_errors],
        reproduction_steps=[
            f"Navigate to passage '{passage}'",
            "Observe SugarCube runtime errors in the browser console",
        ],
        suggested_fix_area="harness/passage.py / story.json (macro expressions)",
    )


def detect_infinite_loop(
    visit_counts: dict[str, int], passage_id: str, step_number: int, threshold: int = 3
) -> PlaytestIssue | None:
    """Return an issue if a passage was visited more than threshold times in one path."""
    count = visit_counts.get(passage_id, 0)
    if count <= threshold:
        return None
    return PlaytestIssue(
        id=f"{step_number:03d}_infinite_loop",
        category=IssueCategory.infinite_loop,
        severity=IssueSeverity.blocker,
        passage=passage_id,
        step_number=step_number,
        description=(
            f"Passage '{passage_id}' visited {count} times in one path "
            f"(threshold={threshold}) — possible infinite loop"
        ),
        reproduction_steps=[
            "Start from the beginning passage",
            f"Follow the path that leads to passage '{passage_id}'",
            f"Observe that the same passage is revisited {count} times",
        ],
        suggested_fix_area="story.json / harness/passage.py (passage links)",
    )


def detect_markdown_leak(
    page_text: str, passage_id: str, step_number: int
) -> PlaytestIssue | None:
    r"""Detect unrendered markdown formatting visible in rendered passage text.

    SugarCube does not render ``**bold**`` or ``*italic*`` — these appear as
    literal asterisks in the browser. The playtester sees the rendered output,
    so finding ``**`` or stray ``*`` in the visible text means the LLM emitted
    markdown instead of SugarCube markup (``''bold''`` / ``//italic//``).
    """
    if not page_text:
        return None
    # Look for **text** or *text* in the RENDERED text (what the player sees)
    # In rendered text, ** should never appear unless markdown leaked through
    import re as _re
    bold_re = _re.compile(r'\*\*([^*]+?)\*\*')
    matches = bold_re.findall(page_text)
    if not matches:
        return None
    return PlaytestIssue(
        id=f"{step_number:03d}_markdown_leak",
        category=IssueCategory.markdown_leak,
        severity=IssueSeverity.minor,
        passage=passage_id,
        step_number=step_number,
        description=(
            f"Unrendered markdown **bold** detected in passage '{passage_id}': "
            + ", ".join(matches[:5])
        ),
        reproduction_steps=[
            f"Navigate to passage '{passage_id}'",
            "Observe literal ** asterisks in the rendered text",
            "The LLM generated markdown instead of SugarCube ''bold'' markup",
        ],
        suggested_fix_area="harness/prompts.py / harness/generators.py (markup conversion)",
    )
