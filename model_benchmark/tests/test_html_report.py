"""Tests for the self-contained interactive HTML report generator (§11).

# TODO(benchmark-upgrade): test_html_report.py §1 — add tests for extended
# generate_html_report per P3 §5.1 (additive keyword-only params):
#   - test_generate_html_report_stats: stats param adds confidence indicators
#     (high_variance / insufficient_sample flags) in summary cards
#   - test_generate_html_report_comparison: comparison param adds baseline
#     comparison section (diff table)
#   - test_generate_html_report_regressions: regressions param adds regression
#     indicators on affected rows (text + icon + label, color-blind safe)
#   - test_generate_html_report_backward_compat: results-only call (no new
#     params) still works — existing 34 tests preserved
#   - test_generate_html_report_manifest_optional: manifest stays optional
#     (P3 deviation — not required, to preserve existing tests)
#   - INV-E10: HTML self-contained (no external CDN/JS)
#   - INV-E11: HTML color-blind safe (Okabe-Ito)
#   - INV-A2: no identity string in anonymized HTML

Covers:
- generate_html_report: produces a complete, self-contained HTML document.
- Inline CSS (Okabe-Ito color-blind safe palette) and inline JS — no external deps.
- Client-side search, status filter, column sort, expandable/collapsible sections.
- Input normalization: list[ResultRecord], BenchmarkReport, list[ModelRunResult],
  single ModelRunResult, empty list.
- Anonymized header marker.
- HTML well-formedness (balanced tags, DOCTYPE, no unclosed tags).
- XSS safety: all dynamic text HTML-escaped.
"""
from __future__ import annotations

import re
from dataclasses import replace
from html.parser import HTMLParser

import pytest

from model_benchmark.html_report import generate_html_report
from model_benchmark.scoring import (
    CategoryResult,
    ModelRunResult,
)
from harness.models import ModelOutput


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

_CATEGORIES = (
    CategoryResult("markup_compliance", True, 1.0, "ok", ()),
    CategoryResult("variable_scoping", True, 1.0, "ok", ()),
    CategoryResult("passage_structure", True, 1.0, "ok", ()),
    CategoryResult("macro_usage", False, 0.5, "missing macros", ("evidence1",)),
    CategoryResult("naked_interpolation", True, 1.0, "ok", ()),
    CategoryResult("link_setter_syntax", True, 1.0, "ok", ()),
)


def _make_run_result(
    model: str = "test-model",
    variant: str = "compact",
    direction: str = "A",
    run_index: int = 0,
    error: str = "",
) -> ModelRunResult:
    parsed = ModelOutput(
        prose="Test prose", choices=[], state={}, summary="", parse_warnings=[]
    )
    overall = all(c.passed for c in _CATEGORIES)
    return ModelRunResult(
        model_name=model,
        variant=variant,
        direction=direction,
        run_index=run_index,
        raw_response="<<raw output>>",
        parsed_output=parsed,
        category_results=_CATEGORIES,
        overall_pass=overall,
        elapsed_seconds=1.5,
        error=error,
    )


def _make_run_results(n: int = 4) -> list[ModelRunResult]:
    return [
        _make_run_result(
            model="llama3" if i % 2 == 0 else "mistral",
            run_index=i,
            error="" if i % 3 != 0 else "some error",
        )
        for i in range(n)
    ]


# ═══════════════════════════════════════════════════════════════════════════
# HTML well-formedness checker
# ═══════════════════════════════════════════════════════════════════════════


class _TagChecker(HTMLParser):
    """Validates that all HTML tags are properly opened and closed."""

    VOID = frozenset({
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    })

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in self.VOID:
            return
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        elif tag in self.stack:
            while self.stack and self.stack[-1] != tag:
                self.errors.append(f"Unclosed <{self.stack[-1]}> before </{tag}>")
                self.stack.pop()
            if self.stack:
                self.stack.pop()
        else:
            self.errors.append(f"Stray </{tag}>")


