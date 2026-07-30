#!/usr/bin/env python3
"""Built-in reference evaluators: exact_match, substring_regex, llm_judge.

These are registered automatically on import via the ``@register`` decorator
so that ``import model_benchmark.evaluators`` makes them resolvable by name.
"""
from __future__ import annotations

import json
import re
import urllib.request
from typing import Any, Optional

from .base import EvalResult, Evaluator
from .registry import register


# ── Helpers ───────────────────────────────────────────────────────────

def _get_expected_field(expected: Any, field: str) -> Any:
    """Extract a field from an ExpectedBehavior (pydantic) or plain dict."""
    if expected is None:
        return None
    if isinstance(expected, dict):
        return expected.get(field)
    return getattr(expected, field, None)


def _extract_keywords(text: str) -> list[str]:
    """Extract significant keywords from a behavioral descriptor string."""
    stop = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "with", "that", "this", "it", "to", "for", "of", "in", "on", "at",
        "and", "or", "not", "no", "yes", "use", "uses", "using", "include",
        "contains", "match", "matches", "must", "should",
    }
    cleaned = re.sub(r'[<{}\[\]|]', ' ', text)
    words = [w for w in cleaned.split() if len(w) > 2 and w.lower() not in stop]
    return words


def _parse_judge_output(raw: str) -> dict[str, Any]:
    """Parse the judge model's JSON output, tolerating surrounding text."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass
    match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {"pass": False, "score": 0.0, "reasoning": "Failed to parse judge output."}


# ── Built-in evaluators ────────────────────────────────────────────────

@register("exact_match")
class ExactMatchEvaluator(Evaluator):
    """Compare the response to the expected answer for exact equality.

    Params:
        case_sensitive: bool (default False) — if True, compare case-sensitively.
        strip_whitespace: bool (default True) — strip both sides before comparing.
        trim_response: bool (default True) — if True, only compare the first
            line of the response (useful for short-answer tests).

    Expected fields used (from ``ExpectedBehavior``):
        answer: the reference answer string.

    Scoring: binary — 1.0 (match) or 0.0 (no match). ``max_score`` defaults
    to 1.0, so ``pass_threshold=1.0`` requires an exact match.
    """

    name = "exact_match"
    description = "Exact string equality against expected.answer"
    deterministic = True

    def __init__(
        self,
        case_sensitive: bool = False,
        strip_whitespace: bool = True,
        trim_response: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            case_sensitive=case_sensitive,
            strip_whitespace=strip_whitespace,
            trim_response=trim_response,
            **kwargs,
        )

    def evaluate(
        self,
        response: str,
        expected: Any = None,
        context: Optional[dict[str, Any]] = None,
    ) -> EvalResult:
        expected_answer = _get_expected_field(expected, "answer")
        if expected_answer is None:
            return EvalResult(
                passed=False,
                score=0.0,
                details="exact_match: expected.answer is None — cannot match.",
            )

        resp = response or ""
        ans = str(expected_answer)

        if self.params.get("trim_response", True) and resp:
            resp = resp.splitlines()[0] if resp.strip() else ""
        if self.params.get("strip_whitespace", True):
            resp = resp.strip()
            ans = ans.strip()

        if not self.params.get("case_sensitive", False):
            resp_cmp = resp.lower()
            ans_cmp = ans.lower()
        else:
            resp_cmp = resp
            ans_cmp = ans

        matched = resp_cmp == ans_cmp
        return EvalResult(
            passed=matched,
            score=1.0 if matched else 0.0,
            max_score=1.0,
            details=f"exact_match: {'PASS' if matched else 'FAIL'} "
                    f"(response={resp!r} vs expected={ans!r})",
            evidence=(f"response={resp!r}", f"expected={ans!r}"),
            metadata={"case_sensitive": self.params.get("case_sensitive", False)},
        )


@register("substring_regex")
class SubstringRegexEvaluator(Evaluator):
    """Check that the response contains required substrings and matches regexes.

    Params:
        case_sensitive: bool (default True) — for substring checks.
        mode: str (default "all") — "all" (every pattern must match) or
            "any" (at least one pattern must match).

    Expected fields used (from ``ExpectedBehavior``):
        contains:     list of substrings the response MUST contain.
        not_contains: list of substrings the response must NOT contain.
        regex:        list of regex patterns the response MUST match.

    Scoring: fraction of satisfied checks. Each ``contains``, ``not_contains``,
    and ``regex`` item is one sub-check. ``max_score`` = total number of checks.
    Example: 2 of 3 checks pass → score=2.0, max_score=3.0, normalized=0.667.
    """

    name = "substring_regex"
    description = "Substring and regex match against expected.contains/not_contains/regex"
    deterministic = True

    def __init__(
        self,
        case_sensitive: bool = True,
        mode: str = "all",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            case_sensitive=case_sensitive,
            mode=mode,
            **kwargs,
        )

    def evaluate(
        self,
        response: str,
        expected: Any = None,
        context: Optional[dict[str, Any]] = None,
    ) -> EvalResult:
        resp = response or ""
        contains = _get_expected_field(expected, "contains") or []
        not_contains = _get_expected_field(expected, "not_contains") or []
        regexes = _get_expected_field(expected, "regex") or []

        case_sensitive = self.params.get("case_sensitive", True)
        mode = self.params.get("mode", "all")

        evidence: list[str] = []
        details_parts: list[str] = []
        passed_count = 0
        total_checks = 0

        for sub in contains:
            total_checks += 1
            if case_sensitive:
                found = sub in resp
            else:
                found = sub.lower() in resp.lower()
            if found:
                passed_count += 1
                evidence.append(f"contains ✓: {sub!r}")
            else:
                evidence.append(f"contains ✗: {sub!r}")
            details_parts.append(f"contains {sub!r}: {'✓' if found else '✗'}")

        for sub in not_contains:
            total_checks += 1
            if case_sensitive:
                found = sub in resp
            else:
                found = sub.lower() in resp.lower()
            if not found:
                passed_count += 1
                evidence.append(f"not_contains ✓: {sub!r}")
            else:
                evidence.append(f"not_contains ✗: {sub!r}")
            details_parts.append(f"not_contains {sub!r}: {'✓' if not found else '✗'}")

        for pat in regexes:
            total_checks += 1
            try:
                m = re.search(pat, resp)
                if m:
                    passed_count += 1
                    evidence.append(f"regex ✓: /{pat}/ → {m.group(0)!r}")
                else:
                    evidence.append(f"regex ✗: /{pat}/")
                details_parts.append(f"regex /{pat}/: {'✓' if m else '✗'}")
            except re.error as e:
                evidence.append(f"regex ✗: /{pat}/ (invalid: {e})")
                details_parts.append(f"regex /{pat}/: invalid pattern ({e})")

        if total_checks == 0:
            return EvalResult(
                passed=False,
                score=0.0,
                max_score=1.0,
                details="substring_regex: no contains/not_contains/regex checks defined.",
            )

        if mode == "any":
            passed = passed_count >= 1
        else:
            passed = passed_count == total_checks

        score = float(passed_count)
        return EvalResult(
            passed=passed,
            score=score,
            max_score=float(total_checks),
            details="substring_regex: " + "; ".join(details_parts),
            evidence=tuple(evidence),
            metadata={
                "passed_checks": passed_count,
                "total_checks": total_checks,
                "mode": mode,
            },
        )


@register("llm_judge")
class LLMJudgeEvaluator(Evaluator):
    """Stub LLM-judge evaluator — a reference implementation.

    In production, this evaluator sends the response + expected to a judge
    model and parses the JSON verdict. For offline/CI use, it can operate in
    two modes:

    - ``mode="stub"`` (default): returns a placeholder verdict based on
      simple heuristics (does the response contain the expected answer?).
      This lets configs reference ``llm_judge`` without a live model.
    - ``mode="api"``: calls a model endpoint via the configured base_url
      and parses the JSON response. This requires Ollama or an OpenAI-
      compatible endpoint to be running.

    Params:
        mode: "stub" | "api" (default "stub").
        model: judge model name (e.g. "llama3.1:8b"). Required for "api".
        base_url: endpoint URL. Defaults to "http://localhost:11434".
        temperature: judge sampling temperature (default 0.0).
        prompt_template: custom Jinja2/text template. If not set, a default
            template is used.
        fallback_score: score to return if the judge fails (default 0.0).

    Expected fields used (from ``ExpectedBehavior``):
        answer:  reference answer (injected into the judge prompt).
        rubric:  scoring rubric items (list of dicts).
        behavior: behavioral descriptors.

    Returns:
        EvalResult with ``score`` in [0, max_score], ``metadata["judge_output"]``
        containing the raw judge response, and ``metadata["reasoning"]``
        containing the extracted reasoning.
    """

    name = "llm_judge"
    description = "LLM-judge evaluator (stub or API mode)"
    deterministic = False

    _DEFAULT_PROMPT = """\
