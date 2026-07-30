"""Failure analysis for model benchmark results (§10).

This module implements the four failure-analysis capabilities required by the
benchmark upgrade spec §10 and the P1 module layout (``failures.py`` home of
``FailureGroup``):

1. :func:`group_failures`        — cluster failure records by category.
2. :func:`classify_failure`      — benchmark-vs-infrastructure distinction.
3. :func:`infer_failure_category`— best-effort map of an error/status to a
                                   :data:`model_benchmark.schema.FailureCategory`.
4. :func:`get_failure_detail`    — per-case detail dict (error, timestamp,
                                   model, case id, …).
5. :func:`write_failures_csv`     — export grouped/classified failures to a CSV
                                   file (stdlib :mod:`csv` only).

Design notes
------------
- **Stdlib only.** No third-party imports. ``csv``, ``os``, ``tempfile`` and
  ``typing`` are the only dependencies.
- **Pure where possible.** ``group_failures``, ``classify_failure``,
  ``infer_failure_category`` and ``get_failure_detail`` have no side effects
  and perform no I/O.  Only ``write_failures_csv`` touches the filesystem.
- **Duck-typed records.** Every accessor accepts either a plain ``dict``
  (e.g. a row loaded from JSON/JSONL) or a frozen dataclass
  (``ResultRecord`` from :mod:`model_benchmark.schema` or the older
  ``ModelRunResult`` from :mod:`model_benchmark.scoring`).  A small
  :func:`_get` helper tries attribute access first, then mapping lookup, then
  a couple of common alias field names, and finally returns a default.
- **Schema alignment.** The categories produced/recognised are exactly the
  members of :data:`model_benchmark.schema.FailureCategory` (the union of
  ``BenchmarkFailure`` + ``InfrastructureFailure`` + ``"none"``).  The grouping
  output is the :class:`model_benchmark.schema.FailureGroup` frozen dataclass,
  re-exported here for convenience.
- **No harness modification** (INV-5).  This module imports only from
  :mod:`model_benchmark.schema` (data types, under ``TYPE_CHECKING``) and the
  stdlib.
"""
from __future__ import annotations

import csv
import os
import tempfile
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Sequence

if TYPE_CHECKING:
    # Referenced only in annotations (string form thanks to
    # ``from __future__ import annotations``); never imported at runtime so
    # this module loads cleanly even if the rest of the package is mid-refactor.
    from model_benchmark.schema import FailureGroup as _FailureGroup

# Re-export the FailureGroup dataclass so callers can do
# ``from model_benchmark.failures import FailureGroup`` without a second
# import.  Imported eagerly (it is a cheap, dependency-free frozen dataclass).
from model_benchmark.schema import FailureGroup  # noqa: E402

__all__ = [
    "FailureGroup",
    "group_failures",
    "classify_failure",
    "infer_failure_category",
    "get_failure_detail",
    "write_failures_csv",
    "write_failure_summary_csv",
    "is_failure",
]

# ═══════════════════════════════════════════════════════════════════════════
# Category sets (mirror model_benchmark.schema aliases — reproduced inline
# so this module does not need to import the Literal aliases at runtime).
# ═══════════════════════════════════════════════════════════════════════════

#: Failure categories that describe the *model's answer* being wrong/bad (§10).
BENCHMARK_FAILURES: frozenset[str] = frozenset({
    "instruction_following",
    "formatting",
    "reasoning",
    "safety",
    "hallucination",
    "refusal",
    "citation",
    "context_handling",
})

#: Failure categories that describe the *evaluation machinery* failing (§10).
INFRASTRUCTURE_FAILURES: frozenset[str] = frozenset({
    "provider_error",
    "auth_error",
    "rate_limit",
    "timeout",
    "network",
    "evaluator_error",
    "parser_error",
    "invalid_test_data",
    "missing_artifact",
    "internal_exception",
})

#: Union of the two sets above plus ``"none"`` (== :data:`FailureCategory`).
ALL_CATEGORIES: frozenset[str] = BENCHMARK_FAILURES | INFRASTRUCTURE_FAILURES | {"none"}

