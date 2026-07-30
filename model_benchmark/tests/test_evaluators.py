#!/usr/bin/env python3
"""Tests for the evaluator plugin interface and built-in evaluators.

Covers: EvalResult dataclass, Evaluator ABC, registry discovery (built-in,
explicit registration, directory scan), the three built-in evaluators
(exact_match, substring_regex, llm_judge stub), threshold application, and
EvaluationContext. These tests are additive — they do not modify existing
tests in test_benchmark.py or test_config_schema.py.
"""
from __future__ import annotations

import pytest

from model_benchmark.evaluators import (
    EvalResult,
    EvaluationContext,
    Evaluator,
    EvaluatorRegistry,
    RegistryError,
    check_threshold,
    evaluate_response,
    get_evaluator,
    get_registry,
    list_evaluators,
    register,
    register_evaluator,
    reset_registry,
)
from model_benchmark.evaluators.base import EvalResult as BaseEvalResult
from model_benchmark.evaluators.registry import EvaluatorRegistry as Reg


# ── EvalResult ──────────────────────────────────────────────────────────

class TestEvalResult:
    def test_defaults(self):
        r = EvalResult(passed=True)
        assert r.passed is True
        assert r.score == 0.0
        assert r.max_score == 1.0
        assert r.details == ""
        assert r.evidence == ()
        assert r.metadata == {}

    def test_normalized_score(self):
        r = EvalResult(passed=True, score=0.75, max_score=1.0)
        assert r.normalized_score == 0.75

    def test_normalized_score_with_max(self):
        r = EvalResult(passed=True, score=3.0, max_score=4.0)
        assert r.normalized_score == 0.75

    def test_normalized_score_zero_max(self):
        r = EvalResult(passed=False, score=0.0, max_score=0.0)
        assert r.normalized_score == 0.0

    def test_is_frozen(self):
        r = EvalResult(passed=True)
        with pytest.raises(Exception):
            r.passed = False  # type: ignore[misc]

    def test_evidence_is_tuple(self):
        r = EvalResult(passed=True, evidence=("a", "b"))
        assert isinstance(r.evidence, tuple)


# ── check_threshold ────────────────────────────────────────────────────

class TestCheckThreshold:
    def test_pass_at_threshold(self):
        r = EvalResult(passed=False, score=0.8, max_score=1.0)
        out = check_threshold(r, pass_threshold=0.8)
        assert out.passed is True

    def test_fail_below_threshold(self):
        r = EvalResult(passed=False, score=0.79, max_score=1.0)
        out = check_threshold(r, pass_threshold=0.8)
        assert out.passed is False

    def test_threshold_with_max_score(self):
        r = EvalResult(passed=False, score=3.0, max_score=4.0)  # norm=0.75
        out = check_threshold(r, pass_threshold=0.8)
        assert out.passed is False
        out2 = check_threshold(r, pass_threshold=0.7)
        assert out2.passed is True

    def test_preserves_other_fields(self):
        r = EvalResult(passed=True, score=1.0, details="ok", evidence=("x",))
        out = check_threshold(r, pass_threshold=0.5)
        assert out.score == 1.0
        assert out.details == "ok"
        assert out.evidence == ("x",)


# ── EvaluationContext ────────────────────────────────────────────────────

class TestEvaluationContext:
    def test_defaults(self):
        ctx = EvaluationContext()
        assert ctx.test_id == ""
        assert ctx.model_name == ""
        assert ctx.input_variables == {}

    def test_to_dict(self):
        ctx = EvaluationContext(test_id="t1", model_name="llama")
        d = ctx.to_dict()
        assert d["test_id"] == "t1"
        assert d["model_name"] == "llama"


# ── Registry ────────────────────────────────────────────────────────────

