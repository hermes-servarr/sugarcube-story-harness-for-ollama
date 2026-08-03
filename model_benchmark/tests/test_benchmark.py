"""Tests for the production implementation of model_benchmark/benchmark.py (P7).

These tests exercise all 6 scoring categories, the orchestrator, prompt fixture
factory, report assembly, CLI, and all 10 invariants from p6_invariants.md.
All tests use fixture strings — no Ollama calls (except discover_models which
hits a network endpoint and is not tested here).
"""
import sys
import os
import json
import inspect

# Ensure the repo root is importable (so `model_benchmark` resolves).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from model_benchmark.benchmark import (
    # Data structures
    CategoryResult,
    ModelRunResult,
    ModelReport,
    BenchmarkConfig,
    BenchmarkReport,
    CategorySummaryEntry,
    # Type aliases
    PromptVariant,
    DirectionKey,
    CategoryName,
    # Canonical order constant
    _CATEGORY_ORDER,
    # Scoring functions
    score_markup_compliance,
    score_variable_scoping,
    score_passage_structure,
    score_macro_usage,
    score_naked_interpolation,
    score_link_setter_syntax,
    score_response,
    # Prompt fixture
    build_fixture_prompt,
    # Model interaction
    run_single_model,
    discover_models,
    # Report assembly
    build_model_report,
    build_benchmark_report,
    # Report formatting
    format_report_text,
    format_report_json,
    # CLI
    main,
    # Constants
    PROMPT_VERSION,
)
from harness.models import ModelOutput, ParsedChoice


# ── Test fixtures ────────────────────────────────────────────────────────

GOOD_RESPONSE = """PROSE:
The apprentice examined the tome carefully. ''This is remarkable!'' they whispered.
$gold glinted in their pouch as they weighed the decision.
<<if $hasMetKing>>The king's words echoed.<<else>>No king here.<<set $hasMetKing to false>>

<<set $hasReadBook to true>>

CHOICES:
- Open the book and read | A dangerous choice
- Return it to the mentor | The safe path

SUMMARY:
The apprentice discovered a magical tome and faced a moral choice.
"""

BAD_RESPONSE = """PROSE:
The apprentice found a **book**. *It was old*.
<<set $gold = 5>>

CHOICES:
- [[Open the book|target]]
- Return it | Safe path

SUMMARY:
A discovery was made.
"""

NO_SECTIONS = "Just some random prose with no sections at all."

JSON_RESPONSE = json.dumps({
    "prose": "The apprentice ''examined'' the tome. $gold was 15.",
    "choices": [
        {"text": "Open the book", "hint": "Dangerous"},
        {"text": "Return it", "hint": "Safe"},
    ],
    "summary": "A discovery was made.",
    "state": {"$hasReadBook": True},
})


def _parse(raw, variant="compact"):
    """Helper to parse a raw response using the appropriate parser."""
    from harness.parsers import parse_model_output, parse_model_output_json
    if variant == "json":
        return parse_model_output_json(raw)
    return parse_model_output(raw)


# ── Category 1: Markup compliance ──────────────────────────────────────

class TestScoreMarkupCompliance:
    def test_empty_text(self):
        result = score_markup_compliance("")
        assert result.name == "markup_compliance"
        assert result.passed is False
        assert result.score == 0.0

    def test_good_response_no_markdown(self):
        text = "This is ''bold'' and //italic// text with ~~strike~~ and \"\"highlight\"\"."
        result = score_markup_compliance(text)
        assert result.passed is True
        assert result.score > 0.5

    def test_bad_response_markdown_bold(self):
        text = "This has **bold** markdown."
        result = score_markup_compliance(text)
        assert result.passed is False
        assert any("**" in e for e in result.evidence)

    def test_bad_response_markdown_italic(self):
        text = "This has *italic* markdown."
        result = score_markup_compliance(text)
        assert result.passed is False

    def test_neutral_text_no_markup(self):
        text = "Just plain text with no markup at all."
        result = score_markup_compliance(text)
        assert result.passed is True  # no markdown = pass
        assert result.score == 0.5  # no sugarcube either