#: Result statuses that count as a failure for grouping purposes.
#: ``PASS`` and ``SKIPPED`` are excluded — a skip is not a failure, it is an
#: intentional non-evaluation.
FAILURE_STATUSES: frozenset[str] = frozenset({
    "FAIL", "ERROR", "TIMEOUT", "INVALID", "CANCELLED",
})

#: Keyword signatures used by :func:`infer_failure_category`.  Order matters:
#: the first matching signature wins, so more specific patterns precede more
#: general ones.  Each entry maps a tuple of lowercase substrings to a
#: :data:`FailureCategory` value.
_INFRA_SIGNATURES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("out of memory", "oom", "memoryerror", "cuda out of memory"), "internal_exception"),
    (("rate limit", "rate_limit", "429", "too many requests"), "rate_limit"),
    (("unauthorized", "forbidden", "401", "403", "invalid api key", "auth"), "auth_error"),
    (("timeout", "timed out", "timed-out", "deadline exceeded", "deadline"), "timeout"),
    (
        (
            "connection", "connectionerror", "connectionreset", "connectionrefused",
            "refused", "unreachable", "network", "name resolution", "dns",
            "nodename nor servname", "temporarily unavailable",
        ),
        "network",
    ),
    (
        ("provider", "500", "502", "503", "504", "internal server error",
         "bad gateway", "service unavailable", "gateway"),
        "provider_error",
    ),
    (("evaluator", "scorer", "score_response"), "evaluator_error"),
    (("missing artifact", "file not found", "no such file", "artifact"), "missing_artifact"),
    (("invalid test data", "malformed test", "bad test data"), "invalid_test_data"),
    # A parser crash on the harness side is infrastructure; a model emitting
    # unparseable text is a benchmark "formatting" failure and is handled by
    # the status==FAIL default below, so keep parser_error narrow.
    (("parser error", "parser crashed", "parseexception", "json decode error"), "parser_error"),
    (("exception", "traceback", "internal error"), "internal_exception"),
)

#: Suggested investigation text per category.  Falls back to a generic message
#: for categories without a specific entry.
_SUGGESTED_INVESTIGATION: dict[str, str] = {
    "instruction_following":
        "Review the prompt and rubric; check whether the model ignored or "
        "misread a directive. Compare against passing cases for prompt gaps.",
    "formatting":
        "Inspect the raw model output for markup/format violations. Verify "
        "the parser and the formatting rubric agree on what is 'valid'.",
    "reasoning":
        "Examine the model's chain of thought; check for logical errors or "
        "unsupported leaps. Consider harder test cases or a stronger model.",
    "safety":
        "Review the safety policy and the flagged output. Confirm the "
        "safety evaluator is not over-blocking benign responses.",
    "hallucination":
        "Compare the output against the reference; flag fabricated facts, "
        "citations, or state values. Tighten the grounding prompt.",
    "refusal":
        "Determine whether the refusal was warranted. If not, adjust the "
        "prompt framing or safety thresholds.",
    "citation":
        "Verify citation format and source accuracy. Check the citation "
        "extractor against the expected schema.",
    "context_handling":
        "Check whether the model lost or misused context (long-context "
        "truncation, wrong window, dropped instructions).",
    "provider_error":
        "Check the model provider logs and HTTP error. Retry with backoff; "
        "confirm the endpoint and model id are correct.",
    "auth_error":
        "Verify API credentials and token scopes. Rotate keys if expired.",
    "rate_limit":
        "Reduce concurrency or add delay/backoff. Check the provider quota "
        "and retry policy.",
    "timeout":
        "Increase the timeout, reduce num_predict, or check server load. "
        "Confirm the model is loaded and warm.",
    "network":
        "Check connectivity to the model server (DNS, firewall, proxy). "
        "Retry on transient errors; verify the base URL.",
    "evaluator_error":
        "Inspect the scorer/evaluator that crashed. This is a harness bug, "
        "not a model issue — fix the evaluator.",
    "parser_error":
        "Inspect the parser exception. If the parser crashed on valid input "
        "this is a harness bug; if the model emitted garbage, recategorise "
        "as 'formatting'.",
    "invalid_test_data":
        "Fix the malformed test fixture or dataset row. This failure is in "
        "the test data, not the model.",
    "missing_artifact":
        "Restore or regenerate the missing artifact (fixture, reference, "
        "rubric). Check the artifact path and run dir.",
    "internal_exception":
        "Unhandled exception in the harness. Read the traceback; this is an "
        "infrastructure defect requiring a code fix.",
    "none":
        "No failure recorded.",
}