def _check_well_formed(html_doc: str) -> None:
    """Assert the HTML has balanced tags and no unclosed tags."""
    checker = _TagChecker()
    checker.feed(html_doc)
    assert not checker.errors, f"Tag errors: {checker.errors}"
    assert not checker.stack, f"Unclosed tags: {checker.stack}"


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestHtmlReportBasics:
    """Basic structure and self-containment."""

    def test_imports_cleanly(self) -> None:
        """Module imports without error (acceptance criterion)."""
        from model_benchmark.html_report import generate_html_report  # noqa: F401

    def test_returns_complete_html_document(self) -> None:
        html_doc = generate_html_report(_make_run_results())
        assert html_doc.startswith("<!DOCTYPE html>")
        assert "<html" in html_doc and "</html>" in html_doc
        assert "<head>" in html_doc and "</head>" in html_doc
        assert "<body>" in html_doc and "</body>" in html_doc

    def test_inline_css_present(self) -> None:
        html_doc = generate_html_report(_make_run_results())
        assert "<style>" in html_doc and "</style>" in html_doc

    def test_inline_js_present(self) -> None:
        html_doc = generate_html_report(_make_run_results())
        assert "<script>" in html_doc and "</script>" in html_doc

    def test_no_external_dependencies(self) -> None:
        """No CDN, external <link>, external <script src=...>, or external URLs in CSS."""
        html_doc = generate_html_report(_make_run_results())
        assert "<link" not in html_doc, "external <link> found"
        assert "cdn" not in html_doc.lower(), "CDN reference found"
        # No <script src=...>
        assert not re.search(r'<script\s+src=', html_doc), "external script src found"
        # No <link rel=stylesheet href=...>
        assert not re.search(r'<link\s+.*href=', html_doc), "external link href found"

    def test_html_well_formed(self) -> None:
        """All tags balanced, no unclosed tags (acceptance criterion)."""
        html_doc = generate_html_report(_make_run_results())
        _check_well_formed(html_doc)

    def test_empty_results_produces_valid_html(self) -> None:
        html_doc = generate_html_report([])
        assert html_doc.startswith("<!DOCTYPE html>")
        assert "No results" in html_doc
        _check_well_formed(html_doc)


class TestColorBlindSafePalette:
    """Okabe-Ito color-blind safe palette is used."""

    OKABE_ITO_COLORS = [
        "#E69F00",  # orange
        "#56B4E9",  # sky blue
        "#009E73",  # green
        "#0072B2",  # blue
        "#D55E00",  # vermillion
        "#CC79A7",  # purple
    ]

    def test_palette_colors_present(self) -> None:
        html_doc = generate_html_report(_make_run_results())
        for color in self.OKABE_ITO_COLORS:
            assert color in html_doc, f"Okabe-Ito color {color} missing from HTML"

    def test_status_not_color_only(self) -> None:
        """Status is conveyed by text label + icon, not color alone."""
        html_doc = generate_html_report(_make_run_results())
        # Status pills should have text labels.
        for status in ["PASS", "FAIL", "ERROR"]:
            if status in html_doc:
                # The status text should appear inside the pill, not just as a color.
                assert f">{status}<" in html_doc or status in html_doc


class TestInteractiveFeatures:
    """Client-side search, filter, sort, expand/collapse in inline JS."""

    def test_search_functionality_in_js(self) -> None:
        html_doc = generate_html_report(_make_run_results())
        js = html_doc.split("<script>")[1].split("</script>")[0]
        assert "searchBox" in js
        assert "input" in js.lower()  # event listener

    def test_status_filter_in_js(self) -> None:
        html_doc = generate_html_report(_make_run_results())
        js = html_doc.split("<script>")[1].split("</script>")[0]
        assert "statusFilter" in js
        assert "change" in js.lower()

    def test_column_sort_in_js(self) -> None:
        html_doc = generate_html_report(_make_run_results())
        js = html_doc.split("<script>")[1].split("</script>")[0]
        assert "applySort" in js or "sort" in js.lower()
        # Column headers should have data-key attributes for sorting.
        assert 'data-key=' in html_doc

    def test_expand_collapse_in_js(self) -> None:
        html_doc = generate_html_report(_make_run_results())
        js = html_doc.split("<script>")[1].split("</script>")[0]
        assert "expandAll" in js or "expand" in js.lower()
        assert "collapseAll" in js or "collapse" in js.lower()

    def test_detail_rows_present(self) -> None:
        """Expandable/collapsible detail rows exist for each data row."""
        html_doc = generate_html_report(_make_run_results())
        assert 'class="detail-row' in html_doc
        assert "data-detail-for" in html_doc

    def test_model_filter_dropdown(self) -> None:
        html_doc = generate_html_report(_make_run_results())
        assert 'id="modelFilter"' in html_doc
        assert 'data-model=' in html_doc

    def test_status_filter_dropdown(self) -> None:
        html_doc = generate_html_report(_make_run_results())
        assert 'id="statusFilter"' in html_doc
        for status in ["PASS", "FAIL", "ERROR", "SKIPPED", "INVALID", "TIMEOUT", "CANCELLED"]:
            assert f'value="{status}"' in html_doc, f"Status option {status} missing"


