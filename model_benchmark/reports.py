"""Text and Markdown report generators for the model benchmark.

Per P1 §4.7 / §9-12, all exports derive from the same canonical
``ResultRecord`` list — no recomputation (INV-A5).  This module produces
two human-readable views of a benchmark run:

* :func:`generate_text_report` — a plain-text summary with key metrics,
  suitable for stdout / ``--output``.
* :func:`generate_markdown_report` — Markdown tables with proper column
  headers, alignment, and optional grouping by model or category,
  suitable for ``summary_internal.md`` / ``summary_anonymized.md``.

Both functions accept the same ``results`` argument: either an iterable of
``ResultRecord`` objects (as defined in ``p2_data_structures.md`` §3.5)
or a mapping/iterable of dict-like records whose keys mirror the
``ResultRecord`` fields.  A "results dict" wrapper with a ``"records"``
key (plus optional ``"manifest"``/``"generated_at"`` metadata) is also
accepted so a plain sample dict matching ``p2_data_structures.md`` works
without constructing real dataclasses.
"""
from __future__ import annotations

from collections import OrderedDict, defaultdict
from collections.abc import Mapping
from typing import Any, Iterable, Sequence

# __all__ extended with aliases per P3 §4.4.
__all__ = ["generate_text_report", "generate_markdown_report",
           "format_summary_text", "format_summary_markdown"]

# Canonical category order, mirrored from scoring._CATEGORY_ORDER (INV-9).
# Reproduced locally so reports.py has no runtime dependency on the not-
# yet-extracted scoring module; the values are the 6 SugarCube categories
# defined in p2_data_structures.md §2.2.
_CATEGORY_ORDER: tuple[str, ...] = (
    "markup_compliance",
    "variable_scoping",
    "passage_structure",
    "macro_usage",
    "naked_interpolation",
    "link_setter_syntax",
)

# Status values in display order (p2 §3.2 ResultStatus).
_STATUS_ORDER: tuple[str, ...] = (
    "PASS", "FAIL", "ERROR", "SKIPPED", "INVALID", "TIMEOUT", "CANCELLED",
)

_BAR_WIDTH = 70


# ═══════════════════════════════════════════════════════════════════════════
# Input normalisation
# ═══════════════════════════════════════════════════════════════════════════


def _coerce_records(results: Any) -> list[Mapping[str, Any]]:
    """Normalise ``results`` into a list of dict-like record mappings.

    Accepted shapes:
      * an iterable of ``ResultRecord`` dataclass instances or dicts;
      * a mapping with a ``"records"`` (or ``"results"``) key holding the
        iterable (a "results dict" wrapper).

    Each record is returned as a mapping supporting ``.get(name)`` for
    both real dataclass instances (via ``getattr``) and plain dicts.
    """
    if isinstance(results, Mapping):
        # Results-dict wrapper: pull the record list out.
        for key in ("records", "results", "model_results"):
            inner = results.get(key)
            if inner is not None:
                results = inner
                break
        else:
            # A single record-as-mapping is not a meaningful "results" input;
            # treat the mapping itself as a one-element list only if it looks
            # like a record (has a test_id / status). Otherwise it's an empty
            # wrapper with no records.
            if "test_id" in results or "status" in results:
                results = [results]
            else:
                return []
    if results is None:
        return []
    return [_as_mapping(r) for r in results]


def _as_mapping(obj: Any) -> Mapping[str, Any]:
    """Return a duck-typed mapping for a dataclass instance or a dict."""
    if isinstance(obj, Mapping):
        return _DictAccessor(obj)
    return _AttrAccessor(obj)


class _DictAccessor(Mapping):
    """Wrap a plain dict so it has a uniform ``.get``-style accessor."""

    __slots__ = ("_d",)

    def __init__(self, d: Mapping[str, Any]) -> None:
        self._d = d

    def get(self, name: str, default: Any = None) -> Any:  # type: ignore[override]
        return self._d.get(name, default)

    def __getitem__(self, name: str) -> Any:
        return self._d[name]

    def __iter__(self):
        return iter(self._d)

    def __len__(self) -> int:
        return len(self._d)