#: Number of representative test_ids retained per :class:`FailureGroup`.
_REPRESENTATIVE_EXAMPLES_LIMIT = 5


# ═══════════════════════════════════════════════════════════════════════════
# Record accessors (duck-typed: dict or dataclass).
# ═══════════════════════════════════════════════════════════════════════════

def _get(record: Any, *names: str, default: Any = None) -> Any:
    """Return the first available value for *names* from *record*.

    Tries, in order: attribute access on *record* (dataclass/object), then
    mapping lookup (``dict``-like), then returns *default*.  The first name
    that yields a non-``None`` value wins, so callers can pass alias field
    names in priority order (e.g. ``"failure_category", "category"``).

    Tolerates records that are neither attributes nor mappings by returning
    *default*.
    """
    for name in names:
        # Attribute access (dataclass, object, namedtuple).
        value = getattr(record, name, None)
        if value is not None:
            return value
        # Mapping access (dict, Mapping).
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


def is_failure(record: Any) -> bool:
    """Return ``True`` if *record* represents a failed evaluation.

    A record is a failure when any of these hold:

    - ``status`` is one of :data:`FAILURE_STATUSES` (FAIL/ERROR/TIMEOUT/
      INVALID/CANCELLED);
    - ``overall_pass`` is ``False`` (the legacy ``ModelRunResult`` shape);
    - ``error``/``error_details`` is a non-empty string;
    - ``failure_category`` is set and not ``"none"``.

    ``PASS`` and ``SKIPPED`` records return ``False``.
    """
    status = _get_str(record, "status").upper()
    if status in FAILURE_STATUSES:
        return True
    if status in {"PASS", "SKIPPED"}:
        # PASS is explicitly not a failure; SKIPPED is an intentional
        # non-evaluation, also not a failure.
        # But a non-empty error still counts even on SKIPPED (rare).
        return bool(_get_str(record, "error", "error_details"))
    overall_pass = _get(record, "overall_pass")
    if overall_pass is False:
        return True
    if _get_str(record, "error", "error_details"):
        return True
    category = _get_str(record, "failure_category", "category", "failure_type")
    if category and category != "none":
        return True
    return False


# ═══════════════════════════════════════════════════════════════════════════
# 2. Benchmark-vs-infrastructure classification.
# ═══════════════════════════════════════════════════════════════════════════

# TODO(benchmark-upgrade): failures.py — align classify_failure signature to
# P3 §3.9.  P3 signature:
#   def classify_failure(record: ResultRecord) -> FailureCategory:
# Current returns a str ("benchmark"/"infrastructure"/"none"); P3 expects a
# FailureCategory literal (the specific category, not just the class).
# The classification logic (timeout, network, provider_error, etc.) is P7.
def classify_failure(record: Any) -> str:
    """Classify *record* as ``"benchmark"``, ``"infrastructure"`` or ``"none"``.

    Benchmark failures (§10) are cases where the *model's answer* is wrong,
    incomplete, or otherwise bad — the evaluation ran cleanly and the model
    simply failed a rubric.  Infrastructure failures are cases where the
    *evaluation machinery* failed (network, OOM, timeout, harness crash, …)
    and the model never got a fair chance.

    The classification is derived from the record's failure category when one
    is present (``failure_category`` / ``category`` / ``failure_type`` field),
    falling back to :func:`infer_failure_category` (which inspects status and
    error text) when no explicit category is available.

    Returns ``"none"`` for records that are not failures (see
    :func:`is_failure`).
    """
    if not is_failure(record):
        return "none"

    category = _resolve_category(record)
    if category in INFRASTRUCTURE_FAILURES:
        return "infrastructure"
    if category in BENCHMARK_FAILURES:
        return "benchmark"
    # Unknown category string: infer from status/error and re-check.
    inferred = infer_failure_category(record)
    if inferred in INFRASTRUCTURE_FAILURES:
        return "infrastructure"
    if inferred in BENCHMARK_FAILURES:
        return "benchmark"
    # A failure with no recognisable category and no infra signature is, by
    # default, a benchmark failure (the model got a fair shot and failed).
    return "benchmark"


