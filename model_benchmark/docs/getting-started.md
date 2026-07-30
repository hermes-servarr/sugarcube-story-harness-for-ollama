# Getting Started

This guide walks you through defining a test in YAML, running it, and
interpreting the results. By the end you will have created a test from
scratch, validated it, run it in dry-run mode, and inspected the output.

**Time:** ~5 minutes. **Prerequisites:** the repo cloned, `uv` installed,
and the Python venv set up (run `uv sync` once in the repo root).

---

## 1. Scaffold a config directory

The `init` subcommand creates a skeleton with a `defaults.yaml`, a sample
test, and a `suites/` directory:

```bash
uv run python -m model_benchmark.cli init my_configs
```

This produces:

```
my_configs/
  defaults.yaml        # global defaults (enabled, difficulty, model params, ...)
  cases/
    sample_test_001.yaml  # a minimal sample test
  suites/
    README.md           # placeholder
```

You can also create files by hand — `init` is a convenience, not a
requirement.

## 2. Write a minimal test

A test needs only three things: a unique `id`, an `input` (the prompt), and
an `expected` block (what the evaluator checks against). Everything else
falls back to built-in defaults or your `defaults.yaml`.

Create `my_configs/cases/my_first_test.yaml`:

```yaml
schema_version: "1.0.0"
kind: test

id: my_first_test
name: My first test
description: Checks that the model says "Paris" when asked about France's capital.

input: |
  What is the capital of France? Reply with just the city name.

expected:
  answer: Paris

evaluation:
  name: exact_match
  pass_threshold: 1.0
```

That is a complete, valid test. The `exact_match` evaluator compares the
model's response to `expected.answer` (case-insensitive by default,
whitespace-stripped). `pass_threshold: 1.0` means the response must match
exactly to pass.

## 3. Validate

Before running, validate the config to catch errors early:

```bash
uv run python -m model_benchmark.cli validate my_configs/cases/my_first_test.yaml
```

Output:

```
OK — my_configs/cases/my_first_test.yaml is valid.
```

If there is an error, the validator reports the file path, line number, and
field path. For example, omitting `id` produces:

```
INVALID — 1 error(s) in my_configs/cases/my_first_test.yaml:
  [my_configs/cases/my_first_test.yaml] Field required (type=missing) (id)
```

To validate an entire directory (all configs discovered recursively):

```bash
uv run python -m model_benchmark.cli validate my_configs/
```

## 4. List discovered tests

```bash
uv run python -m model_benchmark.cli list --config-dir my_configs/
```

Output:

```
Discovered: 1  Selected: 1
  ID              CATEGORY  DIFF    ENABLED  SUITE
  --------------  --------  ------  -------  -----
  my_first_test   -         medium  yes      -
```

The `--config-dir` flag adds a directory to the loader's search path. You
can repeat it to scan multiple directories. Without it, the loader scans
`model_benchmark/tests/` by default.

Use `--select` and `--exclude` to filter:

```bash
# Only tests tagged "smoke"
uv run python -m model_benchmark.cli list --config-dir my_configs/ --select "tag:smoke"

# Exclude expert-difficulty tests
uv run python -m model_benchmark.cli list --config-dir my_configs/ --exclude "difficulty:expert"
```

