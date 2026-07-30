# Declarative Test Configuration — Design Note (schema v1.0.0)

This note explains the merge semantics and versioning policy for the
declarative test configuration system in `model_benchmark/config_schema.py`.
It is the reference for the config loader (t_172dd683), evaluator plugins
(t_b8e82f29), and the benchmark engine.

## 1. Layered Config Hierarchy

Configuration is layered. Each layer overrides the one below it; the loader
merges layers from lowest to highest precedence:

```
  lowest precedence                              highest precedence
  ┌──────────┐   ┌──────────┐   ┌───────┐   ┌──────┐   ┌──────┐
  │ built-in  │ → │  global   │ → │ suite  │ → │ test │ → │ CLI  │
  │ defaults  │   │ defaults  │   │ defaults│   │ cfg  │   │ args │
  └──────────┘   └──────────┘   └───────┘   └──────┘   └──────┘
```

| Layer             | Document kind   | Where it lives                         |
|-------------------|-----------------|----------------------------------------|
| Built-in defaults | (hardcoded)     | `BUILTIN_DEFAULTS` in `config_schema.py` |
| Global defaults   | `kind: defaults`| `tests/defaults.yaml`                  |
| Suite defaults    | `kind: suite`   | `tests/suites/<name>.yaml` (`defaults:` field) |
| Individual test   | `kind: test`    | `tests/cases/<id>.yaml`                 |
| CLI overrides     | (runtime)       | `--timeout`, `--models`, etc.          |

A test that defines only `id`, `input`, and `expected` still resolves to a
fully-specified test because every unset field inherits from the layers below.

## 2. Merge Semantics

`deep_merge(parent, child, merge_policy)` merges `child` onto `parent`. It is
**pure** — neither input is mutated.

### Scalars (str, int, float, bool)

Child replaces parent, **unless** the child value is `None`. `None` means
"not set" — the parent value is preserved. To explicitly clear a field, set
it to an appropriate falsy sentinel (`""`, `0`, `false`, `[]`).

### Dicts

Recursive deep-merge: child keys override parent keys; new keys are added;
keys present only in the parent are inherited unchanged.

### Lists

Controlled by `MergePolicy`:

- **`replace`** (default): the child list replaces the parent list entirely.
  Use this when the child fully specifies the field (e.g., `scoring_categories`,
  `dependencies`).
- **`append`**: the child list extends (concatenates onto) the parent list.
  Use this for accumulative fields.

Per-field overrides via `merge_policy.field_overrides` take precedence over
the document-wide `list_strategy`. Example:

```yaml
merge:
  list_strategy: replace          # default for all list fields
  field_overrides:
    tags: append                  # but tags accumulate
    dependencies: append          # and so do dependencies
```

### Special case: `tags`

`tags` **always union (deduplicated)** regardless of policy. It is a semantic
set, not an ordered list. A test's tags accumulate from every layer it inherits
from: `['sugarcube']` (global) + `['core', 'regression']` (suite) +
`['matrix', 'parametrized']` (test) → `['sugarcube', 'core', 'regression',
'matrix', 'parametrized']`. Order is preserved (first occurrence wins).

### Proof

The reference example (`tests/examples/full_feature_example.yaml`) demonstrates
this: resolving `sugarcube_direction_matrix` across built-in → global → suite
→ test produces:

```
id            = sugarcube_direction_matrix
tags          = ['sugarcube', 'core', 'regression', 'matrix', 'parametrized']
temperature   = 0.0      (global 0.2 → suite 0.0; test doesn't set → kept 0.0)
num_predict   = 512      (global 640 → suite 512; test doesn't set → kept 512)
repetitions   = 5        (built-in 1 → test 5)
evaluator     = sugarcube_rubric  (built-in exact_match → test override)
scoring_cats  = [markup_compliance, passage_structure, macro_usage]  (test subset)
```

## 3. Schema Versioning

### The `schema_version` field

Every config document MUST carry a top-level `schema_version` field with a
semver string (`"1.0.0"`). The pydantic models validate this against
`SUPPORTED_SCHEMA_VERSIONS` and refuse incompatible documents with an
actionable error message:

```
Unsupported schema_version '0.9.0'. Supported: ('1.0.0',).
Use 'benchmark test migrate --from 0.9.0 --to 1.0.0' to upgrade.
```

### Semver policy

Test schemas are versioned **independently** from the benchmark implementation.
This lets the test corpus evolve without forcing a benchmark upgrade, and vice
versa. The version follows semver:

