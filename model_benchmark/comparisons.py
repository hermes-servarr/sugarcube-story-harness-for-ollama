"""Baseline comparison and regression detection.

This module is the **home** of the :func:`load_baseline`, :func:`compare_runs`,
and :func:`detect_regressions` interfaces (P3 §2.1-2.3).  It re-exports its
home types (:class:`ComparisonResult`, :class:`Regression`,
:class:`ResultRecord`, :class:`ResultStatus`) from ``schema.py`` (P2 §1.2) and
defines three module-level threshold constants (P2 §3).

Field access is duck-typed via the :func:`_get` helper (matching
``failures.py``) so that both :class:`ResultRecord` frozen dataclasses and
plain ``dict`` records (e.g. from :func:`load_baseline` JSON) are accepted at
runtime (P5 deviation D5, elevated to invariant INV-CMP8).

Phase 7 — production implementation conforming to P2 (3 threshold constants),
P3 (the three public signatures), and P6 invariants (INV-CMP1..INV-CMP9,
INV-X1..INV-X3).
"""
from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any

from model_benchmark.schema import (
    ComparisonResult,
    Regression,
    ResultRecord,
    ResultStatus,
)

# ── Module-level threshold constants (P2 §3.1) ──────────────────────────────

#: Default score threshold for ``detect_regressions``.  A |score_diff| above
#: this value is flagged as a regression.  0.0 flags any worsening.
DEFAULT_SCORE_THRESHOLD: float = 0.0

#: Default threshold for statistical significance in ``compare_runs``.  An
#: absolute score diff above this value is considered statistically
#: significant.
DEFAULT_STATISTICAL_THRESHOLD: float = 0.05

#: Default threshold for operational significance in ``compare_runs``.  An
#: absolute score diff above this value is considered operationally
#: significant (a practically meaningful change).
DEFAULT_OPERATIONAL_THRESHOLD: float = 0.10


# ── Duck-typing accessors (matching failures.py pattern; P5 deviation D5) ──

_FAILURE_STATUSES = frozenset({"FAIL", "ERROR", "TIMEOUT", "INVALID", "CANCELLED"})


def _get(record: Any, *names: str, default: Any = None) -> Any:
    """Return the first available value for *names* from *record*.

    Tries attribute access (dataclass/object), then mapping lookup (dict),
    then returns *default*.  Matches the pattern in ``failures.py``.
    """
    for name in names:
        value = getattr(record, name, None)
        if value is not None:
            return value
        if isinstance(record, Mapping):
            value = record.get(name)
            if value is not None:
                return value
    return default


def _get_str(record: Any, *names: str, default: str = "") -> str:
    """Like :func:`_get` but coerces to ``str`` and treats ``None`` as empty."""
    value = _get(record, *names, default=None)
    if value is None:
        return default
    return str(value)


def _get_float(record: Any, *names: str, default: float = 0.0) -> float:
    """Extract a float field from a duck-typed record."""
    value = _get(record, *names, default=None)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _get_int(record: Any, *names: str, default: int = 0) -> int:
    """Extract an int field from a duck-typed record."""
    value = _get(record, *names, default=None)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ── Public interfaces (P3 §2.1-2.3) ─────────────────────────────────────────


def load_baseline(path: str) -> list[ResultRecord]:
    """Load ResultRecords from a previous run's JSON or JSONL results.

    Returns an empty list if the file is absent or corrupt — never raises.
    ``path`` may be a run directory or a direct path to
    ``results_internal.json``.
    """
    file_path = path
    if os.path.isdir(path):
        jsonl_path = os.path.join(path, "results_internal.jsonl")
        json_path = os.path.join(path, "results_internal.json")
        file_path = jsonl_path if os.path.isfile(jsonl_path) else json_path
    if not os.path.isfile(file_path):
        return []
    try:
        with open(file_path, encoding="utf-8") as fh:
            if str(file_path).lower().endswith(".jsonl"):
                records = [
                    json.loads(line)
                    for line in fh
                    if line.strip()
                ]
                if not all(isinstance(record, dict) for record in records):
                    return []
                return records
            data = json.load(fh)
    except (OSError, json.JSONDecodeError, ValueError):
        return []

    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = data.get("records", data.get("results", []))
        if not isinstance(records, list):
            return []
    else:
        return []

    return list(records)


