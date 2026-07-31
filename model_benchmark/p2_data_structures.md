# Phase 2: Data Structures

**Task:** Benchmark reliability, reporting, anonymization, and review upgrade
**Repo:** /opt/data/sugarcube-story-harness-for-ollama-p5-input-macros
**Branch:** main (commit a6c7a16)
**Scope:** model_benchmark/ directory only — do not touch harness/ or scripts/
**Prior phase:** P1 approved (t_93baf33064)
**P1 artifact:** p1_research.md (proposed module layout §4.1, result schema §4.2, phase plan §6)

---

## 0. Design Principles

1. **No methods, no functions, no logic.** This artifact defines types only — field names, field types, docstrings. Any behavior belongs to P3 (interfaces) or P7 (implementation).
2. **Preserve existing structures verbatim.** The 3 type aliases + 6 frozen dataclasses + `_CATEGORY_ORDER` from the current `benchmark.py` (lines 83-179) are carried forward unchanged. They move to `scoring.py`/`schema.py` but are re-exported from `benchmark.py` (the shim) so all 63 tests keep passing.
3. **YAGNI.** Only structures justified by the 19-section upgrade spec (§1-§20) and the P1 plan are defined. No speculative future-proofing fields.
4. **Frozen dataclasses, not pydantic.** The existing benchmark uses `@dataclass(frozen=True)`. New benchmark-internal structures follow the same convention for consistency and to avoid pulling pydantic validation overhead into the scoring core. Pydantic models (`ModelOutput`, `HarnessConfig`) come from harness and are referenced, not redefined.
5. **stdlib types.** All field types use Python stdlib (`str`, `int`, `float`, `bool`, `tuple`, `dict`, `list`, `datetime`, `pathlib.Path`). No new third-party deps.
6. **Tuples over lists for frozen data.** Frozen dataclasses cannot hold mutable list defaults; tuples are used for all sequence fields (matching the existing convention: `category_results: tuple[CategoryResult, ...]`).
7. **Every new field added to an existing structure has a default** so keyword construction in the 63 existing tests stays valid (`ModelRunResult(model_name=..., ...)` with 12 fields works because new fields default).

---

## 1. Module Home (where each structure lives)

Per P1 §4.1 module layout. A structure's home module is where it is *defined*; `benchmark.py` (shim) re-exports all of them for backward compatibility.

| Structure | Home module | Re-exported from benchmark.py? | New? |
|-----------|-------------|:---:|:---:|
| `PromptVariant` (alias) | `scoring.py` | yes | no (moved) |
| `DirectionKey` (alias) | `scoring.py` | yes | no (moved) |
| `CategoryName` (alias) | `scoring.py` | yes | no (moved) |
| `_CATEGORY_ORDER` (const) | `scoring.py` | yes | no (moved) |
| `CategoryResult` | `scoring.py` | yes | no (moved) |
| `ModelRunResult` | `scoring.py` | yes | no (moved) |
| `CategorySummaryEntry` | `scoring.py` | yes | no (moved) |
| `ModelReport` | `scoring.py` | yes | no (moved) |
| `BenchmarkConfig` | `config.py` | yes | extended |
| `BenchmarkReport` | `scoring.py` | yes | no (moved) |
| `ResultStatus` (alias) | `schema.py` | no (new module) | **yes** |
| `FailureCategory` (alias) | `schema.py` | no | **yes** |
| `ResultProvenance` (alias) | `schema.py` | no | **yes** |
| `ResultRecord` | `schema.py` | no | **yes** |
| `CheckpointState` | `checkpoint.py` | no | **yes** |
| `RunManifest` | `metadata.py` | no | **yes** |
| `AnonymizationMapping` | `anonymization.py` | no | **yes** |
| `ModelAlias` (alias) | `anonymization.py` | no | **yes** |
| `ProviderAlias` (alias) | `anonymization.py` | no | **yes** |
| `ConfigAlias` (alias) | `anonymization.py` | no | **yes** |
| `ProgressEvent` | `runner.py` | no | **yes** |
| `FailureGroup` | `failures.py` | no | **yes** |
| `ComparisonResult` | `comparisons.py` | no | **yes** |
| `Regression` | `comparisons.py` | no | **yes** |
| `RunStatistics` | `stats.py` | no | **yes** |

---