def _resolve_category(record: Any) -> str:
    """Return the explicit failure category on *record*, or ``""`` if absent.

    Looks for ``failure_category`` (``ResultRecord``), then ``category`` and
    ``failure_type`` (generic dict conventions).  Does not infer — returns an
    empty string when no explicit category is set so the caller can decide to
    fall back to :func:`infer_failure_category`.
    """
    category = _get_str(record, "failure_category", "category", "failure_type")
    return category


# ═══════════════════════════════════════════════════════════════════════════
# 3. Failure-category inference.
# ═══════════════════════════════════════════════════════════════════════════

def infer_failure_category(record: Any) -> str:
    """Best-effort inference of a :data:`FailureCategory` for *record*.

    Used when a record carries no explicit ``failure_category`` field (e.g.
    a legacy ``ModelRunResult`` or a minimal dict).  The inference inspects, in
    priority order:

    1. ``status`` — ``TIMEOUT`` → ``"timeout"``, ``INVALID`` →
       ``"invalid_test_data"``, ``CANCELLED`` → ``"internal_exception"``;
    2. The lowercased error text (``error_details`` / ``error``) matched
       against :data:`_INFRA_SIGNATURES`;
    3. ``status == "FAIL"`` with no infra signature → ``"instruction_following"``
       (the most general benchmark failure);
    4. ``overall_pass is False`` with no other signal → ``"instruction_following"``;
    5. Fallback → ``"internal_exception"`` (the catch-all infrastructure
       category) for unrecognised ERROR/exception states, or ``"none"`` when
       the record is not a failure at all.

    Explicit categories on the record always take precedence over inference —
    call :func:`_resolve_category` first (as :func:`classify_failure` does).
    """
    if not is_failure(record):
        return "none"

    status = _get_str(record, "status").upper()
    error_text = _get_str(record, "error_details", "error").lower()

    # 1. Status-driven shortcuts.
    if status == "TIMEOUT":
        return "timeout"
    if status == "INVALID":
        return "invalid_test_data"
    if status == "CANCELLED":
        return "internal_exception"

    # 2. Error-text signature matching.
    for needles, category in _INFRA_SIGNATURES:
        if any(needle in error_text for needle in needles):
            return category

    # 3. A clean FAIL (no infra signature) is a benchmark failure.
    if status == "FAIL":
        return "instruction_following"

    # 4. Legacy ModelRunResult with overall_pass=False but no status.
    if _get(record, "overall_pass") is False:
        # If there's an error string it would have matched a signature above;
        # otherwise treat the scoring failure as a benchmark failure.
        return "instruction_following"

    # 5. Unrecognised ERROR/exception state → infra catch-all.
    return "internal_exception"


# ═══════════════════════════════════════════════════════════════════════════
# 1. Group failures by category.
# ═══════════════════════════════════════════════════════════════════════════

def _severity_for(category: str, failure_class: str, percent: float) -> str:
    """Assign a severity label from ``{"critical","high","medium","low"}``.

    Heuristic:

    - Infrastructure failures are more alarming than benchmark failures at the
      same rate, so they get a one-tier bump.
    - Rate thresholds (percent of evaluated cases):
      ``>= 50`` → critical/high, ``>= 20`` → high/medium, ``>= 5`` → medium/low,
      else low.
    """
    if failure_class == "infrastructure":
        if percent >= 50.0:
            return "critical"
        if percent >= 20.0:
            return "high"
        if percent >= 5.0:
            return "medium"
        return "low"
    # benchmark
    if percent >= 50.0:
        return "high"
    if percent >= 20.0:
        return "medium"
    return "low"


