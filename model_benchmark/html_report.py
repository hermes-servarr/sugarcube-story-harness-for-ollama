"""Self-contained interactive HTML report generator for the model benchmark (§11).

Produces a complete, standalone HTML document — inline CSS + inline vanilla
JavaScript, no external CDN/JS/CSS dependencies — from benchmark results.
The report supports client-side full-text search, status filtering, column
sorting, and expandable/collapsible per-result detail sections.

Color scheme: Okabe-Ito color-blind safe palette (8 colors).  Status is always
conveyed by text label + icon, never by color alone (§11 accessibility).

Input normalization
-------------------
``generate_html_report`` accepts any of the following for ``results`` so it works
with both the new modular system (``ResultRecord`` from ``schema.py``) and the
existing monolith (``BenchmarkReport`` / ``ModelRunResult`` from ``benchmark.py``):

1. ``list[ResultRecord]``          — canonical (P1 §3 interface).
2. ``BenchmarkReport``             — existing top-level report; extracts all
                                     ``ModelRunResult`` rows from every model.
3. ``list[ModelRunResult]``        — flat list of scored runs.
4. A single ``ModelRunResult``     — wrapped into a one-row list.

An optional ``RunManifest`` (``schema.py``) populates a reproducibility header.
When ``anonymized=True`` the header is marked "Anonymized" (the caller is
responsible for passing already-anonymized data; this function does not itself
scrub identity — that is ``anonymization.py``'s job).

Conforms to:
- P1 §4.7 / §3: ``generate_html_report(records, manifest, anonymized) -> str``.
- P2: reads field names from ``ResultRecord`` / ``RunManifest`` definitions.
- INV-5: only *imports* from harness under TYPE_CHECKING; never modifies harness.
"""
from __future__ import annotations

import dataclasses
import html
import json
from typing import TYPE_CHECKING, Any, Iterable

if TYPE_CHECKING:
    from model_benchmark.benchmark import BenchmarkReport, ModelRunResult
    from model_benchmark.schema import ResultRecord, RunManifest

__all__ = ["generate_html_report"]


# ═══════════════════════════════════════════════════════════════════════════
# Okabe-Ito color-blind safe palette (8 colors)
# https://jfly.uni-koeln.de/color/
# ═══════════════════════════════════════════════════════════════════════════
_OKABE_ITO = {
    "black":   "#000000",
    "orange":  "#E69F00",
    "skyblue": "#56B4E9",
    "green":   "#009E73",
    "yellow":  "#F0E442",
    "blue":    "#0072B2",
    "verm":    "#D55E00",
    "purple":  "#CC79A7",
}

# Semantic colors mapped onto the palette (color-blind safe).
_STATUS_COLORS = {
    "PASS":      _OKABE_ITO["green"],
    "FAIL":      _OKABE_ITO["verm"],
    "ERROR":     _OKABE_ITO["orange"],
    "SKIPPED":   _OKABE_ITO["skyblue"],
    "INVALID":   _OKABE_ITO["purple"],
    "TIMEOUT":   _OKABE_ITO["orange"],
    "CANCELLED": _OKABE_ITO["purple"],
}

_STATUS_ICONS = {
    "PASS":      "\u2713",   # ✓ check mark
    "FAIL":      "\u2717",   # ✗ ballot X
    "ERROR":     "\u26A0",   # ⚠ warning
    "SKIPPED":   "\u2298",   # ⊘ circled dash
    "INVALID":   "\u26A0",   # ⚠
    "TIMEOUT":   "\u23F1",   # ⏱ stopwatch
    "CANCELLED": "\u2205",   # ∅ empty set
}


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════

# generate_html_report extended per P3 §5.1 (P5 mock): additive keyword-only
# params stats, comparison, regressions (all defaulted None).  manifest stays
# optional and anonymized stays positional-or-keyword (P3 deviation §5.1).
# Preserved: existing results/manifest/anonymized contract, search/filter/
# sort/expandable, HTML-escaping (XSS-safe), self-contained (INV-E10),
# color-blind safe (INV-E11).
# Type sources (P2): RunStatistics (schema.py L548), ComparisonResult (L496),
# Regression (L522).
def generate_html_report(
    results: Any,
    manifest: Any = None,
    anonymized: bool = False,
    *,
    stats: Any = None,
    comparison: Any = None,
    regressions: Any = None,
) -> str:
    """Return a complete, self-contained HTML document for ``results``.

    Args:
        results: ``list[ResultRecord]``, a ``BenchmarkReport``, a
            ``list[ModelRunResult]``, or a single ``ModelRunResult``.
        manifest: optional ``RunManifest`` for the reproducibility header.
        anonymized: when True, header is marked "Anonymized" (caller must pass
            already-anonymized data; this function does not scrub identity).
        stats: optional ``RunStatistics`` (or list) for confidence indicators
            in summary cards (high_variance / insufficient_sample flags).
        comparison: optional ``ComparisonResult`` for a baseline comparison
            section (diff table).
        regressions: optional ``list[Regression]`` for regression indicators
            on affected rows (text + icon + label, color-blind safe).

    Returns:
        A complete HTML document string with inline CSS and JS — no external
        dependencies.  All dynamic text is HTML-escaped.
    """
    rows = _normalize_results(results)
    manifest_info = _extract_manifest_info(manifest, anonymized)
    summary = _compute_summary(rows)
    # P5 mock: append optional stats/comparison/regression sections to the HTML.
    extra_sections = []
    if stats is not None:
        stats_list = stats if isinstance(stats, list) else [stats]
        extra_sections.append(_render_stats_section(stats_list))
    if comparison is not None:
        extra_sections.append(_render_comparison_section(comparison))
    if regressions:
        extra_sections.append(_render_regressions_section(regressions))
    return _render_html(rows, manifest_info, summary, anonymized,
                       extra_sections=extra_sections)