## 2. Preserved / Moved Structures (unchanged definitions)

These definitions are reproduced exactly from the current `benchmark.py` lines 83-179. They move to their home module but their field names, types, and defaults do not change. Listed here so the reviewer can verify no silent modification.

### 2.1 Type Aliases (scoring.py)

```python
PromptVariant = Literal["compact", "full", "json"]

DirectionKey = Literal["A", "B", "C"]

CategoryName = Literal[
    "markup_compliance",
    "variable_scoping",
    "passage_structure",
    "macro_usage",
    "naked_interpolation",
    "link_setter_syntax",
]
```

### 2.2 Canonical Order Constant (scoring.py)

```python
# Canonical category order (INV-9). Used by score_response, build_model_report,
# and run_single_model's failing-result construction.
_CATEGORY_ORDER: tuple[CategoryName, ...] = (
    "markup_compliance",
    "variable_scoping",
    "passage_structure",
    "macro_usage",
    "naked_interpolation",
    "link_setter_syntax",
)
```

### 2.3 CategoryResult (scoring.py) — unchanged

```python
@dataclass(frozen=True)
class CategoryResult:
    """One scoring category's verdict for a single model response — 6 per run."""
    name: CategoryName
    passed: bool
    score: float
    details: str
    evidence: tuple[str, ...] = ()
```

### 2.4 ModelRunResult (scoring.py) — unchanged

```python
@dataclass(frozen=True)
class ModelRunResult:
    """One model × one variant × one direction × one run index — a single Ollama call."""
    model_name: str
    variant: PromptVariant
    direction: DirectionKey
    run_index: int
    raw_response: str
    parsed_output: ModelOutput
    category_results: tuple[CategoryResult, ...]
    overall_pass: bool
    elapsed_seconds: float = 0.0
    error: str = ""
```

> **Note (OQ-2 resolution):** `ModelRunResult` stays as the scoring core and is *not* extended with the ~30 schema fields. A new `ResultRecord` (§3.4) wraps/embeds it. This keeps the 63 tests' keyword construction valid and the scoring concerns separate. — Approved direction per P1 §5 OQ-2 (recommendation (b)).

### 2.5 CategorySummaryEntry (scoring.py) — unchanged

```python
@dataclass(frozen=True)
class CategorySummaryEntry:
    """Per-category aggregate for one model — one row of the report's category table."""
    name: CategoryName
    pass_rate: float
    total: int
    passed: int
```

### 2.6 ModelReport (scoring.py) — unchanged

```python
@dataclass(frozen=True)
class ModelReport:
    """Aggregated results for one model across all variants/directions/runs."""
    model_name: str
    runs: tuple[ModelRunResult, ...]
    category_summary: tuple[CategorySummaryEntry, ...]
    overall_score: float
    runs_total: int
    runs_passed: int
```

### 2.7 BenchmarkReport (scoring.py) — unchanged

```python
@dataclass(frozen=True)
class BenchmarkReport:
    """Top-level benchmark report — the full deliverable of one benchmark run."""
    models: tuple[ModelReport, ...]
    prompt_version: int
    config: BenchmarkConfig
    generated_at: str
    ollama_reachable: bool = True
```

---

## 3. New Structures

### 3.1 BenchmarkConfig (config.py) — EXTENDED

The existing `BenchmarkConfig` (current `benchmark.py` lines 155-168) gains new CLI fields. All new fields have defaults so existing keyword construction in tests (which omits them) keeps working.

```python
@dataclass(frozen=True)
class BenchmarkConfig:
    """Run configuration — one CLI invocation's parameters.

    Existing fields (lines 1-12 below) are unchanged from the original
    BenchmarkConfig.  New fields (13 onward) carry the upgrade's
    checkpoint/anonymization/output/verbosity/baseline settings; all
    default so legacy keyword construction stays valid.
    """
    # ── Existing fields (unchanged) ─────────────────────────────────────
    models: tuple[str, ...]
    variants: tuple[PromptVariant, ...]
    directions: tuple[DirectionKey, ...]
    base_url: str
    timeout: int
    num_predict: int
    temperature: float
    runs: int
    dry_run: bool = False
    output_path: str = ""
    json_output_path: str = ""
    # ── New fields (§3 checkpoint, §4 output dir, §2 progress) ──────────
    checkpoint_every: int = 10
    checkpoint_interval_seconds: float = 60.0
    output_dir: str = "benchmark_outputs"
    verbose: bool = False
    quiet: bool = False
    # ── New fields (§6/§7 anonymization) ────────────────────────────────
    anonymize: bool = True
    # ── New fields (§16 baselines) ─────────────────────────────────────
    baseline_dir: str = ""
    # ── New fields (§15 repeated runs / reproducibility) ────────────────
    random_seed: str = ""
    force_rerun: bool = False
```