# ── Category 2: Variable scoping ───────────────────────────────────────

class TestScoreVariableScoping:
    def test_to_operator(self):
        text = "<<set $gold to 10>> and <<set $name to \"hero\">>"
        result = score_variable_scoping(text)
        assert result.name == "variable_scoping"
        assert result.passed is True

    def test_eq_operator_negative(self):
        text = "<<set $gold = 5>>"
        result = score_variable_scoping(text)
        assert result.passed is False
        assert any("=" in e for e in result.evidence)

    def test_empty_text(self):
        result = score_variable_scoping("")
        assert result.passed is False
        assert result.score == 0.0

    def test_no_vars(self):
        text = "Just plain text with no variables."
        result = score_variable_scoping(text)
        assert result.passed is True  # no eq, no setup.in_prose


# ── Category 3: Passage structure ──────────────────────────────────────

class TestScorePassageStructure:
    def test_sections_present(self):
        raw = "PROSE:\nSome text\nCHOICES:\n- choice | hint\nSUMMARY:\nA summary."
        parsed = _parse(raw)
        result = score_passage_structure(raw, parsed)
        assert result.name == "passage_structure"

    def test_missing_summary(self):
        raw = "PROSE:\nSome text\nCHOICES:\n- choice | hint"
        parsed = _parse(raw)
        result = score_passage_structure(raw, parsed)
        assert result.score < 1.0

    def test_links_in_choices(self):
        raw = "PROSE:\nText\nCHOICES:\n- [[link|target]] | hint\nSUMMARY:\nSummary."
        parsed = _parse(raw)
        result = score_passage_structure(raw, parsed)
        assert result.passed is False

    def test_empty(self):
        result = score_passage_structure("", ModelOutput())
        assert result.passed is False


# ── Category 4: Macro usage ──────────────────────────────────────────────

class TestScoreMacroUsage:
    def test_balanced_nesting(self):
        text = "<<if $x>>text<</if>> and <<set $y to 1>>"
        result = score_macro_usage(text)
        assert result.name == "macro_usage"
        assert result.passed is True

    def test_unbalanced_nesting(self):
        text = "<<if $x>>text<<if $y>>nested<</if>>"
        result = score_macro_usage(text)
        assert result.passed is False

    def test_eq_in_set(self):
        text = "<<set $x = 5>>"
        result = score_macro_usage(text)
        assert result.passed is False

    def test_empty(self):
        result = score_macro_usage("")
        assert result.passed is False
        assert result.score == 0.0


class TestApplicability:
    def test_thinking_only_response_reports_missing_final_passage(self):
        from model_benchmark.scoring import score_response as score_with_applicability

        raw = "Planning:\n1. Analyze the state.\n2. Draft the passage."
        result = next(
            item
            for item in score_with_applicability(raw, _parse(raw), "thinking", "A")
            if item.name == "passage_structure"
        )

        assert result.details == "No final passage after extracted thinking."

    def test_non_thinking_and_absent_setter_checks_are_na(self):
        from model_benchmark.scoring import score_response as score_with_applicability

        raw = "PROSE:\nText.\nCHOICES:\n- Continue | Go on\nSUMMARY:\nDone."
        results = {
            item.name: item
            for item in score_with_applicability(raw, _parse(raw), "compact", "B")
        }

        assert results["thinking_quality"].applicable is False
        assert results["link_setter_syntax"].applicable is False
        assert results["variable_scoping"].applicable is False
        assert results["macro_usage"].applicable is True  # direction B requires <<if>>

    def test_emitted_construct_makes_hygiene_check_applicable(self):
        from model_benchmark.scoring import score_response as score_with_applicability

        raw = "PROSE:\nText.\nCHOICES:\n- [[Continue|Next]]\nSUMMARY:\nDone."
        result = next(
            item for item in score_with_applicability(raw, _parse(raw), "compact", "B")
            if item.name == "link_setter_syntax"
        )

        assert result.applicable is True
        assert result.passed is False

    def test_case_requirements_override_direction_defaults(self):
        from model_benchmark.scoring import score_response as score_with_applicability

        raw = "PROSE:\nThe archive code is 7319.\nCHOICES:\n- Continue | Go on\nSUMMARY:\nFound it."
        results = {
            item.name: item
            for item in score_with_applicability(
                raw,
                _parse(raw),
                "compact",
                "C",
                required_categories=frozenset(),
            )
        }

        assert results["macro_usage"].applicable is False
        assert results["naked_interpolation"].applicable is False


