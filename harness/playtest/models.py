"""Data structures for the playtester (Phase 2 definitions).

Pure type definitions — no methods, no functions, no logic.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class IssueCategory(str, Enum):
    """Category of issue detected during playtesting."""
    console_error      = "console_error"
    broken_nav         = "broken_nav"
    dead_end           = "dead_end"
    raw_macro          = "raw_macro"
    blank_passage      = "blank_passage"
    broken_media       = "broken_media"
    sc_runtime_error   = "sc_runtime_error"
    infinite_loop      = "infinite_loop"
    markdown_leak      = "markdown_leak"


class IssueSeverity(str, Enum):
    """Severity level for a detected playtest issue."""
    blocker = "blocker"
    major   = "major"
    minor   = "minor"


class ConsoleMessage(BaseModel):
    """One console message captured from the browser during a playtest step."""
    type: str
    text: str
    url: str = ""


class ChoiceInfo(BaseModel):
    """A single navigational choice (link) discovered on a passage page."""
    text: str
    target: str = ""
    element_index: int
    is_external: bool = False


class PlaytestStep(BaseModel):
    """One step in the playtest exploration: a passage visit and its captured state."""
    step_number: int
    passage_id: str
    passage_type: str = ""
    passage_text: str = ""
    choices: list[ChoiceInfo] = Field(default_factory=list)
    choice_taken: Optional[ChoiceInfo] = None
    parent_step: Optional[int] = None
    screenshot_path: str = ""
    console_messages: list[ConsoleMessage] = Field(default_factory=list)
    visit_count: int = 1
    failed_media: list[str] = Field(default_factory=list)


class PlaytestIssue(BaseModel):
    """A single issue detected during a playtest run, with reproduction context."""
    id: str
    category: IssueCategory
    severity: IssueSeverity
    passage: str
    step_number: int
    description: str = ""
    screenshot_path: str = ""
    console_output: list[str] = Field(default_factory=list)
    reproduction_steps: list[str] = Field(default_factory=list)
    suggested_fix_area: str = ""


class PlaytestConfig(BaseModel):
    """Configuration for a playtest run, derived from CLI arguments."""
    project_path: str
    html_path: str = ""
    max_depth: int = 10
    timeout: int = 30
    no_screenshots: bool = False
    no_kanban: bool = False
    output_dir: str = "playtest_results"


class PlaytestReport(BaseModel):
    """Complete result of a playtest run, serialized to playtest_report.json."""
    story_html_path: str
    config: PlaytestConfig
    started_at: str = ""
    duration_seconds: float = 0.0
    total_steps: int = 0
    total_passages_visited: int = 0
    steps: list[PlaytestStep] = Field(default_factory=list)
    issues: list[PlaytestIssue] = Field(default_factory=list)
    console_log: list[ConsoleMessage] = Field(default_factory=list)
    sugarcube_loaded: bool = True
