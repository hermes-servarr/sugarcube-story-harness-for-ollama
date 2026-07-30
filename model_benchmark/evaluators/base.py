#!/usr/bin/env python3
"""Base classes for the evaluator plugin system.

Defines ``EvalResult`` (the structured verdict), ``EvaluationContext``
(inputs bundled for one call), ``Evaluator`` (the abstract base class /
plugin contract), and ``check_threshold`` (applies the pass/fail
threshold to a raw result).
"""
from __future__ import annotations

import abc
import dataclasses
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class EvalResult:
    """Outcome of a single evaluation of one response against one expected.

    Fields:
        passed:      Whether the response passes the test (score >= threshold).
        score:       Raw score in [0, max_score]. For built-in evaluators that
                     are binary, score is 0 or max_score.
        max_score:   Maximum achievable raw score (default 1.0).
        details:     Human-readable summary of the evaluation.
        evidence:    Tuple of strings — snippets/patterns/matches that
                     support the verdict. Empty tuple if none.
        metadata:    Free-form dict for evaluator-specific diagnostics
                     (e.g. match positions, judge reasoning, timings).
    """
    passed: bool
    score: float = 0.0
    max_score: float = 1.0
    details: str = ""
    evidence: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def normalized_score(self) -> float:
        """Score normalized to [0, 1] by dividing by max_score."""
        if self.max_score <= 0:
            return 0.0
        return self.score / self.max_score


@dataclass(frozen=True)
class EvaluationContext:
    """Inputs bundled for one evaluation call.

    Provides a structured alternative to passing loose kwargs. An
    evaluator may receive either an ``EvaluationContext`` or a plain dict
    as the ``context`` argument to ``evaluate()``.

    Attributes:
        test_id:        Stable unique test identifier.
        test_name:      Human-readable test name.
        input_variables: Variables injected into the prompt template.
        dataset_row:    The source dataset row (dict) if the test is
                        parameterized from a dataset, else None.
        model_name:     Name of the model that produced the response.
        variant:        Prompt variant used (compact/full/json).
        extra:          Free-form dict for any additional context.
    """
    test_id: str = ""
    test_name: str = ""
    input_variables: dict[str, Any] = field(default_factory=dict)
    dataset_row: Optional[dict[str, Any]] = None
    model_name: str = ""
    variant: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dict (useful for serialization)."""
        return dataclasses.asdict(self)


def check_threshold(result: EvalResult, pass_threshold: float) -> EvalResult:
    """Return a new EvalResult with ``passed`` set by the threshold.

    ``pass_threshold`` is a normalized value in [0, 1] — the minimum
    ``normalized_score`` required to pass. This is the canonical pass/fail
    determination used by the runner.
    """
    passed = result.normalized_score >= pass_threshold
    return dataclasses.replace(result, passed=passed)


class Evaluator(abc.ABC):
    """Abstract base class for test evaluators.

    Subclasses must:
    * Set the ``name`` class attribute — the unique registry key that
      config files reference via ``EvaluatorReference.name``.
    * Implement ``evaluate(response, expected, context) -> EvalResult``.

    The ``__init__`` accepts an optional ``params`` dict (from
    ``EvaluatorReference.params``) so config can pass parameters like
    ``case_sensitive`` or ``threshold``. Subclasses should override
    ``__init__`` and accept ``**kwargs`` or explicit params.
    """

    name: str = ""
    """Unique registry key — must match ``EvaluatorReference.name`` in configs."""

    description: str = ""
    """Short human-readable description shown in docs and error messages."""

    deterministic: bool = True
    """Whether this evaluator is deterministic (no model calls / randomness)."""

    def __init__(self, **params: Any) -> None:
        self.params = params

    @abc.abstractmethod
    def evaluate(
        self,
        response: str,
        expected: Any = None,
        context: Optional[dict[str, Any]] = None,
    ) -> EvalResult:
        """Evaluate ``response`` against ``expected`` with optional ``context``.

        Args:
            response: The model's raw output text.
            expected: The expected behavior descriptor. For built-in
                evaluators this is an ``ExpectedBehavior`` instance (pydantic
                model) or a plain dict with the same fields. For custom
                evaluators it can be any object the evaluator understands.
            context: Optional dict or ``EvaluationContext`` with extra
                context — ``test_id``, ``input_variables``, ``dataset_row``, etc.

        Returns:
            An ``EvalResult`` with score, pass/fail, details, and evidence.
        """
        ...

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self.name!r} params={self.params}>"
