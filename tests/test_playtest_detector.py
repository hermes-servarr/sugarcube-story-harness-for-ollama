"""Unit tests for the 8 issue detectors in harness/playtest/detector.py.

Covers INV-6 (all 8 categories detectable) and INV-10 (pure functions, no Playwright).
"""
from __future__ import annotations

from harness.playtest.models import (
    ChoiceInfo, ConsoleMessage, IssueCategory, IssueSeverity,
)
from harness.playtest.detector import (
    detect_console_errors,
    detect_broken_navigation,
    detect_dead_end,
    detect_raw_macros,
    detect_blank_passage,
    detect_broken_media,
    detect_sugarcube_errors,
    detect_infinite_loop,
)


# --- Console errors ---

def test_detect_console_errors_fires():
    msgs = [ConsoleMessage(type="error", text="Uncaught TypeError")]
    issue = detect_console_errors(msgs, "passage_A", 1)
    assert issue is not None
    assert issue.category == IssueCategory.console_error
    assert issue.severity == IssueSeverity.major
    assert issue.passage == "passage_A"

def test_detect_console_errors_no_fire():
    msgs = [ConsoleMessage(type="info", text="hello")]
    assert detect_console_errors(msgs, "passage_A", 1) is None

def test_detect_console_errors_multiple():
    msgs = [
        ConsoleMessage(type="error", text="err1"),
        ConsoleMessage(type="error", text="err2"),
    ]
    issue = detect_console_errors(msgs, "p", 1)
    assert issue is not None
    assert len(issue.console_output) == 2


# --- Broken navigation ---

def test_detect_broken_nav_fires():
    choice = ChoiceInfo(text="click me", element_index=0)
    issue = detect_broken_navigation("passage_A", "passage_A", choice, 2)
    assert issue is not None
    assert issue.category == IssueCategory.broken_nav
    assert issue.severity == IssueSeverity.major

def test_detect_broken_nav_no_fire():
    choice = ChoiceInfo(text="click me", element_index=0)
    assert detect_broken_navigation("A", "B", choice, 2) is None


# --- Dead end ---

def test_detect_dead_end_fires():
    issue = detect_dead_end("passage_A", "normal", [], 1)
    assert issue is not None
    assert issue.category == IssueCategory.dead_end

def test_detect_dead_end_ending_no_fire():
    issue = detect_dead_end("passage_A", "ending", [], 1)
    assert issue is None

def test_detect_dead_end_with_choices_no_fire():
    choices = [ChoiceInfo(text="go", element_index=0)]
    assert detect_dead_end("passage_A", "normal", choices, 1) is None

def test_detect_dead_end_external_only_fires():
    choices = [ChoiceInfo(text="link", element_index=0, is_external=True)]
    issue = detect_dead_end("p", "normal", choices, 1)
    assert issue is not None


# --- Raw macros ---

def test_detect_raw_macros_fires():
    text = "Hello <<set $x = 1>> world"
    issue = detect_raw_macros(text, "p", 1)
    assert issue is not None
    assert issue.category == IssueCategory.raw_macro

def test_detect_raw_macros_if_fires():
    text = "<<if $x>>Something<</if>>"
    issue = detect_raw_macros(text, "p", 1)
    assert issue is not None

def test_detect_raw_macros_no_fire():
    assert detect_raw_macros("Normal text without macros", "p", 1) is None

def test_detect_raw_macros_empty_text_no_fire():
    assert detect_raw_macros("", "p", 1) is None


# --- Blank passage ---

def test_detect_blank_passage_fires_empty():
    assert detect_blank_passage("", "p", 1) is not None

def test_detect_blank_passage_fires_whitespace():
    assert detect_blank_passage("   \n\t  ", "p", 1) is not None

def test_detect_blank_passage_no_fire():
    assert detect_blank_passage("Some content", "p", 1) is None


# --- Broken media ---

def test_detect_broken_media_fires():
    issue = detect_broken_media(["img: broken.png"], "p", 1)
    assert issue is not None
    assert issue.category == IssueCategory.broken_media
    assert issue.severity == IssueSeverity.minor

def test_detect_broken_media_no_fire():
    assert detect_broken_media([], "p", 1) is None

def test_detect_broken_media_multiple():
    media = ["img: a.png", "audio: b.mp3"]
    issue = detect_broken_media(media, "p", 1)
    assert issue is not None
    assert "a.png" in issue.description


# --- SugarCube runtime errors ---

def test_detect_sc_errors_fires():
    msgs = [ConsoleMessage(type="error", text="SugarCube: bad macro")]
    issue = detect_sugarcube_errors(msgs, "p", 1)
    assert issue is not None
    assert issue.category == IssueCategory.sc_runtime_error
    assert issue.severity == IssueSeverity.blocker

def test_detect_sc_errors_no_fire():
    msgs = [ConsoleMessage(type="error", text="some other error")]
    assert detect_sugarcube_errors(msgs, "p", 1) is None

def test_detect_sc_errors_no_fire_non_error():
    msgs = [ConsoleMessage(type="info", text="SugarCube loaded")]
    assert detect_sugarcube_errors(msgs, "p", 1) is None


# --- Infinite loop ---

def test_detect_infinite_loop_fires():
    counts = {"passage_A": 4}
    issue = detect_infinite_loop(counts, "passage_A", 5)
    assert issue is not None
    assert issue.category == IssueCategory.infinite_loop
    assert issue.severity == IssueSeverity.blocker

def test_detect_infinite_loop_no_fire():
    counts = {"passage_A": 2}
    assert detect_infinite_loop(counts, "passage_A", 5) is None

def test_detect_infinite_loop_boundary():
    counts = {"passage_A": 3}
    assert detect_infinite_loop(counts, "passage_A", 5) is None  # threshold=3, 3 is not > 3

def test_detect_infinite_loop_custom_threshold():
    counts = {"passage_A": 3}
    issue = detect_infinite_loop(counts, "passage_A", 5, threshold=2)
    assert issue is not None
