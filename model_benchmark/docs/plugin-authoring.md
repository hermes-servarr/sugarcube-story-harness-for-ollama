# Plugin Authoring Guide

This guide explains how to write, register, and test a custom evaluator for
the SugarCube model benchmark. When the three built-in evaluators
(`exact_match`, `substring_regex`, `llm_judge`) are not enough for your test,
you can add your own without modifying any core code.

---

## How evaluators work

An evaluator takes a model response, the expected behavior descriptor, and
optional context, and returns a structured `EvalResult`:

```
response (str)  ──┐
expected (Any)  ──┤── Evaluator.evaluate() ──> EvalResult
context (dict) ──┘
```

The runner calls `evaluate_response(name, response, expected, context,
params, pass_threshold)` which:

1. Looks up the evaluator by `name` in the registry.
2. Instantiates it with `params` (from the config's `evaluation.params`).
3. Calls `evaluate(response, expected, context)`.
4. Applies `pass_threshold` to set the `passed` boolean on the result.

### EvalResult

```python
@dataclass(frozen=True)
class EvalResult:
    passed: bool                          # set by pass_threshold
    score: float = 0.0                    # raw score in [0, max_score]
    max_score: float = 1.0                # maximum achievable score
    details: str = ""                     # human-readable summary
    evidence: tuple[str, ...] = ()         # supporting snippets/patterns
    metadata: dict[str, Any] = {}         # free-form diagnostics

    @property
    def normalized_score(self) -> float:   # score / max_score (in [0, 1])
        ...
```

`passed` is determined by comparing `normalized_score >= pass_threshold`.
The evaluator sets `score` and `max_score`; the runner applies the
threshold.

### Evaluator (abstract base class)

```python
class Evaluator(abc.ABC):
    name: str = ""          # unique registry key (REQUIRED)
    description: str = ""   # shown in docs and error messages
    deterministic: bool = True

    def __init__(self, **params: Any) -> None:
        self.params = params

    @abc.abstractmethod
    def evaluate(self, response: str, expected: Any = None,
                 context: Optional[dict] = None) -> EvalResult:
        ...
```

The `__init__` accepts `**params` from the config's `evaluation.params`.
Subclasses should override `__init__` to accept explicit keyword arguments
and pass the rest through to `super().__init__()`.

### EvaluationContext

An optional structured context object (passed as the `context` argument):

```python
@dataclass(frozen=True)
class EvaluationContext:
    test_id: str = ""
    test_name: str = ""
    input_variables: dict[str, Any] = {}
    dataset_row: Optional[dict[str, Any]] = None
    model_name: str = ""
    variant: str = ""
    extra: dict[str, Any] = {}
```

Your evaluator can accept either an `EvaluationContext` or a plain `dict`
as the `context` argument.

---

## Writing a custom evaluator

### Option 1: Drop-in plugin (recommended)

Create a `.py` file in `model_benchmark/tests/evaluators/`. The registry
auto-discovers all `.py` files in this directory (excluding files starting
with `_`). No installation needed.

```python
#!/usr/bin/env python3
"""Custom evaluator: word_count.

Checks that the response has at least N words.
"""
from __future__ import annotations
from typing import Any, Optional

from model_benchmark.evaluators import Evaluator, EvalResult, register


@register("word_count")
class WordCountEvaluator(Evaluator):
    """Check that the response contains at least ``min_words`` words.

    Params:
        min_words: int (default 10) — minimum word count to pass.
        separator: str (default " ") — word separator (default whitespace).
    """

    name = "word_count"
    description = "Check minimum word count in the response"
    deterministic = True

    def __init__(self, min_words: int = 10, separator: str = " ", **kwargs: Any) -> None:
        super().__init__(min_words=min_words, separator=separator, **kwargs)

    def evaluate(self, response: str, expected: Any = None,
                 context: Optional[dict[str, Any]] = None) -> EvalResult:
        min_w = self.params.get("min_words", 10)
        resp = response or ""
        words = resp.split()
        count = len(words)

        passed = count >= min_w
        return EvalResult(
            passed=passed,
            score=float(count),
            max_score=float(min_w),
            details=f"word_count: {count} words (minimum {min_w}) — "
                    f"{'PASS' if passed else 'FAIL'}",
            evidence=(f"word_count={count}",),
            metadata={"word_count": count, "min_words": min_w},
        )
```

Save this as `model_benchmark/tests/evaluators/word_count.py`. It is
automatically discovered the next time the registry is queried — no
restart, no installation.

### Option 2: Entry point (for installable packages)

If you are distributing evaluators as a package, register an entry point in
your `pyproject.toml`:

```toml
[project.entry-points."model_benchmark.evaluators"]
word_count = "my_package.evaluators:WordCountEvaluator"
```

The registry discovers entry points in the
`model_benchmark.evaluators` group at runtime.

### Option 3: Explicit registration

Register programmatically at runtime (useful for testing or dynamic
plugins):

```python
from model_benchmark.evaluators import register_evaluator

register_evaluator("word_count", WordCountEvaluator)
```

---

## Referencing your evaluator in config

In your test YAML, reference the evaluator by name with optional parameters:

```yaml
evaluation:
  name: word_count
  type: custom
  params:
    min_words: 20
    separator: " "
  pass_threshold: 1.0
  max_score: 1.0
  deterministic: true
```

The `name` must match the registry key (the `@register("word_count")`
decorator argument or the `register_evaluator` name). `params` are passed
as keyword arguments to the evaluator's `__init__`. `pass_threshold` is
the minimum `normalized_score` (score / max_score) required to pass.

---

## Discovery order

When `get_evaluator("name")` is called, the registry checks in this order:

1. **Explicit registration** — via `@register` decorator or
   `register_evaluator()`.
2. **Built-in evaluators** — loaded from `evaluators/builtin.py` at import
   time.
3. **Entry points** — the `model_benchmark.evaluators` entry-point group
   (installed packages).
4. **Directory scan** — `tests/evaluators/*.py` files (drop-in plugins).

First match wins. Built-ins register first, so a drop-in plugin with the
same name as a built-in will NOT override it. To replace a built-in, use
`registry.unregister("exact_match")` before registering your replacement.

---

## Extracting fields from `expected`

The `expected` argument to `evaluate()` can be:
- An `ExpectedBehavior` pydantic model instance (when the config has an
  `expected:` block), or
- A plain `dict` with the same keys, or
- `None` (when the config omits `expected:`).

Use a helper to extract fields from either:

```python
def _get_expected_field(expected: Any, field: str) -> Any:
    if expected is None:
        return None
    if isinstance(expected, dict):
        return expected.get(field)
    return getattr(expected, field, None)
```

Common fields: `answer`, `answer_type`, `behavior`, `rubric`, `constraints`,
`contains`, `not_contains`, `regex`, `must_parse_as`.

---

## Scoring patterns

### Binary (pass/fail)

```python
matched = resp == expected_answer
return EvalResult(
    passed=matched,
    score=1.0 if matched else 0.0,
    max_score=1.0,
    details=f"exact match: {'PASS' if matched else 'FAIL'}",
)
```

### Fractional (N of M checks)

```python
passed_count = sum(1 for check in checks if check_passes(check))
total = len(checks)
return EvalResult(
    passed=(passed_count == total),
    score=float(passed_count),
    max_score=float(total),
    details=f"{passed_count}/{total} checks passed",
)
```

### Continuous (0.0 to max_score)

```python
similarity = compute_similarity(response, expected_answer)
return EvalResult(
    passed=(similarity >= 0.8),  # will be overridden by pass_threshold
    score=similarity,
    max_score=1.0,
    details=f"similarity: {similarity:.3f}",
)
```

---

## Testing your evaluator

Write a test file alongside the existing tests (e.g.
`model_benchmark/test_word_count.py`):

```python
"""Tests for the word_count evaluator plugin."""
from model_benchmark.evaluators import get_evaluator, reset_registry


def test_word_count_pass():
    reset_registry()
    ev = get_evaluator("word_count", min_words=3)
    result = ev.evaluate("hello world from the evaluator", expected=None)
    assert result.passed
    assert result.score == 6.0
    assert result.max_score == 3.0


def test_word_count_fail():
    reset_registry()
    ev = get_evaluator("word_count", min_words=10)
    result = ev.evaluate("too short", expected=None)
    assert not result.passed
    assert result.score == 2.0


def test_word_count_with_config():
    """End-to-end: parse a config that references word_count, evaluate."""
    reset_registry()
    from model_benchmark.evaluators import evaluate_response
    result = evaluate_response(
        name="word_count",
        response="one two three four five",
        expected=None,
        params={"min_words": 5},
        pass_threshold=1.0,
    )
    assert result.passed
```

Run with:

```bash
uv run python -m pytest model_benchmark/test_word_count.py -v
```

---

## Existing example

A complete drop-in plugin example is already in the repo:

- Plugin: `model_benchmark/tests/evaluators/section_presence.py`
- Config: `model_benchmark/tests/examples/evaluator_dataset_example.yaml`
  (the `section_presence_example` test)

The `section_presence` evaluator checks that required section headers
(e.g. "PROSE:", "CHOICES:", "SUMMARY:") are present in the response. It
demonstrates: `@register` decorator, params, fractional scoring, and
reading from `expected.contains`.

---

## Anonymization safety

Custom evaluators **cannot** bypass anonymization or write untracked
identity into reviewer reports. The anonymization layer runs after the
evaluator and strips model names, providers, paths, and other identity
from the output before generating the anonymized report. Your evaluator
should not embed identity in `details`, `evidence`, or `metadata` — if it
does, the anonymizer will redact it, but it is cleaner to avoid it.

---

## File layout

```
model_benchmark/
├── evaluators/                     # Evaluator plugin package (core)
│   ├── __init__.py                 # Public API re-exports
│   ├── base.py                     # EvalResult, EvaluationContext, Evaluator ABC
│   ├── registry.py                 # EvaluatorRegistry, discovery, register decorator
│   └── builtin.py                  # Built-in: exact_match, substring_regex, llm_judge
├── tests/
│   ├── evaluators/                 # Drop-in plugins (auto-discovered)
│   │   └── section_presence.py     # Example custom evaluator
│   └── examples/
│       └── evaluator_dataset_example.yaml  # Config referencing all 3 evaluators
├── test_evaluators.py              # Tests for built-in evaluators
├── test_dataset_loader.py          # Tests for dataset loader
└── test_evaluator_integration.py   # End-to-end integration tests
```