Field-by-field rationale:

| Field | Type | Default | Spec ref | Purpose |
|-------|------|---------|----------|---------|
| `checkpoint_every` | `int` | `10` | §3 | Auto-persist after every N completed cases. |
| `checkpoint_interval_seconds` | `float` | `60.0` | §3 | Auto-persist after this many seconds elapse. |
| `output_dir` | `str` | `"benchmark_outputs"` | §4 | Root for timestamped run dirs. |
| `verbose` | `bool` | `False` | §2 | Full-detail progress output. |
| `quiet` | `bool` | `False` | §2 | Errors-only progress output. |
| `anonymize` | `bool` | `True` | §6/§7 | Produce anonymized variants alongside internal. Default True (spec wants both versions). |
| `baseline_dir` | `str` | `""` | §16 | Path to a previous run dir for comparison. Empty = no comparison. |
| `random_seed` | `str` | `""` | §5 | Seed for reproducible generation. Empty = no seeding. |
| `force_rerun` | `bool` | `False` | §3 | Re-run completed cases even if checkpoint exists. |

### 3.2 ResultStatus (schema.py) — NEW alias

```python
ResultStatus = Literal[
    "PASS",      # all scoring categories passed
    "FAIL",      # one or more scoring categories failed
    "ERROR",     # infrastructure error during generation/parse/score
    "SKIPPED",   # explicitly skipped (e.g. filtered out, precondition unmet)
    "INVALID",   # malformed/invalid test data or input
    "TIMEOUT",   # generation call exceeded timeout
    "CANCELLED", # run interrupted by user/signal before completion
]
```

Source: §2 (status classifications) + §8 (result schema `status` field).

### 3.3 FailureCategory (schema.py) — NEW alias

```python
# Benchmark failures (§10): the model's answer is wrong/incomplete/bad.
BenchmarkFailure = Literal[
    "instruction_following",
    "formatting",
    "reasoning",
    "safety",
    "hallucination",
    "refusal",
    "citation",
    "context_handling",
]

# Infrastructure failures (§10): the evaluation machinery failed.
InfrastructureFailure = Literal[
    "provider_error",
    "auth_error",
    "rate_limit",
    "timeout",
    "network",
    "evaluator_error",
    "parser_error",
    "invalid_test_data",
    "missing_artifact",
    "internal_exception",
]

FailureCategory = Literal[
    # benchmark failures
    "instruction_following",
    "formatting",
    "reasoning",
    "safety",
    "hallucination",
    "refusal",
    "citation",
    "context_handling",
    # infrastructure failures
    "provider_error",
    "auth_error",
    "rate_limit",
    "timeout",
    "network",
    "evaluator_error",
    "parser_error",
    "invalid_test_data",
    "missing_artifact",
    "internal_exception",
    # no failure (PASS / no failure recorded)
    "none",
]
```

Source: §10 (distinguish benchmark failures from infrastructure failures). The `BenchmarkFailure` and `InfrastructureFailure` sub-aliases are defined for documentation/grouping; `FailureCategory` is the union used on `ResultRecord`.

### 3.4 ResultProvenance (schema.py) — NEW alias

```python
ResultProvenance = Literal[
    "new",       # freshly computed in this run
    "resumed",   # loaded from checkpoint, not recomputed
    "retried",   # recomputed after a prior failure
    "recovered", # salvaged from a partial/interrupted state
]
```

Source: §3 ("Record whether each result was new/resumed/retried/recovered").

### 3.5 ResultRecord (schema.py) — NEW

The versioned, enriched result wrapper (§8). Per P1 §4.2 / OQ-2, this is a **separate** structure that wraps the scored `ModelRunResult` + adds the metadata fields the spec requires. It does not modify `ModelRunResult`.

