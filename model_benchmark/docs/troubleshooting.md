# Troubleshooting & Debug Guide

This guide covers debug mode, common errors, validation diagnostics, and
frequently asked questions.

---

## Debug mode

`--debug` is the primary tool for understanding why a test behaves
unexpectedly. It prints three sections:

1. **Resolved config after merge** — the fully-merged `TestConfig` (built-in
   → global → suite → test), so you can see which layer set each value.
2. **Matrix expansion** — the generated instance IDs and parameter values
   for each expanded case.
3. **Model I/O capture** — the raw model output, parsed output, and
   per-category scoring for each result.

### Usage

```bash
# Debug + dry-run (no model call — uses fixtures)
uv run python -m model_benchmark.cli run --debug --dry-run \
  --config-dir my_configs/ --select "id:my_test"

# Debug + full run (with model call)
uv run python -m model_benchmark.cli run --debug \
  --config-dir my_configs/ --select "id:my_test" --models llama3.1:8b

# Global --debug (also works on the legacy flat-flag flow)
uv run python -m model_benchmark.cli --debug run --dry-run --config-dir my_configs/
```

### What you see

#### 1. Resolved config

```
========================================================================
DEBUG — Resolved Config After Merge
========================================================================

── my_test ──
  suite: (standalone)
  source_files: ['/path/to/my_test.yaml']
  name: My test
  capability: sugarcube_compliance
  category: markup_compliance
  difficulty: easy
  tags: ['sugarcube', 'smoke']
  enabled: True
  repetitions: 1
  model_parameters: base_url=http://localhost:11434 timeout=120 num_predict=640 temperature=0.2
  evaluation: name=exact_match pass_threshold=1.0
  matrix expansion: (no matrix — 1 instance: my_test)

Total: 1 test(s) selected of 1 discovered.
```

This shows you exactly which values the runner will use. If a value is
wrong, check which layer set it:
- Is it a built-in default? (Check `BUILTIN_DEFAULTS` in `config_schema.py`)
- Is it from `defaults.yaml`? (Check the global defaults file)
- Is it from a suite's `defaults:` block?
- Is it from the test itself?

#### 2. Matrix expansion

For a parameterized test:

```
  ── direction_matrix ──
  parameters (matrix dims): ['direction', 'variant']
  matrix: strategy=full max_cases=100
  matrix expansion: 9 instance(s) (full product=9, truncated=False)
    → direction_matrix__direction-A__variant-compact  (direction=A, variant=compact)
    → direction_matrix__direction-A__variant-full      (direction=A, variant=full)
    → direction_matrix__direction-A__variant-json      (direction=A, variant=json)
    → direction_matrix__direction-B__variant-compact  (direction=B, variant=compact)
    ... and 5 more
```

This shows the deterministic instance IDs and the parameter values applied
to each. If you expected 9 instances but got 6, check:
- Is `matrix.strategy` set to `pairwise` (which reduces case count)?
- Is `matrix.max_cases` truncating the expansion?
- Are there duplicate combinations being deduplicated?

#### 3. Model I/O capture

```
========================================================================
DEBUG — Model I/O Capture
========================================================================

── my_test ──
  status: PASS  score: 1.0000
  model output (raw):
    PROSE: The player examines the old key...
    CHOICES: [[Examine the door]] [[Go back]]
    SUMMARY: The player found a key.
  parsed prose:
    The player examines the old key...
  category results:
    markup_compliance: PASS
    variable_scoping: PASS
    passage_structure: PASS
    macro_usage: PASS
    naked_interpolation: PASS
    link_setter_syntax: PASS
```

This shows the raw model output, the parsed prose, and the per-category
scoring. If a test FAILs, check which categories failed and compare the
raw output against the expected behavior.

---

## Plan-only mode

For a lighter-weight preview (no execution at all), use `--plan-only`:

```bash
uv run python -m model_benchmark.cli run --plan-only --config-dir my_configs/
```

This prints the selection + matrix expansion plan without calling the
runner:

