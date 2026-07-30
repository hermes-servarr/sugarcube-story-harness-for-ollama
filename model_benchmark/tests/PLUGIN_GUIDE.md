# Evaluator Plugin Guide

This guide explains how to write, register, and use custom test evaluators in
the SugarCube model benchmark.

## Overview

The evaluator plugin system lets you define custom evaluation logic for
declarative test configs. Three built-in evaluators are provided, and you can
add your own without modifying the core code.

**Built-in evaluators:**

| Name              | Type           | Deterministic | Description                                  |
|-------------------|----------------|---------------|----------------------------------------------|
| `exact_match`     | `exact_match`  | Yes           | Exact string equality against `expected.answer` |
| `substring_regex` | `regex`        | Yes           | Substring and regex checks on the response      |
| `llm_judge`       | `llm_judge`    | No            | LLM-judge (stub heuristic or API call)          |

**Custom evaluator included:**

| Name               | Type           | Description                                        |
|--------------------|----------------|----------------------------------------------------|
| `section_presence` | `section_check`| Checks required section headers in the response    |

## How Evaluators Work

An evaluator takes a model response, the expected behavior, and optional
context, and returns an `EvalResult`:

```
response (str)  ──┐
expected (Any)  ──┤── Evaluator.evaluate() ──> EvalResult
context (dict) ──┘
```

`EvalResult` contains:
- `passed` — bool (set by applying `pass_threshold` to `normalized_score`)
- `score` — raw score (float, in [0, max_score])
- `max_score` — maximum achievable score (default 1.0)
- `normalized_score` — `score / max_score` (property, in [0, 1])
- `details` — human-readable summary
- `evidence` — tuple of supporting strings
- `metadata` — free-form dict for diagnostics

## Writing a Custom Evaluator

### Option 1: Drop-in Plugin (Recommended)

Create a `.py` file in `model_benchmark/tests/evaluators/`:

```python
from model_benchmark.evaluators import Evaluator, EvalResult, register

@register("my_evaluator")
class MyEvaluator(Evaluator):
    name = "my_evaluator"
    description = "Checks that the response is not empty"
    deterministic = True

    def __init__(self, min_length=0, **kwargs):
        super().__init__(min_length=min_length, **kwargs)

    def evaluate(self, response, expected=None, context=None):
        min_len = self.params.get("min_length", 0)
        resp = response or ""
        if len(resp) >= min_len:
            return EvalResult(
                passed=True,
                score=1.0,
                max_score=1.0,
                details=f"Response length {len(resp)} >= {min_len}",
            )
        return EvalResult(
            passed=False,
            score=0.0,
            max_score=1.0,
            details=f"Response too short: {len(resp)} < {min_len}",
        )
```

The file is auto-discovered on import — no installation needed.

### Option 2: Entry Point (For Packages)

If you're distributing evaluators as an installable package, register an
entry point in your `pyproject.toml`:

```toml
[project.entry-points."model_benchmark.evaluators"]
my_evaluator = "my_package.evaluators:MyEvaluator"
```

### Option 3: Explicit Registration

Register programmatically at runtime:

```python
from model_benchmark.evaluators import register_evaluator

register_evaluator("my_evaluator", MyEvaluator)
```

## Referencing Evaluators in Config

In your test config YAML, reference the evaluator by name with optional
parameters:

```yaml
evaluation:
  name: my_evaluator
  type: custom
  params:
    min_length: 10
    case_sensitive: false
  pass_threshold: 0.8
  max_score: 1.0
  deterministic: true
```

The `name` must match the registry key. `params` are passed as keyword
arguments to the evaluator's `__init__`. `pass_threshold` is the minimum
`normalized_score` (score / max_score) required to pass.

## Using Datasets

Tests can reference external datasets that inject rows as parameterized
inputs:

```yaml
dataset:
  name: my_dataset
  format: csv          # csv, jsonl, json, huggingface, or inline
  path: datasets/qa.csv # relative to model_benchmark/tests/
  filters:
    difficulty: easy    # keep rows where difficulty == "easy"
    category: [math, science]  # membership test
  sample: 100           # random sample N rows
  seed: 42              # reproducible sampling
```

**Supported formats:**

| Format       | Description                                          |
|--------------|------------------------------------------------------|
| `csv`        | Comma-separated, first row is the header             |
| `jsonl`      | JSON Lines — one JSON object per line                |
| `json`       | A JSON file containing a list of objects             |
| `huggingface`| A HuggingFace dataset (requires `datasets` package)  |
| `inline`     | Rows provided directly in the config                 |

**Filters:** Each key is a column name. A scalar value matches exactly;
a list value is a membership test. Filtering happens before sampling.

**Sampling:** If `sample` is set, `seed` ensures reproducibility.

## Running the Pipeline

The full pipeline (config → dataset → evaluator → results):

```python
import yaml
from model_benchmark.config_schema import parse_config_dict, resolve_test, BUILTIN_DEFAULTS
from model_benchmark.dataset_loader import DatasetLoader
from model_benchmark.evaluators import evaluate_response

# 1. Parse config
data = yaml.safe_load(open("test_config.yaml"))
doc = parse_config_dict(data)
test_config = resolve_test(BUILTIN_DEFAULTS, doc.to_test_config())

# 2. Load dataset
loader = DatasetLoader(base_dir="model_benchmark/tests/")
loaded = loader.load(test_config.dataset)

# 3. Run evaluator on each row
eval_ref = test_config.evaluation
for row in loaded.rows:
    expected = {"answer": row["answer"]}
    result = evaluate_response(
        eval_ref.name,
        response="simulated model output",
        expected=expected,
        params=eval_ref.params,
        pass_threshold=eval_ref.pass_threshold,
    )
    print(f"{'PASS' if result.passed else 'FAIL'}: {result.details}")
```

## File Layout

```
model_benchmark/
├── evaluators/                     # Evaluator plugin package
│   ├── __init__.py                 # Public API re-exports
│   ├── base.py                     # EvalResult, EvaluationContext, Evaluator ABC
│   ├── registry.py                 # EvaluatorRegistry, discovery, register decorator
│   └── builtin.py                  # Built-in: exact_match, substring_regex, llm_judge
├── dataset_loader.py               # DatasetLoader for CSV/JSONL/JSON/HF/inline
├── tests/
│   ├── evaluators/                 # Drop-in plugins (auto-discovered)
│   │   └── section_presence.py     # Custom evaluator example
│   ├── datasets/                   # Sample dataset files
│   │   ├── qa_simple.csv           # CSV sample (10 Q&A rows)
│   │   └── directions.jsonl        # JSONL sample (5 direction prompts)
│   └── examples/
│       └── evaluator_dataset_example.yaml  # Config with all 3 evaluators + datasets
├── test_evaluators.py              # Tests for evaluators
├── test_dataset_loader.py          # Tests for dataset loader
└── test_evaluator_integration.py   # End-to-end integration tests
```

## Discovery Order

When you call `get_evaluator("name")`, the registry checks in this order:

1. **Explicit registration** — via `@register` decorator or `register_evaluator()`.
2. **Built-in evaluators** — loaded from `evaluators/builtin.py` at import time.
3. **Entry points** — the `model_benchmark.evaluators` entry-point group.
4. **Directory scan** — `tests/evaluators/*.py` files (drop-in plugins).

First match wins. Built-ins cannot be overridden by plugins with the same name
(they register first); use `unregister()` if you need to replace a built-in.