```python
@dataclass(frozen=True)
class ResultRecord:
    """Versioned, enriched result for one evaluated case (§8 schema).

    Wraps the scored ModelRunResult and adds reproducibility, token, cost,
    status, failure-classification, and artifact-reference metadata.
    A converter (P3) bridges ModelRunResult -> ResultRecord so existing
    tests that build ModelRunResult directly still pass.
    """
    # ── Schema identity (§8) ─────────────────────────────────────────────
    schema_version: str
    # ── Test identity (§8) ──────────────────────────────────────────────
    test_id: str
    test_version: str
    capability: str
    category: CategoryName
    subcategory: str
    difficulty: str
    # ── Dataset / split / repetition (§8) ────────────────────────────────
    dataset: str
    split: str
    repetition: int
    # ── Input / expected (§8) ────────────────────────────────────────────
    input_summary: str
    expected_behavior: str
    reference_rubric: str
    # ── Actual output (§8) ───────────────────────────────────────────────
    actual_output_raw: str
    parsed_output: ModelOutput
    # ── Score (§8) ──────────────────────────────────────────────────────
    score: float
    max_score: float
    normalized_score: float
    pass_threshold: float
    # ── Status (§8, §2) ──────────────────────────────────────────────────
    status: ResultStatus
    failure_category: FailureCategory
    # ── Evaluator reasoning (§8) ───────────────────────────────────────
    evaluator_reasoning: str
    evaluator_confidence: float
    # ── Runtime / tokens / cost (§8) ────────────────────────────────────
    runtime_seconds: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: float
    # ── Retry / error (§8) ──────────────────────────────────────────────
    retry_count: int
    error_details: str
    # ── Aliases / versions (§8) ─────────────────────────────────────────
    model_alias: str
    config_alias: str
    prompt_version: int
    evaluator_version: str
    # ── Reproducibility (§5, §8) ─────────────────────────────────────────
    random_seed: str
    # ── Timestamps (§8) ──────────────────────────────────────────────────
    timestamp_start: str
    timestamp_end: str
    # ── Artifact / link references (§8) ─────────────────────────────────
    artifact_refs: tuple[str, ...] = ()
    parent_result_id: str = ""
    comparison_result_id: str = ""
    # ── Provenance (§3) ──────────────────────────────────────────────────
    provenance: ResultProvenance = "new"
    # ── Embedded scored core (P1 §4.2 OQ-2: wrap, not extend) ─────────────
    # The full ModelRunResult (model_name, variant, direction, run_index,
    # raw_response, parsed_output, category_results, overall_pass,
    # elapsed_seconds, error) for traceability to the scoring core.
    scored_result: ModelRunResult | None = None
```

Field-by-field rationale (mapped to spec §8):

| Field | Type | Spec §8 phrase |
|-------|------|----------------|
| `schema_version` | `str` | "result schema version" |
| `test_id` | `str` | "test ID" |
| `test_version` | `str` | "test version" |
| `capability` | `str` | "capability" |
| `category` | `CategoryName` | "category" (the 6 scoring categories) |
| `subcategory` | `str` | "subcategory" |
| `difficulty` | `str` | "difficulty" |
| `dataset` | `str` | "dataset" |
| `split` | `str` | "split" |
| `repetition` | `int` | "repetition" |
| `input_summary` | `str` | "input/task summary" |
| `expected_behavior` | `str` | "expected behavior" |
| `reference_rubric` | `str` | "reference answer/rubric" |
| `actual_output_raw` | `str` | "actual output" |
| `parsed_output` | `ModelOutput` | "parsed output" |
| `score` | `float` | "score" |
| `max_score` | `float` | "max score" |
| `normalized_score` | `float` | "normalized score" |
| `pass_threshold` | `float` | "pass threshold" |
| `status` | `ResultStatus` | "status" |
| `failure_category` | `FailureCategory` | "failure category" |
| `evaluator_reasoning` | `str` | "evaluator reasoning" |
| `evaluator_confidence` | `float` | "evaluator confidence" |
| `runtime_seconds` | `float` | "runtime" |
| `input_tokens` | `int` | "input/output/total tokens" |
| `output_tokens` | `int` | "input/output/total tokens" |
| `total_tokens` | `int` | "input/output/total tokens" |
| `cost` | `float` | "cost" |
| `retry_count` | `int` | "retry count" |
| `error_details` | `str` | "error details" |
| `model_alias` | `str` | "model alias" |
| `config_alias` | `str` | "config alias" |
| `prompt_version` | `int` | "prompt version" |
| `evaluator_version` | `str` | "evaluator version" |
| `random_seed` | `str` | "random seed" (§5) |
| `timestamp_start` | `str` | "timestamps" (start) |
| `timestamp_end` | `str` | "timestamps" (end) |
| `artifact_refs` | `tuple[str, ...]` | "artifact refs" |
| `parent_result_id` | `str` | "parent result ID" |
| `comparison_result_id` | `str` | "comparison result ID" |
| `provenance` | `ResultProvenance` | §3 "new/resumed/retried/recovered" |
| `scored_result` | `ModelRunResult \| None` | P1 §4.2 — embedded scoring core for traceability |