class TestRegistry:
    def test_builtin_evaluators_registered(self):
        names = list_evaluators()
        assert "exact_match" in names
        assert "substring_regex" in names
        assert "llm_judge" in names

    def test_get_evaluator_by_name(self):
        ev = get_evaluator("exact_match")
        assert isinstance(ev, Evaluator)
        assert ev.name == "exact_match"

    def test_unknown_evaluator_raises(self):
        with pytest.raises(RegistryError, match="Unknown evaluator"):
            get_evaluator("nonexistent_evaluator")

    def test_register_decorator(self):
        # Use a fresh registry to avoid polluting the global one.
        local_reg = EvaluatorRegistry()

        @register("custom_test_eval")
        class CustomEval(Evaluator):
            name = "custom_test_eval"
            def evaluate(self, response, expected=None, context=None):
                return EvalResult(passed=True)

        # The decorator registers on the GLOBAL registry, so verify there.
        ev = get_evaluator("custom_test_eval")
        assert ev.name == "custom_test_eval"
        # Clean up.
        get_registry().unregister("custom_test_eval")

    def test_register_evaluator_function(self):
        class MyEval(Evaluator):
            name = "my_func_eval"
            def evaluate(self, response, expected=None, context=None):
                return EvalResult(passed=True)

        register_evaluator("my_func_eval", MyEval)
        ev = get_evaluator("my_func_eval")
        assert isinstance(ev, MyEval)
        get_registry().unregister("my_func_eval")

    def test_directory_scan_discovers_plugins(self):
        """The section_presence plugin in tests/evaluators/ should be discovered."""
        names = list_evaluators()
        assert "section_presence" in names, (
            f"section_presence should be auto-discovered; got {names}"
        )

    def test_plugin_evaluator_works(self):
        ev = get_evaluator("section_presence")
        result = ev.evaluate(
            "PROSE: hello\nCHOICES:\nSUMMARY:",
            expected={"contains": ["PROSE:", "CHOICES:", "SUMMARY:"]},
        )
        assert result.passed is True
        assert result.score == 3.0
        assert result.max_score == 3.0

    def test_registry_names_sorted(self):
        names = list_evaluators()
        assert names == sorted(names)


# ── ExactMatchEvaluator ─────────────────────────────────────────────────

class TestExactMatch:
    def test_exact_match_pass(self):
        r = evaluate_response(
            "exact_match", "Paris", expected={"answer": "Paris"},
            pass_threshold=1.0,
        )
        assert r.passed is True
        assert r.score == 1.0

    def test_exact_match_fail(self):
        r = evaluate_response(
            "exact_match", "London", expected={"answer": "Paris"},
            pass_threshold=1.0,
        )
        assert r.passed is False
        assert r.score == 0.0

    def test_case_insensitive_default(self):
        r = evaluate_response(
            "exact_match", "paris", expected={"answer": "Paris"},
            pass_threshold=1.0,
        )
        assert r.passed is True  # case-insensitive by default

    def test_case_sensitive(self):
        r = evaluate_response(
            "exact_match", "paris", expected={"answer": "Paris"},
            params={"case_sensitive": True}, pass_threshold=1.0,
        )
        assert r.passed is False

    def test_strip_whitespace(self):
        r = evaluate_response(
            "exact_match", "  Paris  ", expected={"answer": "Paris"},
            pass_threshold=1.0,
        )
        assert r.passed is True

    def test_trim_response_first_line(self):
        r = evaluate_response(
            "exact_match", "Paris\nextra text", expected={"answer": "Paris"},
            pass_threshold=1.0,
        )
        assert r.passed is True

    def test_no_trim_response(self):
        r = evaluate_response(
            "exact_match", "Paris\nextra", expected={"answer": "Paris"},
            params={"trim_response": False}, pass_threshold=1.0,
        )
        assert r.passed is False

    def test_no_expected_answer(self):
        r = evaluate_response(
            "exact_match", "Paris", expected=None, pass_threshold=1.0,
        )
        assert r.passed is False
        assert "None" in r.details

    def test_pydantic_expected(self):
        """Should work with ExpectedBehavior pydantic model too."""
        from model_benchmark.config_schema import ExpectedBehavior
        expected = ExpectedBehavior(answer="42")
        r = evaluate_response(
            "exact_match", "42", expected=expected, pass_threshold=1.0,
        )
        assert r.passed is True


