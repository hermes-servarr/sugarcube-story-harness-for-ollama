# Config Reference

This document is the complete reference for every field in the declarative
test configuration schema (v1.0.0). The canonical source of truth is the
pydantic v2 model in `model_benchmark/config_schema.py`. A JSON Schema export
for IDE autocompletion lives at
`model_benchmark/tests/schemas/test_config.schema.json`.

---

## Document kinds

Every config file is one of three document kinds, discriminated by the
`kind` field (or auto-detected by the presence of `defaults`/`tests`/`id`):

| Kind | Model | Required fields | Where it lives |
|------|-------|----------------|----------------|
| `defaults` | `DefaultsDocument` | `defaults` | `tests/defaults.yaml` (global) |
| `suite` | `SuiteDocument` | `name`, `tests` | `tests/suites/<name>.yaml` |
| `test` | `TestDocument` | `id` | `tests/cases/<id>.yaml` |

A single YAML file may contain multiple documents (separated by `---`),
which is how the reference example (`full_feature_example.yaml`) demonstrates
all three kinds in one file. In practice, each kind usually lives in its own
file.

## Config hierarchy

Layers merge from lowest to highest precedence:

```
built-in defaults → global defaults → suite defaults → individual test → CLI overrides
```

- **Built-in defaults** (`BUILTIN_DEFAULTS` in `config_schema.py`): enabled
  = true, difficulty = medium, repetitions = 1, exact_match evaluator,
  temperature 0.2, num_predict 640.
- **Global defaults** (`kind: defaults`): `tests/defaults.yaml`.
- **Suite defaults** (`kind: suite`, `defaults:` field): per-suite overrides.
- **Individual test** (`kind: test`): the test's own fields.
- **CLI overrides**: `--timeout`, `--models`, `--variants`, etc.

Unset fields (`None`) inherit from the layer below. To explicitly clear a
field, use a falsy sentinel (`""`, `0`, `false`, `[]`).

See `model_benchmark/tests/DESIGN_NOTE.md` for the full merge semantics.

---

## Top-level fields (all document kinds)

### `schema_version`
- **Type:** `str` (semver)
- **Default:** `"1.0.0"`
- **Required:** Yes (on every document)
- **Constraint:** Must be in `SUPPORTED_SCHEMA_VERSIONS` = `("1.0.0",)`
- **Example:** `schema_version: "1.0.0"`
- **On error:** Refuses the document with a migration hint.

### `kind`
- **Type:** `Literal["defaults", "suite", "test"]`
- **Default:** auto-detected (see below)
- **Example:** `kind: test`
- **Auto-detection:** If absent, the loader infers: `defaults` if `defaults`
  key is present; `suite` if `tests` key is present; `test` if `id` is
  present; error if ambiguous.

### `merge` (MergePolicy)
- **Type:** `MergePolicy` object (optional)
- **Applies to:** all document kinds
- **Default:** `list_strategy: "replace"`, no field overrides
- **Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `list_strategy` | `Literal["replace", "append"]` | `"replace"` | Default merge strategy for all list fields |
| `field_overrides` | `dict[str, Literal["replace", "append"]]` | `{}` | Per-field override (e.g. `{tags: append}`) |

**Special case:** `tags` always union (deduplicated) regardless of policy.

**Example:**
```yaml
merge:
  list_strategy: replace
  field_overrides:
    tags: append
    dependencies: append
```

---

## `defaults` / test fields (TestConfig)

These fields appear under `defaults:` in a `defaults` or `suite` document,
and at the top level in a `test` document. Every field is optional in the
`defaults`/`suite` context; `id` is required for `kind: test`.

### Identity & classification

#### `id`
- **Type:** `str`
- **Required:** Yes for `kind: test`; absent for `defaults`
- **Description:** Stable unique test identifier.
- **Example:** `id: sugarcube_markup_001`
- **Constraint:** Must be unique across all loaded test documents. Duplicate
  IDs produce a validation error.

#### `name`
- **Type:** `Optional[str]`
- **Default:** `None`
- **Description:** Human-readable test name.
- **Example:** `name: Basic SugarCube markup compliance`

#### `description`
- **Type:** `Optional[str]`
- **Default:** `None`
- **Example:** `description: >` (YAML block scalar)

