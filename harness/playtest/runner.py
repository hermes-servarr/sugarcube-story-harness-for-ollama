"""Playtest orchestrator: resolves HTML, drives browser/explorer/detector/report."""
from __future__ import annotations

import os
import subprocess
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page, Browser

from harness.playtest import browser as br
from harness.playtest import detector as det
from harness.playtest import explorer, report
from harness.playtest.models import (
    ChoiceInfo, ConsoleMessage, IssueCategory, PlaytestConfig,
    PlaytestIssue, PlaytestReport, PlaytestStep,
)


def resolve_html_path(config: PlaytestConfig) -> str:
    """Resolve the story.html path: use --html if given, else compile from project."""
    if config.html_path:
        if os.path.isfile(config.html_path):
            return config.html_path
        raise FileNotFoundError(
            f"story.html not found at: {config.html_path}\n"
            f"Hint: compile the project first with: uv run harness compile "
            f"{config.project_path}"
        )
    # Try default build location
    default_path = os.path.join(config.project_path, "build", "story.html")
    if os.path.isfile(default_path):
        return default_path
    # Try compiling
    try:
        result = subprocess.run(
            ["uv", "run", "harness", "compile", config.project_path],
            capture_output=True, text=True, timeout=120,
            cwd=config.project_path,
        )
        if result.returncode == 0 and os.path.isfile(default_path):
            return default_path
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    raise FileNotFoundError(
        f"story.html not found. Tried: {default_path}\n"
        f"Tweego may not be installed, or the project needs compilation.\n"
        f"Hint: provide a pre-compiled HTML via --html <path>, or run:\n"
        f"  uv run harness compile {config.project_path}"
    )


def run_playtest(config: PlaytestConfig) -> PlaytestReport:
    """Execute a full playtest run and return the complete report."""
    started_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    start_time = time.time()

    # Resolve the HTML path
    try:
        html_path = resolve_html_path(config)
    except FileNotFoundError as e:
        return PlaytestReport(
            story_html_path="",
            config=config,
            started_at=started_at,
            duration_seconds=time.time() - start_time,
            sugarcube_loaded=False,
            issues=[],
        )

    # Ensure output dirs exist
    report.ensure_output_dirs(config.output_dir)

    # Launch browser
    try:
        page = br.launch_browser()
    except Exception:
        return PlaytestReport(
            story_html_path=html_path,
            config=config,
            started_at=started_at,
            duration_seconds=time.time() - start_time,
            sugarcube_loaded=False,
        )

    all_console_messages: list[ConsoleMessage] = []
    seen_issues: set[tuple[str, str]] = set()
    issues: list[PlaytestIssue] = []

    try:
        # Set up console message capture
        page._console_messages = []  # type: ignore[attr-defined]
        def _on_console(msg):
            page._console_messages.append(msg)  # type: ignore[attr-defined]
        page.on("console", _on_console)

        # Load the HTML
        file_url = "file://" + os.path.abspath(html_path)
        br.load_page(page, file_url)

        # Verify SugarCube
        sc_loaded = br.verify_sugarcube(page)
        if not sc_loaded:
            return PlaytestReport(
                story_html_path=html_path,
                config=config,
                started_at=started_at,
                duration_seconds=time.time() - start_time,
                sugarcube_loaded=False,
            )

        # Explore the passage graph
        steps = explorer.explore(page, page._browser, config)  # type: ignore[attr-defined]

        # Run detectors at each step
        for step in steps:
            step_issues = _run_detectors_for_step(step, steps)
            for issue in step_issues:
                key = (issue.category.value, issue.passage)
                if key not in seen_issues:
                    seen_issues.add(key)
                    issues.append(issue)

        # Collect all console messages
        all_console_messages = br.get_console_messages(page)

    finally:
        try:
            br.close_browser(page._browser)  # type: ignore[attr-defined]
        except Exception:
            pass

    # Build the report
    visited_passages = {s.passage_id for s in steps}
    rpt = PlaytestReport(
        story_html_path=html_path,
        config=config,
        started_at=started_at,
        duration_seconds=time.time() - start_time,
        total_steps=len(steps),
        total_passages_visited=len(visited_passages),
        steps=steps,
        issues=issues,
        console_log=all_console_messages,
        sugarcube_loaded=True,
    )

    # Write output files
    report.write_summary(config.output_dir, rpt)
    for issue in issues:
        report.write_issue(config.output_dir, issue)
    report.write_console_log(config.output_dir, all_console_messages)
    report.write_full_report(config.output_dir, rpt)

    # Create kanban tasks unless --no-kanban
    if not config.no_kanban and issues:
        from harness.playtest import task_creator
        task_creator.create_tasks(issues, config.output_dir)

    return rpt


def _run_detectors_for_step(
    step: PlaytestStep, all_steps: list[PlaytestStep]
) -> list[PlaytestIssue]:
    """Run all applicable detectors for a single step."""
    issues: list[PlaytestIssue] = []

    # 1. Console errors
    issue = det.detect_console_errors(step.console_messages, step.passage_id, step.step_number)
    if issue:
        issue.screenshot_path = step.screenshot_path
        issues.append(issue)

    # 2. Broken navigation — check if parent step's choice led here
    if step.parent_step is not None and step.choice_taken:
        parent = next((s for s in all_steps if s.step_number == step.parent_step), None)
        if parent:
            # If the passage didn't change, it's a broken nav
            issue = det.detect_broken_navigation(
                parent.passage_id, step.passage_id, step.choice_taken, step.step_number
            )
            if issue:
                issue.screenshot_path = step.screenshot_path
                issues.append(issue)

    # 3. Dead end
    issue = det.detect_dead_end(step.passage_id, step.passage_type, step.choices, step.step_number)
    if issue:
        issue.screenshot_path = step.screenshot_path
        issues.append(issue)

    # 4. Raw macros
    issue = det.detect_raw_macros(step.passage_text, step.passage_id, step.step_number)
    if issue:
        issue.screenshot_path = step.screenshot_path
        issues.append(issue)

    # 5. Blank passage
    issue = det.detect_blank_passage(step.passage_text, step.passage_id, step.step_number)
    if issue:
        issue.screenshot_path = step.screenshot_path
        issues.append(issue)

    # 6. Broken media (wired per P5 Deviation 4 / INV-15)
    issue = det.detect_broken_media(step.failed_media, step.passage_id, step.step_number)
    if issue:
        issue.screenshot_path = step.screenshot_path
        issues.append(issue)

    # 7. SugarCube runtime errors
    issue = det.detect_sugarcube_errors(step.console_messages, step.passage_id, step.step_number)
    if issue:
        issue.screenshot_path = step.screenshot_path
        issues.append(issue)

    # 8. Infinite loop
    visit_counts = {step.passage_id: step.visit_count}
    issue = det.detect_infinite_loop(visit_counts, step.passage_id, step.step_number)
    if issue:
        issue.screenshot_path = step.screenshot_path
        issues.append(issue)

    return issues