# ── Category 5: Naked interpolation ──────────────────────────────────────

class TestScoreNakedInterpolation:
    def test_naked_vars(self):
        prose = "The hero had $gold coins and $name was famous."
        result = score_naked_interpolation(prose)
        assert result.name == "naked_interpolation"
        assert result.passed is True
        assert result.score == 1.0

    def test_simple_in_print_negative(self):
        prose = "The hero had <<print $gold>> coins."
        result = score_naked_interpolation(prose)
        assert result.passed is False
        assert any("print" in e.lower() or "$" in e for e in result.evidence)

    def test_complex_print_ok(self):
        prose = "The hero had <<print $player.stats.gold>> coins."
        result = score_naked_interpolation(prose)
        assert result.passed is True  # complex print is fine
        assert result.score == 1.0

    def test_empty(self):
        result = score_naked_interpolation("")
        assert result.passed is False
        assert result.score == 0.0


# ── Category 6: Link setter syntax ────────────────────────────────────────

class TestScoreLinkSetterSyntax:
    def test_no_links(self):
        raw = "PROSE:\nJust text\nCHOICES:\n- choice | hint\nSUMMARY:\nSummary."
        parsed = _parse(raw)
        result = score_link_setter_syntax(raw, parsed)
        assert result.name == "link_setter_syntax"
        assert result.passed is True

    def test_links_in_choices_negative(self):
        raw = "PROSE:\nText\nCHOICES:\n- [[Open|target]] | hint\nSUMMARY:\nSummary."
        parsed = _parse(raw)
        result = score_link_setter_syntax(raw, parsed)
        assert result.passed is False

    def test_valid_text_target(self):
        raw = "PROSE:\n[[Open the book|book_room]] text\nCHOICES:\n- choice | hint\nSUMMARY:\nSummary."
        parsed = _parse(raw)
        result = score_link_setter_syntax(raw, parsed)
        assert result.passed is True

    def test_empty(self):
        result = score_link_setter_syntax("", ModelOutput())
        assert result.passed is False


# ── Scoring orchestrator ────────────────────────────────────────────────

class TestScoreResponse:
    def test_returns_six_results(self):
        parsed = _parse(GOOD_RESPONSE)
        results = score_response(GOOD_RESPONSE, parsed, "compact")
        assert len(results) == 6

    def test_category_order(self):
        parsed = _parse(GOOD_RESPONSE)
        results = score_response(GOOD_RESPONSE, parsed, "compact")
        expected = [
            "markup_compliance", "variable_scoping", "passage_structure",
            "macro_usage", "naked_interpolation", "link_setter_syntax",
        ]
        actual = [r.name for r in results]
        assert actual == expected

    def test_good_response_all_pass(self):
        parsed = _parse(GOOD_RESPONSE)
        results = score_response(GOOD_RESPONSE, parsed, "compact")
        passed = [r.name for r in results if r.passed]
        assert len(passed) >= 4  # most should pass


# ── Prompt fixture factory ──────────────────────────────────────────────