#### `version`
- **Type:** `Optional[str]` (semver)
- **Default:** `None`
- **Description:** Test definition version (independent from schema version).
- **Example:** `version: "1.0.0"`

#### `enabled`
- **Type:** `Optional[bool]`
- **Default:** `None` (treated as `True` by the selector)
- **Description:** Set to `false` to disable a test without deleting it.
  Disabled tests are filtered out unless `--include-disabled` is passed.

### Taxonomy

#### `capability`
- **Type:** `Optional[str]`
- **Default:** `None`
- **Description:** Broad capability area (e.g. `sugarcube_compliance`,
  `reasoning`, `tool_use`).
- **Selectable:** `--select "capability:sugarcube_compliance"`

#### `category`
- **Type:** `Optional[str]`
- **Default:** `None`
- **Description:** Scoring category. For SugarCube tests, one of the 6
  canonical categories (see `scoring_categories` below).

#### `subcategory`
- **Type:** `Optional[str]`
- **Default:** `None`
- **Example:** `subcategory: nesting`

#### `difficulty`
- **Type:** `Literal["easy", "medium", "hard", "expert"]`
- **Default:** `"medium"` (from built-in defaults)
- **Selectable:** `--select "difficulty:hard"` (exact match, not glob)

#### `tags`
- **Type:** `list[str]`
- **Default:** `[]`
- **Merge:** Always union (deduplicated), regardless of `MergePolicy`.
- **Selectable:** `--select "tag:smoke"` (glob match against any tag,
  including inherited suite tags)
- **Example:** `tags: ["smoke", "regression", "matrix"]`

### Prompt / input

#### `input`
- **Type:** `Optional[str]`
- **Default:** `None`
- **Description:** Inline input/prompt text sent to the model. Use a YAML
  block scalar (`|`) for multi-line prompts.
- **Example:**
  ```yaml
  input: |
    Generate a SugarCube passage where the player examines an object.
    Output the PROSE, CHOICES, and SUMMARY sections.
  ```

#### `system_instructions`
- **Type:** `Optional[str]`
- **Default:** `None`
- **Description:** System prompt prepended to the model call.

#### `prompt_template` (PromptTemplate)
- **Type:** `Optional[PromptTemplate]`
- **Default:** `None`
- **Constraint:** Exactly one of `ref`, `text`, or `variant` must be set.
- **Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `ref` | `Optional[str]` | `None` | Path to a template file (relative to `tests/prompts/`) |
| `variant` | `Optional[Literal["compact", "full", "json"]]` | `None` | Built-in harness prompt variant |
| `text` | `Optional[str]` | `None` | Inline template text |
| `version` | `Optional[int]` | `None` | Template version for traceability |
| `input_variables` | `dict[str, Any]` | `{}` | Variables injected into the template |

**Example:**
```yaml
prompt_template:
  variant: full
  input_variables:
    direction: "Examine object and set a variable"
```

