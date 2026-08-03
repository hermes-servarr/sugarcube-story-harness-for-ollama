#!/usr/bin/env python3
"""Benchmark execution loop with progress, checkpoint/resume, and dry-run.

This module implements the execution layer of the model benchmark upgrade
(``p1_research.md`` §4.1 module ``runner.py``, §4.4 checkpointing, §4.5
progress reporting).  It provides a :class:`BenchmarkRunner` that:

1. **Iterates over models × prompt-variants × directions × repetitions**
   (the nested loop described in §3 of the research doc) producing one
   :class:`~model_benchmark.schema.ResultRecord` per case.
2. **Displays progress** to ``stderr`` — a simple percentage/counter line
   (``tqdm`` is not a project dependency; see ``pyproject.toml``).  Progress
   is throttled to one line per completed case (plus a final summary).
3. **Saves checkpoint files** to disk at a configurable interval (every N
   completed items and/or every T seconds) using an **atomic write**
   (``tempfile`` + ``os.replace``) so a crash never leaves a partial
   ``checkpoint.json`` (INV-A3).
4. **Resumes from an existing checkpoint** by skipping already-completed
   result IDs (INV-A4), recording ``provenance="resumed"`` for them.
5. **Produces result objects** matching the structures in
   ``p2_data_structures.md`` — specifically :class:`~model_benchmark.schema.ResultRecord`
   and :class:`~model_benchmark.schema.ProgressEvent`, plus a
   :class:`~model_benchmark.schema.CheckpointState` snapshot.
6. **Dry-run mode** that skips actual model calls and instead produces the
   full iteration plan (the ordered list of (model, variant, direction,
   repetition) tuples that *would* run), a :class:`IterationPlan` object,
   without calling Ollama.

Design decisions
----------------
- **No new dependencies.** Uses only the stdlib (``json``, ``os``,
  ``tempfile``, ``time``, ``sys``, ``dataclasses``, ``pathlib``,
  ``datetime``, ``uuid``).  ``tqdm`` is absent from ``pyproject.toml`` so we
  emit a plain-text progress line to ``stderr`` instead.
- **Imports from the existing modules** — ``benchmark.py`` for
  :func:`run_single_model`, :func:`discover_models`, :func:`build_fixture_prompt`,
  :func:`score_response`, and the ``BenchmarkConfig``/``ModelRunResult``
  dataclasses; ``schema.py`` for the new ``ResultRecord`` /
  ``CheckpointState`` / ``ProgressEvent`` types; ``fixtures.py`` for the
  ``_DRY_RUN_RESPONSE``.  We deliberately import from ``benchmark`` (not
  ``scoring``) because ``benchmark`` is the compatibility shim the rest of
  the package still treats as the canonical import surface, and importing
  from it keeps the module working whether or not the shim is later
  reduced to re-exports.
- **The runner does not touch ``harness/`` or ``scripts/``** (INV-5).
- **A single failure does not terminate unrelated evaluations** (INV-A10 /
  carry-forward of INV-6): each case is wrapped in ``try/except`` and a
  failing ``ResultRecord`` (``status="ERROR"``) is produced rather than
  raising.
- **Checkpoint IDs are deterministic.** ``test_id`` for a case is
  ``f"{model}:{variant}:{direction}:{repetition}"`` so the same run resumed
  from a checkpoint skips exactly the same cases.

Reproducibility / resume semantics
----------------------------------
- On resume, the runner loads ``checkpoint.json`` from the run dir, reads
  the ``completed_ids`` set, and skips any case whose ``test_id`` is in
  that set.  Skipped cases get a ``ResultRecord`` with
  ``provenance="resumed"`` and ``status="SKIPPED"`` (they are *not*
  recomputed).  The set of newly-computed records plus the resumed
  placeholders forms the full result list.
- ``--force-rerun`` (``BenchmarkRunner.force_rerun=True``) ignores the
  checkpoint and recomputes everything.

Public API
----------
- :class:`IterationPlan`        — the ordered list of cases (dry-run output).
- :class:`BenchmarkRunner`     — main entry point: ``execute()``, ``dry_run()``,
                                  ``resume_from_checkpoint()``.
- :func:`save_checkpoint`       — atomic checkpoint persistence.
- :func:`load_checkpoint`       — load a ``CheckpointState`` from disk.
- :func:`atomic_write_text`     — tmpfile + ``os.replace`` helper.
- :func:`build_iteration_plan`  — compute the case list for a config.
- :func:`result_record_from_model_run` — bridge ``ModelRunResult`` → ``ResultRecord``.

The module imports cleanly with ``uv run python -c "from model_benchmark.runner import BenchmarkRunner"``.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Sequence

# ── Existing benchmark structures + functions ───────────────────────────
# Use the extracted scoring implementation.  ``benchmark.py`` remains the
# legacy compatibility surface, while active benchmark runs need the
# applicability-aware scorer defined here.
from model_benchmark.scoring import (
    BenchmarkConfig,
    ModelRunResult,
    PROMPT_VERSION,
    discover_models,
    run_single_model,
    score_response,
)
from model_benchmark.fixtures import _DRY_RUN_RESPONSE
from harness.parsers import parse_model_output
from harness.models import ModelOutput

# ── New schema types (Phase 2) ──────────────────────────────────────────
from model_benchmark.schema import (
    CheckpointState,
    ProgressEvent,
    ResultProvenance,
    ResultRecord,
    ResultStatus,
)

if TYPE_CHECKING:  # pragma: no cover
    # Only for typing; never imported at runtime.
    pass

__all__ = [
    "IterationPlan",
    "PlanItem",
    "BenchmarkRunner",
    "save_checkpoint",
    "load_checkpoint",
    "atomic_write_text",
    "build_iteration_plan",
    "result_record_from_model_run",
    "make_test_id",
    "register_signal_handler",
    "unregister_signal_handler",
    "render_progress",
]

# ═══════════════════════════════════════════════════════════════════════════
# Schema version for records produced by this runner.
# ═══════════════════════════════════════════════════════════════════════════
SCHEMA_VERSION = "1.0.0"
EVALUATOR_VERSION = "runner-1.0.0"

# Default checkpoint cadence (§4.4): persist after every N completed cases.
_DEFAULT_CHECKPOINT_EVERY = 10
# Default checkpoint time interval (§4.4): persist after this many seconds.
_DEFAULT_CHECKPOINT_INTERVAL_SECONDS = 60.0

# The capability tag for a SugarCube direction-following case (§8).
_CAPABILITY = "sugarcube_direction_following"


# ═══════════════════════════════════════════════════════════════════════════
# Iteration plan — the ordered list of cases a run will execute (dry-run output)
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class PlanItem:
    """One entry in an :class:`IterationPlan` — a single benchmark case."""

    test_id: str
    model: str
    variant: str
    direction: str
    repetition: int  # 1-based


# TODO(benchmark-upgrade): runner.py — add P3 §3.1 NEW interfaces as
# module-level functions (not just methods on BenchmarkRunner):
#
#   def execute_benchmark(
#       config: BenchmarkConfig,
#       progress_callback: Callable[[ProgressEvent], None] | None = None,
#       checkpoint_callback: Callable[[CheckpointState], None] | None = None,
#   ) -> list[ResultRecord]:
#     Run the full model×variant×direction×run loop, emitting progress and
#     checkpointing; return enriched ResultRecords.  This is the new
#     orchestration entry point that replaces the inline loop in old main().
#
#   def resume_from_checkpoint(checkpoint_path: str) -> CheckpointState:
#     Load a CheckpointState from a checkpoint.json path, returning empty
#     state if the file is absent or corrupt.  (P3 module-level function,
#     not the BenchmarkRunner.resume_from_checkpoint method.)
#
#   def render_progress(event: ProgressEvent, *, verbose: bool = False,
#                       quiet: bool = False, width: int | None = None,
#                       color: bool | None = None) -> str:
#     Format a ProgressEvent into a single terminal progress line/bar (empty string when quiet).
#     Implemented below as a pure function (no I/O, no env queries); the
#     _render_progress_stderr wrapper performs TTY/width/color detection.
#
# Also: run_single_model and discover_models (P3 §2.3, preserved signatures)
# move from scoring.py to runner.py.  Add them here and re-export from
# benchmark.py shim.


@dataclass(frozen=True)
class IterationPlan:
    """The ordered list of benchmark cases a run *would* execute.

    Produced by :func:`build_iteration_plan` and returned by
    :meth:`BenchmarkRunner.dry_run`.  This is the dry-run deliverable: it
    describes the full model × variant × direction × repetition matrix
    *without* calling any model.  Each entry is a :class:`PlanItem`.
    """

    items: tuple[PlanItem, ...]
    total_cases: int
    models: tuple[str, ...]
    variants: tuple[str, ...]
    directions: tuple[str, ...]
    repetitions: int
    dry_run: bool = True


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def make_test_id(model: str, variant: str, direction: str, repetition: int) -> str:
    """Build the deterministic ``test_id`` for one case.

    The id is ``f"{model}:{variant}:{direction}:{repetition}"`` — stable
    across runs so a resumed run skips exactly the same cases.
    """
    return f"{model}:{variant}:{direction}:{repetition}"


def _now_iso() -> str:
    """Current UTC time as an ISO-8601 string (``datetime.isoformat``)."""
    return datetime.now(timezone.utc).isoformat()


def _run_id() -> str:
    """Generate a short run id (8 hex chars) for checkpoint/manifest tagging."""
    return uuid.uuid4().hex[:8]


def atomic_write_text(path: str | os.PathLike[str], text: str) -> None:
    """Write ``text`` to ``path`` atomically (tmpfile + ``os.replace``).

    Writes to a temporary file in the same directory then renames it into
    place via ``os.replace`` so a crash never leaves a partial file (INV-A3).
    The temp file is created with ``delete=False`` and cleaned up on error.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".tmp_", suffix=p.suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, p)
    except Exception:
        # Best-effort cleanup of the temp file on failure.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _checkpoint_to_dict(state: CheckpointState) -> dict[str, Any]:
    """Serialize a :class:`CheckpointState` to a plain JSON-able dict."""
    return {
        "run_id": state.run_id,
        "completed_ids": list(state.completed_ids),
        "total_cases": state.total_cases,
        "last_saved_at": state.last_saved_at,
        "provenance": [list(pair) for pair in state.provenance],
    }