# TODO(benchmark-upgrade): failures.py — group_failures is the P3 §3.9
# interface.  P3 signature:
#   def group_failures(records: list[ResultRecord]) -> list[FailureGroup]:
# Current accepts Iterable[Any] with optional category_field/evaluated_total;
# align to accept list[ResultRecord] per P3.  The grouping logic is P7.
def group_failures(
    records: Iterable[Any],
    *,
    category_field: str | None = None,
    evaluated_total: int | None = None,
) -> list[FailureGroup]:
    """Group failure records by failure category (§10).

    Parameters
    ----------
    records:
        An iterable of failure records (dicts or dataclasses).  Non-failure
        records (``PASS``/``SKIPPED`` with no error) are silently skipped —
        see :func:`is_failure`.
    category_field:
        Optional explicit field name to read the category from.  When
        ``None`` (default) the category is read from ``failure_category`` /
        ``category`` / ``failure_type`` in that order, falling back to
        :func:`infer_failure_category` when none is present.
    evaluated_total:
        Denominator for ``percent_of_evaluated``.  When ``None`` it defaults
        to the number of records consumed (the length of the input iterable,
        evaluated lazily).  Pass an explicit count when *records* is a
        filtered view (e.g. only failures) so percentages stay meaningful.

    Returns
    -------
    list[FailureGroup]
        One :class:`FailureGroup` per distinct category, sorted by
        ``case_count`` descending (most common failure first).  Each group
        carries the category, count, percent of evaluated, affected
        capabilities/datasets, a severity label, up to
        :data:`_REPRESENTATIVE_EXAMPLES_LIMIT` representative test_ids, a
        suggested-investigation string, and the benchmark/infrastructure
        ``failure_class``.
    """
    materialised = list(records)
    if evaluated_total is None:
        evaluated_total = len(materialised)
    # Guard against div-by-zero.
    denom = evaluated_total if evaluated_total > 0 else 0

    # category -> list of records
    buckets: dict[str, list[Any]] = {}
    for record in materialised:
        if not is_failure(record):
            continue
        if category_field is not None:
            category = _get_str(record, category_field) or infer_failure_category(record)
        else:
            category = _resolve_category(record) or infer_failure_category(record)
        # Normalise: unknown strings collapse to the infra catch-all so the
        # group set stays within ALL_CATEGORIES.
        if category not in ALL_CATEGORIES:
            category = "internal_exception"
        buckets.setdefault(category, []).append(record)

    groups: list[FailureGroup] = []
    for category, cases in buckets.items():
        count = len(cases)
        percent = (count / denom * 100.0) if denom > 0 else 0.0
        failure_class = classify_failure(cases[0]) if cases else "benchmark"
        capabilities = sorted({
            _get_str(c, "capability") for c in cases if _get_str(c, "capability")
        })
        datasets = sorted({
            _get_str(c, "dataset", "dataset_name") for c in cases
            if _get_str(c, "dataset", "dataset_name")
        })
        # Representative examples: first N distinct test_ids/case_ids.
        seen: set[str] = set()
        examples: list[str] = []
        for c in cases:
            tid = _get_str(c, "test_id", "case_id", "id")
            if not tid or tid in seen:
                continue
            seen.add(tid)
            examples.append(tid)
            if len(examples) >= _REPRESENTATIVE_EXAMPLES_LIMIT:
                break
        severity = _severity_for(category, failure_class, percent)
        suggestion = _SUGGESTED_INVESTIGATION.get(category, _SUGGESTED_INVESTIGATION["none"])
        groups.append(FailureGroup(
            category=category,  # type: ignore[arg-type]
            case_count=count,
            percent_of_evaluated=round(percent, 2),
            affected_capabilities=tuple(capabilities),
            affected_datasets=tuple(datasets),
            severity=severity,
            representative_examples=tuple(examples),
            suggested_investigation=suggestion,
            failure_class=failure_class,
        ))

    # Most common failure first.
    groups.sort(key=lambda g: g.case_count, reverse=True)
    return groups