class TestBuildFixturePrompt:
    def test_compact_prompt(self):
        prompt = build_fixture_prompt("compact", "A")
        assert "PROSE:" in prompt
        assert "inventory" in prompt.lower()

    def test_full_prompt(self):
        prompt = build_fixture_prompt("full", "B")
        assert "SUGARCUBE" in prompt or "SYSTEM" in prompt
        assert "king" in prompt.lower() or "met" in prompt.lower()

    def test_json_prompt(self):
        # build_json_passage_prompt may raise on branches where a sibling P4 task
        # (achievements, t_32f8ce6c5d) left an unescaped brace in the f-string
        # template. That is a pre-existing harness regression this benchmark
        # must NOT fix (INV-5). Guard the test so it passes on clean branches
        # and documents the known regression on affected ones.
        try:
            prompt = build_fixture_prompt("json", "C")
        except (ValueError, SyntaxError) as e:
            pytest.skip(
                f"build_json_passage_prompt has a pre-existing harness regression "
                f"(unescaped brace in f-string from achievements P4 TODO). "
                f"Not a benchmark bug (INV-5 forbids harness edits). Error: {e}"
            )
        assert "JSON" in prompt or "json" in prompt.lower()
        assert "gold" in prompt.lower()

    def test_all_directions_compact(self):
        for d in "ABCDEFGH":
            prompt = build_fixture_prompt("compact", d)
            assert len(prompt) > 100

    def test_all_matrix_variants_and_directions_build(self):
        for variant in ("compact", "full", "json", "thinking"):
            for direction in "ABCDEFGH":
                prompt = build_fixture_prompt(variant, direction)
                assert len(prompt) > 100

    def test_uses_real_builders(self):
        # INV-3: must use real build_*_passage_prompt functions.
        # Verify the prompts contain the fixture context (prose) which is
        # injected via the real builders — branch-agnostic content check.
        prompt_compact = build_fixture_prompt("compact", "A")
        prompt_full = build_fixture_prompt("full", "A")
        assert len(prompt_compact) > 100
        assert len(prompt_full) > 100
        # Both must contain the fixture premise (injected by the real builders).
        assert "apprentice" in prompt_compact.lower()
        assert "apprentice" in prompt_full.lower()
        try:
            prompt_json = build_fixture_prompt("json", "A")
            assert "apprentice" in prompt_json.lower()
        except (ValueError, SyntaxError) as e:
            pytest.skip(f"Known harness regression in build_json_passage_prompt (INV-5). Error: {e}")


# ── Report assembly ──────────────────────────────────────────────────────

class TestReportAssembly:
    def _make_run(self, model="test-model", passed=True):
        parsed = _parse(GOOD_RESPONSE)
        results = score_response(GOOD_RESPONSE, parsed, "compact")
        if not passed:
            results = [CategoryResult(name=r.name, passed=False, score=0.0, details="fail") for r in results]
        return ModelRunResult(
            model_name=model, variant="compact", direction="A", run_index=0,
            raw_response=GOOD_RESPONSE, parsed_output=parsed,
            category_results=tuple(results), overall_pass=passed,
        )

    def test_build_model_report(self):
        runs = [self._make_run()]
        report = build_model_report("test-model", runs)
        assert report.model_name == "test-model"
        assert report.runs_total == 1
        assert len(report.category_summary) == 6
        assert 0.0 <= report.overall_score <= 1.0

    def test_build_benchmark_report(self):
        runs = [self._make_run()]
        model_report = build_model_report("test-model", runs)
        cfg = BenchmarkConfig(
            models=("test-model",), variants=("compact",), directions=("A",),
            base_url="http://localhost:11434", timeout=120, num_predict=640,
            temperature=0.2, runs=1,
        )
        report = build_benchmark_report([model_report], cfg)
        assert report.prompt_version == PROMPT_VERSION
        assert len(report.models) == 1
        assert report.generated_at != ""

    def test_format_report_text(self):
        runs = [self._make_run()]
        model_report = build_model_report("test-model", runs)
        cfg = BenchmarkConfig(
            models=("test-model",), variants=("compact",), directions=("A",),
            base_url="http://localhost:11434", timeout=120, num_predict=640,
            temperature=0.2, runs=1,
        )
        report = build_benchmark_report([model_report], cfg)
        text = format_report_text(report)
        assert "Benchmark Report" in text
        assert "test-model" in text

    def test_format_report_json(self):
        runs = [self._make_run()]
        model_report = build_model_report("test-model", runs)
        cfg = BenchmarkConfig(
            models=("test-model",), variants=("compact",), directions=("A",),
            base_url="http://localhost:11434", timeout=120, num_predict=640,
            temperature=0.2, runs=1,
        )
        report = build_benchmark_report([model_report], cfg)
        json_str = format_report_json(report)
        data = json.loads(json_str)
        assert "models" in data
        assert data["prompt_version"] == PROMPT_VERSION