def _checkpoint_from_dict(d: dict[str, Any]) -> CheckpointState:
    """Deserialize a :class:`CheckpointState` from a plain dict."""
    prov_raw = d.get("provenance", [])
    prov: tuple[tuple[str, ResultProvenance], ...] = tuple(
        (str(p[0]), str(p[1])) for p in prov_raw  # type: ignore[arg-type]
    )
    return CheckpointState(
        run_id=str(d["run_id"]),
        completed_ids=tuple(str(x) for x in d.get("completed_ids", [])),
        total_cases=int(d.get("total_cases", 0)),
        last_saved_at=str(d.get("last_saved_at", "")),
        provenance=prov,
    )


def save_checkpoint(state: CheckpointState, path: str | os.PathLike[str]) -> None:
    """Persist ``state`` to ``path`` as ``checkpoint.json`` (atomic write)."""
    atomic_write_text(path, json.dumps(_checkpoint_to_dict(state), indent=2))


def load_checkpoint(path: str | os.PathLike[str]) -> CheckpointState | None:
    """Load a :class:`CheckpointState` from ``path``; return ``None`` if absent.

    Returns ``None`` (not raises) when the file does not exist so callers can
    treat "no prior checkpoint" and "corrupt checkpoint" distinctly: a missing
    file is a normal fresh-run condition.
    """
    p = Path(path)
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    return _checkpoint_from_dict(data)