def compare_runs(
    current: list[ResultRecord],
    baseline: list[ResultRecord],
) -> ComparisonResult:
    """Compute aggregate score/outcome/runtime/token diff between current and
    baseline runs, matched by test_id.

    Unmatched records are noted but not double-counted in score diffs.
    Significance flags use module-level threshold constants.
    """
    # Index records by test_id.
    current_by_id: dict[str, Any] = {}
    for rec in current:
        tid = _get_str(rec, "test_id", "id", "case_id")
        if tid:
            current_by_id[tid] = rec

    baseline_by_id: dict[str, Any] = {}
    for rec in baseline:
        tid = _get_str(rec, "test_id", "id", "case_id")
        if tid:
            baseline_by_id[tid] = rec

    # Matched test_ids.
    matched_ids = set(current_by_id) & set(baseline_by_id)

    # Score diffs over matched records (INV-CMP8: normalized_score then score).
    score_diffs: list[float] = []
    base_scores: list[float] = []
    for tid in matched_ids:
        cur_score = _get_float(current_by_id[tid], "normalized_score", "score")
        base_score = _get_float(baseline_by_id[tid], "normalized_score", "score")
        score_diffs.append(cur_score - base_score)
        base_scores.append(base_score)

    absolute_score_diff = (
        sum(score_diffs) / len(score_diffs) if score_diffs else 0.0
    )

    # Relative score diff: absolute / baseline_mean, div-zero guarded.
    base_mean = (
        sum(base_scores) / len(base_scores) if base_scores else 0.0
    )
    relative_score_diff = (
        absolute_score_diff / base_mean if base_mean != 0 else 0.0
    )

    # Newly failing: PASS in baseline, failure now.
    newly_failing: list[str] = []
    for tid in matched_ids:
        base_status = _get_str(baseline_by_id[tid], "status").upper()
        cur_status = _get_str(current_by_id[tid], "status").upper()
        if base_status == "PASS" and cur_status in _FAILURE_STATUSES:
            newly_failing.append(tid)

    # Newly passing: failure in baseline, PASS now.
    newly_passing: list[str] = []
    for tid in matched_ids:
        base_status = _get_str(baseline_by_id[tid], "status").upper()
        cur_status = _get_str(current_by_id[tid], "status").upper()
        if base_status in _FAILURE_STATUSES and cur_status == "PASS":
            newly_passing.append(tid)

    # Category regressions: categories of newly failing records.
    category_regressions: list[str] = []
    for tid in newly_failing:
        cat = _get_str(current_by_id[tid], "category", "capability")
        if cat and cat not in category_regressions:
            category_regressions.append(cat)

    # Runtime / token diffs over matched records.
    runtime_diffs: list[float] = []
    token_diffs: list[int] = []
    for tid in matched_ids:
        cur_runtime = _get_float(current_by_id[tid], "runtime_seconds",
                                 "elapsed_seconds")
        base_runtime = _get_float(baseline_by_id[tid], "runtime_seconds",
                                  "elapsed_seconds")
        runtime_diffs.append(cur_runtime - base_runtime)

        cur_tokens = _get_int(current_by_id[tid], "total_tokens", "tokens")
        base_tokens = _get_int(baseline_by_id[tid], "total_tokens", "tokens")
        token_diffs.append(cur_tokens - base_tokens)

    runtime_diff = (
        sum(runtime_diffs) / len(runtime_diffs) if runtime_diffs else 0.0
    )
    token_diff = sum(token_diffs) if token_diffs else 0

    # Significance (bound to constants by name).
    is_statistically_significant = (
        abs(absolute_score_diff) >= DEFAULT_STATISTICAL_THRESHOLD
    )
    is_operationally_significant = (
        abs(absolute_score_diff) >= DEFAULT_OPERATIONAL_THRESHOLD
    )

    # Run IDs (best-effort extraction).
    baseline_run_id = _get_str(baseline[0], "run_id", "run",
                               default="baseline") if baseline else "baseline"
    current_run_id = _get_str(current[0], "run_id", "run",
                              default="current") if current else "current"

    return ComparisonResult(
        baseline_run_id=baseline_run_id,
        current_run_id=current_run_id,
        absolute_score_diff=absolute_score_diff,
        relative_score_diff=relative_score_diff,
        newly_failing=tuple(newly_failing),
        newly_passing=tuple(newly_passing),
        category_regressions=tuple(category_regressions),
        runtime_diff=runtime_diff,
        token_diff=token_diff,
        is_statistically_significant=is_statistically_significant,
        is_operationally_significant=is_operationally_significant,
    )


def detect_regressions(
    comparison: ComparisonResult,
    current: list[ResultRecord],
    baseline: list[ResultRecord],
    *,
    score_threshold: float = DEFAULT_SCORE_THRESHOLD,
) -> list[Regression]:
    """Detect per-test regressions (worsening outcomes) from a
    ComparisonResult exceeding the score threshold.

    Returns one :class:`Regression` per regressed case.  Only regressions
    (worse outcomes: score decreased or status went PASS→failure) are returned —
    improvements are not regressions.
    """
    current_by_id: dict[str, Any] = {}
    for rec in current:
        tid = _get_str(rec, "test_id", "id", "case_id")
        if tid:
            current_by_id[tid] = rec

    baseline_by_id: dict[str, Any] = {}
    for rec in baseline:
        tid = _get_str(rec, "test_id", "id", "case_id")
        if tid:
            baseline_by_id[tid] = rec

    matched_ids = set(current_by_id) & set(baseline_by_id)
    regressions: list[Regression] = []

    for tid in matched_ids:
        cur_score = _get_float(current_by_id[tid], "normalized_score", "score")
        base_score = _get_float(baseline_by_id[tid], "normalized_score", "score")
        score_diff = cur_score - base_score  # negative = regression

        cur_status = _get_str(current_by_id[tid], "status").upper()
        base_status = _get_str(baseline_by_id[tid], "status").upper()

        # Determine if this is a regression (worsening) — INV-CMP6.
        is_regression = False
        # Score decreased beyond threshold.
        if abs(score_diff) > score_threshold and score_diff < 0:
            is_regression = True
        # Status went PASS → failure.
        if base_status == "PASS" and cur_status in _FAILURE_STATUSES:
            is_regression = True

        if not is_regression:
            continue

        # Determine severity.
        if comparison.is_statistically_significant and abs(score_diff) >= DEFAULT_STATISTICAL_THRESHOLD:
            severity = "statistical"
        elif comparison.is_operationally_significant and abs(score_diff) >= DEFAULT_OPERATIONAL_THRESHOLD:
            severity = "operational"
        elif score_diff < 0:
            severity = "minor"
        else:
            severity = "version"

        category = _get_str(current_by_id[tid], "category", "capability",
                            default="overall")

        regressions.append(Regression(
            test_id=tid,
            category=category,
            baseline_score=base_score,
            current_score=cur_score,
            score_diff=score_diff,
            baseline_status=base_status,  # type: ignore[arg-type]
            current_status=cur_status,  # type: ignore[arg-type]
            severity=severity,
            threshold=score_threshold,
        ))

    return regressions