class _AttrAccessor(Mapping):
    """Wrap a dataclass instance, exposing fields via ``.get``."""

    __slots__ = ("_o",)

    def __init__(self, o: Any) -> None:
        self._o = o

    def get(self, name: str, default: Any = None) -> Any:  # type: ignore[override]
        # Direct attribute first.
        val = getattr(self._o, name, None)
        if val is not None:
            return val
        # Fall back to the embedded scored_result (ModelRunResult) for
        # legacy fields like model_name / variant / direction / run_index.
        scored = getattr(self._o, "scored_result", None)
        if scored is not None:
            return getattr(scored, name, default)
        return default

    def __getitem__(self, name: str) -> Any:
        val = self.get(name)
        if val is None:
            raise KeyError(name)
        return val

    def __iter__(self):
        # Best-effort iteration over the object's public field names.
        if hasattr(self._o, "__dataclass_fields__"):
            return iter(self._o.__dataclass_fields__)
        return iter(getattr(self._o, "__dict__", {}) or {})

    def __len__(self) -> int:
        if hasattr(self._o, "__dataclass_fields__"):
            return len(self._o.__dataclass_fields__)
        return len(getattr(self._o, "__dict__", {}) or {})


# ═══════════════════════════════════════════════════════════════════════════
# Field extractors
# ═══════════════════════════════════════════════════════════════════════════


def _model_of(rec: Mapping[str, Any]) -> str:
    """Display model identifier for a record (alias preferred)."""
    alias = rec.get("model_alias", "")
    if alias:
        return str(alias)
    name = rec.get("model_name", "")
    if name:
        return str(name)
    return "unknown"


def _category_of(rec: Mapping[str, Any]) -> str:
    cat = rec.get("category", "")
    return str(cat) if cat else "unknown"


def _status_of(rec: Mapping[str, Any]) -> str:
    st = rec.get("status", "")
    return str(st).upper() if st else "FAIL"


def _float(rec: Mapping[str, Any], name: str, default: float = 0.0) -> float:
    val = rec.get(name, default)
    try:
        return float(val)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _int(rec: Mapping[str, Any], name: str, default: int = 0) -> int:
    val = rec.get(name, default)
    try:
        return int(val)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _is_pass(status: str) -> bool:
    return status == "PASS"


# ═══════════════════════════════════════════════════════════════════════════
# Aggregation
# ═══════════════════════════════════════════════════════════════════════════