Defaults: only the trailing optional fields (`artifact_refs`, `parent_result_id`, `comparison_result_id`, `provenance`, `scored_result`) have defaults. Required fields (the spec §8 core) must be provided at construction. This is intentional — a `ResultRecord` with a missing `test_id` or `status` is not a valid record.

### 3.6 CheckpointState (checkpoint.py) — NEW

```python
@dataclass(frozen=True)
class CheckpointState:
    """Resumable run state — which result IDs are already finalized (§3).

    Persisted to checkpoint.json via atomic write (tmpfile + os.replace).
    On resume, completed_ids are skipped unless force_rerun is set.
    """
    run_id: str
    completed_ids: tuple[str, ...]
    total_cases: int
    last_saved_at: str
    # Per-result provenance, keyed by test_id (§3: new/resumed/retried/recovered)
    provenance: tuple[tuple[str, ResultProvenance], ...]
```

Source: §3 (fault tolerance / checkpointing). `provenance` is a tuple of (test_id, provenance) pairs because frozen dataclasses cannot hold a mutable dict default; the P3 `load_checkpoint`/`save_checkpoint` interfaces will convert to/from a dict internally.

### 3.7 RunManifest (metadata.py) — NEW

Reproducibility metadata for one run (§5). Written to `run_manifest.json` in the run dir.

```python
@dataclass(frozen=True)
class RunManifest:
    """Reproducibility metadata for one benchmark run (§5).

    Written to run_manifest.json. Contains everything needed to
    reproduce or interpret a run, with secrets redacted.
    """
    # ── Run identity ────────────────────────────────────────────────────
    run_id: str
    benchmark_name: str
    benchmark_version: str
    schema_version: str
    # ── Source / commit (§5) ────────────────────────────────────────────
    source_commit_hash: str
    # ── Model / provider (§5) ───────────────────────────────────────────
    model_names: tuple[str, ...]
    provider: str
    model_configs: tuple[dict[str, str], ...]
    generation_params: dict[str, str]
    # ── Prompt / evaluator (§5) ─────────────────────────────────────────
    prompt_template: str
    prompt_version: int
    evaluator_prompt: str
    evaluator_version: str
    # ── Dataset (§5) ────────────────────────────────────────────────────
    dataset_name: str
    dataset_version: str
    dataset_split: str
    dataset_checksums: tuple[str, ...]
    # ── Runtime settings (§5) ───────────────────────────────────────────
    runtime_settings: dict[str, str]
    concurrency: int
    retry_policy: str
    timeouts: int
    random_seed: str
    sampling_seed: str
    repeated_runs_count: int
    # ── Timestamps / duration (§5) ──────────────────────────────────────
    start_timestamp: str
    completion_timestamp: str
    duration_seconds: float
    # ── Environment (§5) ────────────────────────────────────────────────
    os_info: str
    python_version: str
    package_versions: dict[str, str]
    hardware: str
    env_vars_redacted: dict[str, str]
    cli_args: tuple[str, ...]
    config_file_contents: str
    config_file_checksum: str
    # ── Resume (§5) ─────────────────────────────────────────────────────
    resumed: bool
    parent_run_id: str
```

Source: §5 (reproducibility metadata — every field listed there). `env_vars_redacted` holds the env dict with secrets stripped (never API keys/tokens/credentials per §5). `model_configs`/`generation_params`/`runtime_settings`/`package_versions`/`env_vars_redacted` are typed `dict[str, str]` (or tuple of dicts) for frozen-compatibility; values are stringified at construction time by the P3 metadata collector.