# ═══════════════════════════════════════════════════════════════════════════
# 4. Per-case detail.
# ═══════════════════════════════════════════════════════════════════════════

#: Canonical key order for the per-case detail dict returned by
#: :func:`get_failure_detail`.  Stable ordering makes CSV column mapping
#: predictable.
DETAIL_KEYS: tuple[str, ...] = (
    "case_id",
    "model",
    "status",
    "category",
    "classification",
    "error_message",
    "timestamp",
    "score",
    "capability",
    "dataset",
    "variant",
    "direction",
    "run_index",
    "elapsed_seconds",
)


def get_failure_detail(record: Any, *, anonymized: bool = False) -> dict[str, str]:
    """Return a flat per-case detail dict for *record*.

    The returned dict always has the keys in :data:`DETAIL_KEYS` (missing
    values become ``""``) so the shape is stable for CSV serialisation.  Values
    are coerced to ``str``.

    Parameters
    ----------
    record:
        A failure record (dict or dataclass).
    anonymized:
        When ``True``, prefer the ``model_alias`` field over the raw
        ``model_name`` and redact file paths / URLs / hostnames from the error
        text.  This is a best-effort redaction without an
        :class:`~model_benchmark.schema.AnonymizationMapping`; for full
        anonymization build a mapping first and rewrite the records.

    The fields populated are:

    - ``case_id``        — ``test_id`` / ``case_id`` / ``id``, else a composite
                           ``model|variant|direction|run_index``.
    - ``model``          — ``model_alias`` (if anonymized) else ``model_name``.
    - ``status``         — ``status`` (e.g. FAIL/ERROR/TIMEOUT) or inferred
                           (``FAIL`` when ``overall_pass`` is False).
    - ``category``       — explicit failure category or inferred.
    - ``classification`` — ``"benchmark"`` / ``"infrastructure"`` / ``"none"``.
    - ``error_message``  — ``error_details`` / ``error`` (redacted if
                           *anonymized*).
    - ``timestamp``      — ``timestamp_start`` (or ``timestamp_end``) else
                           ``""``.
    - ``score``          — ``normalized_score`` / ``score`` else ``""``.
    - ``capability``     — ``capability`` else ``""``.
    - ``dataset``        — ``dataset`` / ``dataset_name`` else ``""``.
    - ``variant``        — ``variant`` else ``""``.
    - ``direction``      — ``direction`` else ``""``.
    - ``run_index``      — ``run_index`` else ``""``.
    - ``elapsed_seconds``— ``elapsed_seconds`` else ``""``.
    """
    status = _get_str(record, "status").upper()
    if not status:
        if _get(record, "overall_pass") is False:
            status = "FAIL"
        elif _get_str(record, "error", "error_details"):
            status = "ERROR"

    category = _resolve_category(record) or infer_failure_category(record)
    classification = classify_failure(record)

    # case_id with a sensible composite fallback.
    case_id = _get_str(record, "test_id", "case_id", "id")
    if not case_id:
        model_part = _get_str(record, "model_name", "model_alias")
        variant_part = _get_str(record, "variant")
        direction_part = _get_str(record, "direction")
        run_part = _get_str(record, "run_index")
        composite = "|".join(p for p in (model_part, variant_part, direction_part, run_part) if p)
        case_id = composite or "unknown"

    # model (with anonymization preference).
    if anonymized:
        model = _get_str(record, "model_alias", "model_name", default="")
        if not model:
            model = "REDACTED_MODEL"
    else:
        model = _get_str(record, "model_name", "model_alias")

    # error message (with best-effort redaction when anonymized).
    error_message = _get_str(record, "error_details", "error")
    if anonymized and error_message:
        error_message = _redact_identifiers(error_message)

    # timestamp (start preferred, end as fallback).
    timestamp = _get_str(record, "timestamp_start", "timestamp_end")

    # score (normalized preferred, raw as fallback).
    score_value = _get(record, "normalized_score", "score")
    score = "" if score_value is None else str(score_value)

    return {
        "case_id": case_id,
        "model": model,
        "status": status,
        "category": category,
        "classification": classification,
        "error_message": error_message,
        "timestamp": timestamp,
        "score": score,
        "capability": _get_str(record, "capability"),
        "dataset": _get_str(record, "dataset", "dataset_name"),
        "variant": _get_str(record, "variant"),
        "direction": _get_str(record, "direction"),
        "run_index": _get_str(record, "run_index"),
        "elapsed_seconds": _get_str(record, "elapsed_seconds"),
    }