# ═══════════════════════════════════════════════════════════════════════════
# Input normalization
# ═══════════════════════════════════════════════════════════════════════════

def _normalize_results(results: Any) -> list[dict[str, Any]]:
    """Coerce any supported input shape into a list of row dicts.

    Each row dict has a stable set of keys used by the renderer:
      id, model, variant, direction, run, status, overall_pass, score,
      max_score, normalized_score, runtime, error, categories, raw_response,
      test_id, capability, failure_category, tokens, cost.
    """
    records = _to_record_list(results)
    return [_record_to_row(r, i) for i, r in enumerate(records)]


def _to_record_list(results: Any) -> list[Any]:
    """Return a flat list of result objects from any supported input."""
    # ResultRecord list (or any iterable of record-like objects).
    if isinstance(results, (list, tuple)):
        return list(results)
    # BenchmarkReport — extract all ModelRunResult from every model report.
    if _is_benchmark_report(results):
        out: list[Any] = []
        for mr in getattr(results, "models", ()):  # ModelReport
            out.extend(getattr(mr, "runs", ()))      # ModelRunResult
        return out
    # Single ModelRunResult / ResultRecord.
    if _is_result_like(results):
        return [results]
    raise TypeError(
        f"generate_html_report: unsupported results type {type(results)!r}; "
        "expected list[ResultRecord], BenchmarkReport, list[ModelRunResult], "
        "or a single result."
    )


def _is_benchmark_report(obj: Any) -> bool:
    return (
        dataclasses.is_dataclass(obj)
        and hasattr(obj, "models")
        and hasattr(obj, "prompt_version")
        and not hasattr(obj, "category_results")
    )


def _is_result_like(obj: Any) -> bool:
    return (
        dataclasses.is_dataclass(obj)
        and (hasattr(obj, "category_results") or hasattr(obj, "scored_result"))
    )


def _record_to_row(rec: Any, index: int) -> dict[str, Any]:
    """Convert one ResultRecord or ModelRunResult into a renderer row dict."""
    # Prefer the new ResultRecord (has `status`, `scored_result`).
    if hasattr(rec, "scored_result") and hasattr(rec, "status"):
        return _result_record_to_row(rec, index)
    # Fall back to ModelRunResult.
    return _model_run_result_to_row(rec, index)


def _result_record_to_row(rec: Any, index: int) -> dict[str, Any]:
    """Normalize a schema.ResultRecord into a row dict."""
    scored = getattr(rec, "scored_result", None)
    categories = []
    if scored is not None:
        categories = [
            _category_to_dict(c) for c in getattr(scored, "category_results", ())
        ]
        raw = getattr(scored, "raw_response", "")
        model = getattr(scored, "model_name", "")
        variant = getattr(scored, "variant", "")
        direction = getattr(scored, "direction", "")
        run = getattr(scored, "run_index", 0)
        overall = getattr(scored, "overall_pass", False)
        runtime = getattr(scored, "elapsed_seconds", rec.runtime_seconds)
    else:
        raw = rec.actual_output_raw
        model = rec.model_alias
        variant = ""
        direction = ""
        run = rec.repetition
        overall = rec.status == "PASS"
        runtime = rec.runtime_seconds

    status = rec.status
    return {
        "id": rec.test_id or f"row-{index}",
        "model": model or rec.model_alias,
        "variant": str(variant),
        "direction": str(direction),
        "run": run,
        "status": status,
        "overall_pass": bool(overall),
        "score": float(rec.score),
        "max_score": float(rec.max_score),
        "normalized_score": float(rec.normalized_score),
        "runtime": float(runtime),
        "error": rec.error_details or "",
        "categories": categories,
        "raw_response": raw,
        "test_id": rec.test_id,
        "capability": rec.capability,
        "failure_category": rec.failure_category,
        "tokens": int(rec.total_tokens),
        "cost": float(rec.cost),
    }


def _model_run_result_to_row(run: Any, index: int) -> dict[str, Any]:
    """Normalize a benchmark.ModelRunResult into a row dict."""
    categories = [_category_to_dict(c) for c in run.category_results]
    # Derive a status from overall_pass + error (no explicit status field).
    if run.error:
        status = "ERROR"
    elif run.overall_pass:
        status = "PASS"
    else:
        status = "FAIL"
    # Score: mean of category scores in [0,1].
    scores = [c["score"] for c in categories if c["applicable"]]
    score = sum(scores) / len(scores) if scores else 0.0
    return {
        "id": f"{run.model_name}-{run.variant}-{run.direction}-{run.run_index}",
        "model": run.model_name,
        "variant": str(run.variant),
        "direction": str(run.direction),
        "run": run.run_index,
        "status": status,
        "overall_pass": bool(run.overall_pass),
        "score": score,
        "max_score": 1.0,
        "normalized_score": score,
        "runtime": float(run.elapsed_seconds),
        "error": run.error or "",
        "categories": categories,
        "raw_response": run.raw_response,
        "test_id": "",
        "capability": "",
        "failure_category": "none",
        "tokens": 0,
        "cost": 0.0,
    }