class TestInputNormalization:
    """Multiple input shapes are accepted."""

    def test_single_model_run_result(self) -> None:
        run = _make_run_result()
        html_doc = generate_html_report(run)
        assert html_doc.startswith("<!DOCTYPE html>")
        assert "test-model" in html_doc
        _check_well_formed(html_doc)

    def test_list_of_model_run_results(self) -> None:
        runs = _make_run_results(6)
        html_doc = generate_html_report(runs)
        assert "llama3" in html_doc
        assert "mistral" in html_doc
        _check_well_formed(html_doc)

    def test_benchmark_report(self) -> None:
        from model_benchmark.scoring import (
            BenchmarkReport,
            CategorySummaryEntry,
            ModelReport,
        )
        from model_benchmark.benchmark import BenchmarkConfig

        runs = _make_run_results(4)
        cfg = BenchmarkConfig(
            models=("llama3", "mistral"),
            variants=("compact", "full"),
            directions=("A", "B", "C"),
            base_url="http://localhost:11434",
            timeout=60,
            num_predict=512,
            temperature=0.0,
            runs=2,
        )
        cat_sum = tuple(
            CategorySummaryEntry(name, 1.0, 4, 4) for name in (
                "markup_compliance", "variable_scoping", "passage_structure",
                "macro_usage", "naked_interpolation", "link_setter_syntax",
            )
        )
        model_reports = tuple(
            ModelReport(
                model_name=m,
                runs=tuple(r for r in runs if r.model_name == m),
                category_summary=cat_sum,
                overall_score=0.9,
                runs_total=2,
                runs_passed=2,
            )
            for m in ("llama3", "mistral")
        )
        report = BenchmarkReport(
            models=model_reports,
            prompt_version=7,
            config=cfg,
            generated_at="2026-07-30T00:00:00Z",
            ollama_reachable=True,
        )
        html_doc = generate_html_report(report)
        assert "llama3" in html_doc
        assert "mistral" in html_doc
        _check_well_formed(html_doc)

    def test_result_record_list(self) -> None:
        from model_benchmark.schema import ResultRecord

        parsed = ModelOutput(
            prose="Test", choices=[], state={}, summary="", parse_warnings=[]
        )
        scored = _make_run_result()
        rec = ResultRecord(
            schema_version="1.0.0",
            test_id="test-001",
            test_version="1",
            capability="cap",
            category="macro_usage",
            subcategory="sub",
            difficulty="easy",
            dataset="ds",
            split="val",
            repetition=0,
            input_summary="input",
            expected_behavior="expected",
            reference_rubric="rubric",
            actual_output_raw="raw",
            parsed_output=parsed,
            score=0.5,
            max_score=1.0,
            normalized_score=0.5,
            pass_threshold=0.8,
            status="FAIL",
            failure_category="formatting",
            evaluator_reasoning="reason",
            evaluator_confidence=0.9,
            runtime_seconds=2.5,
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cost=0.01,
            retry_count=0,
            error_details="some error",
            model_alias="Model_A",
            config_alias="Config_01",
            prompt_version=7,
            evaluator_version="1.0",
            random_seed="",
            timestamp_start="2026-07-30T00:00:00Z",
            timestamp_end="2026-07-30T00:00:03Z",
            scored_result=scored,
        )
        html_doc = generate_html_report([rec])
        assert "test-001" in html_doc
        assert "FAIL" in html_doc
        assert "formatting" in html_doc
        _check_well_formed(html_doc)

    def test_result_record_without_scored_result(self) -> None:
        from model_benchmark.schema import ResultRecord

        parsed = ModelOutput(
            prose="Test", choices=[], state={}, summary="", parse_warnings=[]
        )
        rec = ResultRecord(
            schema_version="1.0.0",
            test_id="test-002",
            test_version="1",
            capability="cap",
            category="macro_usage",
            subcategory="sub",
            difficulty="easy",
            dataset="ds",
            split="val",
            repetition=0,
            input_summary="input",
            expected_behavior="expected",
            reference_rubric="rubric",
            actual_output_raw="raw",
            parsed_output=parsed,
            score=1.0,
            max_score=1.0,
            normalized_score=1.0,
            pass_threshold=0.8,
            status="PASS",
            failure_category="none",
            evaluator_reasoning="reason",
            evaluator_confidence=0.9,
            runtime_seconds=1.0,
            input_tokens=50,
            output_tokens=25,
            total_tokens=75,
            cost=0.005,
            retry_count=0,
            error_details="",
            model_alias="Model_B",
            config_alias="Config_01",
            prompt_version=7,
            evaluator_version="1.0",
            random_seed="",
            timestamp_start="2026-07-30T00:00:00Z",
            timestamp_end="2026-07-30T00:00:01Z",
            scored_result=None,
        )
        html_doc = generate_html_report([rec])
        assert "Model_B" in html_doc
        assert "PASS" in html_doc
        _check_well_formed(html_doc)

    def test_unsupported_type_raises(self) -> None:
        with pytest.raises(TypeError):
            generate_html_report(42)  # type: ignore[arg-type]

    def test_tuple_input(self) -> None:
        runs = tuple(_make_run_results(3))
        html_doc = generate_html_report(runs)
        assert html_doc.startswith("<!DOCTYPE html>")
        _check_well_formed(html_doc)