#### `input_variables`
- **Type:** `dict[str, Any]`
- **Default:** `{}`
- **Description:** Variables injected into the prompt template. Also used
  by the matrix expansion to inject unknown dimension values (see
  [Matrices](#matrices) below).

### Expected behavior

#### `expected` (ExpectedBehavior)
- **Type:** `Optional[ExpectedBehavior]`
- **Default:** `None`
- **Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `answer` | `Optional[str]` | `None` | Reference / gold answer |
| `answer_type` | `Optional[Literal["exact", "numeric", "multiple_choice", "structured", "free_text"]]` | `None` | Answer type hint |
| `answer_choices` | `Optional[list[str]]` | `None` | Choices for `multiple_choice` |
| `numeric_tolerance` | `Optional[float]` | `None` | Tolerance for numeric answers (>= 0) |
| `behavior` | `Optional[list[str]]` | `None` | Behavioral descriptors the model should exhibit |
| `rubric` | `Optional[list[dict[str, Any]]]` | `None` | Scoring rubric items `[{criterion, weight, description}]` |
| `constraints` | `Optional[list[str]]` | `None` | Constraints the answer must satisfy |
| `contains` | `Optional[list[str]]` | `None` | Substrings the output MUST contain |
| `not_contains` | `Optional[list[str]]` | `None` | Substrings the output must NOT contain |
| `regex` | `Optional[list[str]]` | `None` | Regex patterns the output MUST match |
| `must_parse_as` | `Optional[Literal["json", "yaml", "csv", "sugarcube_passage"]]` | `None` | Format the output must parse as |

Which fields the evaluator uses depends on the evaluator type. For
example, `exact_match` uses `answer`; `substring_regex` uses `contains`,
`not_contains`, and `regex`.

### Evaluation

#### `evaluation` (EvaluatorReference)
- **Type:** `Optional[EvaluatorReference]`
- **Default:** `name="exact_match", pass_threshold=1.0, max_score=1.0` (from built-in defaults)
- **Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | (required) | Evaluator plugin name (registry key) |
| `type` | `Optional[str]` | `None` | Evaluator category (`exact_match`, `regex`, `llm_judge`, etc.) |
| `version` | `Optional[str]` | `None` | Evaluator version for traceability |
| `params` | `dict[str, Any]` | `{}` | Evaluator-specific parameters (passed to `__init__`) |
| `prompt` | `Optional[str]` | `None` | Evaluator prompt (inline text or template ref) |
| `prompt_template_ref` | `Optional[str]` | `None` | Reference to a prompt template file |
| `pass_threshold` | `float` | `1.0` | Minimum `normalized_score` to pass (range [0, 1]) |
| `max_score` | `float` | `1.0` | Maximum raw score (must be > 0) |
| `deterministic` | `Optional[bool]` | `None` | Whether the evaluator is deterministic |

**Built-in evaluators:**

| Name | Params | Deterministic | Uses expected fields |
|------|--------|---------------|----------------------|
| `exact_match` | `case_sensitive` (bool, default false), `strip_whitespace` (bool, default true), `trim_response` (bool, default true) | Yes | `answer` |
| `substring_regex` | `case_sensitive` (bool, default true), `mode` (`"all"` or `"any"`, default `"all"`) | Yes | `contains`, `not_contains`, `regex` |
| `llm_judge` | `mode` (`"stub"` or `"api"`, default `"stub"`), `model` (str), `base_url` (str), `temperature` (float), `prompt_template` (str), `fallback_score` (float) | No | `answer`, `behavior`, `rubric` |

**Example:**
```yaml
evaluation:
  name: substring_regex
  type: regex
  params:
    case_sensitive: false
    mode: all
  pass_threshold: 1.0
  max_score: 1.0
```

See [plugin-authoring.md](plugin-authoring.md) for writing custom evaluators.

### Dataset

#### `dataset` (DatasetReference)
- **Type:** `Optional[DatasetReference]`
- **Default:** `None`
- **Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | (required) | Stable dataset identifier |
| `version` | `Optional[str]` | `None` | Dataset version tag |
| `split` | `Optional[str]` | `None` | Train/val/test split name |
| `path` | `Optional[str]` | `None` | Local file path (portable, relative to `tests/`) |
| `format` | `Literal["csv", "jsonl", "json", "huggingface", "inline"]` | `"jsonl"` | Source format |
| `huggingface_id` | `Optional[str]` | `None` | HF dataset repo ID (required if format=huggingface) |
| `filters` | `Optional[dict[str, Any]]` | `None` | Row filters (column → value or value-list) |
| `sample` | `Optional[int]` | `None` | Random sample N rows (>= 1) |
| `seed` | `Optional[int]` | `None` | Seed for sampling (>= 0) |
| `checksum` | `Optional[str]` | `None` | Content checksum (sha256) |
| `inline_data` | `Optional[list[dict[str, Any]]]` | `None` | Inline rows (required if format=inline) |

**Cross-field constraints:**
- `format="huggingface"` requires `huggingface_id`
- `format="inline"` requires `inline_data`
- Other formats require `path`

See [dataset-guide.md](dataset-guide.md) for format details and examples.

### Model parameters

#### `model_parameters` (ModelParameters)
- **Type:** `Optional[ModelParameters]`
- **Default:** `base_url="http://localhost:11434", timeout=120, num_predict=640, temperature=0.2` (from built-in defaults)
- **Fields:**

| Field | Type | Default | Constraint | Description |
|-------|------|---------|-----------|-------------|
| `base_url` | `str` | `"http://localhost:11434"` | — | Ollama API base URL |
| `timeout` | `int` | `120` | > 0 | Seconds per model call |
| `num_predict` | `int` | `640` | > 0 | Max tokens to generate |
| `temperature` | `float` | `0.2` | [0.0, 2.0] | Sampling temperature |
| `top_p` | `Optional[float]` | `None` | [0.0, 1.0] | Nucleus sampling |
| `top_k` | `Optional[int]` | `None` | >= 0 | Top-k sampling |
| `seed` | `Optional[int]` | `None` | >= 0 | Deterministic generation seed |
| `stop` | `Optional[list[str]]` | `None` | — | Stop sequences |
| `repeat_penalty` | `Optional[float]` | `None` | >= 0.0 | Repetition penalty |

### Scoring

#### `scoring_categories`
- **Type:** `Optional[list[ScoringCategory]]`
- **Default:** `None` (all 6 categories scored)
- **Description:** Which of the 6 SugarCube scoring categories to apply.
- **Allowed values:** `markup_compliance`, `variable_scoping`,
  `passage_structure`, `macro_usage`, `naked_interpolation`,
  `link_setter_syntax`
- **Example:**
  ```yaml
  scoring_categories:
    - markup_compliance
    - passage_structure
  ```

### Execution

#### `timeout`
- **Type:** `Optional[int]`
- **Default:** `None` (uses `model_parameters.timeout`)
- **Constraint:** > 0
- **Description:** Seconds per model call. Overrides
  `model_parameters.timeout` when set.

#### `retry_policy` (RetryPolicy)
- **Type:** `Optional[RetryPolicy]`
- **Default:** `None` (no retries)
- **Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_retries` | `int` | `0` | Max retry attempts (>= 0) |
| `backoff` | `Literal["fixed", "linear", "exponential"]` | `"exponential"` | Backoff strategy |
| `initial_delay` | `float` | `1.0` | Initial delay in seconds (> 0) |
| `max_delay` | `float` | `60.0` | Maximum delay cap (> 0) |
| `retry_on` | `list[str]` | `["timeout", "network_error", "rate_limit"]` | Error categories that trigger a retry |

#### `max_input_tokens`
- **Type:** `Optional[int]`
- **Default:** `None`
- **Constraint:** > 0

#### `max_output_tokens`
- **Type:** `Optional[int]`
- **Default:** `None`
- **Constraint:** > 0

#### `random_seed`
- **Type:** `Optional[int]`
- **Default:** `None`
- **Constraint:** >= 0
- **Description:** Seed for deterministic generation. Also used for matrix
  `sample` strategy when `matrix.seed` is not set.

#### `repetitions`
- **Type:** `Optional[int]`
- **Default:** `1` (from built-in defaults)
- **Constraint:** >= 1
- **Description:** Number of repeated runs per case for variance analysis.

### Model eligibility

#### `model_eligibility` (ModelEligibility)
- **Type:** `Optional[ModelEligibility]`
- **Default:** `None`
- **Constraint:** `required` and `excluded` must not overlap.
- **Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `required` | `Optional[list[str]]` | `None` | Model tags that CAN run this test (allowlist) |
| `excluded` | `Optional[list[str]]` | `None` | Model tags that CANNOT run (denylist) |
| `min_context_length` | `Optional[int]` | `None` | Minimum context length (> 0) |
| `min_parameters` | `Optional[int]` | `None` | Minimum parameter count (> 0, e.g. `7000000000`) |
| `required_capabilities` | `Optional[list[str]]` | `None` | Required capabilities (e.g. `["tool_use", "vision"]`) |

#### `required_tools`
- **Type:** `list[str]`
- **Default:** `[]`
- **Description:** Tools the test requires (e.g. `["calculator", "code_execution"]`).

### Dependencies

#### `dependencies`
- **Type:** `list[str]`
- **Default:** `[]`
- **Merge:** `replace` by default; set `field_overrides: {dependencies: append}` to accumulate.
- **Description:** Prerequisite test IDs that must pass before this test runs.
- **Example:** `dependencies: ["sugarcube_markup_001"]`

#### `skip_conditions`
- **Type:** `Optional[list[str]]`
- **Default:** `None`
- **Description:** Conditions under which to skip this test (e.g.
  `["ollama_unreachable", "model_not_in_required_list"]`).

#### `expected_failure`
- **Type:** `Optional[bool]`
- **Default:** `None`
- **Description:** If `true`, a `FAIL` is the expected outcome (negative
  test). Used to validate that a test correctly catches model errors.

### Matrices

#### `parameters`
- **Type:** `Optional[dict[str, list[Any]]]`
- **Default:** `None`
- **Description:** Matrix dimensions: dimension name → list of values. The
  matrix expansion generates one concrete test instance per combination
  (per the strategy in `matrix`).
- **Example:**
  ```yaml
  parameters:
    variant: ["compact", "full", "json"]
    direction: ["A", "B", "C"]
  ```

#### `matrix` (MatrixConfig)
- **Type:** `Optional[MatrixConfig]`
- **Default:** `None` (if `parameters` is set without `matrix`, defaults to
  `strategy: full`)
- **Constraint:** `matrix` requires `parameters` to be set. `strategy:
  explicit` requires `explicit_combinations`. `strategy: sample` requires
  `sample_size`.
- **Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `strategy` | `Literal["full", "pairwise", "explicit", "sample"]` | `"full"` | Combination strategy |
| `max_cases` | `Optional[int]` | `None` | Hard cap on generated cases (> 0) |
| `sample_size` | `Optional[int]` | `None` | N for `sample` strategy (> 0) |
| `explicit_combinations` | `Optional[list[dict[str, Any]]]` | `None` | Explicit combos for `explicit` strategy |
| `seed` | `Optional[int]` | `None` | Seed for `sample` strategy (>= 0) |

**Strategies:**

| Strategy | Description | Example |
|----------|-------------|---------|
| `full` | Cartesian product of all dimensions | 3 variants × 3 directions = 9 cases |
| `pairwise` | All-pairs combination (greedy); reduces case count for 3+ dimensions | 3 dims × 3 vals → ~9 cases (not 27) |
| `explicit` | Only the combos listed in `explicit_combinations` | hand-picked cases |
| `sample` | Random sample of `sample_size` cases from the full product | 5 of 27 |

**Generated instance IDs** are deterministic:
`<test_id>__<dim1>-<val1>__<dim2>-<val2>` (dimensions sorted
alphabetically). Example: `my_test__direction-A__variant-compact`.

**Parameter application rules** (how dimension values map to config fields):

| Dimension name | Applied to |
|----------------|-----------|
| `difficulty`, `timeout`, `repetitions`, `random_seed`, `max_input_tokens`, `max_output_tokens`, `priority` | Direct TestConfig scalar field override |
| `variant` | `prompt_template.variant` |
| `temperature` | `model_parameters.temperature` |
| `num_predict` | `model_parameters.num_predict` |
| `top_p` | `model_parameters.top_p` |
| `top_k` | `model_parameters.top_k` |
| `seed` | `model_parameters.seed` |
| Any other name | `input_variables[dim_name]` |

### Selection priority

#### `priority`
- **Type:** `Optional[int]`
- **Default:** `None` (treated as lowest priority)
- **Constraint:** >= 0
- **Description:** Selection priority. Lower value = higher priority. Used
  by the test selector to order and truncate the selected set when
  `--max-selected` is set. Tests with unset priority sort last.
- **Example:** `priority: 1` (runs before `priority: 5`)

### Metadata

#### `metadata` (TestMetadata)
- **Type:** `Optional[TestMetadata]`
- **Default:** `None`
- **Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `owner` | `Optional[str]` | `None` | Test owner |
| `source` | `Optional[str]` | `None` | Source file / origin |
| `created` | `Optional[str]` | `None` | ISO-8601 creation timestamp |
| `modified` | `Optional[str]` | `None` | ISO-8601 last-modified timestamp |
| `deprecated` | `bool` | `False` | Deprecation flag |
| `deprecation_message` | `Optional[str]` | `None` | Deprecation explanation |
| `notes` | `Optional[str]` | `None` | Free-form notes |

---

## Suite-only fields

These fields appear only in `kind: suite` documents.

### `name`
- **Type:** `str`
- **Required:** Yes
- **Description:** Unique suite name. Used for `--select "suite:<name>"`.

### `tests`
- **Type:** `list[Union[str, TestConfig]]`
- **Required:** Yes (min length 1)
- **Description:** Test entries. Each entry is either:
  - A **string** referencing a test ID (the loader finds the file
    containing that ID in `cases/`), or
  - An **inline TestConfig** (a full test definition embedded in the
    suite).
- **Example:**
  ```yaml
  tests:
    - sugarcube_markup_001           # reference by ID
    - id: inline_test                # inline definition
      name: Inline test
      input: "..."
      expected:
        answer: "..."
  ```

### `tags` (suite-level)
- **Type:** `list[str]`
- **Default:** `[]`
- **Description:** Suite-level tags inherited by all member tests. These
  union with the test's own tags and global tags.

### `defaults` (suite-level)
- **Type:** `Optional[TestConfig]`
- **Default:** `None`
- **Description:** Suite-level overrides applied to all tests in the suite.
  Merges between global defaults and individual test config.

---

## Defaults-only fields

### `defaults`
- **Type:** `TestConfig`
- **Required:** Yes
- **Description:** Default values applied to all tests. Every field is
  optional; unset fields fall back to built-in defaults.

---

## Selection expressions

The `--select` and `--exclude` flags accept boolean selection expressions.

### Fields

| Field | Match type | Example |
|-------|-----------|---------|
| `tag` | Glob (matches any tag, including inherited suite tags) | `tag:smoke`, `tag:regression*` |
| `name` | Glob | `name:story_*` |
| `id` | Glob | `id:arithmetic_001` |
| `capability` | Glob | `capability:reasoning` |
| `category` | Glob | `category:arithmetic` |
| `subcategory` | Glob | `subcategory:nesting` |
| `difficulty` | Exact (enum) | `difficulty:hard` |
| `suite` | Glob | `suite:core` |
| `enabled` | Boolean | `enabled:true`, `enabled:false` |

### Operators

| Operator | Example | Description |
|----------|---------|-------------|
| `AND` (explicit) | `tag:smoke AND tag:fast` | Both must match |
| `AND` (implicit) | `tag:smoke tag:fast` | Adjacent atoms = AND |
| `OR` | `tag:smoke OR tag:fast` | Either matches |
| `NOT` | `NOT tag:slow` | Negation |
| Parentheses | `(tag:smoke OR tag:fast) AND NOT difficulty:expert` | Grouping |

### Precedence

`NOT` > `AND` > `OR`

### Quoted values

Values with spaces can be quoted: `name:"my test name"`

### Multiple flags

- Multiple `--select` flags: ALL must match (AND across flags).
- Multiple `--exclude` flags: ANY match removes (OR across flags).

---

## CLI flags (run subcommand)

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--select` | append (str) | `[]` | Include expression (repeatable) |
| `--exclude` | append (str) | `[]` | Exclude expression (repeatable) |
| `--max-selected` | int | `None` | Truncate to N tests (highest priority first) |
| `--include-disabled` | flag | `False` | Include tests with `enabled: false` |
| `--config-dir` | append (str) | `[]` | Additional config search directory (repeatable) |
| `--dry-run` | flag | `False` | Score fixtures without calling Ollama |
| `--plan-only` | flag | `False` | Show selection + matrix plan without executing |
| `--output-format` | `text`/`json`/`markdown` | `text` | Report format |
| `--output-dir` | str | `benchmark_outputs` | Directory for run outputs |
| `--models` | nargs (str) | `[]` | Model tags to test (empty=auto-discover) |
| `--variants` | nargs (`compact`/`full`/`json`) | all 3 | Prompt variants |
| `--directions` | nargs (`A`/`B`/`C`) | all 3 | Directions |
| `--runs` | int | `1` | N runs per model×variant×direction |
| `--debug` | flag | `False` | Verbose: resolved config + matrix + model I/O |
| `--quiet` | flag | `False` | Suppress progress output |
| `--verbose` | flag | `False` | Detailed per-case progress to stderr |