# ── SubstringRegexEvaluator ──────────────────────────────────────────────

class TestSubstringRegex:
    def test_contains_all_pass(self):
        r = evaluate_response(
            "substring_regex",
            "PROSE: hello\nCHOICES:\nSUMMARY:",
            expected={"contains": ["PROSE:", "CHOICES:", "SUMMARY:"]},
            pass_threshold=1.0,
        )
        assert r.passed is True
        assert r.score == 3.0
        assert r.max_score == 3.0

    def test_contains_partial_fail(self):
        r = evaluate_response(
            "substring_regex",
            "PROSE: hello",
            expected={"contains": ["PROSE:", "CHOICES:"]},
            pass_threshold=1.0,
        )
        assert r.passed is False
        assert r.score == 1.0
        assert r.max_score == 2.0
        assert r.normalized_score == 0.5

    def test_not_contains(self):
        r = evaluate_response(
            "substring_regex",
            "hello world",
            expected={"not_contains": ["**", "##"]},
            pass_threshold=1.0,
        )
        assert r.passed is True
        assert r.score == 2.0

    def test_not_contains_fail(self):
        r = evaluate_response(
            "substring_regex",
            "hello **world**",
            expected={"not_contains": ["**"]},
            pass_threshold=1.0,
        )
        assert r.passed is False

    def test_regex_match(self):
        r = evaluate_response(
            "substring_regex",
            "The answer is 42.",
            expected={"regex": [r"\d+"]},
            pass_threshold=1.0,
        )
        assert r.passed is True
        assert r.score == 1.0

    def test_regex_no_match(self):
        r = evaluate_response(
            "substring_regex",
            "no numbers here",
            expected={"regex": [r"\d+"]},
            pass_threshold=1.0,
        )
        assert r.passed is False

    def test_combined_checks(self):
        r = evaluate_response(
            "substring_regex",
            "PROSE: hello **world**",
            expected={
                "contains": ["PROSE:"],
                "not_contains": ["**"],
            },
            pass_threshold=1.0,
        )
        assert r.passed is False  # contains passes, not_contains fails
        assert r.score == 1.0
        assert r.max_score == 2.0

    def test_mode_any(self):
        r = evaluate_response(
            "substring_regex",
            "PROSE: hello",
            expected={"contains": ["PROSE:", "MISSING"]},
            params={"mode": "any"}, pass_threshold=0.5,
        )
        assert r.passed is True  # at least one passes, threshold met (1/2=0.5)
        # With pass_threshold=1.0, mode="any" still requires normalized_score=1.0
        r2 = evaluate_response(
            "substring_regex",
            "PROSE: hello",
            expected={"contains": ["PROSE:", "MISSING"]},
            params={"mode": "any"}, pass_threshold=1.0,
        )
        assert not r2.passed  # 1/2 = 0.5 < 1.0

    def test_no_checks_defined(self):
        r = evaluate_response(
            "substring_regex", "hello", expected={}, pass_threshold=1.0,
        )
        assert r.passed is False
        assert "no contains" in r.details.lower()

    def test_case_insensitive(self):
        r = evaluate_response(
            "substring_regex",
            "prose: hello",
            expected={"contains": ["PROSE:"]},
            params={"case_sensitive": False}, pass_threshold=1.0,
        )
        assert r.passed is True

    def test_evidence_collected(self):
        r = evaluate_response(
            "substring_regex",
            "PROSE: hello",
            expected={"contains": ["PROSE:"], "regex": [r"\d+"]},
            pass_threshold=0.5,
        )
        assert len(r.evidence) == 2
        assert any("PROSE" in e for e in r.evidence)

    def test_metadata(self):
        r = evaluate_response(
            "substring_regex",
            "PROSE: yes",
            expected={"contains": ["PROSE:", "MISSING"]},
            pass_threshold=0.5,
        )
        assert r.metadata["passed_checks"] == 1
        assert r.metadata["total_checks"] == 2
        assert r.metadata["mode"] == "all"


# ── LLMJudgeEvaluator ────────────────────────────────────────────────────