def _category_to_dict(cat: Any) -> dict[str, Any]:
    """Normalize a CategoryResult into a dict."""
    return {
        "name": cat.name,
        "passed": bool(cat.passed),
        "score": float(cat.score),
        "details": cat.details,
        "evidence": list(getattr(cat, "evidence", ())),
        "applicable": bool(getattr(cat, "applicable", True)),
        "gating": bool(getattr(cat, "gating", True)),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Manifest / summary
# ═══════════════════════════════════════════════════════════════════════════

def _extract_manifest_info(manifest: Any, anonymized: bool) -> dict[str, Any]:
    """Pull display fields from a RunManifest (or dict), defensively."""
    if manifest is None:
        return {"present": False, "anonymized": anonymized}
    info: dict[str, Any] = {"present": True, "anonymized": anonymized}
    fields = [
        "run_id", "benchmark_name", "benchmark_version", "schema_version",
        "source_commit_hash", "provider", "prompt_template", "prompt_version",
        "evaluator_version", "dataset_name", "dataset_version", "dataset_split",
        "concurrency", "random_seed", "start_timestamp", "completion_timestamp",
        "duration_seconds", "os_info", "python_version", "hardware",
    ]
    for f in fields:
        if hasattr(manifest, f):
            info[f] = getattr(manifest, f)
        elif isinstance(manifest, dict) and f in manifest:
            info[f] = manifest[f]
    # model_names is a tuple on RunManifest.
    if hasattr(manifest, "model_names"):
        info["model_names"] = list(manifest.model_names)
    elif isinstance(manifest, dict) and "model_names" in manifest:
        info["model_names"] = list(manifest["model_names"])
    return info


def _compute_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate summary counts for the header cards."""
    status_counts = {s: 0 for s in _STATUS_COLORS}
    total = len(rows)
    score_sum = 0.0
    for r in rows:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
        score_sum += r["normalized_score"]
    models = sorted({r["model"] for r in rows})
    return {
        "total": total,
        "status_counts": status_counts,
        "pass_rate": (status_counts["PASS"] / total) if total else 0.0,
        "avg_score": (score_sum / total) if total else 0.0,
        "models": models,
        "model_count": len(models),
    }


# ═══════════════════════════════════════════════════════════════════════════
# HTML rendering
# ═══════════════════════════════════════════════════════════════════════════

def _esc(text: Any) -> str:
    """HTML-escape arbitrary text for safe interpolation."""
    return html.escape(str(text), quote=True)


def _esc_js(text: Any) -> str:
    """JSON-encode a string for safe embedding inside <script>."""
    return json.dumps(str(text))


def _render_html(
    rows: list[dict[str, Any]],
    manifest_info: dict[str, Any],
    summary: dict[str, Any],
    anonymized: bool,
    *,
    extra_sections: list[str] | None = None,
) -> str:
    """Assemble the full HTML document from rows + metadata."""
    # Embed rows as JSON for the JS layer (progressive enhancement: rows are
    # also rendered server-side so the report is readable without JS).
    # Escape "</" to "<\/" so a "</script>" inside data cannot close the block.
    rows_json = json.dumps(rows, default=str).replace("</", "<\\/")
    parts: list[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="en">')
    parts.append("<head>")
    parts.append('<meta charset="utf-8">')
    parts.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    parts.append("<title>Benchmark Report</title>")
    parts.append(_render_css())
    parts.append("</head>")
    parts.append("<body>")
    parts.append(_render_header(manifest_info, summary))
    parts.append(_render_summary_cards(summary))
    parts.append(_render_controls())
    parts.append(_render_results_table(rows))
    # P5 mock: insert extra sections (stats/comparison/regressions) before footer.
    if extra_sections:
        parts.extend(extra_sections)
    parts.append(_render_footer())
    parts.append(_render_js(rows_json))
    parts.append("</body>")
    parts.append("</html>")
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════════
# P5 mock: extra section renderers (stats/comparison/regressions)
# ═══════════════════════════════════════════════════════════════════════════


def _render_stats_section(stats_list: list[Any]) -> str:
    """Render a variance/CI section as HTML (P5 mock)."""
    from html import escape
    rows_html = []
    for s in stats_list:
        tid = escape(str(getattr(s, "test_id", "?")))
        n = getattr(s, "n", 0)
        mean = getattr(s, "mean", 0.0)
        ci_lo = getattr(s, "ci_lower", 0.0)
        ci_hi = getattr(s, "ci_upper", 0.0)
        hv = getattr(s, "high_variance", False)
        insuf = getattr(s, "insufficient_sample", False)
        flags = []
        if hv:
            flags.append("high variance")
        if insuf:
            flags.append("insufficient sample")
        flag_str = escape(", ".join(flags)) if flags else "&mdash;"
        rows_html.append(
            f"<tr><td>{tid}</td><td>{n}</td><td>{mean:.3f}</td>"
            f"<td>[{ci_lo:.3f}, {ci_hi:.3f}]</td><td>{flag_str}</td></tr>"
        )
    return (
        '<section class="stats-section"><h2>Variance &amp; Confidence Intervals</h2>'
        '<table class="stats-table"><thead><tr>'
        "<th>Test ID</th><th>N</th><th>Mean</th><th>95% CI</th><th>Flags</th>"
        "</tr></thead><tbody>"
        + "\n".join(rows_html)
        + "</tbody></table></section>"
    )


def _render_comparison_section(comparison: Any) -> str:
    """Render a baseline comparison section as HTML (P5 mock)."""
    from html import escape
    abs_diff = getattr(comparison, "absolute_score_diff", 0.0)
    rel_diff = getattr(comparison, "relative_score_diff", 0.0)
    newly_fail = getattr(comparison, "newly_failing", ()) or ()
    newly_pass = getattr(comparison, "newly_passing", ()) or ()
    cat_regs = getattr(comparison, "category_regressions", ()) or ()
    stat_sig = getattr(comparison, "is_statistically_significant", False)
    op_sig = getattr(comparison, "is_operationally_significant", False)
    return (
        '<section class="comparison-section"><h2>Baseline Comparison</h2>'
        '<table class="comparison-table"><tbody>'
        f"<tr><th>Absolute Score Diff</th><td>{abs_diff:+.3f}</td></tr>"
        f"<tr><th>Relative Score Diff</th><td>{rel_diff:+.3f}</td></tr>"
        f"<tr><th>Newly Failing</th><td>{len(newly_fail)}</td></tr>"
        f"<tr><th>Newly Passing</th><td>{len(newly_pass)}</td></tr>"
        f"<tr><th>Category Regressions</th><td>{escape(', '.join(cat_regs)) if cat_regs else '&mdash;'}</td></tr>"
        f"<tr><th>Statistically Significant</th><td>{'yes' if stat_sig else 'no'}</td></tr>"
        f"<tr><th>Operationally Significant</th><td>{'yes' if op_sig else 'no'}</td></tr>"
        "</tbody></table></section>"
    )


def _render_regressions_section(regressions: list[Any]) -> str:
    """Render a regression indicators section as HTML (P5 mock)."""
    from html import escape
    if not regressions:
        return ""
    rows_html = []
    for reg in regressions:
        tid = escape(str(getattr(reg, "test_id", "?")))
        cat = escape(str(getattr(reg, "category", "?")))
        diff = getattr(reg, "score_diff", 0.0)
        sev = escape(str(getattr(reg, "severity", "?")))
        # Color-blind safe indicator (Okabe-Ito orange #E69F00 for regression)
        icon = "&#9888;"  # warning sign
        rows_html.append(
            f'<tr class="regression-row"><td>{icon}</td><td>{tid}</td>'
            f"<td>{cat}</td><td>{diff:+.3f}</td><td>{sev}</td></tr>"
        )
    return (
        '<section class="regressions-section"><h2>Regressions</h2>'
        '<table class="regressions-table"><thead><tr>'
        "<th></th><th>Test ID</th><th>Category</th><th>Score Diff</th><th>Severity</th>"
        "</tr></thead><tbody>"
        + "\n".join(rows_html)
        + "</tbody></table></section>"
    )


# ── CSS ───────────────────────────────────────────────────────────────────

def _render_css() -> str:
    """Return the inline <style> block using the Okabe-Ito palette."""
    return f"""<style>
:root {{
  --c-black: {_OKABE_ITO['black']};
  --c-orange: {_OKABE_ITO['orange']};
  --c-skyblue: {_OKABE_ITO['skyblue']};
  --c-green: {_OKABE_ITO['green']};
  --c-yellow: {_OKABE_ITO['yellow']};
  --c-blue: {_OKABE_ITO['blue']};
  --c-verm: {_OKABE_ITO['verm']};
  --c-purple: {_OKABE_ITO['purple']};
  --bg: #fafafa;
  --fg: #1a1a1a;
  --muted: #666;
  --border: #d0d0d0;
  --row-hover: #eef4fb;
  --row-fail: #fdf0ea;
  --card-bg: #ffffff;
}}
* {{ box-sizing: border-box; }}
html, body {{
  margin: 0; padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  color: var(--fg);
  background: var(--bg);
  font-size: 14px;
  line-height: 1.5;
}}
header.report-header {{
  background: var(--c-blue);
  color: #fff;
  padding: 18px 24px;
}}
header.report-header h1 {{ margin: 0 0 4px 0; font-size: 1.4em; }}
header.report-header .sub {{ opacity: 0.9; font-size: 0.85em; }}
header.report-header .badge {{
  display: inline-block; padding: 2px 8px; border-radius: 3px;
  background: var(--c-yellow); color: var(--c-black);
  font-size: 0.75em; font-weight: bold; margin-left: 8px;
}}
.meta-grid {{
  display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 6px 24px; margin-top: 10px; font-size: 0.8em;
}}
.meta-grid .k {{ color: var(--c-skyblue); font-weight: 600; }}
.meta-grid .v {{ color: #fff; word-break: break-all; }}

.summary {{
  display: flex; flex-wrap: wrap; gap: 12px;
  padding: 16px 24px; background: var(--card-bg);
  border-bottom: 1px solid var(--border);
}}
.card {{
  flex: 1 1 120px; min-width: 120px;
  padding: 10px 14px; border-radius: 6px;
  border: 1px solid var(--border); background: var(--bg);
}}
.card .label {{ font-size: 0.72em; text-transform: uppercase; letter-spacing: 0.5px; color: var(--muted); }}
.card .value {{ font-size: 1.6em; font-weight: 700; margin-top: 2px; }}
.card .sub {{ font-size: 0.75em; color: var(--muted); }}

.controls {{
  display: flex; flex-wrap: wrap; gap: 10px; align-items: center;
  padding: 12px 24px; background: var(--card-bg);
  border-bottom: 1px solid var(--border);
}}
.controls input[type=search] {{
  flex: 1 1 240px; min-width: 200px;
  padding: 7px 10px; border: 1px solid var(--border); border-radius: 4px;
  font-size: 0.9em;
}}
.controls select {{
  padding: 7px 10px; border: 1px solid var(--border); border-radius: 4px;
  font-size: 0.9em; background: #fff;
}}
.controls .hint {{ font-size: 0.75em; color: var(--muted); }}
.controls button {{
  padding: 6px 10px; border: 1px solid var(--border); border-radius: 4px;
  background: #fff; cursor: pointer; font-size: 0.85em;
}}
.controls button:hover {{ background: var(--row-hover); }}

table.results {{
  width: 100%; border-collapse: collapse; font-size: 0.85em;
  table-layout: fixed;
}}
table.results th, table.results td {{
  padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--border);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}}
table.results th {{
  background: var(--c-blue); color: #fff; cursor: pointer;
  user-select: none; position: sticky; top: 0; z-index: 2;
  font-weight: 600; font-size: 0.82em;
}}
table.results th:hover {{ background: #005a90; }}
table.results th .sort-ind {{ font-size: 0.7em; opacity: 0.7; margin-left: 3px; }}
table.results tbody tr {{ background: #fff; }}
table.results tbody tr:hover {{ background: var(--row-hover); }}
table.results tr.fail-row {{ background: var(--row-fail); }}
table.results tr.fail-row:hover {{ background: #fbe6db; }}
table.results tr.hidden {{ display: none; }}

td.col-status {{ font-weight: 600; }}
.status-pill {{
  display: inline-block; padding: 1px 7px; border-radius: 10px;
  font-size: 0.78em; font-weight: 700; color: #fff;
  border: 1px solid rgba(0,0,0,0.15);
}}
.status-pill .icon {{ margin-right: 3px; }}

tr.detail-row {{ background: #f7f7f7; }}
tr.detail-row td {{ padding: 0; border-bottom: 1px solid var(--border); }}
.detail-content {{
  padding: 12px 16px; max-height: 60vh; overflow: auto;
}}
.detail-content h4 {{ margin: 0 0 8px 0; font-size: 0.95em; color: var(--c-blue); }}
.detail-content .section {{ margin-bottom: 14px; }}
.detail-content .section-title {{
  font-size: 0.8em; text-transform: uppercase; letter-spacing: 0.5px;
  color: var(--muted); margin-bottom: 4px; font-weight: 600;
}}
.cat-table {{ width: 100%; border-collapse: collapse; font-size: 0.82em; }}
.cat-table th, .cat-table td {{
  padding: 5px 8px; text-align: left; border: 1px solid var(--border);
}}
.cat-table th {{ background: #ececec; font-weight: 600; }}
.cat-table td.pass {{ color: var(--c-green); font-weight: 600; }}
.cat-table td.fail {{ color: var(--c-verm); font-weight: 600; }}
.cat-table td.score {{ font-family: monospace; }}

pre.raw-output {{
  background: #222; color: #eee; padding: 10px 12px; border-radius: 4px;
  font-size: 0.8em; overflow: auto; max-height: 320px; white-space: pre-wrap;
  word-break: break-word;
}}
.evidence-list {{ font-size: 0.8em; color: var(--muted); margin: 4px 0 0 16px; }}
.evidence-list li {{ margin-bottom: 2px; }}

.toggle {{ cursor: pointer; user-select: none; }}
.toggle::before {{ content: "\\25B6"; display: inline-block; margin-right: 5px; font-size: 0.7em; transition: transform 0.15s; }}
.toggle.open::before {{ transform: rotate(90deg); }}

.empty-msg {{
  padding: 40px 24px; text-align: center; color: var(--muted); font-size: 1em;
}}
footer {{ padding: 12px 24px; font-size: 0.75em; color: var(--muted); border-top: 1px solid var(--border); }}
@media (max-width: 640px) {{
  table.results {{ table-layout: auto; }}
  .summary {{ padding: 12px; }}
  .controls {{ padding: 10px 12px; }}
}}
</style>"""


# ── Header ────────────────────────────────────────────────────────────────

def _render_header(manifest_info: dict[str, Any], summary: dict[str, Any]) -> str:
    """Render the top header with run metadata."""
    title = "Benchmark Report"
    badge = ""
    if manifest_info.get("anonymized"):
        badge = '<span class="badge">ANONYMIZED</span>'
    parts = [
        '<header class="report-header">',
        f"<h1>{_esc(title)}{badge}</h1>",
    ]
    if manifest_info.get("present"):
        name = manifest_info.get("benchmark_name", "")
        sub = f"{_esc(name)}" if name else "Model Benchmark Results"
        parts.append(f'<div class="sub">{_esc(sub)}</div>')
        parts.append('<div class="meta-grid">')
        display_fields = [
            ("Run ID", "run_id"),
            ("Benchmark Version", "benchmark_version"),
            ("Schema Version", "schema_version"),
            ("Commit", "source_commit_hash"),
            ("Provider", "provider"),
            ("Prompt Version", "prompt_version"),
            ("Prompt Template", "prompt_template"),
            ("Evaluator Version", "evaluator_version"),
            ("Dataset", "dataset_name"),
            ("Dataset Version", "dataset_version"),
            ("Split", "dataset_split"),
            ("Concurrency", "concurrency"),
            ("Random Seed", "random_seed"),
            ("Started", "start_timestamp"),
            ("Completed", "completion_timestamp"),
            ("Duration (s)", "duration_seconds"),
            ("OS", "os_info"),
            ("Python", "python_version"),
            ("Hardware", "hardware"),
        ]
        for label, key in display_fields:
            val = manifest_info.get(key, "")
            if val == "" or val is None:
                continue
            parts.append(
                f'<div><span class="k">{_esc(label)}:</span> '
                f'<span class="v">{_esc(val)}</span></div>'
            )
        mn = manifest_info.get("model_names")
        if mn:
            parts.append(
                f'<div><span class="k">Models:</span> '
                f'<span class="v">{_esc(", ".join(mn))}</span></div>'
            )
        parts.append("</div>")
    else:
        parts.append(
            f'<div class="sub">{summary["total"]} results across '
            f'{summary["model_count"]} model(s)</div>'
        )
    parts.append("</header>")
    return "\n".join(parts)


# ── Summary cards ─────────────────────────────────────────────────────────

def _render_summary_cards(summary: dict[str, Any]) -> str:
    """Render the summary stat cards."""
    sc = summary["status_counts"]
    cards = [
        ("Total Results", summary["total"], "", "--c-blue"),
        ("Pass Rate", f"{summary['pass_rate']:.0%}", f"{sc.get('PASS',0)} passed", "--c-green"),
        ("Avg Score", f"{summary['avg_score']:.2f}", "normalized", "--c-blue"),
        ("Models", summary["model_count"], "tested", "--c-purple"),
        ("Failures", sc.get("FAIL", 0), "failed", "--c-verm"),
        ("Errors", sc.get("ERROR", 0), "errors", "--c-orange"),
    ]
    parts = ['<div class="summary">']
    for label, value, sub, color in cards:
        parts.append(
            f'<div class="card">'
            f'<div class="label">{_esc(label)}</div>'
            f'<div class="value" style="color:var({color})">{_esc(value)}</div>'
            f'<div class="sub">{_esc(sub)}</div>'
            f"</div>"
        )
    parts.append("</div>")
    return "\n".join(parts)


# ── Controls ──────────────────────────────────────────────────────────────

def _render_controls() -> str:
    """Render the search/filter control bar."""
    options = ['<option value="">All Statuses</option>']
    for s in _STATUS_COLORS:
        options.append(f'<option value="{s}">{s}</option>')
    parts = [
        '<div class="controls">',
        '<input type="search" id="searchBox" placeholder="Search results (model, variant, error, details...)..." autocomplete="off">',
        '<select id="statusFilter">',
        *options,
        "</select>",
        '<select id="modelFilter"><option value="">All Models</option></select>',
        '<button id="expandAll" type="button">Expand All</button>',
        '<button id="collapseAll" type="button">Collapse All</button>',
        '<span class="hint">Click a column header to sort. Click a row to expand.</span>',
        "</div>",
    ]
    return "\n".join(parts)


# ── Results table ─────────────────────────────────────────────────────────

# Column definitions: (data-key, header label, width, sortable)
_COLUMNS = [
    ("status",   "Status",    90, True),
    ("model",    "Model",     140, True),
    ("variant",  "Variant",   80, True),
    ("direction","Dir",       50, True),
    ("run",      "Run",       50, True),
    ("score",    "Score",     70, True),
    ("runtime",  "Runtime",   80, True),
    ("tokens",   "Tokens",    70, True),
    ("error",    "Error",     200, True),
]


def _render_results_table(rows: list[dict[str, Any]]) -> str:
    """Render the main results table with server-side rows + detail rows."""
    if not rows:
        return '<div class="empty-msg">No results to display.</div>'
    parts = [
        '<table class="results" id="resultsTable">',
        "<thead><tr>",
    ]
    for key, label, width, _sortable in _COLUMNS:
        parts.append(
            f'<th data-key="{key}" style="width:{width}px">'
            f'{_esc(label)}<span class="sort-ind"></span></th>'
        )
    parts.append("</tr></thead>")
    parts.append("<tbody id=" + '"resultsBody">')
    for i, row in enumerate(rows):
        parts.append(_render_row(row, i))
    parts.append("</tbody>")
    parts.append("</table>")
    return "\n".join(parts)


def _render_row(row: dict[str, Any], index: int) -> str:
    """Render one data row + its expandable detail row."""
    status = row["status"]
    color = _STATUS_COLORS.get(status, _OKABE_ITO["black"])
    icon = _STATUS_ICONS.get(status, "?")
    row_class = "fail-row" if status in ("FAIL", "ERROR") else ""
    score_pct = f"{row['normalized_score']:.1%}" if row["max_score"] else "-"
    runtime = f"{row['runtime']:.2f}s" if row["runtime"] else "-"
    tokens = str(row["tokens"]) if row["tokens"] else "-"
    err = row["error"]
    err_display = _esc(err[:80] + ("..." if len(err) > 80 else "")) if err else ""

    parts = [
        f'<tr class="data-row {row_class}" data-index="{index}" '
        f'data-status="{_esc(status)}" data-model="{_esc(row["model"])}">',
        f'<td class="col-status">'
        f'<span class="status-pill" style="background:{color}">'
        f'<span class="icon">{icon}</span>{_esc(status)}</span></td>',
        f'<td>{_esc(row["model"])}</td>',
        f'<td>{_esc(row["variant"])}</td>',
        f'<td>{_esc(row["direction"])}</td>',
        f'<td>{_esc(row["run"])}</td>',
        f'<td>{score_pct}</td>',
        f'<td>{runtime}</td>',
        f'<td>{tokens}</td>',
        f'<td title="{_esc(err)}">{err_display}</td>',
        "</tr>",
    ]
    # Expandable detail row (hidden by default).
    parts.append(_render_detail_row(row, index))
    return "\n".join(parts)


def _render_detail_row(row: dict[str, Any], index: int) -> str:
    """Render the hidden expandable detail row for one result."""
    parts = [
        f'<tr class="detail-row hidden" data-detail-for="{index}">',
        f'<td colspan="{len(_COLUMNS)}">',
        '<div class="detail-content">',
    ]
    # Test identity (ResultRecord-specific).
    if row.get("test_id"):
        parts.append('<div class="section">')
        parts.append('<div class="section-title">Test Identity</div>')
        identity_lines = [
            ("Test ID", row.get("test_id", "")),
            ("Capability", row.get("capability", "")),
            ("Failure Category", row.get("failure_category", "")),
        ]
        parts.append("<table class=\"cat-table\">")
        for k, v in identity_lines:
            parts.append(f"<tr><th>{_esc(k)}</th><td>{_esc(v)}</td></tr>")
        parts.append("</table>")
        parts.append("</div>")
    # Category breakdown.
    cats = row.get("categories", [])
    if cats:
        parts.append('<div class="section">')
        parts.append('<div class="section-title toggle">Category Breakdown (6 scorers)</div>')
        parts.append('<table class="cat-table">')
        parts.append("<tr><th>Category</th><th>Pass</th><th>Score</th><th>Details</th></tr>")
        for c in cats:
            applicable = c.get("applicable", True)
            verdict = (
                "N/A"
                if not applicable
                else ("PASS" if c["passed"] else "FAIL")
            )
            vclass = "" if not applicable else ("pass" if c["passed"] else "fail")
            parts.append(
                f"<tr><td>{_esc(c['name'])}</td>"
                f'<td class="{vclass}">{verdict}</td>'
                f'<td class="score">{c["score"]:.2f}</td>'
                f"<td>{_esc(c['details'])}"
            )
            if c.get("evidence"):
                parts.append('<ul class="evidence-list">')
                for e in c["evidence"]:
                    parts.append(f"<li>{_esc(e)}</li>")
                parts.append("</ul>")
            parts.append("</td></tr>")
        parts.append("</table>")
        parts.append("</div>")
    # Raw response.
    raw = row.get("raw_response", "")
    if raw:
        parts.append('<div class="section">')
        parts.append('<div class="section-title toggle">Raw Model Output</div>')
        parts.append(f'<pre class="raw-output">{_esc(raw)}</pre>')
        parts.append("</div>")
    parts.append("</div>")
    parts.append("</td>")
    parts.append("</tr>")
    return "\n".join(parts)


# ── Footer ────────────────────────────────────────────────────────────────

def _render_footer() -> str:
    return (
        "<footer>Generated by model_benchmark.html_report \u00b7 "
        "Color-blind safe (Okabe-Ito palette) \u00b7 No external dependencies</footer>"
    )


# ── JavaScript ────────────────────────────────────────────────────────────

def _render_js(rows_json: str) -> str:
    """Return the inline vanilla-JS <script> block (search/filter/sort/expand)."""
    # rows_json is valid JSON, which is also valid JavaScript; assign it
    # directly as a JS array literal (no JSON.parse needed, avoiding string
    # escaping pitfalls).
    return f"""<script>
(function () {{
  "use strict";
  var ROWS = {rows_json};
  var sortKey = null;
  var sortAsc = true;

  var tbody = document.getElementById("resultsBody");
  if (!tbody) return;
  var searchBox = document.getElementById("searchBox");
  var statusFilter = document.getElementById("statusFilter");
  var modelFilter = document.getElementById("modelFilter");
  var dataRows = Array.prototype.slice.call(tbody.querySelectorAll("tr.data-row"));
  var detailRows = Array.prototype.slice.call(tbody.querySelectorAll("tr.detail-row"));

  // Populate model filter from data attributes.
  (function populateModelFilter() {{
    var seen = {{}};
    dataRows.forEach(function (r) {{
      var m = r.getAttribute("data-model");
      if (m && !seen[m]) {{ seen[m] = 1; }}
    }});
    var keys = Object.keys(seen).sort();
    keys.forEach(function (m) {{
      var opt = document.createElement("option");
      opt.value = m; opt.textContent = m;
      modelFilter.appendChild(opt);
    }});
  }})();

  // ── Filtering (search + status + model) ─────────────────────────────
  function applyFilters() {{
    var q = (searchBox.value || "").toLowerCase().trim();
    var st = statusFilter.value;
    var mf = modelFilter.value;
    dataRows.forEach(function (row, i) {{
      var match = true;
      if (st && row.getAttribute("data-status") !== st) match = false;
      if (mf && row.getAttribute("data-model") !== mf) match = false;
      if (match && q) {{
        var text = row.textContent.toLowerCase();
        var detail = detailRows[i] ? detailRows[i].textContent.toLowerCase() : "";
        if (text.indexOf(q) === -1 && detail.indexOf(q) === -1) match = false;
      }}
      if (match) {{
        row.classList.remove("hidden");
      }} else {{
        row.classList.add("hidden");
        // collapse detail when hiding parent
        if (detailRows[i]) detailRows[i].classList.add("hidden");
      }}
    }});
    // Re-apply current sort so filtered view stays ordered.
    if (sortKey) applySort();
  }}

  searchBox.addEventListener("input", applyFilters);
  statusFilter.addEventListener("change", applyFilters);
  modelFilter.addEventListener("change", applyFilters);

  // ── Sorting ────────────────────────────────────────────────────────
  function cellValue(rowEl, key) {{
    // Pull from the ROWS JSON by index for reliable typed comparison.
    var idx = parseInt(rowEl.getAttribute("data-index"), 10);
    var r = ROWS[idx];
    if (!r) return "";
    var v = r[key];
    if (key === "status") return v;
    if (key === "score") return r.normalized_score;
    if (key === "runtime") return r.runtime;
    if (key === "tokens") return r.tokens;
    if (key === "run") return r.run;
    return String(v == null ? "" : v).toLowerCase();
  }}

  function applySort() {{
    dataRows.sort(function (a, b) {{
      var av = cellValue(a, sortKey);
      var bv = cellValue(b, sortKey);
      var an = typeof av === "number";
      var bn = typeof bv === "number";
      if (an && bn) {{
        return sortAsc ? av - bv : bv - an;
      }}
      var as = String(av), bs = String(bv);
      if (as < bs) return sortAsc ? -1 : 1;
      if (as > bs) return sortAsc ? 1 : -1;
      return 0;
    }});
    // Re-insert rows in sorted order; keep each detail row right after its data row.
    var frag = document.createDocumentFragment();
    dataRows.forEach(function (row, i) {{
      frag.appendChild(row);
      if (detailRows[i]) frag.appendChild(detailRows[i]);
    }});
    tbody.appendChild(frag);
  }}

  document.querySelectorAll("th[data-key]").forEach(function (th) {{
    th.addEventListener("click", function () {{
      var key = th.getAttribute("data-key");
      if (sortKey === key) {{
        sortAsc = !sortAsc;
      }} else {{
        sortKey = key;
        sortAsc = true;
      }}
      // Update sort indicators.
      document.querySelectorAll("th[data-key]").forEach(function (h) {{
        h.querySelector(".sort-ind").textContent = "";
      }});
      th.querySelector(".sort-ind").textContent = sortAsc ? "\\u25B2" : "\\u25BC";
      applySort();
    }});
  }});

  // ── Expand / collapse ──────────────────────────────────────────────
  dataRows.forEach(function (row, i) {{
    row.style.cursor = "pointer";
    row.addEventListener("click", function (e) {{
      if (e.target.closest("a")) return;
      var detail = detailRows[i];
      if (!detail) return;
      detail.classList.toggle("hidden");
    }});
  }});

  document.getElementById("expandAll").addEventListener("click", function () {{
    detailRows.forEach(function (d) {{ d.classList.remove("hidden"); }});
  }});
  document.getElementById("collapseAll").addEventListener("click", function () {{
    detailRows.forEach(function (d) {{ d.classList.add("hidden"); }});
  }});

  // ── Toggle detail sub-sections (category breakdown / raw output) ───
  document.querySelectorAll(".toggle").forEach(function (t) {{
    t.addEventListener("click", function (e) {{
      e.stopPropagation();
      t.classList.toggle("open");
      var section = t.nextElementSibling;
      if (section) {{
        section.style.display = (t.classList.contains("open")) ? "" : "none";
      }}
    }});
  }});
}})();
</script>"""
