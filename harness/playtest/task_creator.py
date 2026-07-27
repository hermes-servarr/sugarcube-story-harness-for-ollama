"""Kanban task creation via hermes CLI subprocess."""
from __future__ import annotations

import subprocess

from harness.playtest.models import PlaytestIssue, IssueSeverity

_HERMES_BIN = "/opt/hermes/bin/hermes"


def create_tasks(issues: list[PlaytestIssue], output_dir: str) -> list[str]:
    """Create a kanban task for each issue via hermes CLI subprocess, return created task ids."""
    created: list[str] = []
    for issue in issues:
        title = _build_title(issue)
        body = _build_issue_body(issue, output_dir)
        task_id = _run_hermes_create(title, body)
        if task_id:
            created.append(task_id)
    return created


def _build_title(issue: PlaytestIssue) -> str:
    """Build the kanban task title: [Playtest] <severity>: <short description>."""
    short_desc = issue.description[:60] if issue.description else issue.category.value
    return f"[Playtest] {issue.severity.value}: {short_desc}"


def _build_issue_body(issue: PlaytestIssue, output_dir: str) -> str:
    """Build the kanban task body text from the issue details."""
    lines: list[str] = []
    lines.append(f"**Category:** {issue.category.value}")
    lines.append(f"**Severity:** {issue.severity.value}")
    lines.append(f"**Passage:** {issue.passage}")
    lines.append(f"**Step:** {issue.step_number}")
    lines.append("")
    lines.append(f"**Description:** {issue.description}")
    lines.append("")

    if issue.screenshot_path:
        lines.append(f"**Screenshot:** {issue.screenshot_path}")
        lines.append("")

    if issue.reproduction_steps:
        lines.append("**Reproduction Steps:**")
        for idx, step in enumerate(issue.reproduction_steps, 1):
            lines.append(f"{idx}. {step}")
        lines.append("")

    if issue.suggested_fix_area:
        lines.append(f"**Suggested Fix Area:** {issue.suggested_fix_area}")
        lines.append("")

    if issue.console_output:
        lines.append("**Console Output:**")
        lines.append("```")
        for msg in issue.console_output:
            lines.append(msg)
        lines.append("```")

    return "\n".join(lines)


def _run_hermes_create(title: str, body: str) -> str | None:
    """Run the hermes kanban create CLI command, return the created task id."""
    cmd = [
        _HERMES_BIN, "kanban", "create", title,
        "--triage",
        "--body", body,
        "--assignee", "default",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return None
        # Try to extract task id from stdout
        stdout = result.stdout.strip()
        # The CLI typically prints the task id
        for line in stdout.splitlines():
            if line.strip():
                return line.strip()
        return stdout or None
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return None