class TestLLMJudge:
    def test_stub_mode_pass(self):
        r = evaluate_response(
            "llm_judge",
            "The capital of France is Paris.",
            expected={"answer": "Paris", "behavior": ["capital of France"]},
            pass_threshold=1.0,
        )
        assert r.passed is True
        assert r.metadata["mode"] == "stub"

    def test_stub_mode_fail(self):
        r = evaluate_response(
            "llm_judge",
            "I don't know.",
            expected={"answer": "Paris", "behavior": ["capital of France"]},
            pass_threshold=1.0,
        )
        assert r.passed is False

    def test_stub_no_answer(self):
        r = evaluate_response(
            "llm_judge",
            "some response",
            expected={"behavior": ["something"]},
            pass_threshold=1.0,
        )
        # No answer → answer check auto-passes, behavior may fail
        assert r.score >= 0.0

    def test_stub_metadata(self):
        r = evaluate_response(
            "llm_judge",
            "test",
            expected={"answer": "test"},
            pass_threshold=1.0,
        )
        assert "mode" in r.metadata
        assert r.metadata["mode"] == "stub"
        assert "reasoning" in r.metadata
        assert "checks_passed" in r.metadata

    def test_api_mode_missing_model(self):
        r = evaluate_response(
            "llm_judge",
            "test",
            expected={"answer": "test"},
            params={"mode": "api"}, pass_threshold=1.0,
        )
        assert r.passed is False
        assert "model" in r.details.lower()

    def test_api_mode_connection_error(self):
        """API mode should gracefully handle connection errors."""
        r = evaluate_response(
            "llm_judge",
            "test",
            expected={"answer": "test"},
            params={"mode": "api", "model": "test-model",
                    "base_url": "http://127.0.0.1:1"},  # invalid port
            pass_threshold=1.0,
        )
        assert r.passed is False
        assert "error" in r.metadata

    def test_is_not_deterministic(self):
        ev = get_evaluator("llm_judge")
        assert ev.deterministic is False

    def test_custom_prompt_template(self):
        """Custom prompt template should be accepted (tested in stub mode)."""
        ev = get_evaluator("llm_judge", mode="stub", prompt_template="custom")
        assert ev.params.get("prompt_template") == "custom"


# ── Custom plugin (section_presence) ────────────────────────────────────

class TestSectionPresencePlugin:
    def test_all_sections_present(self):
        r = evaluate_response(
            "section_presence",
            "PROSE: hello\nCHOICES:\nSUMMARY:",
            expected={"contains": ["PROSE:", "CHOICES:", "SUMMARY:"]},
            pass_threshold=1.0,
        )
        assert r.passed is True
        assert r.score == 3.0

    def test_missing_section(self):
        r = evaluate_response(
            "section_presence",
            "PROSE: hello",
            expected={"contains": ["PROSE:", "CHOICES:"]},
            pass_threshold=1.0,
        )
        assert r.passed is False
        assert r.score == 1.0
        assert r.max_score == 2.0

    def test_partial_match_mode(self):
        r = evaluate_response(
            "section_presence",
            "some text PROSE: here",
            expected={"contains": ["PROSE:"]},
            params={"partial_match": True}, pass_threshold=1.0,
        )
        assert r.passed is True

    def test_case_insensitive_default(self):
        r = evaluate_response(
            "section_presence",
            "prose: hello\nchoices:\nsummary:",
            expected={"contains": ["PROSE:", "CHOICES:", "SUMMARY:"]},
            pass_threshold=1.0,
        )
        assert r.passed is True  # case-insensitive by default

    def test_no_sections_defined(self):
        r = evaluate_response(
            "section_presence", "hello", expected={}, pass_threshold=1.0,
        )
        assert r.passed is False
        assert "no sections" in r.details.lower()


# ── Evaluator base class contract ──────────────────────────────────────

class TestEvaluatorABC:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            Evaluator()  # type: ignore[abstract]

    def test_repr(self):
        ev = get_evaluator("exact_match", case_sensitive=True)
        s = repr(ev)
        assert "ExactMatchEvaluator" in s
        assert "exact_match" in s
