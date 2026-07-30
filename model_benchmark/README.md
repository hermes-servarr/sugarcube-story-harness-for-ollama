# SugarCube Model Benchmark

Tests how well LLM models follow SugarCube markup conventions when generating story passages.

Sends controlled prompts (built from the real `harness/prompts.py` templates with fixed context) to one or more Ollama models, scores each response across 6 compliance categories, and emits a per-model report.

## Quick Start

This project uses [uv](https://docs.astral.sh/uv/) for dependency management. All commands below use `uv run` which automatically handles the venv and dependencies.

### Dry run (no Ollama needed)

```bash
uv run python -m model_benchmark.cli --dry-run --config-dir model_benchmark/docs/examples/
```

The dry run scores a known-good fixture response. Use it to verify the scoring logic works without needing a running Ollama server. Good for CI.

### Real run (requires Ollama)

```bash
# Auto-discover all installed Ollama models
uv run python -m model_benchmark.cli

# Test specific models
uv run python -m model_benchmark.cli --models llama3.1:8b qwen2.5:7b

# Save text report to a file
uv run python -m model_benchmark.cli --models llama3.1:8b --output report.txt
```

### Rich Terminal Progress Bar

When running in a real terminal (TTY), the benchmark displays an animated
progress bar with ANSI colors. No flags needed -- it activates automatically.

```
[=====>    ] 45.0% 9/20 3:42 pass=7 fail=1 err=0 skip=0 llama3.2 v=full dir=A rep=1
```

The bar shows:
- Progress bar with `>` head
- Percentage and completed/total count
- ETA (MM:SS or H:MM:SS)
- Pass/fail/error/skip counts (green/red/yellow/dim when color is supported)
- Model alias, variant, direction, repetition (in `--verbose` mode)

Flags:
- `--verbose` -- add model/variant/direction/repetition to the bar
- `--quiet` -- suppress all progress output

Behavior by environment:
- **TTY** (interactive terminal): in-place `\r` refresh with ANSI colors
- **Pipe/CI** (non-TTY): one line per update, no colors
- `NO_COLOR` env var or `TERM=dumb`: colors disabled, bar still works

Stdlib only -- no tqdm, rich, or other external dependencies.

## Choosing Models

### Auto-discover (default)

If you don't pass `--models`, the benchmark queries `<base_url>/api/tags` on your Ollama server and tests every installed model. This is the simplest way to compare all your local models.

```bash
uv run python -m model_benchmark.cli
```

### Specific models

Pass model tags as space-separated arguments. These must match tags visible in `ollama list`:

```bash
uv run python -m model_benchmark.cli --models llama3.1:8b mistral:7b qwen2.5:14b
```

### Remote Ollama server

Point at a remote server with `--base-url`:

```bash
uv run python -m model_benchmark.cli \
  --base-url http://192.168.1.100:11434 \
  --models llama3.1:8b
```

## CLI Reference

There are two ways to invoke the CLI:

### Legacy flat-flag mode

Pass flags directly (no subcommand). This is the original interface and the
only one that generates the full HTML report:

```bash
uv run python -m model_benchmark.cli --dry-run --config-dir model_benchmark/docs/examples/
```

### Subcommand mode

Use the `run` subcommand for the newer interface with selection filters and
output-format control:

```bash
uv run python -m model_benchmark.cli run --dry-run --config-dir model_benchmark/docs/examples/
```

| Flag | Default | Description |
|------|---------|-------------|
| `--models` | (auto-discover) | Model tags to test. Empty = discover from Ollama |
| `--variants` | `compact full json` | Prompt variants to test |
| `--directions` | `A B C` | Direction prompts (A: inventory/set flag, B: conditional, C: stats) |
| `--base-url` | `http://localhost:11434` | Ollama server URL |
| `--timeout` | `120` | Seconds per model call |
| `--num-predict` | `640` | Max tokens to generate |
| `--temperature` | `0.2` | Sampling temperature |
| `--runs` | `1` | Runs per model x variant x direction |
| `--dry-run` | off | Score a fixture response, skip Ollama (CI mode) |
| `--verbose` | off | Show model/variant/direction/repetition in progress bar |
| `--quiet` | off | Suppress all progress output |
| `--output` | stdout | Text report file path (legacy mode only) |
| `--json-output` | none | JSON report file path (legacy mode only) |
| `--config-dir` | `model_benchmark/tests/` | Config search directory (can repeat) |
| `--output-dir` | `benchmark_outputs/` | Directory for run outputs |
| `--output-format` | `text` | Report format: `text`, `json`, or `markdown` (subcommand mode only) |
| `--select` | (none) | Include filter expression (can repeat, subcommand mode only) |
| `--exclude` | (none) | Exclude filter expression (can repeat, subcommand mode only) |
| `--plan-only` | off | Show selection plan without executing (subcommand mode only) |
| `--debug` | off | Show resolved config, matrix expansion, and model I/O |

## The 6 Scoring Categories

Each model response is scored across these categories. A response "passes" a category if it has no violations.

### 1. markup_compliance
Checks that SugarCube markup is used, not Markdown.

| Good (SugarCube) | Bad (Markdown) |
|---|---|
| `''bold''` | `**bold**` |
| `//italic//` | `*italic*` |
| `~~strike~~` | |
| `""highlight""` | |

Pass if: no Markdown found. Score: 2 sub-checks (no markdown, has SugarCube).

### 2. variable_scoping
Checks that `<<set>>` uses the `to` operator (not `=`), and `setup.` variables don't leak into prose.

```sugarcube
<<set $gold to 10>>      // good
<<set $gold = 10>>       // bad: uses = instead of to
setup.startingGold       // bad: setup. in prose (should be in macros only)
```

Pass if: no `=` in `<<set>>`, no `setup.` in non-macro text. Score: 3 sub-checks.

### 3. passage_structure
Checks that PROSE, CHOICES, and SUMMARY sections are present, no raw `[[links]]` or `<<macros>>` leak into choice text, and parse warnings are clean.

Pass if: all sections present, no parse warnings, no links/macros in choices. Score: 4 sub-checks.

### 4. macro_usage
Checks that `<<set>>`/`<<if>>`/`<<print>>` macros are used correctly, and container macro nesting is balanced (every `<<if>>` has a matching `<</if>>`).

```sugarcube
<<if $hasKey>>text<</if>>           // good: balanced
<<if $x>>text<<if $y>>nested<</if>> // bad: unclosed outer <<if>>
```

Pass if: no `=` in `<<set>>`, no nesting errors. Score: 3 sub-checks.

### 5. naked_interpolation
Checks that simple variables appear naked in prose (`$gold`) and `<<print>>` is reserved for complex expressions only.

```sugarcube
You have $gold coins.                    // good: simple var, naked
You have <<print $gold>> coins.           // bad: simple var wasted in print
You have <<print $player.stats.gold>> coins.  // good: complex expression in print
```

Pass if: no simple vars in `<<print>>`. Score: 2 sub-checks.

### 6. link_setter_syntax
Checks that `[[Text|Target]]` link syntax is valid and no `[[links]]` appear in choice text (the harness renders those automatically).

Pass if: all links valid, no links in choices. Score: 2 sub-checks.

## How It Works

1. **Prompt construction**: Uses the real `build_compact_passage_prompt`, `build_full_passage_prompt`, and `build_json_passage_prompt` functions from `harness/prompts.py` with fixed fixture context (same premise, story points, entities, snapshot, parent prose for every call).

2. **Direction prompts**: Each variant gets 3 direction prompts that stress different SugarCube features:
   - **A**: "The protagonist checks their inventory and sets a flag" (tests `<<set>>`)
   - **B**: "Include a conditional: if the player has met the king, reference it" (tests `<<if>>`)
   - **C**: "Show the player's gold count and a complex stat" (tests naked interpolation)

3. **Model call**: Sends the prompt to Ollama via `call_ollama_sync`. No auto-repair, no `generate_story_output` - the raw response is scored as-is.

4. **Scoring**: 6 pure scoring functions evaluate the response. Each returns a `CategoryResult` with pass/fail, a 0.0-1.0 score, details, and evidence.

5. **Report**: Aggregates per-model results into pass rates per category and an overall score. Legacy mode writes text, markdown, and HTML reports to the output directory; subcommand mode prints to stdout and persists JSONL only.

## Output Formats

### Text report (default: stdout)

Human-readable summary with per-model pass rates and category breakdown.

### JSON report (`--json-output` in legacy mode, `--output-format json` in subcommand mode)

Full structured report including:
- Per-model `ModelReport` with every run's raw response, parsed output, and category results
- `prompt_version` from the live `harness.prompts.PROMPT_VERSION` (traceability)
- Full run configuration

### HTML report (legacy mode only)

The legacy flat-flag mode generates a self-contained interactive HTML report
(`report_internal.html`) with inline CSS + vanilla JS, no external
dependencies. Features client-side full-text search, status filtering, column
sorting, and expandable per-result detail sections. Color scheme is
Okabe-Ito color-blind safe; status is always conveyed by text label + icon,
never color alone.

To get the HTML report, use the legacy mode (no subcommand):

```bash
uv run python -m model_benchmark.cli --dry-run --config-dir model_benchmark/docs/examples/
```

Then open `benchmark_outputs/<run-dir>/report_internal.html` in a browser.

### Output directory

All runs persist results to a timestamped directory under `--output-dir`
(default: `benchmark_outputs/`):

```
benchmark_outputs/
  <timestamp>_<run-id>/
    results_internal.jsonl     # machine-readable results (all modes)
    run_manifest.json           # reproducibility metadata (legacy mode)
    summary_internal.md        # markdown report (legacy mode)
    report_internal.html        # self-contained HTML report (legacy mode)
    results_anonymized.json     # anonymized results (legacy mode + --anonymize)
    checkpoint.json             # checkpoint state for resume
```

This directory is gitignored. Run outputs are ephemeral and not committed.

| Mode | Files written |
|------|---------------|
| Legacy flat-flag | `results_internal.jsonl`, `run_manifest.json`, `summary_internal.md`, `report_internal.html` |
| Subcommand `run` | `results_internal.jsonl` only |

If you need the HTML report from subcommand mode, use the legacy mode instead,
or copy the results JSONL and generate the report manually.

## Running the Tests

```bash
# All benchmark tests (774 tests: scoring, runner, config, reports, HTML, progress bar)
uv run python -m pytest model_benchmark/tests/ tests/test_compiled_html_validation.py -v

# Specific test modules
uv run python -m pytest model_benchmark/tests/test_render_progress.py -v   # progress bar
uv run python -m pytest model_benchmark/tests/test_scoring.py -v            # scoring
uv run python -m pytest model_benchmark/tests/test_config_loader.py -v      # config
```

Tests cover:
- All 6 scoring categories (good/bad/empty/garbage inputs)
- Scoring orchestrator (category count, order, pass logic)
- Prompt fixture factory (all variants, all directions)
- Report assembly (text, markdown, HTML generation)
- Dry run integration
- Graceful failure on malformed input
- Config discovery, merge, and validation
- HTML report generation and accessibility
- Progress bar rendering (purity, color gating, width clamping, TTY vs pipe)
- Compiled HTML story validation

## File Structure

```
model_benchmark/
  __init__.py             # Package marker
  benchmark.py            # Original benchmark implementation (scoring, CLI)
  cli.py                  # Subcommand CLI (init, new, validate, list, run) + legacy mode
  runner.py               # Benchmark execution loop + progress bar + checkpoint/resume
  scoring.py              # 6 SugarCube compliance scoring functions
  schema.py               # Core data structures (ResultRecord, ProgressEvent, etc.)
  config.py               # BenchmarkConfig + CLI arg parsing
  config_schema.py        # Pydantic v2 schema (source of truth)
  config_loader.py        # Discovery, validation, merge resolution
  test_selection.py       # Selection expressions + matrix expansion
  reports.py              # Text + markdown report generators
  html_report.py          # Self-contained interactive HTML report generator
  persistence.py          # Run directory creation + JSON/JSONL/manifest writing
  metadata.py             # Reproducibility metadata collection
  anonymization.py        # Result + metadata anonymization
  comparisons.py          # Baseline comparison + regression detection
  stats.py                # Run statistics (when runs > 1)
  failures.py             # Failure classification
  fixtures.py             # Dry-run fixture responses
  dataset_loader.py       # Dataset loader (CSV, JSONL, JSON, HuggingFace, inline)
  checkpoint.py           # Checkpoint save/load for resume
  runner_selfcheck.py     # Runner self-check / sanity tests
  tests/                  # Test suite (774 tests)
  docs/                   # Contributor documentation
  docs/examples/          # Example test configs (01-10)
```

## Invariants

The benchmark enforces 10 invariants (documented in the module docstring of `benchmark.py`):

| # | Name | What it ensures |
|---|------|-----------------|
| INV-1 | Raw response, no auto-repair | Scores raw model output, never calls `generate_story_output` |
| INV-2 | Scoring purity | Scorers take only (str) or (str, ModelOutput), no I/O in bodies |
| INV-3 | Real prompt templates | Uses the actual `build_*_passage_prompt` functions, no inline prompts |
| INV-4 | PROMPT_VERSION traceability | Report includes the live `PROMPT_VERSION` from harness |
| INV-5 | No harness modification | Benchmark only imports from harness, never modifies it |
| INV-6 | Graceful failure | Empty/malformed input returns failing result, never raises |
| INV-7 | Choice text+hint scanning | Scans combined text+hint for links/macros (parser may split `[[A|B]]`) |
| INV-8 | Dry-run self-consistency | Dry-run fixture passes all 6 categories |
| INV-9 | Category count + order | Exactly 6 results in canonical order |
| INV-10 | Score range | All scores in [0.0, 1.0] |