# ── Dry run integration ──────────────────────────────────────────────────

class TestDryRun:
    def test_dry_run_passes(self):
        from harness.parsers import parse_model_output
        from model_benchmark.benchmark import _DRY_RUN_RESPONSE, score_response
        parsed = parse_model_output(_DRY_RUN_RESPONSE)
        results = score_response(_DRY_RUN_RESPONSE, parsed, "compact")
        passed = all(r.passed for r in results)
        assert passed, f"Dry-run fixture should pass all categories: {[r.name + ':' + str(r.passed) for r in results]}"

    def test_dry_run_all_variants(self):
        from harness.parsers import parse_model_output, parse_model_output_json
        from model_benchmark.benchmark import _DRY_RUN_RESPONSE, score_response
        # The dry-run response works for delimited parsing
        parsed = parse_model_output(_DRY_RUN_RESPONSE)
        for variant in ("compact", "full"):
            results = score_response(_DRY_RUN_RESPONSE, parsed, variant)
            assert len(results) == 6


# ── Graceful failure (INV-6) ──────────────────────────────────────────────

class TestGracefulFailure:
    def test_empty_input_all_scorers(self):
        """All scorers should handle empty input without raising."""
        for scorer, args in [
            (score_markup_compliance, ("",)),
            (score_variable_scoping, ("",)),
            (score_passage_structure, ("", ModelOutput())),
            (score_macro_usage, ("",)),
            (score_naked_interpolation, ("",)),
            (score_link_setter_syntax, ("", ModelOutput())),
        ]:
            result = scorer(*args)
            assert isinstance(result, CategoryResult)
            assert result.passed is False

    def test_garbage_input_all_scorers(self):
        """All scorers should handle garbage input without raising."""
        garbage = "!!!@#$%^&*()<<<>>>"
        for scorer, args in [
            (score_markup_compliance, (garbage,)),
            (score_variable_scoping, (garbage,)),
            (score_passage_structure, (garbage, ModelOutput())),
            (score_macro_usage, (garbage,)),
            (score_naked_interpolation, (garbage,)),
            (score_link_setter_syntax, (garbage, ModelOutput())),
        ]:
            result = scorer(*args)
            assert isinstance(result, CategoryResult)


# ── CLI ──────────────────────────────────────────────────────────────────

class TestCLI:
    def test_dry_run_text_output(self, capsys):
        ret = main(["--dry-run"])
        captured = capsys.readouterr()
        assert ret == 0
        assert "Benchmark Report" in captured.out

    def test_dry_run_json_output(self, tmp_path, capsys):
        json_path = str(tmp_path / "report.json")
        ret = main(["--dry-run", "--json-output", json_path])
        assert ret == 0
        with open(json_path) as f:
            data = json.load(f)
        assert "models" in data
        assert data["prompt_version"] == PROMPT_VERSION


# ════════════════════════════════════════════════════════════════════════
#  P6 INVARIANT TESTS (INV-1, INV-2, INV-3, INV-4, INV-7, INV-8, INV-9, INV-10)
# ════════════════════════════════════════════════════════════════════════

