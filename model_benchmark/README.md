# SugarCube Model Benchmark

Tests how well LLM models follow SugarCube markup conventions when generating story passages.

Sends controlled prompts (built from the real `harness/prompts.py` templates with fixed context) to one or more Ollama models, scores each response across 6 compliance categories, and emits a per-model report.

## Quick Start

### Dry run (no Ollama needed)

```bash
python model_benchmark/benchmark.py --dry-run
```

Output:
```
======================================================================
SugarCube Direction-Following Benchmark Report
======================================================================
Generated: 2026-07-29T22:20:36.450149+00:00
Prompt Version: 7
Ollama Reachable: True

Model: (dry-run)
  Runs: 1/1 passed
  Overall Score: 100.0%
  Category Summary:
    markup_compliance: 1/1 (100.0%)
    variable_scoping: 1/1 (100.0%)
    passage_structure: 1/1 (100.0%)
    macro_usage: 1/1 (100.0%)
    naked_interpolation: 1/1 (100.0%)
    link_setter_syntax: 1/1 (100.0%)
```

The dry run scores a known-good fixture response. Use it to verify the scoring logic works without needing a running Ollama server. Good for CI.

### Real run (requires Ollama)

```bash
# Auto-discover all installed Ollama models
python model_benchmark/benchmark.py

# Test specific models
python model_benchmark/benchmark.py --models llama3.1:8b qwen2.5:7b

# Save reports to files
python model_benchmark/benchmark.py --models llama3.1:8b \
  --output report.txt \
  --json-output report.json
```

## Choosing Models

### Auto-discover (default)

If you don't pass `--models`, the benchmark queries `<base_url>/api/tags` on your Ollama server and tests every installed model. This is the simplest way to compare all your local models.

```bash
python model_benchmark/benchmark.py
```

### Specific models

Pass model tags as space-separated arguments. These must match tags visible in `ollama list`:

```bash
python model_benchmark/benchmark.py --models llama3.1:8b mistral:7b qwen2.5:14b
```

### Remote Ollama server

Point at a remote server with `--base-url`:

```bash
python model_benchmark/benchmark.py \
  --base-url http://192.168.1.100:11434 \
  --models llama3.1:8b
```

## CLI Reference

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
| `--output` | stdout | Text report file path |
| `--json-output` | none | JSON report file path |

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

5. **Report**: Aggregates per-model results into pass rates per category and an overall score.

## Output Formats

### Text report (default: stdout)
Human-readable summary with per-model pass rates and category breakdown.

### JSON report (`--json-output`)
Full structured report including:
- Per-model `ModelReport` with every run's raw response, parsed output, and category results
- `prompt_version` from the live `harness.prompts.PROMPT_VERSION` (traceability)
- Full run configuration

## Running the Tests

```bash
# From the repo root with the venv activated
python -m pytest model_benchmark/test_benchmark.py -v

# Or specific test classes
python -m pytest model_benchmark/test_benchmark.py::TestScoreMarkupCompliance -v
python -m pytest model_benchmark/test_benchmark.py::TestInvariants -v
```

63 tests covering:
- All 6 scoring categories (good/bad/empty/garbage inputs)
- Scoring orchestrator (category count, order, pass logic)
- Prompt fixture factory (all variants, all directions)
- Report assembly (text and JSON formatting)
- Dry run integration
- Graceful failure on malformed input
- All 10 invariants (INV-1 through INV-10)

## File Structure

```
model_benchmark/
  __init__.py          # Package marker
  benchmark.py         # Benchmark implementation (scoring, CLI, report)
  test_benchmark.py    # 63 tests including 10 invariant enforcement tests
  README.md            # This file
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
