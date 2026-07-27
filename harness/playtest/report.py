"""Output writer: directory tree, summary README, per-issue details, console log, full report."""
from __future__ import annotations

import json
import os

from harness.playtest.models import ConsoleMessage, PlaytestIssue, PlaytestReport


def ensure_output_dirs(output_dir: str) -> None:
    """Create the output directory tree (output_dir/, screenshots/, issues/)."""
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "screenshots"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "issues"), exist_ok=True)


def write_summary(output_dir: str, report: PlaytestReport) -> str:
    """Write the summary README.md and return its path."""
    path = os.path.join(output_dir, "README.md")
    lines: list[str] = []
    lines.append("# Playtest Summary Report")
    lines.append("")
    lines.append(f"**Story HTML:** {report.story_html_path}")
    lines.append(f"**Started at:** {report.started_at}")
    lines.append(f"**Duration:** {report.duration_seconds:.2f}s")
    lines.append(f"**SugarCube loaded:** {'Yes' if report.sugarcube_loaded else 'No'}")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append(f"- Total steps: **{report.total_steps}**")
    lines.append(f"- Total passages visited: **{report.total_passages_visited}**")
    lines.append(f"- Total issues: **{len(report.issues)}**")
    lines.append("")

    # Issue counts by severity
    blockers = [i for i in report.issues if i.severity.value == "blocker"]
    majors = [i for i in report.issues if i.severity.value == "major"]
    minors = [i for i in report.issues if i.severity.value == "minor"]
    lines.append("## Issues by Severity")
    lines.append("")
    lines.append(f"- Blockers: **{len(blockers)}**")
    lines.append(f"- Major: **{len(majors)}**")
    lines.append(f"- Minor: **{len(minors)}**")
    lines.append("")

    # Issue counts by category
    lines.append("## Issues by Category")
    lines.append("")
    categories: dict[str, int] = {}
    for issue in report.issues:
        cat = issue.category.value
        categories[cat] = categories.get(cat, 0) + 1
    if categories:
        for cat, count in sorted(categories.items()):
            lines.append(f"- {cat}: {count}")
    else:
        lines.append("- No issues detected")
    lines.append("")

    # Issue list
    if report.issues:
        lines.append("## Issue Details")
        lines.append("")
        for issue in report.issues:
            lines.append(f"### [{issue.severity.value.upper()}] {issue.id}")
            lines.append(f"- **Category:** {issue.category.value}")
            lines.append(f"- **Passage:** {issue.passage}")
            lines.append(f"- **Step:** {issue.step_number}")
            lines.append(f"- **Description:** {issue.description}")
            if issue.screenshot_path:
                lines.append(f"- **Screenshot:** {issue.screenshot_path}")
            if issue.suggested_fix_area:
                lines.append(f"- **Suggested fix area:** {issue.suggested_fix_area}")
            lines.append("")

    # Passages visited
    if report.steps:
        lines.append("## Passages Visited")
        lines.append("")
        lines.append("| Step | Passage ID | Type | Choices | Screenshot |")
        lines.append("|------|-----------|------|---------|------------|")
        for step in report.steps:
            lines.append(
                f"| {step.step_number} | {step.passage_id} | {step.passage_type or '-'} "
                f"| {len(step.choices)} | {step.screenshot_path or '-'} |"
            )
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def write_issue(output_dir: str, issue: PlaytestIssue) -> str:
    """Write a per-issue detail markdown file under issues/ and return its path."""
    issues_dir = os.path.join(output_dir, "issues")
    os.makedirs(issues_dir, exist_ok=True)
    path = os.path.join(issues_dir, f"{issue.id}.md")
    lines: list[str] = []
    lines.append(f"# Issue: {issue.id}")
    lines.append("")
    lines.append(f"**Category:** {issue.category.value}")
    lines.append(f"**Severity:** {issue.severity.value}")
    lines.append(f"**Passage:** {issue.passage}")
    lines.append(f"**Step:** {issue.step_number}")
    lines.append("")

    lines.append("## Description")
    lines.append("")
    lines.append(issue.description or "(no description)")
    lines.append("")

    if issue.screenshot_path:
        lines.append("## Screenshot")
        lines.append("")
        lines.append(f"`{issue.screenshot_path}`")
        lines.append("")

    if issue.console_output:
        lines.append("## Console Output")
        lines.append("")
        lines.append("```")
        for msg in issue.console_output:
            lines.append(msg)
        lines.append("```")
        lines.append("")

    if issue.reproduction_steps:
        lines.append("## Reproduction Steps")
        lines.append("")
        for idx, step in enumerate(issue.reproduction_steps, 1):
            lines.append(f"{idx}. {step}")
        lines.append("")

    if issue.suggested_fix_area:
        lines.append("## Suggested Fix Area")
        lines.append("")
        lines.append(issue.suggested_fix_area)
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def write_console_log(output_dir: str, console_messages: list[ConsoleMessage]) -> str:
    """Write the aggregated console log as JSON and return its path."""
    path = os.path.join(output_dir, "console_log.json")
    data = [m.model_dump() for m in console_messages]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


def write_full_report(output_dir: str, report: PlaytestReport) -> str:
    """Write the complete playtest report as JSON and return its path."""
    path = os.path.join(output_dir, "playtest_report.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2))
    return path