```
========================================================================
DRY RUN — Test Selection & Matrix Expansion
========================================================================

Filters:
  Include: (none — all tests match)
  Exclude: (none)
  Include disabled: False

Selection:
  Discovered:  5
  Disabled:    1
  Excluded:     0
  Selected:     4

Matrix Expansion:
  Total instances: 12

  ── my_test ──
    Strategy:  (no matrix — 1 instance)
    Instance:  my_test

  ── direction_matrix ──
    Strategy:    full
    Dimensions:  direction[3], variant[3]
    Full product: 9
    Instances:   9
    → direction_matrix__direction-A__variant-compact  (direction=A, variant=compact)
    ...

========================================================================
Summary: 4 test(s) → 12 instance(s)
========================================================================
```

---

## Models score badly for reasons that are not the model

Before attributing a low score to a model or to a prompt overlay, rule out
these two run-level confounds. Neither raises an error, and neither is
currently recorded in the run manifest.

### Bare chat templates

A model imported from a GGUF with no embedded `tokenizer.chat_template` gets
Ollama's `{{ .Prompt }}` passthrough. The benchmark prompt then reaches it as
raw text with no role markers, and it will tend to *continue* the prompt
rather than follow it. The usual signature is fluent prose that ignores the
requested output structure entirely — no section headers, no required layout
blocks — while markup-level checks still pass.

Audit the roster before a comparison run:

```powershell
(Invoke-RestMethod 'http://localhost:11434/api/tags').models |
  ForEach-Object {
    $body = @{ model = $_.name } | ConvertTo-Json
    $t = (Invoke-RestMethod -Method Post -Uri 'http://localhost:11434/api/show' -Body $body -ContentType 'application/json').template
    [pscustomobject]@{ Name = $_.name; Bare = ($t.Trim() -eq '{{ .Prompt }}') }
  } | Sort-Object Bare, Name | Format-Table -AutoSize
```

This matters most across quantizations of one base model: if some quants were
imported bare and others were not, the comparison conflates quantization with
template presence. See
[docs/import-local-ollama-model.md](../../docs/import-local-ollama-model.md).

### Context-window truncation on XL cases

The capability ladder's XL cases build prompts of roughly 14,300 characters
(~3,570 tokens). With the default `--num-predict 640` a model needs about
4,200 tokens of context. A model reporting `context_length` of 4096 will
truncate on every XL case, and the resulting structural failures are
indistinguishable in the scores from genuine layout failures.

Check `context_length` before including a model in an XL comparison:

```powershell
(Invoke-RestMethod 'http://localhost:11434/api/tags').models |
  Select-Object name, @{n='ctx';e={$_.details.context_length}} |
  Sort-Object ctx
```

Approximate prompt sizes per tier: S ~1,470 tokens, M ~1,680, L ~2,180,
XL ~3,570.

---

## Common errors

### "Field required (type=missing)"

**Cause:** A required field is absent.

**Fix:** Check the error's field path (in parentheses). For `kind: test`,
`id` is required. For `kind: suite`, `name` and `tests` are required.
For `kind: defaults`, `defaults` is required.

```
INVALID — 1 error(s) in cases/my_test.yaml:
  [cases/my_test.yaml] Field required (type=missing) (id)
```

### "Unsupported schema_version"

**Cause:** The `schema_version` field is not in `SUPPORTED_SCHEMA_VERSIONS`.

**Fix:** Update it to `"1.0.0"`, or use `benchmark test migrate --from
<old> --to 1.0.0` (when migrations are available).

```
Unsupported schema_version '0.9.0'. Supported: ('1.0.0',).
Use 'benchmark test migrate --from 0.9.0 --to 1.0.0' to upgrade.
```

### "Cannot determine document kind"

**Cause:** The loader cannot auto-detect the document kind because none of
the discriminating keys (`defaults`, `tests`, `id`) are present and `kind`
is not set.

**Fix:** Add `kind: defaults|suite|test` explicitly.

### "Unknown evaluator '<name>'"

**Cause:** The evaluator name in `evaluation.name` is not registered.

**Fix:**
- Check the spelling.
- If it is a drop-in plugin, ensure the `.py` file is in
  `model_benchmark/tests/evaluators/` and does not start with `_`.
- If it is an entry point, ensure the package is installed and the entry
  point group is `model_benchmark.evaluators`.
- Run `python -c "from model_benchmark.evaluators import list_evaluators;
  print(list_evaluators())"` to see all available evaluators.

### "Suite '<name>' references unknown test id '<id>'"

