# SugarCube Model Benchmark — Contributor Documentation

This directory contains the complete contributor documentation for the
declarative test configuration and extensibility system in `model_benchmark/`.

## What this system is

The SugarCube model benchmark evaluates LLM-generated SugarCube passage markup
against six compliance categories (markup compliance, variable scoping, passage
structure, macro usage, naked interpolation, link setter syntax). Instead of
hard-coding test cases in Python, the benchmark reads **declarative test
definitions** from YAML/JSON files. A layered config hierarchy (built-in →
global → suite → test → CLI) provides sensible defaults so a minimal test
needs only a few fields, while a full-featured test can exercise datasets,
parameterized matrices, custom evaluators, and model eligibility constraints.

## Documentation index

| Document | Audience | What it covers |
|----------|----------|----------------|
| [getting-started.md](getting-started.md) | New contributors | Define a test in YAML, run it, interpret results — end to end in 5 minutes |
| [config-reference.md](config-reference.md) | All config authors | Every schema field: type, default, example, constraints |
| [plugin-authoring.md](plugin-authoring.md) | Evaluator authors | Write, register, and test a custom evaluator plugin |
| [dataset-guide.md](dataset-guide.md) | Test authors | Reference external/inline datasets (CSV, JSONL, HuggingFace) from tests |
| [troubleshooting.md](troubleshooting.md) | Everyone | Debug mode, common errors, validation diagnostics, FAQ |

## Example test configs

The `model_benchmark/tests/examples/` directory contains reference examples
that demonstrate every feature. The contributor examples below (in
`examples/`) are smaller, self-contained configs ordered by complexity:

| Example | Complexity | Demonstrates |
|---------|------------|--------------|
| `examples/01_smoke_test.yaml` | Minimal | One test, three fields — the smallest valid test |
| `examples/02_exact_match.yaml` | Simple | Built-in `exact_match` evaluator with params |
| `examples/03_substring_regex.yaml` | Simple | `substring_regex` evaluator (contains / regex / not_contains) |
| `examples/04_parameterized_matrix.yaml` | Intermediate | Full Cartesian matrix with deterministic IDs |
| `examples/05_pairwise_matrix.yaml` | Intermediate | Pairwise strategy reduces case count |
| `examples/06_custom_evaluator.yaml` | Intermediate | References a drop-in plugin from `tests/evaluators/` |
| `examples/07_dataset_driven.yaml` | Intermediate | CSV dataset injects rows as parameterized inputs |
| `examples/08_inline_dataset.yaml` | Intermediate | `inline_data` rows defined directly in the config |
| `examples/09_multi_suite_with_overrides.yaml` | Advanced | Suite + defaults + test layers with merge semantics |
| `examples/10_llm_judge_stub.yaml` | Advanced | LLM-judge in stub mode (CI-safe, no model call) |

All examples validate against the schema and run in dry-run mode without
Ollama. See `getting-started.md` for the exact commands.

## Quick start

```bash
# List models discovered from Ollama (no benchmark run)
uv run python -m model_benchmark.cli models

# Validate all example configs
uv run python -m model_benchmark.cli validate model_benchmark/docs/examples/

# List discovered tests
uv run python -m model_benchmark.cli list --config-dir model_benchmark/docs/examples/

# Dry-run the benchmark (scores fixtures, no model call)
uv run python -m model_benchmark.cli run --dry-run --config-dir model_benchmark/docs/examples/

# Debug mode: show resolved config + matrix expansion + model I/O
uv run python -m model_benchmark.cli run --debug --dry-run --config-dir model_benchmark/docs/examples/
```

### Progress bar

In a real terminal, an animated progress bar with ANSI colors appears
automatically on stderr. Use `--verbose` for model/variant/direction detail,
`--quiet` to suppress. Falls back to line-per-update in non-TTY environments.

### Getting the HTML report

Both legacy and subcommand `run` modes produce the same set of output files,
including the interactive HTML report (`report_internal.html`):

```bash
# Subcommand mode
uv run python -m model_benchmark.cli run --dry-run --config-dir model_benchmark/docs/examples/

# Legacy mode
uv run python -m model_benchmark.cli --dry-run
```

Then open `benchmark_outputs/<run-dir>/report_internal.html` in a browser.
Both modes also write `results_anonymized.json`, `run_manifest.json`, and
`summary_internal.md`.

## Related files

| File | Purpose |
|------|---------|
| `model_benchmark/config_schema.py` | Canonical pydantic v2 schema (source of truth) |
| `model_benchmark/config_loader.py` | Discovery, validation, merge resolution |
| `model_benchmark/test_selection.py` | Selection expressions + matrix expansion |
| `model_benchmark/cli.py` | Subcommand CLI (`init`, `new`, `validate`, `list`, `run`) |
| `model_benchmark/evaluators/` | Evaluator plugin package (base, registry, builtins) |
| `model_benchmark/dataset_loader.py` | Dataset loader (CSV, JSONL, JSON, HuggingFace, inline) |
| `model_benchmark/tests/DESIGN_NOTE.md` | Merge semantics + versioning policy |
| `model_benchmark/tests/PLUGIN_GUIDE.md` | Plugin authoring (condensed) |
| `model_benchmark/tests/schemas/test_config.schema.json` | JSON Schema export for IDE autocompletion |

## Conventions

- **YAML** for test definitions (pyyaml is already a dependency). JSON is also
  accepted but YAML is the convention.
- **One logical test per file** under `tests/cases/`. Suites reference tests by
  ID and live under `tests/suites/`.
- **Use `uv run python -m model_benchmark.cli`** for all CLI invocations — it
  activates the project venv automatically.
- **SugarCube-specific scoring** is isolated in `scoring.py` and referenced via
  `scoring_categories`, not hard-coded in the generic schema. This keeps the
  test framework extractable for other projects.