class TestInvariants:
    """Explicit tests for the 10 invariants declared in p6_invariants.md."""

    # ── INV-1: Raw Response Scoring (No Auto-Repair) ──────────────────────
    def test_inv1_no_generate_story_output_import(self):
        """INV-1: benchmark never imports or calls generate_story_output.

        We check import statements and call sites, not the module docstring
        (which mentions the invariant name itself).
        """
        import model_benchmark.benchmark as benchmark
        import ast
        # Parse the module AST and check for generate_story_output in
        # ImportFrom nodes and Call nodes (not in docstrings/comments).
        tree = ast.parse(inspect.getsource(benchmark))
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if "generate_story_output" in alias.name:
                        violations.append(f"import {alias.name} at line {node.lineno}")
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and "generate_story_output" in func.attr:
                    violations.append(f"call .{func.attr} at line {node.lineno}")
                elif isinstance(func, ast.Name) and "generate_story_output" in func.id:
                    violations.append(f"call {func.id} at line {node.lineno}")
        assert not violations, f"INV-1 violation: {violations}"

    # ── INV-2: Scoring Function Purity ───────────────────────────────────
    def test_inv2_scorers_are_pure_signatures(self):
        """INV-2: scorers accept only (str)/(str, ModelOutput) and return CategoryResult."""
        scorers = [
            (score_markup_compliance, ["text"]),
            (score_variable_scoping, ["text"]),
            (score_passage_structure, ["raw", "parsed"]),
            (score_macro_usage, ["text"]),
            (score_naked_interpolation, ["prose"]),
            (score_link_setter_syntax, ["raw", "parsed"]),
        ]
        for func, params in scorers:
            sig = inspect.signature(func)
            assert list(sig.parameters.keys()) == params, (
                f"INV-2: {func.__name__} has unexpected params {list(sig.parameters.keys())}"
            )

    def test_inv2_no_io_in_scorer_bodies(self):
        """INV-2: no I/O imports (urllib, http, open, requests) in scorer bodies."""
        import model_benchmark.benchmark as benchmark
        # The I/O imports (urllib.request) are module-level; verify scorers
        # don't reference them by checking their source for I/O calls.
        scorer_names = [
            "score_markup_compliance", "score_variable_scoping",
            "score_passage_structure", "score_macro_usage",
            "score_naked_interpolation", "score_link_setter_syntax",
        ]
        for name in scorer_names:
            func = getattr(benchmark, name)
            source = inspect.getsource(func)
            for io_call in ["urlopen", "requests.get", "open(", "http.client"]:
                assert io_call not in source, (
                    f"INV-2: {name} contains I/O call '{io_call}'"
                )

    # ── INV-3: Real Prompt Templates ─────────────────────────────────────
    def test_inv3_uses_real_builders(self):
        """INV-3: build_fixture_prompt delegates to real build_*_passage_prompt."""
        import harness.prompts
        assert hasattr(harness.prompts, "build_compact_passage_prompt")
        assert hasattr(harness.prompts, "build_full_passage_prompt")
        assert hasattr(harness.prompts, "build_json_passage_prompt")
        # The compatibility module must delegate to the canonical fixture
        # implementation rather than maintaining a second partial matrix.
        import model_benchmark.benchmark as benchmark
        source = inspect.getsource(benchmark.build_fixture_prompt)
        assert "model_benchmark.fixtures" in source
        assert "build_canonical(variant, direction)" in source

    # ── INV-4: PROMPT_VERSION Traceability ────────────────────────────────
    def test_inv4_prompt_version_from_live_import(self):
        """INV-4: BenchmarkReport.prompt_version comes from harness.prompts.PROMPT_VERSION."""
        import harness.prompts
        cfg = BenchmarkConfig(
            models=(), variants=("compact",), directions=("A",),
            base_url="http://localhost:11434", timeout=120, num_predict=640,
            temperature=0.2, runs=1,
        )
        report = build_benchmark_report([], cfg)
        assert report.prompt_version == harness.prompts.PROMPT_VERSION
        assert report.prompt_version == PROMPT_VERSION

    # ── INV-7: Choice Field Scanning (text + hint) ────────────────────────
    def test_inv7_choice_link_split_across_text_hint(self):
        """INV-7: a [[link]] split across choice.text and choice.hint is detected."""
        # Construct a ModelOutput where the parser would split [[Open|target]]
        # into text="[[Open" and hint="target]]" — combined scan must catch it.
        parsed = ModelOutput(choices=[
            ParsedChoice(text="[[Open", hint="target]]"),
        ])
        # Cat 3: passage structure — links in choices should fail
        raw = "PROSE:\nText\nCHOICES:\n- [[Open|target]]\nSUMMARY:\nSummary."
        result3 = score_passage_structure(raw, parsed)
        assert result3.passed is False, "INV-7: link split across text/hint not detected in Cat 3"
        # Cat 6: link setter syntax — links in choices should fail
        result6 = score_link_setter_syntax(raw, parsed)
        assert result6.passed is False, "INV-7: link split across text/hint not detected in Cat 6"

    # ── INV-8: Dry-Run Self-Consistency ───────────────────────────────────
    def test_inv8_dry_run_all_categories_pass(self):
        """INV-8: --dry-run produces a report where all 6 categories pass."""
        ret = main(["--dry-run"])
        assert ret == 0
        # Also verify directly via score_response
        from harness.parsers import parse_model_output
        from model_benchmark.benchmark import _DRY_RUN_RESPONSE
        parsed = parse_model_output(_DRY_RUN_RESPONSE)
        results = score_response(_DRY_RUN_RESPONSE, parsed, "compact")
        assert len(results) == 6
        for r in results:
            assert r.passed is True, f"INV-8: {r.name} failed on dry-run fixture: {r.details}"

    # ── INV-9: Category Result Count and Ordering ────────────────────────
    def test_inv9_exactly_six_in_canonical_order(self):
        """INV-9: score_response returns exactly 6 results in canonical order."""
        parsed = _parse(GOOD_RESPONSE)
        results = score_response(GOOD_RESPONSE, parsed, "compact")
        assert len(results) == 6
        names = [r.name for r in results]
        assert names == list(_CATEGORY_ORDER)
        # No duplicates, no omissions
        assert len(set(names)) == 6
        expected = [
            "markup_compliance", "variable_scoping", "passage_structure",
            "macro_usage", "naked_interpolation", "link_setter_syntax",
        ]
        assert names == expected

    # ── INV-10: Score Range Validity ──────────────────────────────────────
    @pytest.mark.parametrize("text", [
        "",  # empty
        "plain text",  # no markup
        "''bold'' //italic// ~~strike~~ \"\"hi\"\"",  # all sugarcube
        "**bold** *italic*",  # all markdown
        "<<set $x to 1>>",  # good scoping
        "<<set $x = 1>>",  # bad scoping
    ])
    def test_inv10_score_range_markup(self, text):
        """INV-10: score_markup_compliance always returns score in [0.0, 1.0]."""
        result = score_markup_compliance(text)
        assert 0.0 <= result.score <= 1.0

    @pytest.mark.parametrize("text", ["", "plain", "<<set $x to 1>>", "<<set $x = 1>>", "setup.x in prose"])
    def test_inv10_score_range_variable_scoping(self, text):
        """INV-10: score_variable_scoping always returns score in [0.0, 1.0]."""
        result = score_variable_scoping(text)
        assert 0.0 <= result.score <= 1.0

    def test_inv10_score_range_all_scorers_good_bad_empty(self):
        """INV-10: all scorers return score in [0.0, 1.0] for good, bad, and empty inputs."""
        for text, parsed_arg in [
            (GOOD_RESPONSE, _parse(GOOD_RESPONSE)),
            (BAD_RESPONSE, _parse(BAD_RESPONSE)),
            ("", ModelOutput()),
        ]:
            for result in score_response(text, parsed_arg, "compact"):
                assert 0.0 <= result.score <= 1.0, (
                    f"INV-10: {result.name} score {result.score} out of range"
                )
