#!/usr/bin/env python3
"""Custom evaluator plugin: section_presence

This is a drop-in plugin — it is auto-discovered by the registry's
directory scan of ``model_benchmark/tests/evaluators/*.py`` (no
installation needed). It demonstrates how to write a custom evaluator
without modifying the core ``evaluators.py`` module.

What it does: checks that a model response contains all required section
headers (e.g. "PROSE:", "CHOICES:", "SUMMARY:"). This is a SugarCube-
specific evaluator that complements the generic built-ins.

Config reference::

    evaluation:
      name: section_presence
      type: section_check
      params:
        case_sensitive: false
      pass_threshold: 1.0

Expected fields used (from ``ExpectedBehavior``):
    contains: list of section headers the response must include.

Scoring: fraction of required sections present.
"""
from __future__ import annotations

from typing import Any, Optional

from model_benchmark.evaluators import Evaluator, EvalResult, register


@register("section_presence")
class SectionPresenceEvaluator(Evaluator):
    """Check that required section headers are present in the response.

    Params:
        case_sensitive: bool (default False) — case-insensitive by default
            since section headers may appear as "PROSE:" or "prose:".
        partial_match: bool (default False) — if True, a section is considered
            present if the header text appears anywhere in the response,
            not just at the start of a line.
    """

    name = "section_presence"
    description = "Check that required section headers are present"
    deterministic = True

    def __init__(
        self,
        case_sensitive: bool = False,
        partial_match: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            case_sensitive=case_sensitive,
            partial_match=partial_match,
            **kwargs,
        )

    def evaluate(
        self,
        response: str,
        expected: Any = None,
        context: Optional[dict[str, Any]] = None,
    ) -> EvalResult:
        resp = response or ""
        sections = self._get_expected_field(expected, "contains") or []

        if not sections:
            return EvalResult(
                passed=False,
                score=0.0,
                max_score=1.0,
                details="section_presence: no sections in expected.contains",
            )

        case_sensitive = self.params.get("case_sensitive", False)
        partial = self.params.get("partial_match", False)
        search_text = resp if case_sensitive else resp.lower()

        found: list[str] = []
        missing: list[str] = []
        for section in sections:
            target = section if case_sensitive else section.lower()
            if partial:
                ok = target in search_text
            else:
                # Check if the section appears at the start of any line.
                ok = any(
                    (line if case_sensitive else line.lower()).startswith(target)
                    for line in resp.splitlines()
                )
            if ok:
                found.append(section)
            else:
                missing.append(section)

        total = len(sections)
        score = float(len(found))
        return EvalResult(
            passed=(len(missing) == 0),
            score=score,
            max_score=float(total),
            details=f"section_presence: {len(found)}/{total} sections found; "
                    f"missing={missing}",
            evidence=tuple(f"found: {s}" for s in found) +
                      tuple(f"missing: {s}" for s in missing),
            metadata={
                "found": found,
                "missing": missing,
                "total": total,
            },
        )

    @staticmethod
    def _get_expected_field(expected: Any, field: str) -> Any:
        if expected is None:
            return None
        if isinstance(expected, dict):
            return expected.get(field)
        return getattr(expected, field, None)