class _Aggregates:
    """Pre-computed aggregates shared by both renderers."""

    def __init__(self, records: Sequence[Mapping[str, Any]], meta: Mapping[str, Any]) -> None:
        self.meta = meta
        self.records = list(records)
        self.total = len(self.records)
        self.generated_at = str(meta.get("generated_at", "")) if meta else ""

        # Status counts (ordered).
        self.status_counts: "OrderedDict[str, int]" = OrderedDict(
            (s, 0) for s in _STATUS_ORDER
        )
        # Per-model aggregates.
        per_model: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"total": 0, "passed": 0, "score_sum": 0.0,
                     "runtime_sum": 0.0, "tokens_sum": 0, "cost_sum": 0.0}
        )
        # Per-category aggregates.
        per_category: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"total": 0, "passed": 0, "score_sum": 0.0}
        )
        # Per (model, category) for grouped tables.
        per_model_category: dict[tuple[str, str], dict[str, Any]] = defaultdict(
            lambda: {"total": 0, "passed": 0, "score_sum": 0.0}
        )
        # Failure-category counts.
        failure_counts: dict[str, int] = defaultdict(int)

        runtime_total = 0.0
        tokens_total = 0
        cost_total = 0.0
        score_total = 0.0
        passed_total = 0

        for rec in self.records:
            status = _status_of(rec)
            self.status_counts[status] = self.status_counts.get(status, 0) + 1

            model = _model_of(rec)
            cat = _category_of(rec)
            passed = _is_pass(status)
            score = _float(rec, "normalized_score",
                           _float(rec, "score", 0.0))
            runtime = _float(rec, "runtime_seconds",
                            _float(rec, "elapsed_seconds", 0.0))
            tokens = _int(rec, "total_tokens",
                          _int(rec, "output_tokens", 0))
            cost = _float(rec, "cost", 0.0)

            if passed:
                passed_total += 1
            score_total += score
            runtime_total += runtime
            tokens_total += tokens
            cost_total += cost

            m = per_model[model]
            m["total"] += 1
            if passed:
                m["passed"] += 1
            m["score_sum"] += score
            m["runtime_sum"] += runtime
            m["tokens_sum"] += tokens
            m["cost_sum"] += cost

            c = per_category[cat]
            c["total"] += 1
            if passed:
                c["passed"] += 1
            c["score_sum"] += score

            mc = per_model_category[(model, cat)]
            mc["total"] += 1
            if passed:
                mc["passed"] += 1
            mc["score_sum"] += score

            fc = rec.get("failure_category", "")
            if fc and str(fc) != "none":
                failure_counts[str(fc)] += 1

        self.passed_total = passed_total
        self.runtime_total = runtime_total
        self.tokens_total = tokens_total
        self.cost_total = cost_total
        self.score_total = score_total
        self.overall_pass_rate = (
            passed_total / self.total if self.total else 0.0
        )
        self.mean_score = score_total / self.total if self.total else 0.0
        self.mean_runtime = runtime_total / self.total if self.total else 0.0
        self.mean_tokens = tokens_total / self.total if self.total else 0
        self.mean_cost = cost_total / self.total if self.total else 0.0

        # Sort models by name for deterministic output (stable).
        self.per_model = OrderedDict(
            sorted(per_model.items(), key=lambda kv: kv[0])
        )
        # Sort categories by canonical order, unknowns last alphabetically.
        self.per_category = OrderedDict(
            sorted(
                per_category.items(),
                key=lambda kv: (
                    _CATEGORY_ORDER.index(kv[0])
                    if kv[0] in _CATEGORY_ORDER
                    else len(_CATEGORY_ORDER),
                    kv[0],
                ),
            )
        )
        self.per_model_category = per_model_category
        self.failure_counts = OrderedDict(
            sorted(failure_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        )

    def model_pass_rate(self, model: str) -> float:
        m = self.per_model[model]
        return m["passed"] / m["total"] if m["total"] else 0.0

    def model_mean_score(self, model: str) -> float:
        m = self.per_model[model]
        return m["score_sum"] / m["total"] if m["total"] else 0.0

    def model_mean_runtime(self, model: str) -> float:
        m = self.per_model[model]
        return m["runtime_sum"] / m["total"] if m["total"] else 0.0


# ═══════════════════════════════════════════════════════════════════════════
# Formatting helpers
# ═══════════════════════════════════════════════════════════════════════════


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _money(x: float) -> str:
    return f"${x:.4f}" if x < 10 else f"${x:.2f}"


def _meta_timestamp(results: Any) -> str:
    """Best-effort generated_at from a results-dict wrapper, else now()."""
    from datetime import datetime, timezone

    if isinstance(results, Mapping):
        ts = results.get("generated_at") or results.get("timestamp")
        if ts:
            return str(ts)
        manifest = results.get("manifest")
        if manifest is not None:
            ts = (
                manifest.get("completion_timestamp")
                if isinstance(manifest, Mapping)
                else getattr(manifest, "completion_timestamp", None)
            )
            if ts:
                return str(ts)
    return datetime.now(timezone.utc).isoformat()


def _meta_title(results: Any) -> str:
    if isinstance(results, Mapping):
        title = results.get("title") or results.get("benchmark_name")
        if title:
            return str(title)
    return "Model Benchmark Report"


# ═══════════════════════════════════════════════════════════════════════════
# Text report
# ═══════════════════════════════════════════════════════════════════════════


# generate_text_report extended per P3 §4.1: additive keyword-only params
# manifest, stats, comparison, regressions (all defaulted None).
# New sections appended only when the corresponding param is non-None.
# Type sources (P2): RunManifest (schema.py L303), RunStatistics (L548),
# ComparisonResult (L496), Regression (L522).
def generate_text_report(
    results: Any,
    *,
    manifest: Any = None,
    stats: Any = None,
    comparison: Any = None,
    regressions: Any = None,
) -> str:
    """Render a plain-text summary report with key metrics.

    Args:
        results: an iterable of ``ResultRecord`` objects (or dict-like
            records), or a mapping with a ``"records"`` key.  An optional
            ``generated_at`` / ``manifest.completion_timestamp`` in the
            wrapper is used as the report timestamp.
        manifest: optional ``RunManifest`` for the report header.
        stats: optional ``RunStatistics`` (or list thereof) for variance/CI table.
        comparison: optional ``ComparisonResult`` for baseline diff table.
        regressions: optional ``list[Regression]`` for per-case regression table.

    Returns:
        A multi-line plain-text string suitable for stdout or ``--output``.
    """
    records = _coerce_records(results)
    meta = results if isinstance(results, Mapping) else {}
    agg = _Aggregates(records, meta)
    title = _meta_title(results)
    generated_at = agg.generated_at or _meta_timestamp(results)

    lines: list[str] = []
    bar = "=" * _BAR_WIDTH
    lines.append(bar)
    lines.append(title)
    lines.append(bar)
    if generated_at:
        lines.append(f"Generated: {generated_at}")
    lines.append(f"Total Cases: {agg.total}")
    lines.append(f"Overall Pass Rate: {_pct(agg.overall_pass_rate)}")
    lines.append(f"Mean Score: {agg.mean_score:.3f}")
    lines.append("")

    # Status summary.
    lines.append("Status Summary:")
    for status in _STATUS_ORDER:
        count = agg.status_counts.get(status, 0)
        if count:
            lines.append(f"  {status:<9}: {count}")
    # Any unexpected statuses.
    for status, count in agg.status_counts.items():
        if status not in _STATUS_ORDER and count:
            lines.append(f"  {status:<9}: {count}")
    lines.append("")

    # Per-model results.
    if agg.per_model:
        lines.append("Per-Model Results:")
        for model, m in agg.per_model.items():
            rate = m["passed"] / m["total"] if m["total"] else 0.0
            mean_score = m["score_sum"] / m["total"] if m["total"] else 0.0
            mean_rt = m["runtime_sum"] / m["total"] if m["total"] else 0.0
            lines.append(f"  {model}")
            lines.append(
                f"    Cases: {m['total']}   Passed: {m['passed']}   "
                f"Failed: {m['total'] - m['passed']}   Pass Rate: {_pct(rate)}"
            )
            lines.append(
                f"    Avg Score: {mean_score:.3f}   "
                f"Avg Runtime: {mean_rt:.3f}s   "
                f"Total Tokens: {m['tokens_sum']}   "
                f"Cost: {_money(m['cost_sum'])}"
            )
        lines.append("")

    # Per-category results.
    if agg.per_category:
        lines.append("Per-Category Results:")
        for cat, c in agg.per_category.items():
            rate = c["passed"] / c["total"] if c["total"] else 0.0
            lines.append(
                f"  {cat}: {c['passed']}/{c['total']} ({_pct(rate)})"
            )
        lines.append("")

    # Runtime & token summary.
    lines.append("Runtime & Token Summary:")
    lines.append(
        f"  Mean Runtime: {agg.mean_runtime:.3f}s   "
        f"Total Tokens: {agg.tokens_total}   "
        f"Mean Tokens: {agg.mean_tokens}   "
        f"Mean Cost: {_money(agg.mean_cost)}"
    )
    lines.append("")

    # Failure-category breakdown (if any failures recorded).
    if agg.failure_counts:
        lines.append("Failure Categories:")
        for fc, count in agg.failure_counts.items():
            lines.append(f"  {fc}: {count}")
        lines.append("")

    # ── Manifest header ───────────────────────────────────────────────────
    if manifest is not None:
        lines.append("Run Manifest:")
        run_id = getattr(manifest, "run_id", "") or ""
        if run_id:
            lines.append(f"  Run ID: {run_id}")
        commit = getattr(manifest, "source_commit_hash", "") or ""
        if commit:
            lines.append(f"  Commit: {commit}")
        models = getattr(manifest, "model_names", ()) or ()
        if models:
            lines.append(f"  Models: {', '.join(models)}")
        lines.append("")

    # ── Variance/CI table ─────────────────────────────────────────────────
    if stats is not None:
        stats_list = stats if isinstance(stats, list) else [stats]
        if stats_list:
            lines.append("Variance & Confidence Intervals:")
            for s in stats_list:
                tid = getattr(s, "test_id", "?")
                n = getattr(s, "n", 0)
                mean = getattr(s, "mean", 0.0)
                ci_lo = getattr(s, "ci_lower", 0.0)
                ci_hi = getattr(s, "ci_upper", 0.0)
                hv = getattr(s, "high_variance", False)
                lines.append(
                    f"  {tid}: n={n} mean={mean:.3f} "
                    f"CI=[{ci_lo:.3f}, {ci_hi:.3f}]"
                    f"{' (high variance)' if hv else ''}"
                )
            lines.append("")

    # ── Baseline comparison table ─────────────────────────────────────────
    if comparison is not None:
        lines.append("Baseline Comparison:")
        abs_diff = getattr(comparison, "absolute_score_diff", 0.0)
        rel_diff = getattr(comparison, "relative_score_diff", 0.0)
        newly_fail = getattr(comparison, "newly_failing", ()) or ()
        newly_pass = getattr(comparison, "newly_passing", ()) or ()
        lines.append(f"  Absolute Score Diff: {abs_diff:+.3f}")
        lines.append(f"  Relative Score Diff: {rel_diff:+.3f}")
        if newly_fail:
            lines.append(f"  Newly Failing: {len(newly_fail)}")
        if newly_pass:
            lines.append(f"  Newly Passing: {len(newly_pass)}")
        lines.append("")

    # ── Regression table ─────────────────────────────────────────────────
    if regressions:
        lines.append("Regressions:")
        for reg in regressions:
            tid = getattr(reg, "test_id", "?")
            cat = getattr(reg, "category", "?")
            diff = getattr(reg, "score_diff", 0.0)
            sev = getattr(reg, "severity", "?")
            lines.append(
                f"  {tid} ({cat}): diff={diff:+.3f} severity={sev}"
            )
        lines.append("")

    lines.append(bar)
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# Markdown report
# ═══════════════════════════════════════════════════════════════════════════


def _md_table(header: Sequence[str], rows: Sequence[Sequence[Any]],
              aligns: Sequence[str] | None = None) -> str:
    """Render a GitHub-flavoured Markdown table.

    Args:
        header: column header labels.
        rows: one row of cell values per record (values stringified).
        aligns: per-column alignment: ``"l"`` (left), ``"c"`` (centre),
            ``"r"`` (right).  Defaults to left for all columns.
    """
    n = len(header)
    if aligns is None:
        aligns = ["l"] * n
    align_marks = {"l": ":--", "c": ":-:", "r": "--:"}
    sep = [align_marks.get(a, ":--") for a in aligns]
    out = []
    out.append("| " + " | ".join(str(h) for h in header) + " |")
    out.append("| " + " | ".join(sep) + " |")
    for row in rows:
        cells = [str(c) for c in row]
        # Pad/trim to header width.
        if len(cells) < n:
            cells += [""] * (n - len(cells))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


# generate_markdown_report extended per P3 §4.2: same 4 new keyword-only
# params as generate_text_report plus the existing group_by.  New Markdown
# sections appended only when the corresponding param is non-None.
def generate_markdown_report(
    results: Any,
    *,
    manifest: Any = None,
    stats: Any = None,
    comparison: Any = None,
    regressions: Any = None,
    group_by: str | None = None,
) -> str:
    """Render a Markdown report with tables for key metrics.

    Args:
        results: an iterable of ``ResultRecord`` objects (or dict-like
            records), or a mapping with a ``"records"`` key.
        manifest: optional ``RunManifest`` for the report header.
        stats: optional ``RunStatistics`` (or list thereof) for variance/CI section.
        comparison: optional ``ComparisonResult`` for baseline diff section.
        regressions: optional ``list[Regression]`` for per-case regression section.
        group_by: optional grouping for the breakdown section:

            * ``"model"`` — one per-model subsection, each with a
              per-category table for that model.
            * ``"category"`` — one per-category subsection, each with a
              per-model table for that category.
            * ``None`` (default) — flat per-model and per-category tables.

    Returns:
        A Markdown string with a top-level heading, an overall summary
        table, a per-model results table, a per-category table, a status
        breakdown table, and (optionally) grouped subsections.
    """
    records = _coerce_records(results)
    meta = results if isinstance(results, Mapping) else {}
    agg = _Aggregates(records, meta)
    title = _meta_title(results)
    generated_at = agg.generated_at or _meta_timestamp(results)

    out: list[str] = []
    out.append(f"# {title}")
    out.append("")
    if generated_at:
        out.append(f"_Generated: {generated_at}_")
        out.append("")

    # ── Overall summary table ────────────────────────────────────────────
    out.append("## Overall Summary")
    out.append("")
    out.append(_md_table(
        ["Metric", "Value"],
        [
            ["Total Cases", agg.total],
            ["Passed", agg.passed_total],
            ["Failed", agg.total - agg.passed_total],
            ["Overall Pass Rate", _pct(agg.overall_pass_rate)],
            ["Mean Score", f"{agg.mean_score:.3f}"],
            ["Mean Runtime (s)", f"{agg.mean_runtime:.3f}"],
            ["Total Tokens", agg.tokens_total],
            ["Mean Tokens", agg.mean_tokens],
            ["Total Cost", _money(agg.cost_total)],
        ],
        aligns=["l", "r"],
    ))
    out.append("")

    # ── Status breakdown table ───────────────────────────────────────────
    status_rows = [
        [status, agg.status_counts.get(status, 0)]
        for status in _STATUS_ORDER
        if agg.status_counts.get(status, 0)
    ]
    for status, count in agg.status_counts.items():
        if status not in _STATUS_ORDER and count:
            status_rows.append([status, count])
    if status_rows:
        out.append("## Status Breakdown")
        out.append("")
        out.append(_md_table(
            ["Status", "Count"],
            status_rows,
            aligns=["l", "r"],
        ))
        out.append("")

    # ── Per-model results table ───────────────────────────────────────────
    if agg.per_model:
        out.append("## Per-Model Results")
        out.append("")
        rows = []
        for model, m in agg.per_model.items():
            rate = m["passed"] / m["total"] if m["total"] else 0.0
            mean_score = m["score_sum"] / m["total"] if m["total"] else 0.0
            mean_rt = m["runtime_sum"] / m["total"] if m["total"] else 0.0
            rows.append([
                model, m["total"], m["passed"],
                m["total"] - m["passed"], _pct(rate),
                f"{mean_score:.3f}", f"{mean_rt:.3f}",
                m["tokens_sum"], _money(m["cost_sum"]),
            ])
        out.append(_md_table(
            ["Model", "Cases", "Passed", "Failed", "Pass Rate",
             "Avg Score", "Avg Runtime (s)", "Total Tokens", "Cost"],
            rows,
            aligns=["l", "r", "r", "r", "r", "r", "r", "r", "r"],
        ))
        out.append("")

    # ── Per-category results table ───────────────────────────────────────
    if agg.per_category:
        out.append("## Per-Category Results")
        out.append("")
        rows = []
        for cat, c in agg.per_category.items():
            rate = c["passed"] / c["total"] if c["total"] else 0.0
            mean_score = c["score_sum"] / c["total"] if c["total"] else 0.0
            rows.append([
                cat, c["total"], c["passed"], c["total"] - c["passed"],
                _pct(rate), f"{mean_score:.3f}",
            ])
        out.append(_md_table(
            ["Category", "Total", "Passed", "Failed", "Pass Rate", "Avg Score"],
            rows,
            aligns=["l", "r", "r", "r", "r", "r"],
        ))
        out.append("")

    # ── Failure-category table ───────────────────────────────────────────
    if agg.failure_counts:
        out.append("## Failure Categories")
        out.append("")
        rows = [
            [fc, count, _pct(count / agg.total) if agg.total else "0.0%"]
            for fc, count in agg.failure_counts.items()
        ]
        out.append(_md_table(
            ["Failure Category", "Count", "% of Cases"],
            rows,
            aligns=["l", "r", "r"],
        ))
        out.append("")

    # ── Optional grouped subsections ─────────────────────────────────────
    if group_by == "model" and agg.per_model:
        out.append("## Breakdown by Model")
        out.append("")
        for model in agg.per_model:
            out.append(f"### {model}")
            out.append("")
            rows = []
            for cat in agg.per_category:
                mc = agg.per_model_category.get((model, cat))
                if mc is None:
                    continue
                rate = mc["passed"] / mc["total"] if mc["total"] else 0.0
                mean_score = mc["score_sum"] / mc["total"] if mc["total"] else 0.0
                rows.append([
                    cat, mc["total"], mc["passed"],
                    mc["total"] - mc["passed"], _pct(rate),
                    f"{mean_score:.3f}",
                ])
            if rows:
                out.append(_md_table(
                    ["Category", "Total", "Passed", "Failed",
                     "Pass Rate", "Avg Score"],
                    rows,
                    aligns=["l", "r", "r", "r", "r", "r"],
                ))
            else:
                out.append("_No cases for this model._")
            out.append("")

    elif group_by == "category" and agg.per_category:
        out.append("## Breakdown by Category")
        out.append("")
        for cat in agg.per_category:
            out.append(f"### {cat}")
            out.append("")
            rows = []
            for model in agg.per_model:
                mc = agg.per_model_category.get((model, cat))
                if mc is None:
                    continue
                rate = mc["passed"] / mc["total"] if mc["total"] else 0.0
                mean_score = mc["score_sum"] / mc["total"] if mc["total"] else 0.0
                rows.append([
                    model, mc["total"], mc["passed"],
                    mc["total"] - mc["passed"], _pct(rate),
                    f"{mean_score:.3f}",
                ])
            if rows:
                out.append(_md_table(
                    ["Model", "Total", "Passed", "Failed",
                     "Pass Rate", "Avg Score"],
                    rows,
                    aligns=["l", "r", "r", "r", "r", "r"],
                ))
            else:
                out.append("_No cases for this category._")
            out.append("")

    # ── Manifest header (P5 mock) ─────────────────────────────────────────
    if manifest is not None:
        out.append("## Run Manifest")
        out.append("")
        run_id = getattr(manifest, "run_id", "") or ""
        commit = getattr(manifest, "source_commit_hash", "") or ""
        models = getattr(manifest, "model_names", ()) or ()
        rows = []
        if run_id:
            rows.append(["Run ID", run_id])
        if commit:
            rows.append(["Commit", commit])
        if models:
            rows.append(["Models", ", ".join(models)])
        if rows:
            out.append(_md_table(["Field", "Value"], rows, aligns=["l", "l"]))
            out.append("")

    # ── Variance/CI table (P5 mock) ───────────────────────────────────────
    if stats is not None:
        stats_list = stats if isinstance(stats, list) else [stats]
        if stats_list:
            out.append("## Variance & Confidence Intervals")
            out.append("")
            rows = []
            for s in stats_list:
                tid = getattr(s, "test_id", "?")
                n = getattr(s, "n", 0)
                mean = getattr(s, "mean", 0.0)
                ci_lo = getattr(s, "ci_lower", 0.0)
                ci_hi = getattr(s, "ci_upper", 0.0)
                hv = getattr(s, "high_variance", False)
                rows.append([
                    tid, n, f"{mean:.3f}",
                    f"[{ci_lo:.3f}, {ci_hi:.3f}]",
                    "yes" if hv else "no",
                ])
            out.append(_md_table(
                ["Test ID", "N", "Mean", "95% CI", "High Var"],
                rows,
                aligns=["l", "r", "r", "r", "l"],
            ))
            out.append("")

    # ── Baseline comparison section (P5 mock) ──────────────────────────────
    if comparison is not None:
        out.append("## Baseline Comparison")
        out.append("")
        abs_diff = getattr(comparison, "absolute_score_diff", 0.0)
        rel_diff = getattr(comparison, "relative_score_diff", 0.0)
        newly_fail = getattr(comparison, "newly_failing", ()) or ()
        newly_pass = getattr(comparison, "newly_passing", ()) or ()
        out.append(_md_table(
            ["Metric", "Value"],
            [
                ["Absolute Score Diff", f"{abs_diff:+.3f}"],
                ["Relative Score Diff", f"{rel_diff:+.3f}"],
                ["Newly Failing", len(newly_fail)],
                ["Newly Passing", len(newly_pass)],
            ],
            aligns=["l", "r"],
        ))
        out.append("")

    # ── Regression table (P5 mock) ─────────────────────────────────────────
    if regressions:
        out.append("## Regressions")
        out.append("")
        rows = []
        for reg in regressions:
            tid = getattr(reg, "test_id", "?")
            cat = getattr(reg, "category", "?")
            diff = getattr(reg, "score_diff", 0.0)
            sev = getattr(reg, "severity", "?")
            rows.append([tid, cat, f"{diff:+.3f}", sev])
        out.append(_md_table(
            ["Test ID", "Category", "Score Diff", "Severity"],
            rows,
            aligns=["l", "l", "r", "l"],
        ))
        out.append("")

    return "\n".join(out)


# Interface aliases per P3 §4.3 (P5 mock).
format_summary_text = generate_text_report
format_summary_markdown = generate_markdown_report


# Legacy format_report_text / format_report_json stay in scoring.py (P3 §8.6
# reference only — backward compat).  Listed here for reference.
