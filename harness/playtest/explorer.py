"""DFS passage graph explorer with browser backtracking."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page, Browser

from harness.playtest import browser as br
from harness.playtest.models import (
    ChoiceInfo, ConsoleMessage, PlaytestConfig, PlaytestStep,
)


def explore(page: Page, browser: Browser, config: PlaytestConfig) -> list[PlaytestStep]:
    """DFS-explore the passage graph up to max_depth, returning all steps with captured state.

    Uses browser back navigation to return to parent passages after exploring
    each branch. Falls back to page reload if back navigation fails.
    """
    steps: list[PlaytestStep] = []
    step_counter = [0]  # mutable counter for nested function

    start_passage = br.get_current_passage(page) or "start"
    file_url = page.url

    def _dfs(passage_id: str, depth: int, parent_step: int | None,
             choice_taken: ChoiceInfo | None, path_visits: dict[str, int]) -> None:
        if depth > config.max_depth:
            return
        if path_visits.get(passage_id, 0) > 3:
            return

        step_counter[0] += 1
        step_num = step_counter[0]
        visit_count = path_visits.get(passage_id, 0) + 1

        # Capture the current page state
        step = _capture_step(
            page, step_num, passage_id, parent_step, choice_taken,
            visit_count, config,
        )
        steps.append(step)

        # Update path visits for children
        new_path_visits = dict(path_visits)
        new_path_visits[passage_id] = visit_count

        # Explore each internal choice
        for choice in step.choices:
            if choice.is_external:
                continue
            target = choice.target or choice.text
            if not target:
                continue
            if new_path_visits.get(target, 0) >= 3:
                continue

            # Click the choice to navigate
            br.click_choice(page, choice.element_index)
            after_passage = br.get_current_passage(page) or target

            # Recursively explore the child
            _dfs(after_passage, depth + 1, step_num, choice, dict(new_path_visits))

            # Go back to the current passage for the next choice
            _go_back(page, file_url, config.timeout)

    _dfs(start_passage, 0, None, None, {})
    return steps


def _go_back(page: Page, file_url: str, timeout: int) -> None:
    """Navigate back to the previous page, with reload fallback."""
    try:
        page.go_back(timeout=timeout * 1000, wait_until="domcontentloaded")
        page.wait_for_timeout(200)
    except Exception:
        # If go_back fails (e.g., no history for JS-based navigation),
        # reload the start page
        try:
            page.goto(file_url, wait_until="domcontentloaded", timeout=timeout * 1000)
        except Exception:
            pass


def _capture_step(
    page: Page,
    step_number: int,
    passage_id: str,
    parent_step: int | None,
    choice_taken: ChoiceInfo | None,
    visit_count: int,
    config: PlaytestConfig,
) -> PlaytestStep:
    """Capture the current page state into a PlaytestStep."""
    passage_type = br.get_passage_type(page)
    passage_text = br.get_page_text(page)
    choices = br.get_choices(page)
    console_messages = br.get_console_messages(page)
    failed_media = br.check_media_loads(page)

    screenshot_path = ""
    if not config.no_screenshots:
        screenshot_path = os.path.join(
            config.output_dir, "screenshots",
            f"{step_number:03d}_{passage_id}.png"
        )
        br.take_screenshot(page, screenshot_path)

    return PlaytestStep(
        step_number=step_number,
        passage_id=passage_id,
        passage_type=passage_type,
        passage_text=passage_text,
        choices=choices,
        choice_taken=choice_taken,
        parent_step=parent_step,
        screenshot_path=screenshot_path,
        console_messages=console_messages,
        visit_count=visit_count,
        failed_media=failed_media,
    )