### 3.8 AnonymizationMapping (anonymization.py) — NEW

The private mapping from aliases to originals (§7). Written to `anonymization_mapping.private.json`. Never referenced in anonymized outputs.

```python
@dataclass(frozen=True)
class AnonymizationMapping:
    """Private alias->original mapping for one run (§7).

    Stored separately in anonymization_mapping.private.json, never
    referenced in anonymized reports. Deterministic: a stable sort of
    internal names produces Model_A, Model_B, Provider_A, Config_01, Run_01.
    """
    model_aliases: tuple[tuple[ModelAlias, str], ...]   # alias -> original model name
    provider_aliases: tuple[tuple[ProviderAlias, str], ...]  # alias -> original provider
    config_aliases: tuple[tuple[ConfigAlias, str], ...]     # alias -> original config label
    run_aliases: tuple[tuple[str, str], ...]               # alias -> original run id
    # Identity strings that must be scrubbed from anonymized artifacts (§6):
    # hostnames, file paths, account ids, etc.  Each entry is replaced by its
    # mapped alias or a generic redaction token.
    identity_strings: tuple[str, ...]
```

Source: §7 (private anonymization mapping) + §6 (identity strings to remove). Tuple-of-pairs (not dict) because frozen dataclasses cannot hold a mutable dict default; P3 `build_anonymization_mapping` builds these from a stable-sorted list.

### 3.9 Alias Type Aliases (anonymization.py) — NEW

```python
ModelAlias = str
```

> Model aliases use an unbounded spreadsheet-style letter sequence: `Model_A` through `Model_Z`, followed by `Model_AA`, `Model_AB`, and so on. The scheme never switches from letters to numbers.

```python
ProviderAlias = Literal["Provider_A", "Provider_B"]
```

> Two providers (local Ollama + one remote) is the realistic max for this benchmark.

```python
ConfigAlias = str  # e.g. "Config_01", "Config_02" — format: Config_NN
```

> `ConfigAlias` is a `str` (not `Literal`) because config count is unbounded (temperature/num_predict permutations). The format `Config_NN` is a convention enforced by `build_anonymization_mapping` (P3) and checked by INV-A2 (P6), not by the type itself.

### 3.10 ProgressEvent (runner.py) — NEW

```python
@dataclass(frozen=True)
class ProgressEvent:
    """One structured progress update emitted during execution (§2).

    Consumed by the terminal renderer and optional machine-readable log.
    Fields mirror §2's progress-reporting requirements.
    """
    stage: str              # current stage: "discovery", "generation", "scoring", "reporting"
    current_test: str       # test_id of the in-progress case, "" if between cases
    completed: int          # number of cases completed so far
    total: int              # total cases in the run
    percent: float          # completed / total * 100
    elapsed_seconds: float
    eta_seconds: float      # estimated time remaining, -1.0 if unknown
    model_alias: str        # anonymized model alias for display
    config_alias: str       # config alias for display
    variant: str            # prompt variant
    direction: str          # direction key
    repetition: int         # 1-based repetition number
    # Status counts so far (§2)
    pass_count: int
    fail_count: int
    error_count: int
    skipped_count: int
    invalid_count: int
    timeout_count: int
    cancelled_count: int
```

Source: §2 (progress reporting — current test/stage, completed/total, %, elapsed, ETA, model alias, config, variant/direction/repetition, status counts).

### 3.11 FailureGroup (failures.py) — NEW

```python
@dataclass(frozen=True)
class FailureGroup:
    """One cluster of related failures for failure reporting (§10).

    Groups failures by FailureCategory. Per-group: category, affected case
    count, % of evaluated, affected capabilities/datasets, severity,
    representative examples, suggested investigation.
    """
    category: FailureCategory
    case_count: int
    percent_of_evaluated: float
    affected_capabilities: tuple[str, ...]
    affected_datasets: tuple[str, ...]
    severity: str          # "critical", "high", "medium", "low"
    representative_examples: tuple[str, ...]  # test_ids of up to N representative cases
    suggested_investigation: str
    # Whether this is a benchmark failure or infrastructure failure (§10)
    failure_class: str      # "benchmark" | "infrastructure"
```

