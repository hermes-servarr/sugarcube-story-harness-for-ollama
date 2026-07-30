#!/usr/bin/env python3
"""Evaluator plugin interface and built-in evaluators for model_benchmark.

This package defines the pluggable evaluation system for declarative test
configs. It is the runtime counterpart to the ``EvaluatorReference`` model
defined in ``config_schema.py`` (task t_b8e82f29).

Design overview (see PLUGIN_GUIDE.md for the full guide):

* **EvalResult** — frozen dataclass returned by every evaluator. Holds
  ``passed`` (bool), ``score`` (float in [0, max_score]), ``max_score``
  (float), ``details`` (str), ``evidence`` (tuple of str), and ``metadata``
  (dict). ``passed`` is determined by comparing ``score / max_score`` against
  the ``pass_threshold`` from the config.
* **Evaluator** — abstract base class. Subclasses implement
  ``evaluate(response, expected, context) -> EvalResult`` and set the
  ``name`` class attribute (the registry key).
* **EvaluationContext** — dataclass bundling inputs for one evaluation call.
  Provides a structured alternative to passing loose kwargs.
* **Registry** — three discovery mechanisms, tried in order:
  1. Built-in evaluators (registered at import time).
  2. Entry-point group ``model_benchmark.evaluators`` (installed packages).
  3. Directory scan of ``model_benchmark/tests/evaluators/*.py`` (drop-in
     plugins without installation).
  4. Explicit registration via ``@register("name")`` or the registry API.
* **Built-in evaluators**:
  - ``exact_match`` — string equality (case-insensitive optional).
  - ``substring_regex`` — substring and/or regex match against expected.
  - ``llm_judge`` — stub that calls a model endpoint or returns a
    placeholder when no backend is configured (reference implementation).

Config files reference evaluators by name (see ``EvaluatorReference``)::

    evaluation:
      name: exact_match
      params:
        case_sensitive: false
      pass_threshold: 1.0

The runner (loader) resolves the name via ``get_evaluator()``, instantiates
the evaluator with ``params``, and calls ``evaluate()`` on each response.

Public API (re-exported from submodules for convenience):

    EvalResult, EvaluationContext, Evaluator   — from .base
    EvaluatorRegistry, get_registry, register,
        register_evaluator, reset_registry      — from .registry
    ExactMatchEvaluator, SubstringRegexEvaluator,
        LLMJudgeEvaluator                       — from .builtin
    list_evaluators, get_evaluator,
        evaluate_response, check_threshold       — convenience helpers
"""
from __future__ import annotations

from .base import EvalResult, EvaluationContext, Evaluator, check_threshold
from .registry import (
    EvaluatorRegistry,
    RegistryError,
    get_registry,
    register,
    register_evaluator,
    reset_registry,
)
from .builtin import (
    ExactMatchEvaluator,
    SubstringRegexEvaluator,
    LLMJudgeEvaluator,
)

__all__ = [
    "EvalResult",
    "EvaluationContext",
    "Evaluator",
    "check_threshold",
    "EvaluatorRegistry",
    "RegistryError",
    "get_registry",
    "register",
    "register_evaluator",
    "reset_registry",
    "ExactMatchEvaluator",
    "SubstringRegexEvaluator",
    "LLMJudgeEvaluator",
    "list_evaluators",
    "get_evaluator",
    "evaluate_response",
]


# ── Convenience helpers (re-export the registry-backed shortcuts) ──────

def list_evaluators() -> list[str]:
    """Return the names of all available evaluators (built-in + plugins)."""
    return get_registry().names()


def get_evaluator(name: str, **params):  # type: ignore[no-untyped-def]
    """Instantiate evaluator ``name`` with ``params``."""
    return get_registry().get_evaluator(name, **params)


def evaluate_response(
    name: str,
    response: str,
    expected=None,  # type: ignore[no-untyped-def]
    context=None,  # type: ignore[no-untyped-def]
    params=None,  # type: ignore[no-untyped-def]
    pass_threshold: float = 1.0,
) -> EvalResult:
    """Convenience: instantiate, evaluate, and apply threshold in one call.

    This is the high-level entry point the runner uses. It:
    1. Looks up the evaluator by ``name``.
    2. Instantiates it with ``params`` (from ``EvaluatorReference.params``).
    3. Calls ``evaluate(response, expected, context)``.
    4. Applies ``pass_threshold`` to set ``passed``.

    Args:
        name:          Evaluator name (registry key).
        response:      Model's raw output text.
        expected:      Expected behavior descriptor (ExpectedBehavior or dict).
        context:       Optional context dict or EvaluationContext.
        params:        Evaluator params (from config).
        pass_threshold: Normalized score threshold for passing [0, 1].

    Returns:
        EvalResult with ``passed`` set by the threshold.
    """
    ev = get_evaluator(name, **(params or {}))
    raw_result = ev.evaluate(response, expected, context)
    return check_threshold(raw_result, pass_threshold)


# Eagerly populate the default registry with built-in evaluators so that a
# bare ``import model_benchmark.evaluators`` is sufficient to make them
# resolvable by name. ``builtin`` imports this module for the decorator, so
# guard against double-initialisation.
_registry = get_registry()
if not _registry._builtins_loaded:  # pragma: no cover - internal flag
    _registry._load_builtins()