You are evaluating a model response against expected behavior.

Response:
{response}

Expected answer: {expected_answer}
Behavioral descriptors: {behavior}
Rubric: {rubric}

Return a JSON object:
{{"pass": true|false, "score": 0.0-1.0, "reasoning": "..."}}
Only return the JSON, no other text."""

    def __init__(
        self,
        mode: str = "stub",
        model: str = "",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.0,
        prompt_template: str = "",
        fallback_score: float = 0.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            mode=mode,
            model=model,
            base_url=base_url,
            temperature=temperature,
            prompt_template=prompt_template,
            fallback_score=fallback_score,
            **kwargs,
        )

    def evaluate(
        self,
        response: str,
        expected: Any = None,
        context: Optional[dict[str, Any]] = None,
    ) -> EvalResult:
        mode = self.params.get("mode", "stub")
        if mode == "api":
            return self._evaluate_api(response, expected, context)
        return self._evaluate_stub(response, expected, context)

    def _evaluate_stub(
        self,
        response: str,
        expected: Any = None,
        context: Optional[dict[str, Any]] = None,
    ) -> EvalResult:
        """Heuristic fallback — no model call needed."""
        resp = response or ""
        answer = _get_expected_field(expected, "answer")
        behavior = _get_expected_field(expected, "behavior") or []
        rubric = _get_expected_field(expected, "rubric") or []

        checks_passed = 0
        checks_total = 0
        evidence: list[str] = []

        checks_total += 1
        if answer and str(answer).strip():
            if str(answer).lower() in resp.lower():
                checks_passed += 1
                evidence.append(f"stub: expected answer {str(answer)!r} found in response")
            else:
                evidence.append(f"stub: expected answer {str(answer)!r} NOT found")
        else:
            checks_passed += 1
            evidence.append("stub: no expected answer to check")

        for desc in behavior:
            checks_total += 1
            keywords = _extract_keywords(str(desc))
            if keywords and all(kw.lower() in resp.lower() for kw in keywords):
                checks_passed += 1
                evidence.append(f"stub: behavior ✓ {desc!r}")
            else:
                evidence.append(f"stub: behavior ✗ {desc!r}")

        score = float(checks_passed)
        max_score = float(checks_total) if checks_total > 0 else 1.0

        return EvalResult(
            passed=(checks_passed == checks_total) if checks_total > 0 else False,
            score=score,
            max_score=max_score,
            details=f"llm_judge (stub): {checks_passed}/{checks_total} heuristic checks passed",
            evidence=tuple(evidence),
            metadata={
                "mode": "stub",
                "judge_output": None,
                "reasoning": "Heuristic stub — no model call made.",
                "checks_passed": checks_passed,
                "checks_total": checks_total,
                "rubric_items": len(rubric),
            },
        )

    def _evaluate_api(
        self,
        response: str,
        expected: Any = None,
        context: Optional[dict[str, Any]] = None,
    ) -> EvalResult:
        """Call a judge model endpoint and parse the JSON verdict."""
        model = self.params.get("model", "")
        if not model:
            return EvalResult(
                passed=False,
                score=0.0,
                details="llm_judge (api): 'model' param is required for API mode.",
                metadata={"mode": "api", "error": "missing_model"},
            )

        base_url = self.params.get("base_url", "http://localhost:11434")
        temperature = float(self.params.get("temperature", 0.0))
        fallback = float(self.params.get("fallback_score", 0.0))

        answer = _get_expected_field(expected, "answer") or ""
        behavior = _get_expected_field(expected, "behavior") or []
        rubric = _get_expected_field(expected, "rubric") or []

        prompt_tpl = self.params.get("prompt_template", "") or self._DEFAULT_PROMPT
        prompt = prompt_tpl.format(
            response=response or "",
            expected_answer=str(answer),
            behavior=str(behavior),
            rubric=str(rubric),
        )

        payload = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }).encode()

        try:
            url = f"{base_url.rstrip('/')}/api/generate"
            req = urllib.request.Request(url, data=payload, method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=60) as resp_raw:
                data = json.loads(resp_raw.read())
            raw_output = data.get("response", "")
            verdict = _parse_judge_output(raw_output)
            return EvalResult(
                passed=bool(verdict.get("pass", False)),
                score=float(verdict.get("score", fallback)),
                max_score=1.0,
                details=f"llm_judge (api): model={model}, score={verdict.get('score')}",
                evidence=(f"judge_output={raw_output[:200]}",),
                metadata={
                    "mode": "api",
                    "model": model,
                    "judge_output": raw_output,
                    "reasoning": verdict.get("reasoning", ""),
                },
            )
        except Exception as e:
            return EvalResult(
                passed=False,
                score=fallback,
                max_score=1.0,
                details=f"llm_judge (api): error calling judge model: {e}",
                metadata={"mode": "api", "error": str(e)},
            )