Selection expressions support `tag:`, `name:`, `id:`, `capability:`,
`category:`, `subcategory:`, `difficulty:`, `suite:`, `enabled:` fields,
glob patterns (`*`, `?`), and `AND`/`OR`/`NOT` with parentheses. See the
[config reference](config-reference.md#selection-expressions) for the full
syntax.

## 5. Run the test

### Dry-run (no model call)

Dry-run scores fixtures without calling Ollama. This is the fastest way to
verify your config is wired correctly:

```bash
uv run python -m model_benchmark.cli run --dry-run --config-dir my_configs/
```

The dry-run produces scored records (using fixture responses) and writes
results to a run directory under `benchmark_outputs/`.

### Plan-only (no execution at all)

To see what *would* run without executing anything:

```bash
uv run python -m model_benchmark.cli run --plan-only --config-dir my_configs/
```

This prints the selection + matrix expansion plan:

```
========================================================================
DRY RUN — Test Selection & Matrix Expansion
========================================================================

Filters:
  Include: (none — all tests match)
  Exclude: (none)
  Include disabled: False

Selection:
  Discovered:  1
  Disabled:    0
  Excluded:    0
  Selected:    1

Matrix Expansion:
  Total instances: 1

  ── my_first_test ──
    Strategy:  (no matrix — 1 instance)
    Instance:  my_first_test

========================================================================
Summary: 1 test(s) → 1 instance(s)
========================================================================
```

### Full run (calls Ollama)

For a real run, Ollama must be running at `http://localhost:11434` (or
whatever `base_url` your config specifies):

```bash
uv run python -m model_benchmark.cli run --config-dir my_configs/ \
  --models llama3.1:8b --variants compact --directions A
```

See `config-reference.md` for all `run` flags.

### Progress bar

When running in a real terminal (TTY), a pre-run summary banner and an
animated progress bar appear automatically on stderr:

```
[dry-run] benchmark run starting
[dry-run]   models: 1
[dry-run]     - (dry-run)
[dry-run]   variants: compact, full, json
[dry-run]   directions: A, B, C
[dry-run]   repetitions: 1
[dry-run]   total cases: 9
[dry-run]   mode: dry-run (no model calls)
[dry-run]   ollama: http://localhost:11434
[dry-run]   timeout: 120s  num_predict: 640  temperature: 0.2
[dry-run] starting...
```

In full-run mode, the banner shows `[generation]` and includes resumed vs new
case counts. The banner lists every discovered model (one per line), so you
can verify Ollama is reachable and the right models are loaded before the
benchmark starts.

Add `--verbose` to show model/variant/direction/repetition in the progress
bar. Use `--quiet` to suppress all progress output. In non-TTY environments
(pipes, CI), the bar falls back to one line per update without colors.

## 6. Interpret results

### Text report (default)

```
uv run python -m model_benchmark.cli run --dry-run --config-dir my_configs/ --quiet
```

The text report shows per-model summaries: overall score, scores by
category, pass/fail counts, runtime, and token usage.

### JSON output

```bash
uv run python -m model_benchmark.cli run --dry-run --config-dir my_configs/ \
  --output-format json
```

Returns a JSON array of result objects:

```json
[
  {
    "test_id": "my_first_test",
    "status": "PASS",
    "score": 1.0,
    "category": "markup_compliance",
    "error_details": ""
  }
]
```

### Markdown report

```bash
uv run python -m model_benchmark.cli run --dry-run --config-dir my_configs/ \
  --output-format markdown
```

### Result status classifications

Each result has one of these statuses:

| Status | Meaning |
|--------|---------|
| `PASS` | The response met the pass threshold |
| `FAIL` | The response scored below the pass threshold |
| `ERROR` | An infrastructure error occurred (not a model failure) |
| `SKIPPED` | The test was skipped (disabled, or a skip condition matched) |
| `INVALID` | The test definition or evaluator output was malformed |
| `TIMEOUT` | The model call exceeded the timeout |
| `CANCELLED` | The run was interrupted |

### Output directory

Results are persisted to a timestamped run directory:

```
benchmark_outputs/
  2026-07-30T120000Z_<benchmark-id>_<run-id>/
    results_internal.jsonl     # machine-readable results (all modes)
    run_manifest.json           # reproducibility metadata (legacy mode)
    summary_internal.md        # markdown report (legacy mode)
    report_internal.html        # self-contained HTML report (legacy mode)
    checkpoint.json             # checkpoint state (for resume)
```

**Which files you get depends on how you invoke the CLI:**

| Mode | Files written |
|------|---------------|
| Legacy flat-flag (`python -m model_benchmark.cli --dry-run ...`) | All files below |
| Subcommand (`python -m model_benchmark.cli run --dry-run ...`) | All files below |

Both modes produce the same output files:

```
benchmark_outputs/<run-dir>/
  results_internal.jsonl     # raw results with real model names
  results_anonymized.json     # anonymized results (when --anonymize, default)
  run_manifest.json           # reproducibility metadata
  summary_internal.md         # markdown report
  report_internal.html        # self-contained HTML report
```

To get the interactive HTML report with search, filtering, and sortable
columns, use either mode:

```bash
# Subcommand mode (with --config-dir)
uv run python -m model_benchmark.cli run --dry-run --config-dir my_configs/

# Legacy mode (defaults to model_benchmark/tests/)
uv run python -m model_benchmark.cli --dry-run
```

Then open `benchmark_outputs/<run-dir>/report_internal.html` in a browser.

The `benchmark_outputs/` directory is gitignored. Run outputs are ephemeral.

## 7. Debug mode

When a test fails and you need to understand why, use `--debug`:

```bash
uv run python -m model_benchmark.cli run --debug --dry-run \
  --config-dir my_configs/ --select "id:my_first_test"
```

Debug mode prints three sections:

1. **Resolved config after merge** — shows the fully-merged `TestConfig`
   (built-in → global → suite → test), so you can see which layer set each
   value.
2. **Matrix expansion** — shows the generated instance IDs and parameter
   values for each expanded case.
3. **Model I/O capture** — shows the raw model output, parsed output, and
   per-category scoring for each result.

See [troubleshooting.md](troubleshooting.md) for a detailed debug-mode
walkthrough.

## 8. Next steps

- **Add more tests:** copy `my_first_test.yaml`, change the `id` and
  content, validate, and run. Each test is independent.
- **Create a suite:** group tests by writing a `kind: suite` document that
  references them by ID. See
  `examples/09_multi_suite_with_overrides.yaml`.
- **Use a dataset:** reference a CSV or JSONL file so each row becomes a
  parameterized test case. See [dataset-guide.md](dataset-guide.md).
- **Write a custom evaluator:** when the built-in evaluators (exact_match,
  substring_regex, llm_judge) aren't enough, add your own. See
  [plugin-authoring.md](plugin-authoring.md).
- **Parameterize with matrices:** run one test across multiple variants,
  directions, or model settings. See
  `examples/04_parameterized_matrix.yaml`.
- **Read the full field reference:** every schema field is documented in
  [config-reference.md](config-reference.md).