Source: §10 (failure reporting — per-group fields). `failure_class` is the benchmark-vs-infrastructure distinction from §10. `severity` is a `str` (not `Literal`) to allow the classifier (P3) to assign graduated severity without type churn; P6 INV will check it's one of the four values.

### 3.12 ComparisonResult (comparisons.py) — NEW

```python
@dataclass(frozen=True)
class ComparisonResult:
    """Outcome of comparing a current run against a baseline run (§16)."""
    baseline_run_id: str
    current_run_id: str
    # Absolute and relative score diffs (§16)
    absolute_score_diff: float
    relative_score_diff: float
    # Changed outcomes (§16)
    newly_failing: tuple[str, ...]      # test_ids that passed in baseline, fail now
    newly_passing: tuple[str, ...]     # test_ids that failed in baseline, pass now
    # Category-level regressions (§16)
    category_regressions: tuple[str, ...]   # CategoryName values that regressed
    # Runtime / token changes (§16)
    runtime_diff: float
    token_diff: int
    # Significance (§16)
    is_statistically_significant: bool
    is_operationally_significant: bool
```

Source: §16 (baselines + comparisons + regressions — absolute/relative diff, changed pass/fail, category regressions, runtime/token changes, significance).

### 3.13 Regression (comparisons.py) — NEW

```python
@dataclass(frozen=True)
class Regression:
    """One detected regression between current and baseline runs (§16).

    A regression is a case or category whose outcome changed for the worse
    beyond a configurable threshold.
    """
    test_id: str
    category: str           # CategoryName or "overall"
    baseline_score: float
    current_score: float
    score_diff: float       # current - baseline (negative = regression)
    baseline_status: ResultStatus
    current_status: ResultStatus
    severity: str            # "statistical" | "operational" | "minor" | "version"
    threshold: float        # the configured threshold this regression exceeded
```

Source: §16 ("Distinguish statistically meaningful regressions, operationally meaningful, small numerical changes, version-difference changes, missing/failed-case changes"). `severity` is a `str` (not `Literal`) for the same reason as `FailureGroup.severity`; P6 INV checks membership.

### 3.14 RunStatistics (stats.py) — NEW

```python
@dataclass(frozen=True)
class RunStatistics:
    """Repeated-run statistics for one test/category/model (§15).

    Mean/median/stddev/min/max/CI over the per-repetition scores.
    Includes variance flags and insufficient-sample-size flags.
    """
    test_id: str
    n: int                  # number of repetitions (sample size)
    mean: float
    median: float
    stddev: float
    min: float
    max: float
    # Confidence interval (§15) — 95% CI bounds
    ci_lower: float
    ci_upper: float
    # Per-test consistency (§15): fraction of repetitions with same pass/fail outcome
    pass_rate_consistency: float
    # Flags (§15): high-variance, unstable, outcome-changing, insufficient-sample
    high_variance: bool
    unstable: bool
    outcome_changing: bool
    insufficient_sample: bool
    # Variance flags as human-readable strings (§15: "flag high-variance categories, unstable tests...")
    variance_flags: tuple[str, ...]
```

Source: §15 (repeated runs — mean/median/stddev/min/max, confidence intervals, per-test consistency, pass-rate consistency, flag high-variance, unstable, outcome-changing, insufficient sample sizes).

---

## 4. Summary: New vs Preserved

### New structures (14 total)

| # | Structure | Home module | Spec source |
|---|-----------|-------------|-------------|
| 1 | `ResultStatus` (alias) | `schema.py` | §2, §8 |
| 2 | `FailureCategory` (alias) | `schema.py` | §10 |
| 3 | `ResultProvenance` (alias) | `schema.py` | §3 |
| 4 | `ResultRecord` | `schema.py` | §8 |
| 5 | `CheckpointState` | `checkpoint.py` | §3 |
| 6 | `RunManifest` | `metadata.py` | §5 |
| 7 | `AnonymizationMapping` | `anonymization.py` | §7 |
| 8 | `ModelAlias` (alias) | `anonymization.py` | §6 |
| 9 | `ProviderAlias` (alias) | `anonymization.py` | §6 |
| 10 | `ConfigAlias` (alias) | `anonymization.py` | §6 |
| 11 | `ProgressEvent` | `runner.py` | §2 |
| 12 | `FailureGroup` | `failures.py` | §10 |
| 13 | `ComparisonResult` | `comparisons.py` | §16 |
| 14 | `Regression` | `comparisons.py` | §16 |
| 15 | `RunStatistics` | `stats.py` | §15 |