# ═══════════════════════════════════════════════════════════════════════════
# Signal handler for emergency checkpointing (P1 §4.1, P6 INV-C6)
# ═══════════════════════════════════════════════════════════════════════════
# Module-level state so the signal handler can find the current checkpoint
# builder closure and the target path.  signal.signal() requires a
# module-level callable, so we store the per-run state here.
_prev_sigint_handler: Any = None
_prev_sigterm_handler: Any = None
_active_state_builder: Callable[[], CheckpointState] | None = None
_active_checkpoint_path: str = ""


def _emergency_checkpoint_handler(signum: int, frame: Any) -> None:
    """Signal handler: save an emergency checkpoint then exit.

    Called when SIGINT or SIGTERM is received during a benchmark run.
    Builds the current :class:`CheckpointState` from the registered closure,
    writes it atomically via :func:`save_checkpoint` (INV-A3), then exits
    with the conventional signal exit code (``128 + signum``).
    """
    builder = _active_state_builder
    path = _active_checkpoint_path
    if builder is not None and path:
        try:
            state = builder()
            save_checkpoint(state, path)
        except Exception:
            # Best-effort: a failure in the builder or write must not
            # corrupt the run.  Exit regardless (P1 §4.1 safety).
            pass
    sys.exit(128 + signum)


def register_signal_handler(
    state_builder: Callable[[], CheckpointState],
    checkpoint_path: str | os.PathLike[str],
) -> None:
    """Install SIGINT/SIGTERM handlers that save an emergency checkpoint.

    ``state_builder`` is a zero-arg closure returning the current
    :class:`CheckpointState`; ``checkpoint_path`` is where the emergency
    checkpoint is written.  The previous handlers are saved so
    :func:`unregister_signal_handler` can restore them.
    """
    global _prev_sigint_handler, _prev_sigterm_handler  # noqa: PLW0603
    global _active_state_builder, _active_checkpoint_path  # noqa: PLW0603

    _active_state_builder = state_builder
    _active_checkpoint_path = str(checkpoint_path)
    _prev_sigint_handler = signal.signal(signal.SIGINT, _emergency_checkpoint_handler)
    _prev_sigterm_handler = signal.signal(signal.SIGTERM, _emergency_checkpoint_handler)


def unregister_signal_handler() -> None:
    """Restore default SIGINT/SIGTERM handlers after the execution loop.

    Restores the previous (or default) signal handlers and clears the
    module-level state so a stray signal after the run does not trigger
    an emergency checkpoint.  Safe to call even if register was not called.
    """
    global _prev_sigint_handler, _prev_sigterm_handler  # noqa: PLW0603
    global _active_state_builder, _active_checkpoint_path  # noqa: PLW0603

    if _prev_sigint_handler is not None:
        signal.signal(signal.SIGINT, _prev_sigint_handler)
        _prev_sigint_handler = None
    if _prev_sigterm_handler is not None:
        signal.signal(signal.SIGTERM, _prev_sigterm_handler)
        _prev_sigterm_handler = None
    _active_state_builder = None
    _active_checkpoint_path = ""


def build_iteration_plan(
    models: Sequence[str],
    variants: Sequence[str],
    directions: Sequence[str],
    repetitions: int = 1,
    matrix_cases: Sequence[tuple[str, str]] | None = None,
) -> IterationPlan:
    """Compute the ordered list of cases for a run without calling models.

    The iteration order matches the existing ``benchmark.py`` nested loop:
    for each model, for each variant, for each direction, for each repetition
    (1-based).  This is the core of dry-run mode.
    """
    pairs = (
        tuple(matrix_cases)
        if matrix_cases is not None
        else tuple(
            (variant, direction)
            for variant in variants
            for direction in directions
        )
    )
    plan_variants = tuple(dict.fromkeys(variant for variant, _ in pairs))
    plan_directions = tuple(dict.fromkeys(direction for _, direction in pairs))
    items: list[PlanItem] = []
    for model in models:
        for variant, direction in pairs:
            for rep in range(1, repetitions + 1):
                items.append(
                    PlanItem(
                        test_id=make_test_id(model, variant, direction, rep),
                        model=model,
                        variant=variant,
                        direction=direction,
                        repetition=rep,
                    )
                )
    return IterationPlan(
        items=tuple(items),
        total_cases=len(items),
        models=tuple(models),
        variants=plan_variants,
        directions=plan_directions,
        repetitions=repetitions,
    )