**Cause:** A suite's `tests` list contains a string ID that the loader
cannot find among the standalone test documents.

**Fix:** Ensure the test file exists in `cases/` (or another scanned
directory) and its `id` field matches the reference exactly.

### "matrix config requires parameters to be set"

**Cause:** A test has a `matrix:` block but no `parameters:` block.

**Fix:** Add `parameters:` with at least one dimension, or remove the
`matrix:` block.

### "matrix.strategy='explicit' requires explicit_combinations"

**Cause:** `matrix.strategy` is `explicit` but `explicit_combinations` is
not set.

**Fix:** Add `explicit_combinations:` with a list of dicts, each mapping
dimension names to values.

### "format='huggingface' requires huggingface_id to be set"

**Cause:** `dataset.format` is `huggingface` but `huggingface_id` is
absent.

**Fix:** Add `huggingface_id: <repo_id>` (e.g. `squad`).

### "model_eligibility.required and .excluded overlap"

**Cause:** The same model tag appears in both `required` and `excluded`.

**Fix:** Remove the tag from one of the lists.

### "prompt_template requires one of: ref, text, or variant"

**Cause:** A `prompt_template` block has none of `ref`, `text`, or
`variant` set (or has both `ref` and `text`, which are mutually
exclusive).

**Fix:** Set exactly one of `ref`, `text`, or `variant`.

---

## FAQ

### How do I disable a test without deleting it?

Set `enabled: false` in the test config. The selector filters it out
unless `--include-disabled` is passed.

### How do I run only a subset of tests?

Use selection expressions with `--select` and `--exclude`:

```bash
# Only smoke tests
--select "tag:smoke"

# Exclude expert difficulty
--exclude "difficulty:expert"

# Specific test by ID
--select "id:my_test"

# Compound expression
--select "tag:regression AND NOT tag:slow"
```

### How do I see what configs the loader discovers?

```bash
uv run python -m model_benchmark.cli validate
```

This lists all discovered documents (kind, id, source path).

### How do I add a new search directory?

Use `--config-dir` (repeatable):

```bash
uv run python -m model_benchmark.cli list --config-dir path/to/configs --config-dir another/dir
```

### How do I regenerate the JSON Schema for IDE autocompletion?

```bash
uv run python -c "
from model_benchmark.config_schema import export_json_schema
import json
print(json.dumps(export_json_schema(), indent=2, default=str))
" > model_benchmark/tests/schemas/test_config.schema.json
```

### How do I run tests in CI without Ollama?

Use `--dry-run`:

```bash
uv run python -m model_benchmark.cli run --dry-run --config-dir my_configs/
```

Dry-run scores fixtures (predefined responses) without calling Ollama.
This verifies config validity and exercises the pipeline end-to-end.

### How do I run the full test suite?

```bash
uv run python -m pytest model_benchmark/ -q
```

All 698 tests should pass.

### How do I check if my custom evaluator is registered?

```python
python -c "
from model_benchmark.evaluators import list_evaluators
print(list_evaluators())
"
```

This prints all available evaluator names (built-in + plugins).

### Why is my test's `tags` different from what I specified?

`tags` always union across layers (global → suite → test). If your
`defaults.yaml` has `tags: ["sugarcube"]` and your test has `tags:
["smoke"]`, the resolved tags are `["sugarcube", "smoke"]`. This is by
design — tags are a semantic set. To see the resolved tags, use
`--debug`.

### Why does my matrix produce fewer cases than the full product?

Check the `matrix.strategy`:
- `pairwise` reduces cases for 3+ dimensions (all-pairs coverage).
- `sample` takes a random subset.
- `explicit` only includes listed combinations.
- `full` is the full Cartesian product.

Also check `matrix.max_cases` — it truncates the expansion if the
product exceeds it.

### How do I set up IDE schema validation?

Point your editor's YAML/JSON schema validator at
`model_benchmark/tests/schemas/test_config.schema.json`. For VS Code with
the YAML extension, add to `.vscode/settings.json`:

```json
{
  "yaml.schemas": {
    "model_benchmark/tests/schemas/test_config.schema.json": [
      "model_benchmark/tests/**/*.yaml",
      "model_benchmark/docs/examples/**/*.yaml"
    ]
  }
}
```