def _redact_identifiers(text: str) -> str:
    """Best-effort redaction of file paths, URLs and hostnames from *text*.

    Replaces common identity-bearing substrings (``/home/user/...`` paths,
    ``http(s)://host`` URLs, bare host:port pairs, Windows drive paths) with
    a ``[REDACTED]`` token.  Used by :func:`get_failure_detail` when
    ``anonymized=True`` and no full :class:`AnonymizationMapping` is available.
    """
    import re  # local import — only needed for the redaction helper

    redacted = text
    # URLs (with or without scheme).
    redacted = re.sub(r"https?://[^\s'\"<>]+", "[REDACTED_URL]", redacted)
    # Unix file paths.
    redacted = re.sub(r"(?:/[\w.\-]+){2,}", "[REDACTED_PATH]", redacted)
    # Windows drive paths.
    redacted = re.sub(r"[A-Za-z]:\\[^\s'\"<>]+", "[REDACTED_PATH]", redacted)
    # host:port pairs.
    redacted = re.sub(r"\b[\w.\-]+:\d{2,5}\b", "[REDACTED_HOST]", redacted)
    return redacted


# ═══════════════════════════════════════════════════════════════════════════
# 3. CSV export.
# ═══════════════════════════════════════════════════════════════════════════

#: Column order for the per-case CSV written by :func:`write_failures_csv`.
#: Includes the required columns (category, classification, count) plus the
#: per-case detail columns from :data:`DETAIL_KEYS`.
CSV_COLUMNS: tuple[str, ...] = (
    "category",
    "classification",
    "count",
    "case_id",
    "model",
    "status",
    "error_message",
    "timestamp",
    "score",
    "capability",
    "dataset",
    "variant",
    "direction",
    "run_index",
    "elapsed_seconds",
)

#: Column order for the per-group summary CSV written by
#: :func:`write_failure_summary_csv`.
SUMMARY_COLUMNS: tuple[str, ...] = (
    "category",
    "classification",
    "case_count",
    "percent_of_evaluated",
    "severity",
    "affected_capabilities",
    "affected_datasets",
    "representative_examples",
    "suggested_investigation",
)


# TODO(benchmark-upgrade): failures.py — write_failures_csv is the P3 §3.7
# interface (home = persistence.py, calls failures.group_failures).  P3
# signature (in persistence.py):
#   def write_failures_csv(records: list[ResultRecord], path: str, *, anonymized: bool) -> None:
# Current returns int and accepts extra kwargs; the persistence.py version
# should delegate to this for the CSV writing, or this should move to
# persistence.py per P3 §3.7.  Keep the grouping logic in failures.py.
def write_failures_csv(
    records: Iterable[Any],
    path: str | os.PathLike[str],
    *,
    anonymized: bool = False,
    category_field: str | None = None,
) -> int:
    """Write grouped/classified failure data to a CSV file (stdlib :mod:`csv`).

    Produces a flat, one-row-per-failure-case table.  Each row carries the
    group's ``category`` and ``classification``, the group's total ``count``
    (repeated for every case in the group so the column is self-contained),
    and the per-case detail columns from :func:`get_failure_detail`.

    Columns (:data:`CSV_COLUMNS`):
    ``category, classification, count, case_id, model, status, error_message,
    timestamp, score, capability, dataset, variant, direction, run_index,
    elapsed_seconds``.

    The file is written **atomically** (temp file in the same directory then
    :func:`os.replace`), consistent with the project's write conventions, so a
    crash mid-write never leaves a partial CSV.

    Parameters
    ----------
    records:
        Iterable of failure records (dicts or dataclasses).  Non-failure
        records are skipped.
    path:
        Destination CSV file path.  Parent directories are created.
    anonymized:
        Pass ``True`` to redact model names and identity-bearing substrings
        in error messages (best-effort; see :func:`get_failure_detail`).
    category_field:
        Optional explicit category field name (see :func:`group_failures`).

    Returns
    -------
    int
        Number of failure-case rows written (excluding the header).
    """
    materialised = list(records)
    groups = group_failures(materialised, category_field=category_field)
    # category -> count, for the repeated count column.
    count_by_category = {g.category: g.case_count for g in groups}

    rows: list[dict[str, str]] = []
    for record in materialised:
        if not is_failure(record):
            continue
        detail = get_failure_detail(record, anonymized=anonymized)
        category = detail["category"]
        rows.append({
            "category": category,
            "classification": detail["classification"],
            "count": str(count_by_category.get(category, 0)),
            "case_id": detail["case_id"],
            "model": detail["model"],
            "status": detail["status"],
            "error_message": detail["error_message"],
            "timestamp": detail["timestamp"],
            "score": detail["score"],
            "capability": detail["capability"],
            "dataset": detail["dataset"],
            "variant": detail["variant"],
            "direction": detail["direction"],
            "run_index": detail["run_index"],
            "elapsed_seconds": detail["elapsed_seconds"],
        })

    _write_csv_atomic(path, CSV_COLUMNS, rows)
    return len(rows)