def result_record_from_model_run(
    run: ModelRunResult,
    *,
    run_id: str = "",
    provenance: ResultProvenance = "new",
) -> ResultRecord:
    """Bridge a :class:`ModelRunResult` (scoring core) to a :class:`ResultRecord` (§8 schema).

    Maps the 6-category scored result into the versioned, enriched record
    defined in ``p2_data_structures.md`` §3.5.  The overall score is the
    fraction of the 6 categories that passed (matching the existing
    ``ModelReport.overall_score`` convention).  The status is ``PASS`` if
    every category passed, ``FAIL`` if any failed, ``ERROR`` if the run
    captured an infrastructure error (``run.error`` non-empty).
    """
    applicable_categories = tuple(
        c for c in run.category_results if getattr(c, "applicable", True)
    )
    n_cats = len(applicable_categories)
    n_passed = sum(1 for c in applicable_categories if c.passed)
    overall_pass = (
        all(c.passed for c in applicable_categories) if n_cats else False
    )
    max_score = float(n_cats) if n_cats else 1.0
    score = float(n_passed)
    normalized_score = (score / max_score) if max_score > 0 else 0.0

    if run.error:
        status: ResultStatus = "ERROR"
    elif overall_pass:
        status = "PASS"
    else:
        status = "FAIL"

    # Failure category — best-effort: "none" for PASS, else "instruction_following"
    # (the most general benchmark-failure category for a SugarCube direction-
    # following case).  A finer classifier lives in ``failures.py``.
    failure_category = "none" if status == "PASS" else "instruction_following"
    if status == "ERROR":
        failure_category = "internal_exception"

    test_id = make_test_id(run.model_name, run.variant, run.direction, run.run_index + 1)
    ts_end = _now_iso()

    return ResultRecord(
        schema_version=SCHEMA_VERSION,
        test_id=test_id,
        test_version=f"v{PROMPT_VERSION}",
        capability=_CAPABILITY,
        # category: use the first failing category if any, else the first one.
        # The full category breakdown, including N/A checks, is preserved in
        # ``scored_result``.
        category=(
            next((c.name for c in applicable_categories if not c.passed), None)
            or (
                applicable_categories[0].name
                if applicable_categories
                else "markup_compliance"
            )
        ),
        subcategory=run.variant,
        difficulty=run.direction,
        dataset="sugarcube_fixtures",
        split="default",
        repetition=run.run_index + 1,
        input_summary=run.variant,
        expected_behavior="SugarCube-compliant PROSE/CHOICES/SUMMARY",
        reference_rubric="applicability-aware category scoring (INV-9)",
        actual_output_raw=run.raw_response,
        parsed_output=run.parsed_output,
        score=score,
        max_score=max_score,
        normalized_score=normalized_score,
        pass_threshold=1.0,
        status=status,
        failure_category=failure_category,  # type: ignore[arg-type]
        evaluator_reasoning="applicable scorers from scoring.py (INV-2/9/10)",
        evaluator_confidence=1.0,
        runtime_seconds=run.elapsed_seconds,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        total_tokens=run.input_tokens + run.output_tokens,
        cost=0.0,
        retry_count=0,
        error_details=run.error,
        model_alias=run.model_name,
        config_alias=f"temp={0.2}",
        prompt_version=PROMPT_VERSION,
        evaluator_version=EVALUATOR_VERSION,
        random_seed=str(getattr(run, "random_seed", "") or ""),
        timestamp_start=ts_end,
        timestamp_end=ts_end,
        artifact_refs=(),
        parent_result_id="",
        comparison_result_id="",
        provenance=provenance,
        scored_result=run,
        finish_reason=run.finish_reason,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Progress rendering
# ═══════════════════════════════════════════════════════════════════════════


def _format_eta(seconds: float) -> str:
    """Format an ETA in seconds as --:-- (unknown), MM:SS (<1h), or H:MM:SS (>=1h)."""
    if seconds < 0:
        return "--:--"
    seconds = int(round(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _supports_color() -> bool:
    """Return True if stderr is a TTY, NO_COLOR is unset, and TERM is not dumb."""
    if not os.isatty(sys.stderr.fileno()):
        return False
    if "NO_COLOR" in os.environ:
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return True


# ANSI color codes (pure byte sequences, no dependency).
_ANSI_RESET = "\033[0m"
_ANSI_GREEN = "\033[32m"
_ANSI_RED = "\033[31m"
_ANSI_YELLOW = "\033[33m"
_ANSI_DIM = "\033[2m"

# Bar character set (ASCII-only, universally safe).
_BAR_FILL = "="
_BAR_HEAD = ">"
_BAR_EMPTY = " "

_DEFAULT_WIDTH = 80
_MIN_WIDTH = 20
_MAX_WIDTH = 120


def render_progress(
    event: ProgressEvent,
    *,
    verbose: bool = False,
    quiet: bool = False,
    width: int | None = None,
    color: bool | None = None,
) -> str:
    """Format a ProgressEvent into a single terminal progress line/bar (empty string when quiet)."""
    if quiet:
        return ""

    # Resolve display config with safe fallbacks (no env queries here).
    w = _DEFAULT_WIDTH if width is None else max(_MIN_WIDTH, min(width, _MAX_WIDTH))
    use_color = bool(color)

    # Build the status-counts segment.
    def _colorize(text: str, code: str) -> str:
        if use_color:
            return f"{code}{text}{_ANSI_RESET}"
        return text

    counts = (
        f"pass={_colorize(str(event.pass_count), _ANSI_GREEN)} "
        f"fail={_colorize(str(event.fail_count), _ANSI_RED)} "
        f"err={_colorize(str(event.error_count), _ANSI_YELLOW)} "
        f"skip={_colorize(str(event.skipped_count), _ANSI_DIM)}"
    )

    pct = event.percent
    eta_str = _format_eta(event.eta_seconds)

    # Build the right-side text: pct, counts, eta, (optional verbose case label).
    completed_total = f"{event.completed}/{event.total}"
    right = f"{pct:5.1f}% {completed_total} {eta_str} {counts}"

    if verbose and event.current_test:
        case_label = (
            f" {event.model_alias} v={event.variant} "
            f"dir={event.direction} rep={event.repetition}"
        )
        right += case_label

    # Build the bar.  Reserve space for the right-side text + brackets.
    # Format: [====>   ] <right>
    bracket_overhead = 4  # "[", "] ", space after ]
    bar_max = max(10, w - len(right) - bracket_overhead)

    if event.total > 0:
        filled = int(bar_max * event.completed / event.total)
        filled = min(filled, bar_max)
    else:
        filled = 0

    bar = _BAR_FILL * filled
    if filled < bar_max:
        bar += _BAR_HEAD
        bar += _BAR_EMPTY * (bar_max - filled - 1)

    line = f"[{bar}] {right}"
    return line


def _render_progress_stderr(
    event: ProgressEvent,
    verbose: bool,
    quiet: bool,
) -> None:
    """Write a formatted ProgressEvent to stderr with TTY-aware in-place refresh (no-op when quiet)."""
    if quiet:
        return

    is_tty = os.isatty(sys.stderr.fileno())
    w = shutil.get_terminal_size().columns if is_tty else _DEFAULT_WIDTH
    use_color = _supports_color() if is_tty else False

    line = render_progress(
        event, verbose=verbose, quiet=False, width=w, color=use_color
    )
    if not line:
        return

    prefix = "\r" if is_tty else ""
    suffix = "" if is_tty else "\n"
    sys.stderr.write(prefix + line + suffix)
    sys.stderr.flush()


# ═══════════════════════════════════════════════════════════════════════════
# BenchmarkRunner — the main execution class
# ═══════════════════════════════════════════════════════════════════════════


class BenchmarkRunner:
    """Execute a benchmark run with progress, checkpoint/resume, and dry-run.

    Parameters
    ----------
    config:
        The :class:`BenchmarkConfig` describing models, variants, directions,
        runs, base_url, timeout, etc.  This is the existing config from
        ``benchmark.py``; the runner adds checkpoint/resume behaviour on top
        of it via the keyword arguments below.
    checkpoint_every:
        Persist a checkpoint after this many completed cases (default 10).
    checkpoint_interval_seconds:
        Also persist after this many seconds elapse since the last checkpoint
        (default 60.0).  Both triggers are checked after each case.
    output_dir:
        Directory for checkpoint files and (optionally) results.  The
        checkpoint file is ``<output_dir>/checkpoint.json``.  Created if
        absent.  Defaults to ``"benchmark_outputs"``.
    verbose:
        Emit detailed progress lines (per-case model/variant/direction).
    quiet:
        Suppress all progress output (errors still print to stderr).
    force_rerun:
        Ignore any existing checkpoint and recompute every case.
    progress_callback:
        Optional ``Callable[[ProgressEvent], None]`` invoked with each
        progress event.  When provided, the default stderr rendering is
        still emitted unless ``quiet`` is set.  Useful for machine-readable
        progress logging or UI integration.
    run_id:
        Optional explicit run id; a short random id is generated if omitted.

    Notes
    -----
    - The runner never touches ``harness/`` or ``scripts/`` (INV-5).
    - A single case failure produces a failing ``ResultRecord`` and does not
      stop the run (INV-A10 / INV-6 carry-forward).
    - On resume, completed cases are skipped (``provenance="resumed"``) and
      are not recomputed (INV-A4).
    """

    def __init__(
        self,
        config: BenchmarkConfig,
        *,
        checkpoint_every: int = _DEFAULT_CHECKPOINT_EVERY,
        checkpoint_interval_seconds: float = _DEFAULT_CHECKPOINT_INTERVAL_SECONDS,
        output_dir: str = "benchmark_outputs",
        verbose: bool = False,
        quiet: bool = False,
        force_rerun: bool = False,
        progress_callback: Callable[[ProgressEvent], None] | None = None,
        run_id: str | None = None,
    ) -> None:
        self.config = config
        self.checkpoint_every = max(1, int(checkpoint_every))
        self.checkpoint_interval_seconds = max(0.0, float(checkpoint_interval_seconds))
        self.output_dir = Path(output_dir)
        self.verbose = bool(verbose)
        self.quiet = bool(quiet)
        self.force_rerun = bool(force_rerun)
        self.progress_callback = progress_callback
        self.run_id = run_id or _run_id()
        self.checkpoint_path = self.output_dir / "checkpoint.json"

        # In-progress counters (reset per execute() call).
        self._completed: int = 0
        self._pass_count: int = 0
        self._fail_count: int = 0
        self._error_count: int = 0
        self._skipped_count: int = 0
        self._invalid_count: int = 0
        self._timeout_count: int = 0
        self._cancelled_count: int = 0
        self._completed_ids: set[str] = set()
        self._provenance: dict[str, ResultProvenance] = {}
        self._last_checkpoint_time: float = 0.0
        self._start_time: float = 0.0

    # ── Public API ──────────────────────────────────────────────────────

    def dry_run(self) -> IterationPlan:
        """Produce the iteration plan without calling any model.

        Returns the ordered list of cases (model × variant × direction ×
        repetition) that ``execute()`` would run.  No Ollama calls, no
        network, no checkpoint writes.  This satisfies the dry-run
        acceptance criterion.
        """
        models = self._resolve_models()
        plan = build_iteration_plan(
            models=models,
            variants=tuple(self.config.variants),
            directions=tuple(self.config.directions),
            repetitions=max(1, self.config.runs),
            matrix_cases=self._matrix_cases(),
        )
        if not self.quiet:
            self._print_run_summary(plan, models, dry_run=True)
        return plan

    def execute(self, resume: bool = False) -> list[ResultRecord]:
        """Execute the full benchmark loop and return the result records.

        Parameters
        ----------
        resume:
            If ``True``, load any existing checkpoint at
            ``self.checkpoint_path`` and skip already-completed cases.  If
            ``self.force_rerun`` is set, the checkpoint is ignored even if
            ``resume`` is ``True``.

        Returns
        -------
        list of :class:`~model_benchmark.schema.ResultRecord`, one per case,
        in iteration order.  Resumed (skipped) cases appear with
        ``provenance="resumed"`` and ``status="SKIPPED"``.
        """
        # If the config itself is a dry-run, defer to the fixture path so
        # callers using the CLI's dry-run flag still get a result list.
        if getattr(self.config, "dry_run", False):
            return self._execute_dry_run_fixture()

        models = self._resolve_models()
        plan = build_iteration_plan(
            models=models,
            variants=tuple(self.config.variants),
            directions=tuple(self.config.directions),
            repetitions=max(1, self.config.runs),
            matrix_cases=self._matrix_cases(),
        )
        total = plan.total_cases

        # Load checkpoint if resuming.
        prior_state: CheckpointState | None = None
        if resume and not self.force_rerun:
            prior_state = load_checkpoint(self.checkpoint_path)
        completed_ids: set[str] = set()
        if prior_state is not None and not self.force_rerun:
            completed_ids = set(prior_state.completed_ids)
            self._completed_ids = set(completed_ids)
            # Pre-populate provenance for resumed items.
            for tid, prov in prior_state.provenance:
                self._provenance[tid] = prov  # type: ignore[assignment]

        self._start_time = time.monotonic()
        self._last_checkpoint_time = self._start_time

        register_signal_handler(self._build_checkpoint_state, self.checkpoint_path)

        try:
            if not self.quiet:
                self._print_run_summary(
                    plan, models, dry_run=False,
                    resumed=len(completed_ids), new=total - len(completed_ids),
                )

            results: list[ResultRecord] = []
            for idx, item in enumerate(plan.items):
                test_id = item.test_id

                # Resume: skip already-completed cases.
                if test_id in completed_ids and not self.force_rerun:
                    rec = self._make_resumed_record(item)
                    results.append(rec)
                    self._skipped_count += 1
                    self._completed += 1
                    self._emit_progress("generation", item, total)
                    self._maybe_checkpoint(force=False)
                    continue

                # Execute one case (model call + parse + score).
                rec = self._run_one_case(item)
                results.append(rec)
                self._completed += 1
                self._update_status_counts(rec)
                self._completed_ids.add(test_id)
                self._provenance[test_id] = "new"

                self._emit_progress("generation", item, total)
                self._maybe_checkpoint(force=False)

            # Final checkpoint.
            self._maybe_checkpoint(force=True)

            # Bar hygiene: when an in-place \r progress bar has been rendering
            # (TTY + non-quiet), emit a newline so the [done] summary starts
            # on a fresh line instead of overwriting the bar.
            if not self.quiet:
                if os.isatty(sys.stderr.fileno()):
                    sys.stderr.write("\n")
                elapsed = time.monotonic() - self._start_time
                sys.stderr.write(
                    f"[done] {self._completed}/{total} in {elapsed:.1f}s "
                    f"pass={self._pass_count} fail={self._fail_count} "
                    f"err={self._error_count} skip={self._skipped_count}\n"
                )
        finally:
            unregister_signal_handler()

        return results

    def resume_from_checkpoint(self) -> list[ResultRecord]:
        """Resume a run from the existing checkpoint file.

        Convenience wrapper around ``execute(resume=True)``.  Raises
        ``FileNotFoundError`` if no checkpoint exists.
        """
        if not self.checkpoint_path.exists():
            raise FileNotFoundError(
                f"No checkpoint to resume from: {self.checkpoint_path}"
            )
        return self.execute(resume=True)

    # ── Internal helpers ────────────────────────────────────────────────

    def _print_run_summary(
        self,
        plan: IterationPlan,
        models: list[str],
        *,
        dry_run: bool,
        resumed: int = 0,
        new: int = 0,
    ) -> None:
        """Print a pre-run summary banner to stderr.

        Shows what was discovered/configured before the benchmark starts:
        models, variants, directions, repetitions, total cases, Ollama URL,
        timeout, and token/temperature settings.  In dry-run mode, labels the
        banner accordingly; in execute mode, shows resumed vs new case counts.
        """
        w = sys.stderr.write
        label = "dry-run" if dry_run else "generation"
        w(f"[{label}] benchmark run starting\n")
        w(f"[{label}]   models: {len(models)}\n")
        for m in models:
            w(f"[{label}]     - {m}\n")
        w(
            f"[{label}]   variants: {', '.join(plan.variants)}\n"
            f"[{label}]   directions: {', '.join(plan.directions)}\n"
            f"[{label}]   repetitions: {plan.repetitions}\n"
            f"[{label}]   total cases: {plan.total_cases}\n"
        )
        if dry_run:
            w(f"[{label}]   mode: dry-run (no model calls)\n")
        else:
            w(
                f"[{label}]   mode: full run\n"
                f"[{label}]   resumed: {resumed}  new: {new}\n"
            )
        w(
            f"[{label}]   ollama: {self.config.base_url}\n"
            f"[{label}]   timeout: {self.config.timeout}s  "
            f"num_predict: {self.config.num_predict}  "
            f"temperature: {self.config.temperature}\n"
        )
        if self.force_rerun:
            w(f"[{label}]   force_rerun: ignoring any checkpoint\n")
        w(f"[{label}] starting...\n")

    def _resolve_models(self) -> list[str]:
        """Determine the model list: explicit config models, else discover."""
        models = list(self.config.models)
        if not models and not getattr(self.config, "dry_run", False):
            models = discover_models(self.config.base_url)
        if not models and getattr(self.config, "dry_run", False):
            models = ["(dry-run)"]
        if not models:
            # No models found and not dry-run: surface a clear message.
            sys.stderr.write(
                "No models found. Is Ollama running? "
                "(use --models to specify, or --dry-run)\n"
            )
        return models

    def _matrix_cases(self) -> tuple[tuple[str, str], ...]:
        from model_benchmark.profiles import resolve_matrix_cases

        return resolve_matrix_cases(
            getattr(self.config, "benchmark_profile", ""),
            self.config.variants,
            self.config.directions,
        )

    def _run_one_case(self, item: PlanItem) -> ResultRecord:
        """Run a single model call + parse + score and build a ResultRecord.

        Wrapped in try/except so a single failure produces an ERROR record
        rather than aborting the run (INV-A10 / INV-6).
        """
        try:
            run = run_single_model(
                item.model,
                item.variant,  # type: ignore[arg-type]
                item.direction,  # type: ignore[arg-type]
                self.config,
                run_index=item.repetition - 1,
            )
            return result_record_from_model_run(run, run_id=self.run_id, provenance="new")
        except Exception as exc:
            # Infrastructure failure — produce an ERROR record, do not raise.
            return self._make_error_record(item, str(exc))

    def _make_error_record(self, item: PlanItem, error: str) -> ResultRecord:
        """Build an ERROR ResultRecord for a case that raised an exception."""
        ts = _now_iso()
        empty = ModelOutput()
        return ResultRecord(
            schema_version=SCHEMA_VERSION,
            test_id=item.test_id,
            test_version=f"v{PROMPT_VERSION}",
            capability=_CAPABILITY,
            category="markup_compliance",
            subcategory=item.variant,
            difficulty=item.direction,
            dataset="sugarcube_fixtures",
            split="default",
            repetition=item.repetition,
            input_summary=item.variant,
            expected_behavior="SugarCube-compliant PROSE/CHOICES/SUMMARY",
            reference_rubric="applicability-aware category scoring (INV-9)",
            actual_output_raw="",
            parsed_output=empty,
            score=0.0,
            max_score=6.0,
            normalized_score=0.0,
            pass_threshold=1.0,
            status="ERROR",
            failure_category="internal_exception",
            evaluator_reasoning="runner caught exception during case execution",
            evaluator_confidence=1.0,
            runtime_seconds=0.0,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            cost=0.0,
            retry_count=0,
            error_details=error,
            model_alias=item.model,
            config_alias="",
            prompt_version=PROMPT_VERSION,
            evaluator_version=EVALUATOR_VERSION,
            random_seed=str(getattr(self.config, "random_seed", "") or ""),
            timestamp_start=ts,
            timestamp_end=ts,
            provenance="new",
        )

    def _make_resumed_record(self, item: PlanItem) -> ResultRecord:
        """Build a SKIPPED ResultRecord for a case resumed from checkpoint."""
        ts = _now_iso()
        empty = ModelOutput()
        return ResultRecord(
            schema_version=SCHEMA_VERSION,
            test_id=item.test_id,
            test_version=f"v{PROMPT_VERSION}",
            capability=_CAPABILITY,
            category="markup_compliance",
            subcategory=item.variant,
            difficulty=item.direction,
            dataset="sugarcube_fixtures",
            split="default",
            repetition=item.repetition,
            input_summary=item.variant,
            expected_behavior="SugarCube-compliant PROSE/CHOICES/SUMMARY",
            reference_rubric="6-category scoring (INV-9)",
            actual_output_raw="",
            parsed_output=empty,
            score=0.0,
            max_score=6.0,
            normalized_score=0.0,
            pass_threshold=1.0,
            status="SKIPPED",
            failure_category="none",
            evaluator_reasoning="resumed from checkpoint; not recomputed",
            evaluator_confidence=1.0,
            runtime_seconds=0.0,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            cost=0.0,
            retry_count=0,
            error_details="",
            model_alias=item.model,
            config_alias="",
            prompt_version=PROMPT_VERSION,
            evaluator_version=EVALUATOR_VERSION,
            random_seed=str(getattr(self.config, "random_seed", "") or ""),
            timestamp_start=ts,
            timestamp_end=ts,
            provenance="resumed",
        )

    def _execute_dry_run_fixture(self) -> list[ResultRecord]:
        """Produce ResultRecords from the dry-run fixture (no model calls).

        When ``config.dry_run`` is set, ``execute()`` delegates here: it
        scores the known-good ``_DRY_RUN_RESPONSE`` fixture (INV-8) for a
        single synthetic case and returns one ResultRecord.  This keeps
        the run loop exercisable in CI without Ollama.
        """
        parsed = parse_model_output(_DRY_RUN_RESPONSE)
        results = score_response(_DRY_RUN_RESPONSE, parsed, "compact")
        run = ModelRunResult(
            model_name="(dry-run)",
            variant="compact",
            direction="A",
            run_index=0,
            raw_response=_DRY_RUN_RESPONSE,
            parsed_output=parsed,
            category_results=tuple(results),
            overall_pass=all(r.passed for r in results if r.applicable),
            elapsed_seconds=0.0,
        )
        rec = result_record_from_model_run(run, run_id=self.run_id, provenance="new")
        if not self.quiet:
            sys.stderr.write(
                f"[dry-run] scored 1 fixture case: status={rec.status} "
                f"score={rec.score}/{rec.max_score}\n"
            )
        return [rec]

    def _update_status_counts(self, rec: ResultRecord) -> None:
        """Increment the per-status counters from a completed ResultRecord."""
        s = rec.status
        if s == "PASS":
            self._pass_count += 1
        elif s == "FAIL":
            self._fail_count += 1
        elif s == "ERROR":
            self._error_count += 1
        elif s == "SKIPPED":
            self._skipped_count += 1
        elif s == "INVALID":
            self._invalid_count += 1
        elif s == "TIMEOUT":
            self._timeout_count += 1
        elif s == "CANCELLED":
            self._cancelled_count += 1

    def _emit_progress(self, stage: str, item: PlanItem, total: int) -> None:
        """Build a ProgressEvent, invoke the callback, and render to stderr."""
        elapsed = time.monotonic() - self._start_time
        pct = (self._completed / total * 100.0) if total > 0 else 0.0
        if self._completed > 0 and elapsed > 0:
            eta = elapsed * (total - self._completed) / self._completed
        else:
            eta = -1.0
        event = ProgressEvent(
            stage=stage,
            current_test=item.test_id,
            completed=self._completed,
            total=total,
            percent=pct,
            elapsed_seconds=elapsed,
            eta_seconds=eta,
            model_alias=item.model,
            config_alias="",
            variant=item.variant,
            direction=item.direction,
            repetition=item.repetition,
            pass_count=self._pass_count,
            fail_count=self._fail_count,
            error_count=self._error_count,
            skipped_count=self._skipped_count,
            invalid_count=self._invalid_count,
            timeout_count=self._timeout_count,
            cancelled_count=self._cancelled_count,
        )
        if self.progress_callback is not None:
            try:
                self.progress_callback(event)
            except Exception:
                pass  # a callback error must not abort the run
        _render_progress_stderr(event, self.verbose, self.quiet)

    def _maybe_checkpoint(self, *, force: bool) -> None:
        """Persist a checkpoint if the count or time interval trigger fires.

        ``force=True`` always writes (used for the final checkpoint).
        Otherwise writes when ``self._completed`` is a multiple of
        ``checkpoint_every`` OR ``checkpoint_interval_seconds`` have
        elapsed since the last write.
        """
        now = time.monotonic()
        count_trigger = (self._completed % self.checkpoint_every == 0) and self._completed > 0
        time_trigger = (
            self.checkpoint_interval_seconds > 0
            and (now - self._last_checkpoint_time) >= self.checkpoint_interval_seconds
        )
        if not (force or count_trigger or time_trigger):
            return
        state = self._build_checkpoint_state()
        try:
            save_checkpoint(state, self.checkpoint_path)
            self._last_checkpoint_time = now
        except Exception as exc:
            # A checkpoint write failure must not abort the run.
            if not self.quiet:
                sys.stderr.write(f"[checkpoint] write failed: {exc}\n")

    def _build_checkpoint_state(self) -> CheckpointState:
        """Snapshot the current resumable state into a CheckpointState."""
        prov_tuple = tuple(sorted(self._provenance.items()))
        return CheckpointState(
            run_id=self.run_id,
            completed_ids=tuple(sorted(self._completed_ids)),
            total_cases=self._completed,
            last_saved_at=_now_iso(),
            provenance=prov_tuple,  # type: ignore[arg-type]
        )


# ═══════════════════════════════════════════════════════════════════════════
# Module-level convenience: run as ``python -m model_benchmark.runner``
# ═══════════════════════════════════════════════════════════════════════════


def _cli_main(argv: list[str] | None = None) -> int:
    """Minimal CLI entry point so the runner can be invoked directly.

    This is a thin convenience wrapper; the full CLI with all flags lives in
    ``cli.py`` (a sibling task).  Here we accept ``--dry-run`` and a couple of
    basic options so ``python -m model_benchmark.runner --dry-run`` works.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="model_benchmark.runner",
        description="Benchmark runner with checkpoint/resume (full CLI in cli.py)",
    )
    parser.add_argument("--models", nargs="*", default=[], help="Model tags (empty=auto-discover)")
    parser.add_argument("--variants", nargs="*", choices=["compact", "full", "json"],
                        default=["compact", "full", "json"], help="Prompt variants")
    parser.add_argument("--directions", nargs="*", choices=["A", "B", "C"],
                        default=["A", "B", "C"], help="Directions")
    parser.add_argument("--base-url", default="http://localhost:11434", help="Ollama base URL")
    parser.add_argument("--timeout", type=int, default=120, help="Seconds per call")
    parser.add_argument("--num-predict", type=int, default=640, help="Max tokens")
    parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature")
    parser.add_argument("--runs", type=int, default=1, help="Repetitions per case")
    parser.add_argument("--dry-run", action="store_true", help="Plan only, no model calls")
    parser.add_argument("--output-dir", default="benchmark_outputs", help="Output/checkpoint dir")
    parser.add_argument("--checkpoint-every", type=int, default=10, help="Checkpoint cadence (N cases)")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--verbose", action="store_true", help="Detailed progress")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")

    args = parser.parse_args(argv)

    cfg = BenchmarkConfig(
        models=tuple(args.models),
        variants=tuple(args.variants),
        directions=tuple(args.directions),
        base_url=args.base_url,
        timeout=args.timeout,
        num_predict=args.num_predict,
        temperature=args.temperature,
        runs=args.runs,
        dry_run=args.dry_run,
    )
    runner = BenchmarkRunner(
        cfg,
        checkpoint_every=args.checkpoint_every,
        output_dir=args.output_dir,
        verbose=args.verbose,
        quiet=args.quiet,
    )
    if args.dry_run:
        plan = runner.dry_run()
        sys.stdout.write(
            json.dumps(
                {
                    "total_cases": plan.total_cases,
                    "models": list(plan.models),
                    "variants": list(plan.variants),
                    "directions": list(plan.directions),
                    "repetitions": plan.repetitions,
                    "items": [
                        {
                            "test_id": it.test_id,
                            "model": it.model,
                            "variant": it.variant,
                            "direction": it.direction,
                            "repetition": it.repetition,
                        }
                        for it in plan.items
                    ],
                },
                indent=2,
            )
        )
        sys.stdout.write("\n")
        return 0

    records = runner.execute(resume=args.resume)
    sys.stdout.write(
        json.dumps(
            {
                "run_id": runner.run_id,
                "total": len(records),
                "pass": sum(1 for r in records if r.status == "PASS"),
                "fail": sum(1 for r in records if r.status == "FAIL"),
                "error": sum(1 for r in records if r.status == "ERROR"),
                "skipped": sum(1 for r in records if r.status == "SKIPPED"),
            },
            indent=2,
        )
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_cli_main())