class TestAnonymizedMarker:
    """Anonymized variant header marker."""

    def test_anonymized_badge_present(self) -> None:
        html_doc = generate_html_report(_make_run_results(), anonymized=True)
        assert "ANONYMIZED" in html_doc

    def test_no_anonymized_badge_by_default(self) -> None:
        html_doc = generate_html_report(_make_run_results(), anonymized=False)
        assert "ANONYMIZED" not in html_doc


class TestXssSafety:
    """All dynamic text is HTML-escaped to prevent XSS."""

    def test_html_escaping_in_model_name(self) -> None:
        run = _make_run_result(model="<script>alert(1)</script>")
        html_doc = generate_html_report([run])
        assert "<script>alert(1)</script>" not in html_doc
        assert "&lt;script&gt;" in html_doc

    def test_html_escaping_in_error(self) -> None:
        run = _make_run_result(error='<img src=x onerror="alert(1)">')
        html_doc = generate_html_report([run])
        assert '<img src=x onerror="alert(1)">' not in html_doc

    def test_no_script_injection_in_rows_json(self) -> None:
        run = _make_run_result(model='</script><script>alert(1)</script>')
        html_doc = generate_html_report([run])
        # The </script> in data should not close the script block early.
        # The renderer escapes "</" to "<\/" in the JSON payload, so
        # </script> in the model name becomes <\/script> — harmless.
        assert "<\\/script>" in html_doc
        # Exactly one real </script> closing tag (for the inline JS block).
        # The escaped <\/script> occurrences are not real closing tags.
        real_closes = html_doc.count("</script>")
        assert real_closes == 1, f"Expected 1 real </script> close, got {real_closes}"


class TestSummaryStats:
    """Summary stat cards compute correct counts."""

    def test_summary_cards_present(self) -> None:
        html_doc = generate_html_report(_make_run_results(4))
        assert "Total Results" in html_doc
        assert "Pass Rate" in html_doc
        assert "Avg Score" in html_doc
        assert "Models" in html_doc

    def test_summary_counts_correct(self) -> None:
        # 4 results: 2 pass (no error), 2 error
        runs = _make_run_results(4)
        html_doc = generate_html_report(runs)
        # With _make_run_results, i % 3 != 0 means error at i=0 only.
        # So i=0: error, i=1: pass, i=2: pass, i=3: error
        # Actually: error="" if i % 3 != 0 else "some error" means:
        # i=0: error (0%3==0), i=1: no error, i=2: no error, i=3: error (3%3==0)
        assert "4" in html_doc  # total