def write_failure_summary_csv(
    records: Iterable[Any],
    path: str | os.PathLike[str],
    *,
    category_field: str | None = None,
    evaluated_total: int | None = None,
) -> int:
    """Write a per-group summary CSV (one row per :class:`FailureGroup`).

    Columns (:data:`SUMMARY_COLUMNS`):
    ``category, classification, case_count, percent_of_evaluated, severity,
    affected_capabilities, affected_datasets, representative_examples,
    suggested_investigation``.

    This is the grouped view of the same data :func:`write_failures_csv` emits
    per-case.  Useful for a quick "what broke and how often" overview.

    Parameters
    ----------
    records:
        Iterable of failure records (dicts or dataclasses).
    path:
        Destination CSV file path (created atomically).
    category_field:
        Optional explicit category field name (see :func:`group_failures`).
    evaluated_total:
        Optional denominator for percentages (see :func:`group_failures`).

    Returns
    -------
    int
        Number of summary rows written (excluding the header) — equal to the
        number of distinct failure categories.
    """
    groups = group_failures(records, category_field=category_field,
                            evaluated_total=evaluated_total)
    rows = [
        {
            "category": g.category,
            "classification": g.failure_class,
            "case_count": str(g.case_count),
            "percent_of_evaluated": str(g.percent_of_evaluated),
            "severity": g.severity,
            "affected_capabilities": "; ".join(g.affected_capabilities),
            "affected_datasets": "; ".join(g.affected_datasets),
            "representative_examples": "; ".join(g.representative_examples),
            "suggested_investigation": g.suggested_investigation,
        }
        for g in groups
    ]
    _write_csv_atomic(path, SUMMARY_COLUMNS, rows)
    return len(rows)


def _write_csv_atomic(
    path: str | os.PathLike[str],
    columns: Sequence[str],
    rows: Sequence[Mapping[str, str]],
) -> None:
    """Write *rows* to *path* as CSV with a header row from *columns*.

    Atomic: writes to a temp file in the same directory then
    :func:`os.replace` it into place.  Parent directories are created.
    Uses :func:`csv.DictWriter` (stdlib) with ``newline=""`` to avoid extra
    blank lines on Windows-style line endings.
    """
    path = os.fspath(path)
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)

    # tempfile in the same directory guarantees os.replace is atomic on the
    # same filesystem.
    fd, tmp_name = tempfile.mkstemp(prefix=".failures-", suffix=".csv", dir=parent)
    try:
        with os.fdopen(fd, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(columns))
            writer.writeheader()
            for row in rows:
                writer.writerow({col: row.get(col, "") for col in columns})
        os.replace(tmp_name, path)
    except BaseException:
        # Clean up the temp file on any failure; never leave partial state.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
