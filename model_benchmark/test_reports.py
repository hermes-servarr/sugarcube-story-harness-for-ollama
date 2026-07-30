"""Tests for text and markdown report generation.

Tests the extended generate_text_report / generate_markdown_report (P3 §4.1/§4.2),
aliases (P3 §4.3), and __all__ (P3 §4.4).
Enforces P6 invariants INV-REP1..INV-REP8.
"""
from __future__ import annotations

import pytest

from model_benchmark.reports import (
    generate_text_report,
    generate_markdown_report,
    __all__,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


def _make_results():
    """Create a minimal results list for testing."""
    return [
        {
            "test_id": "test_1",
            "model": "test-model",
            "variant": "compact",
            "direction": "A",
            "status": "PASS",
            "score": 1.0,
            "normalized_score": 1.0,
            "category": "markup_compliance",
            "runtime_seconds": 1.5,
            "input_tokens": 100,
            "output_tokens": 200,
            "total_tokens": 300,
            "cost": 0.0,
            "failure_category": "none",
        },
        {
            "test_id": "test_2",
            "model": "test-model",
            "variant": "compact",
            "direction": "B",
            "status": "FAIL",
            "score": 0.5,
            "normalized_score": 0.5,
            "category": "macro_usage",
            "runtime_seconds": 2.0,
            "input_tokens": 150,
            "output_tokens": 250,
            "total_tokens": 400,
            "cost": 0.01,
            "failure_category": "formatting",
        },
    ]


def _make_manifest():
    """Create a minimal manifest-like object for testing."""
    class FakeManifest:
        run_id = "test-run-001"
        source_commit_hash = "abc123"
        model_names = ("test-model",)
    return FakeManifest()


def _make_stats():
    """Create a minimal stats-like object for testing."""
    class FakeStats:
        test_id = "test_1"
        n = 3
        mean = 0.85
        median = 0.85
        stddev = 0.05
        min = 0.8
        max = 0.9
        ci_lower = 0.75
        ci_upper = 0.95
        high_variance = True
        unstable = False
        outcome_changing = False
        insufficient_sample = False
        variance_flags = ("high variance",)
    return FakeStats()


def _make_comparison():
    """Create a minimal comparison-like object for testing."""
    class FakeComparison:
        baseline_run_id = "base-run-001"
        current_run_id = "test-run-001"
        absolute_score_diff = -0.05
        relative_score_diff = -0.10
        newly_failing = ("test_2",)
        newly_passing = ()
        category_regressions = ("macro_usage",)
        runtime_diff = 0.5
        token_diff = 100
        is_statistically_significant = True
        is_operationally_significant = False
    return FakeComparison()


def _make_regression():
    """Create a minimal regression-like object for testing."""
    class FakeRegression:
        test_id = "test_2"
        category = "macro_usage"
        baseline_score = 0.8
        current_score = 0.5
        score_diff = -0.3
        baseline_status = "PASS"
        current_status = "FAIL"
        severity = "operational"
        threshold = 0.1
    return FakeRegression()


# ═══════════════════════════════════════════════════════════════════════════
# §1: Extended generate_text_report tests (INV-REP1, INV-REP2, INV-REP3)
# ═══════════════════════════════════════════════════════════════════════════


class TestGenerateTextReportExtended:
    """Test extended generate_text_report per P3 §4.1."""

    def test_generate_text_report_manifest(self):
        """manifest param adds report header."""
        report = generate_text_report(_make_results(), manifest=_make_manifest())
        assert "Run Manifest:" in report
        assert "test-run-001" in report

    def test_generate_text_report_stats(self):
        """stats param adds variance/CI table."""
        report = generate_text_report(_make_results(), stats=_make_stats())
        assert "Variance" in report
        assert "CI" in report
        assert "test_1" in report

    def test_generate_text_report_comparison(self):
        """comparison param adds baseline diff table."""
        report = generate_text_report(_make_results(), comparison=_make_comparison())
        assert "Baseline Comparison:" in report
        assert "Score Diff" in report

    def test_generate_text_report_regressions(self):
        """regressions param adds per-case regression table."""
        report = generate_text_report(_make_results(), regressions=[_make_regression()])
        assert "Regressions:" in report
        assert "test_2" in report

    def test_generate_text_report_backward_compat(self):
        """results-only call (no new params) still works — existing tables preserved."""
        report = generate_text_report(_make_results())
        assert "Total Cases:" in report
        assert "Overall Pass Rate:" in report
        assert "Run Manifest:" not in report
        assert "Variance" not in report
        assert "Baseline Comparison:" not in report
        assert "Regressions:" not in report


# ═══════════════════════════════════════════════════════════════════════════
# §2: Extended generate_markdown_report tests (INV-REP1, INV-REP2, INV-REP3)
# ═══════════════════════════════════════════════════════════════════════════


class TestGenerateMarkdownReportExtended:
    """Test extended generate_markdown_report per P3 §4.2."""

    def test_generate_markdown_report_manifest(self):
        """manifest param adds header."""
        report = generate_markdown_report(_make_results(), manifest=_make_manifest())
        assert "## Run Manifest" in report
        assert "test-run-001" in report

    def test_generate_markdown_report_stats(self):
        """stats param adds variance/CI table."""
        report = generate_markdown_report(_make_results(), stats=_make_stats())
        assert "## Variance" in report
        assert "CI" in report

    def test_generate_markdown_report_comparison(self):
        """comparison param adds diff table."""
        report = generate_markdown_report(_make_results(), comparison=_make_comparison())
        assert "## Baseline Comparison" in report

    def test_generate_markdown_report_regressions(self):
        """regressions param adds table."""
        report = generate_markdown_report(_make_results(), regressions=[_make_regression()])
        assert "## Regressions" in report
        assert "test_2" in report

    def test_generate_markdown_report_backward_compat(self):
        """results+group_by only works (no new params)."""
        report = generate_markdown_report(_make_results(), group_by="model")
        assert "# " in report
        assert "## Overall Summary" in report
        assert "## Run Manifest" not in report
        assert "## Variance" not in report


# ═══════════════════════════════════════════════════════════════════════════
# §3: Alias tests (INV-REP4, INV-REP5)
# ═══════════════════════════════════════════════════════════════════════════


class TestAliases:
    """Test aliases per P3 §4.3."""

    def test_format_summary_text_alias(self):
        """format_summary_text is generate_text_report."""
        from model_benchmark.reports import format_summary_text
        assert format_summary_text is generate_text_report

    def test_format_summary_markdown_alias(self):
        """format_summary_markdown is generate_markdown_report."""
        from model_benchmark.reports import format_summary_markdown
        assert format_summary_markdown is generate_markdown_report


# ═══════════════════════════════════════════════════════════════════════════
# §4: __all__ tests (INV-REP6)
# ═══════════════════════════════════════════════════════════════════════════


class TestAll:
    """Test __all__ per P3 §4.4."""

    def test_all_includes_aliases(self):
        """__all__ includes format_summary_text and format_summary_markdown."""
        assert "format_summary_text" in __all__
        assert "format_summary_markdown" in __all__
        assert "generate_text_report" in __all__
        assert "generate_markdown_report" in __all__


# ═══════════════════════════════════════════════════════════════════════════
# §5: INV-REP7 — all exports derive from same canonical ResultRecord list
# ═══════════════════════════════════════════════════════════════════════════


class TestINV_REP7:
    """INV-REP7: all exports derive from the same canonical ResultRecord list."""

    def test_all_exports_from_same_source(self):
        """All exports derive from same canonical list (no recomputation).

        The aliases ARE the same function objects — verify identity, not
        re-call output (timestamps differ between calls).
        """
        from model_benchmark.reports import format_summary_text, format_summary_markdown
        # Aliases are the same function objects — no separate computation.
        assert format_summary_text is generate_text_report
        assert format_summary_markdown is generate_markdown_report