### Preserved / moved structures (9 total, unchanged)

| # | Structure | From → To | Changed? |
|---|-----------|-----------|:--------:|
| 1 | `PromptVariant` (alias) | benchmark.py → scoring.py | no |
| 2 | `DirectionKey` (alias) | benchmark.py → scoring.py | no |
| 3 | `CategoryName` (alias) | benchmark.py → scoring.py | no |
| 4 | `_CATEGORY_ORDER` (const) | benchmark.py → scoring.py | no |
| 5 | `CategoryResult` | benchmark.py → scoring.py | no |
| 6 | `ModelRunResult` | benchmark.py → scoring.py | no (not extended — OQ-2 resolution) |
| 7 | `CategorySummaryEntry` | benchmark.py → scoring.py | no |
| 8 | `ModelReport` | benchmark.py → scoring.py | no |
| 9 | `BenchmarkReport` | benchmark.py → scoring.py | no |

### Extended structures (1)

| # | Structure | From → To | Change |
|---|-----------|-----------|--------|
| 1 | `BenchmarkConfig` | benchmark.py → config.py | +9 new fields, all defaulted (§2/§3/§4/§5/§6/§7/§16) |

---

## 5. What This Artifact Does NOT Define (deferred)

- **No methods.** No `__init__`, `__post_init__`, `to_json`, `from_dict`, validators, properties, or any behavior. P3 defines interfaces (function signatures); P7 implements them.
- **No module function signatures.** Those are P3.
- **No TODO markers.** Those are P4.
- **No regex patterns or scoring constants.** The existing scoring regexes (`_MARKDOWN_BOLD_RE`, `_SET_EQ_RE`, etc.) are implementation details that stay in `scoring.py` unchanged — they are not data structures.
- **No `_DRY_RUN_RESPONSE` fixture.** That is a string constant (implementation), not a data structure. It moves to `fixtures.py` unchanged.
- **No pydantic models.** `ModelOutput`, `ParsedChoice`, `HarnessConfig` are defined in `harness/models.py` and are *referenced* by these structures (e.g. `ResultRecord.parsed_output: ModelOutput`), never redefined. INV-5 (no harness modification) is preserved.
- **No CSV/HTML/JSON serialization format definitions.** Those are export concerns handled in P3/P7; this artifact defines the in-memory types only.

---

## 6. Verification Checklist (for the reviewer)

- [x] Every new structure justified by a specific spec section (§2-§16) — see field rationales.
- [x] No methods, no functions, no logic — all definitions are field declarations + docstrings.
- [x] No existing field types changed — the 9 preserved structures are byte-for-byte identical to current benchmark.py lines 83-179.
- [x] `BenchmarkConfig` extension is purely additive — 9 new fields, all with defaults; existing test construction `BenchmarkConfig(models=..., ...)` with 11 fields stays valid.
- [x] `ModelRunResult` is NOT extended (OQ-2 resolution: separate `ResultRecord` wraps it) — 63 tests' keyword construction unchanged.
- [x] All new structures use frozen dataclasses (matching existing convention) or Literal aliases.
- [x] No new third-party dependencies — all types are stdlib (`str`, `int`, `float`, `bool`, `tuple`, `dict`, `datetime`, `Literal`).
- [x] Tuples (not lists) used for all sequence fields in frozen dataclasses (matches existing `category_results: tuple[CategoryResult, ...]` convention).
- [x] Dict-typed fields on frozen dataclasses (`RunManifest.generation_params`, etc.) are fine: `dict[str, str]` is an annotation, not a default; the P3 constructor supplies the dict. No mutable default is declared.
- [x] No over-engineering (YAGNI): `ModelAlias`/`ProviderAlias` are bounded Literals reflecting realistic model counts; `ConfigAlias` is `str` (unbounded configs).
- [x] Field names are clear and consistent with existing conventions (snake_case, no abbreviations).
- [x] Each structure has a docstring explaining its role.
- [x] No harness modifications — `ModelOutput`/`ParsedChoice`/`HarnessConfig` referenced, not redefined (INV-5).
