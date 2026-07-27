"""Unit tests for the kanban task creator in harness/playtest/task_creator.py.

Covers INV-7 (correct CLI format).
"""
from __future__ import annotations

import subprocess
from unittest import mock

from harness.playtest.models import (
    IssueCategory, IssueSeverity, PlaytestIssue,
)
from harness.playtest.task_creator import create_tasks, _build_title, _build_issue_body


def _make_issue(severity=IssueSeverity.major, desc="broken link") -> PlaytestIssue:
    return PlaytestIssue(
        id="001_broken_nav",
        category=IssueCategory.broken_nav,
        severity=severity,
        passage="passage_A",
        step_number=2,
        description=desc,
        screenshot_path="/tmp/screenshot.png",
        console_output=["some error"],
        reproduction_steps=["step 1", "step 2"],
        suggested_fix_area="harness/passage.py",
    )


def test_build_title_format():
    """INV-7: Title is [Playtest] <severity>: <description>."""
    title = _build_title(_make_issue())
    assert title.startswith("[Playtest] major: ")
    assert "broken link" in title


def test_build_title_blocker():
    title = _build_title(_make_issue(severity=IssueSeverity.blocker))
    assert title.startswith("[Playtest] blocker: ")


def test_build_title_minor():
    title = _build_title(_make_issue(severity=IssueSeverity.minor))
    assert title.startswith("[Playtest] minor: ")


def test_build_issue_body_contains_required_fields():
    """INV-7: Body contains screenshot path and reproduction steps."""
    body = _build_issue_body(_make_issue(), "/tmp/output")
    assert "/tmp/screenshot.png" in body
    assert "step 1" in body
    assert "step 2" in body
    assert "harness/passage.py" in body
    assert "broken_nav" in body


def test_create_tasks_invokes_hermes_cli():
    """INV-7: create_tasks calls hermes kanban create with --triage and --assignee default."""
    with mock.patch("harness.playtest.task_creator.subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=0, stdout="t_12345\n", stderr="")
        issues = [_make_issue()]
        result = create_tasks(issues, "/tmp/output")
        assert len(result) == 1
        # Check the command was called
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert cmd[0] == "/opt/hermes/bin/hermes"
        assert "kanban" in cmd
        assert "create" in cmd
        assert "--triage" in cmd
        assert "--assignee" in cmd
        assert "default" in cmd
        # The title must start with [Playtest]
        title_arg = [a for a in cmd if isinstance(a, str) and a.startswith("[Playtest]")]
        assert len(title_arg) == 1


def test_create_tasks_multiple_issues():
    with mock.patch("harness.playtest.task_creator.subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=0, stdout="t_123\n", stderr="")
        issues = [_make_issue(), _make_issue()]
        result = create_tasks(issues, "/tmp/output")
        assert len(result) == 2
        assert mock_run.call_count == 2


def test_create_tasks_handles_failure():
    with mock.patch("harness.playtest.task_creator.subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=1, stdout="", stderr="error")
        issues = [_make_issue()]
        result = create_tasks(issues, "/tmp/output")
        assert len(result) == 0
