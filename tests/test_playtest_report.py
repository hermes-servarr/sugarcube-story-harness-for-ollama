"""Unit tests for the report writer in harness/playtest/report.py.

Covers INV-5 (output directory structure) and INV-11 (JSON-serializable report).
"""
from __future__ import annotations

import json
import os
import tempfile

from harness.playtest.models import (
    ChoiceInfo, ConsoleMessage, IssueCategory, IssueSeverity,
    PlaytestConfig, PlaytestIssue, PlaytestReport, PlaytestStep,
)
from harness.playtest.report import (
    ensure_output_dirs,
    write_summary,
    write_issue,
    write_console_log,
    write_full_report,
)


def _make_report() -> PlaytestReport:
    """Build a small realistic report for testing."""
    step = PlaytestStep(
        step_number=1,
        passage_id="start",
        passage_type="normal",
        passage_text="Welcome to the game",
        choices=[ChoiceInfo(text="Go north", element_index=0)],
        screenshot_path="/tmp/001_start.png",
    )
    issue = PlaytestIssue(
        id="001_console_error",
        category=IssueCategory.console_error,
        severity=IssueSeverity.major,
        passage="start",
        step_number=1,
        description="Test error",
        console_output=["error msg"],
        reproduction_steps=["step 1", "step 2"],
        suggested_fix_area="story.json",
    )
    return PlaytestReport(
        story_html_path="/tmp/story.html",
        config=PlaytestConfig(project_path="/tmp"),
        started_at="2026-01-01T00:00:00",
        duration_seconds=1.5,
        total_steps=1,
        total_passages_visited=1,
        steps=[step],
        issues=[issue],
        console_log=[ConsoleMessage(type="error", text="error msg")],
        sugarcube_loaded=True,
    )


def test_ensure_output_dirs():
    with tempfile.TemporaryDirectory() as d:
        ensure_output_dirs(d)
        assert os.path.isdir(d)
        assert os.path.isdir(os.path.join(d, "screenshots"))
        assert os.path.isdir(os.path.join(d, "issues"))


def test_write_summary_creates_file():
    with tempfile.TemporaryDirectory() as d:
        path = write_summary(d, _make_report())
        assert os.path.isfile(path)
        assert path == os.path.join(d, "README.md")
        with open(path) as f:
            content = f.read()
        assert "Playtest Summary Report" in content
        assert "console_error" in content
        assert "start" in content


def test_write_summary_no_issues():
    rpt = _make_report()
    rpt.issues = []
    with tempfile.TemporaryDirectory() as d:
        path = write_summary(d, rpt)
        with open(path) as f:
            content = f.read()
        assert "No issues detected" in content


def test_write_issue_creates_file():
    issue = _make_report().issues[0]
    with tempfile.TemporaryDirectory() as d:
        path = write_issue(d, issue)
        assert os.path.isfile(path)
        assert path == os.path.join(d, "issues", "001_console_error.md")
        with open(path) as f:
            content = f.read()
        assert "001_console_error" in content
        assert "console_error" in content
        assert "Reproduction Steps" in content


def test_write_console_log():
    msgs = [ConsoleMessage(type="error", text="err"), ConsoleMessage(type="info", text="info")]
    with tempfile.TemporaryDirectory() as d:
        path = write_console_log(d, msgs)
        assert os.path.isfile(path)
        assert path == os.path.join(d, "console_log.json")
        with open(path) as f:
            data = json.load(f)
        assert len(data) == 2
        assert data[0]["type"] == "error"


def test_write_full_report():
    rpt = _make_report()
    with tempfile.TemporaryDirectory() as d:
        path = write_full_report(d, rpt)
        assert os.path.isfile(path)
        assert path == os.path.join(d, "playtest_report.json")
        with open(path) as f:
            data = json.load(f)
        assert data["story_html_path"] == "/tmp/story.html"
        assert data["total_steps"] == 1


def test_report_json_roundtrip():
    """INV-11: PlaytestReport round-trips through JSON without data loss."""
    rpt = _make_report()
    json_str = rpt.model_dump_json()
    restored = PlaytestReport.model_validate_json(json_str)
    assert restored.story_html_path == rpt.story_html_path
    assert restored.total_steps == rpt.total_steps
    assert len(restored.steps) == len(rpt.steps)
    assert restored.steps[0].passage_id == "start"
    assert len(restored.issues) == len(rpt.issues)
    assert restored.issues[0].category == IssueCategory.console_error
    assert len(restored.console_log) == len(rpt.console_log)


def test_output_dir_structure_complete():
    """INV-5: All 5 output paths exist after a full report write."""
    rpt = _make_report()
    with tempfile.TemporaryDirectory() as d:
        ensure_output_dirs(d)
        write_summary(d, rpt)
        write_issue(d, rpt.issues[0])
        write_console_log(d, rpt.console_log)
        write_full_report(d, rpt)
        assert os.path.isfile(os.path.join(d, "README.md"))
        assert os.path.isdir(os.path.join(d, "screenshots"))
        assert os.path.isdir(os.path.join(d, "issues"))
        assert os.path.isfile(os.path.join(d, "console_log.json"))
        assert os.path.isfile(os.path.join(d, "playtest_report.json"))