| Change type      | Bump     | Examples                                          |
|------------------|----------|---------------------------------------------------|
| Breaking         | MAJOR    | Renamed/removed field, changed merge semantics    |
| Backward-additive| MINOR    | New optional field, new enum value, new doc kind  |
| Fix/clarification| PATCH    | Doc fix, constraint relaxation, error message     |

- **MAJOR bump**: old configs MUST migrate. The loader rejects them with a
  migration hint. `benchmark test migrate --from N --to M` transforms them.
- **MINOR bump**: old configs continue to load unchanged (new fields are
  optional). No migration required.
- **PATCH bump**: no behavioral change; old configs work as-is.

### Migration path (future versions)

When schema v2.0.0 is introduced:

1. Add `"2.0.0"` to `SUPPORTED_SCHEMA_VERSIONS` (or make it a range check).
2. Add a migration function `migrate_v1_to_v2(data: dict) -> dict` that
   transforms v1 documents to v2 shape.
3. The loader detects an older `schema_version` and either:
   - Auto-migrates with a warning (if `--auto-migrate` is set), or
   - Refuses with a `benchmark test migrate --from 1 --to 2` hint.
4. Migrations are pure transforms (no execution side-effects) and recorded in
   VCS so changes are auditable.

The `parse_config_dict()` entry point is the integration point: the loader
calls it after any migration transform.

## 4. Document Kinds

Three document kinds, discriminated by the `kind` field (or auto-detected by
the presence of `defaults`/`tests`/`id`):

### `kind: defaults` — `DefaultsDocument`
Global defaults. Has a `defaults: TestConfig` block. Loaded first.

### `kind: suite` — `SuiteDocument`
A named collection. Has `defaults: TestConfig` (suite-level overrides) and
`tests: [str | TestConfig]` (ID references or inline definitions). Suite-level
`tags` are inherited by member tests.

### `kind: test` — `TestDocument`
A single test. `id` is required; all other fields optional. Flattened fields
(top-level, not nested under `defaults:`) for ergonomic YAML.

## 5. Validation Rules

Pydantic v2 models enforce:

- **Required fields**: `id` for test docs, `defaults` for defaults docs, `name`
  + `tests` for suite docs.
- **Type constraints**: `timeout > 0`, `temperature ∈ [0, 2]`,
  `pass_threshold ∈ [0, 1]`, `num_predict > 0`, etc.
- **Enum values**: `kind`, `difficulty`, `prompt_template.variant`,
  `scoring_categories` (the 6 canonical SugarCube categories), `status`, etc.
- **Cross-field constraints** (via `@model_validator`):
  - `prompt_template`: exactly one of `ref` / `text` / `variant` set.
  - `dataset`: `format='huggingface'` requires `huggingface_id`;
    `format='inline'` requires `inline_data`; others require `path`.
  - `matrix.strategy='explicit'` requires `explicit_combinations`;
    `strategy='sample'` requires `sample_size`.
  - `matrix` requires `parameters` to be set.
  - `model_eligibility.required` and `.excluded` must not overlap.

The JSON Schema export (`test_config.schema.json`) provides the same rules for
IDE autocompletion and offline validation (e.g., `jsonschema` CLI,
VS Code YAML extension with schema association).

## 6. Parameterized Matrices

A test with a `parameters` dict (dimension name → value list) and a `matrix`
config expands into concrete cases at load time:

```yaml
parameters:
  variant: ["compact", "full", "json"]   # 3 values
  direction: ["A", "B", "C"]             # 3 values
matrix:
  strategy: full                         # 3 x 3 = 9 cases
  max_cases: 100                         # safety cap
```

Strategies:
- **`full`** — Cartesian product of all dimensions.
- **`pairwise`** — pairwise (all-pairs) combination; reduces case count.
- **`explicit`** — only the combos listed in `explicit_combinations`.
- **`sample`** — random sample of `sample_size` cases from the full product.

Generated case IDs are **deterministic**: `<test_id>__<dim1>-<val1>__<dim2>-<val2>`.
This makes them traceable to the source test and stable across runs.

## 7. Relationship to the Benchmark Engine

This schema is the **input** layer. It does not modify the existing
`BenchmarkConfig` dataclass or the 6 scoring functions in `benchmark.py`.
The config loader (t_172dd683) converts resolved `TestConfig` instances into
the `BenchmarkConfig` the engine already consumes. SugarCube-specific scoring
categories are **referenced** via `scoring_categories`, not hard-coded in the
schema — this keeps the generic test framework extractable for other projects.

The result schema (from t_b3f38f49) is the **output** layer; every executed
result links back to the exact test definition (`test_id`, `test_version`) that
produced it, as required by the acceptance criteria.