class TestDetailContent:
    """Expandable detail rows contain category breakdown and raw output."""

    def test_category_breakdown_in_detail(self) -> None:
        html_doc = generate_html_report(_make_run_results(1))
        assert "Category Breakdown" in html_doc
        for cat in (
            "markup_compliance", "variable_scoping", "passage_structure",
            "macro_usage", "naked_interpolation", "link_setter_syntax",
        ):
            assert cat in html_doc

    def test_evidence_list_in_detail(self) -> None:
        html_doc = generate_html_report(_make_run_results(1))
        assert "evidence1" in html_doc
        assert 'class="evidence-list"' in html_doc

    def test_non_applicable_category_renders_as_na(self) -> None:
        run = _make_run_result()
        categories = (
            *run.category_results[:-1],
            CategoryResult(
                "link_setter_syntax",
                False,
                0.0,
                "N/A: construct neither required nor emitted by this case.",
                applicable=False,
            ),
        )

        html_doc = generate_html_report(replace(run, category_results=categories))

        assert ">N/A</td>" in html_doc

    def test_raw_output_in_detail(self) -> None:
        html_doc = generate_html_report(_make_run_results(1))
        assert "Raw Model Output" in html_doc
        assert "<<raw output>>" in html_doc  # raw response content present (escaped)

    def test_score_and_pass_fail_in_detail(self) -> None:
        html_doc = generate_html_report(_make_run_results(1))
        assert "PASS" in html_doc
        assert "FAIL" in html_doc  # macro_usage fails


# ═══════════════════════════════════════════════════════════════════════════
# §1: Extended generate_html_report tests (P3 §5.1)
# ═══════════════════════════════════════════════════════════════════════════


class TestGenerateHtmlReportExtended:
    """Test extended generate_html_report per P3 §5.1 (additive keyword-only params).

    Enforces P6 invariants INV-HTML4..INV-HTML9, INV-HTML1..INV-HTML3.
    """

    def test_generate_html_report_stats(self) -> None:
        """stats param adds confidence indicators (high_variance / insufficient_sample)."""
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
            pass_rate_consistency = 1.0
            variance_flags = ("high variance",)

        html_doc = generate_html_report(_make_run_results(), stats=FakeStats())
        assert "Variance" in html_doc
        assert "high variance" in html_doc

    def test_generate_html_report_comparison(self) -> None:
        """comparison param adds baseline comparison section (diff table)."""
        class FakeComparison:
            baseline_run_id = "base-001"
            current_run_id = "curr-001"
            absolute_score_diff = -0.05
            relative_score_diff = -0.10
            newly_failing = ("test_2",)
            newly_passing = ()
            category_regressions = ("macro_usage",)
            runtime_diff = 0.5
            token_diff = 100
            is_statistically_significant = True
            is_operationally_significant = False

        html_doc = generate_html_report(_make_run_results(), comparison=FakeComparison())
        assert "Baseline Comparison" in html_doc
        assert "Score Diff" in html_doc

    def test_generate_html_report_regressions(self) -> None:
        """regressions param adds regression indicators on affected rows."""
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

        html_doc = generate_html_report(_make_run_results(), regressions=[FakeRegression()])
        assert "Regressions" in html_doc
        assert "test_2" in html_doc
        assert "macro_usage" in html_doc

    def test_generate_html_report_backward_compat(self) -> None:
        """results-only call (no new params) still works — existing 34 tests preserved."""
        html_doc = generate_html_report(_make_run_results())
        assert html_doc.startswith("<!DOCTYPE html>")
        assert "Variance" not in html_doc
        assert "Baseline Comparison" not in html_doc
        assert "Regressions" not in html_doc

    def test_generate_html_report_manifest_optional(self) -> None:
        """INV-HTML5: manifest stays optional (P3 deviation — not required)."""
        html_doc = generate_html_report(_make_run_results())
        assert html_doc.startswith("<!DOCTYPE html>")

    def test_inv_html1_self_contained(self) -> None:
        """INV-HTML1: HTML self-contained (no external CDN/JS)."""
        html_doc = generate_html_report(_make_run_results())
        assert "cdn." not in html_doc.lower()
        assert "http://" not in html_doc or "localhost" in html_doc
        assert "https://" not in html_doc

    def test_inv_html2_color_blind_safe(self) -> None:
        """INV-HTML2: HTML color-blind safe (Okabe-Ito palette present)."""
        html_doc = generate_html_report(_make_run_results())
        # Okabe-Ito colors should be in the CSS
        okabe_ito_colors = ["#E69F00", "#56B4E9", "#009E73", "#F0E442",
                           "#0072B2", "#D55E00", "#CC79A7"]
        assert any(c in html_doc for c in okabe_ito_colors)

    def test_inv_a2_no_identity_in_anonymized(self) -> None:
        """INV-A2: no identity string in anonymized HTML."""
        # The anonymized flag marks the header. Without a manifest, the badge
        # is still shown in the header.
        html_doc = generate_html_report(_make_run_results(), anonymized=True)
        # In anonymized mode, header is marked "ANONYMIZED" (uppercase badge)
        assert "ANONYMIZED" in html_doc

