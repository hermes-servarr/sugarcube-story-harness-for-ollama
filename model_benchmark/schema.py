"""Phase 2 data structures for the model benchmark (new types only).

Defines the 15 NEW types specified in ``p2_data_structures.md`` (§3 New
Structures, §4 summary table). Per the spec's design principles (§0):

- No methods, no functions, no logic — field declarations + docstrings only.
- Frozen dataclasses (matching the existing benchmark convention), not pydantic.
- stdlib types only (``str``, ``int``, ````float``, ``bool``, ``tuple``,
  ``dict``, ``Literal``).
- Tuples (not lists) for all sequence fields in frozen dataclasses.
- ``from __future__ import annotations`` + ``TYPE_CHECKING`` keeps the harness
  pydantic model (``ModelOutput``) and the not-yet-extracted scoring types
  (``CategoryName``, ``ModelRunResult``) as string annotations, so this
  module imports cleanly even when pydantic is not installed.

The 9 preserved/moved structures (``PromptVariant``, ``DirectionKey``,
``CategoryName``, ``_CATEGORY_ORDER``, ``CategoryResult``, ``ModelRunResult``,
``CategorySummaryEntry``, ``ModelReport``, ``BenchmarkReport``) and the 1
extended structure (``BenchmarkConfig``) are **not** defined here — they live
in ``scoring.py`` / ``config.py`` per the spec's module-home table (§1) and
are re-exported from ``benchmark.py``. Only the 15 new types below call
``schema.py`` home.

The 15 new types (§4 summary):
  1.  ResultStatus        (alias)      §2, §8
  2.  FailureCategory     (alias)      §10
  3.  ResultProvenance    (alias)      §3
  4.  ResultRecord        (dataclass)  §8
  5.  CheckpointState     (dataclass)  §3
  6.  RunManifest         (dataclass)  §5
  7.  AnonymizationMapping(dataclass)  §7
  8.  ModelAlias          (alias)      §6
  9.  ProviderAlias       (alias)      §6
  10. ConfigAlias         (alias)      §6
  11. ProgressEvent       (dataclass)  §2
  12. FailureGroup        (dataclass)  §10
  13. ComparisonResult    (dataclass)  §16
  14. Regression          (dataclass)  §16
  15. RunStatistics       (dataclass)  §15
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    # Referenced only in annotations (string form thanks to
    # ``from __future__ import annotations``), so never imported at runtime.
    # Imported under TYPE_CHECKING so type checkers can resolve the names.
    from harness.models import ModelOutput
    # CategoryName and ModelRunResult live in scoring.py (§1 module home).
    # Referenced here only as annotations on ResultRecord (category,
    # scored_result).  Importing under TYPE_CHECKING avoids a circular import
    # (scoring.py imports fixtures.py at runtime; fixtures.py references
    # PromptVariant/DirectionKey from scoring.py under TYPE_CHECKING only;
    # benchmark.py shim imports scoring.py + fixtures.py + schema.py).
    from model_benchmark.scoring import CategoryName, ModelRunResult


__all__ = [
    # Type aliases (6 of the 15 new types)
    "ResultStatus",
    "FailureCategory",
    "ResultProvenance",
    "ModelAlias",
    "ProviderAlias",
    "ConfigAlias",
    # Frozen dataclasses (9 of the 15 new types)
    "ResultRecord",
    "CheckpointState",
    "RunManifest",
    "AnonymizationMapping",
    "ProgressEvent",
    "FailureGroup",
    "ComparisonResult",
    "Regression",
    "RunStatistics",
    # Documentation/grouping sub-aliases (not counted among the 15)
    "BenchmarkFailure",
    "InfrastructureFailure",
]


# ═══════════════════════════════════════════════════════════════════════════
# §3.2  ResultStatus  (schema.py) — NEW alias
# ═══════════════════════════════════════════════════════════════════════════

ResultStatus = Literal[
    "PASS",      # all scoring categories passed
    "FAIL",      # one or more scoring categories failed
    "ERROR",     # infrastructure error during generation/parse/score
    "SKIPPED",   # explicitly skipped (e.g. filtered out, precondition unmet)
    "INVALID",   # malformed/invalid test data or input
    "TIMEOUT",   # generation call exceeded timeout
    "CANCELLED", # run interrupted by user/signal before completion
]
"""Result outcome classification for one evaluated case.

Source: §2 (status classifications) + §8 (result schema ``status`` field).
Used on ``ResultRecord.status``."""


# ═══════════════════════════════════════════════════════════════════════════
# §3.3  FailureCategory  (schema.py) — NEW alias
# ═══════════════════════════════════════════════════════════════════════════

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
"""Benchmark-failure sub-aliases (§10) — the model's answer is wrong/bad.

Defined for documentation/grouping; ``FailureCategory`` is the union used on
``ResultRecord.failure_category``."""

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
"""Infrastructure-failure sub-aliases (§10) — the evaluation machinery failed.

Defined for documentation/grouping; ``FailureCategory`` is the union used on
``ResultRecord.failure_category``."""

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
"""Union of benchmark + infrastructure failure categories plus ``"none"``.

Source: §10 (distinguish benchmark failures from infrastructure failures).
``BenchmarkFailure`` and ``InfrastructureFailure`` sub-aliases are defined
above for documentation/grouping; this ``FailureCategory`` union is the one
used on ``ResultRecord.failure_category``."""


# ═══════════════════════════════════════════════════════════════════════════
# §3.4  ResultProvenance  (schema.py) — NEW alias
# ═══════════════════════════════════════════════════════════════════════════

ResultProvenance = Literal[
    "new",       # freshly computed in this run
    "resumed",   # loaded from checkpoint, not recomputed
    "retried",   # recomputed after a prior failure
    "recovered", # salvaged from a partial/interrupted state
]
"""How a result was obtained.

Source: §3 ("Record whether each result was new/resumed/retried/recovered").
Used on ``ResultRecord.provenance`` and ``CheckpointState.provenance``."""


# ═══════════════════════════════════════════════════════════════════════════
# §3.5  ResultRecord  (schema.py) — NEW
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ResultRecord:
    """Versioned, enriched result for one evaluated case (§8 schema).

    Wraps the scored ``ModelRunResult`` and adds reproducibility, token, cost,
    status, failure-classification, and artifact-reference metadata.  A
    converter (P3) bridges ``ModelRunResult`` -> ``ResultRecord`` so existing
    tests that build ``ModelRunResult`` directly still pass.

    Only the trailing optional fields (``artifact_refs``,
    ``parent_result_id``, ``comparison_result_id``, ``provenance``,
    ``scored_result``) have defaults.  Required fields (the §8 core) must be
    provided at construction — a ``ResultRecord`` with a missing ``test_id``
    or ``status`` is not a valid record.
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
    # ── Actual output (§8) ────────────────────────────────────────────────
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
    finish_reason: str = ""


# ═══════════════════════════════════════════════════════════════════════════
# §3.6  CheckpointState  (checkpoint.py home, defined here) — NEW
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class CheckpointState:
    """Resumable run state — which result IDs are already finalized (§3).

    Persisted to ``checkpoint.json`` via atomic write (tmpfile +
    ``os.replace``).  On resume, ``completed_ids`` are skipped unless
    ``force_rerun`` is set.

    ``provenance`` is a tuple of ``(test_id, provenance)`` pairs because
    frozen dataclasses cannot hold a mutable dict default; the P3
    ``load_checkpoint`` / ``save_checkpoint`` interfaces will convert to/from
    a dict internally.
    """
    run_id: str
    completed_ids: tuple[str, ...]
    total_cases: int
    last_saved_at: str
    # Per-result provenance, keyed by test_id (§3: new/resumed/retried/recovered)
    provenance: tuple[tuple[str, ResultProvenance], ...]


# ═══════════════════════════════════════════════════════════════════════════
# §3.7  RunManifest  (metadata.py home, defined here) — NEW
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class RunManifest:
    """Reproducibility metadata for one benchmark run (§5).

    Written to ``run_manifest.json``.  Contains everything needed to reproduce
    or interpret a run, with secrets redacted.

    ``env_vars_redacted`` holds the env dict with secrets stripped (never API
    keys/tokens/credentials per §5).  ``model_configs`` /
    ``generation_params`` / ``runtime_settings`` / ``package_versions`` /
    ``env_vars_redacted`` are typed ``dict[str, str]`` (or tuple of dicts) for
    frozen-compatibility; values are stringified at construction time by the
    P3 metadata collector.
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


# ═══════════════════════════════════════════════════════════════════════════
# §3.9  Alias type aliases  (anonymization.py home, defined here) — NEW
# ═══════════════════════════════════════════════════════════════════════════

ModelAlias = str
"""Anonymized model alias (§6).

Aliases use an unbounded spreadsheet-style letter sequence: ``Model_A``
through ``Model_Z``, followed by ``Model_AA``, ``Model_AB``, and so on."""

ProviderAlias = Literal["Provider_A", "Provider_B"]
"""Anonymized provider alias (§6).

Two providers (local Ollama + one remote) is the realistic max for this
benchmark."""

ConfigAlias = str  # e.g. "Config_01", "Config_02" — format: Config_NN
"""Anonymized config alias (§6).

``ConfigAlias`` is a ``str`` (not ``Literal``) because config count is
unbounded (temperature/num_predict permutations).  The format ``Config_NN``
is a convention enforced by ``build_anonymization_mapping`` (P3) and checked
by INV-A2 (P6), not by the type itself."""


# ═══════════════════════════════════════════════════════════════════════════
# §3.8  AnonymizationMapping  (anonymization.py home, defined here) — NEW
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class AnonymizationMapping:
    """Private alias->original mapping for one run (§7).

    Stored separately in ``anonymization_mapping.private.json``, never
    referenced in anonymized reports.  Deterministic: a stable sort of
    internal names produces ``Model_A``, ``Model_B``, ``Provider_A``,
    ``Config_01``, ``Run_01``.

    Tuple-of-pairs (not dict) because frozen dataclasses cannot hold a
    mutable dict default; P3 ``build_anonymization_mapping`` builds these
    from a stable-sorted list.

    ``identity_strings`` holds the identity strings that must be scrubbed
    from anonymized artifacts (§6): hostnames, file paths, account ids, etc.
    Each entry is replaced by its mapped alias or a generic redaction token.
    """
    model_aliases: tuple[tuple[ModelAlias, str], ...]        # alias -> original model name
    provider_aliases: tuple[tuple[ProviderAlias, str], ...]  # alias -> original provider
    config_aliases: tuple[tuple[ConfigAlias, str], ...]      # alias -> original config label
    run_aliases: tuple[tuple[str, str], ...]                # alias -> original run id
    identity_strings: tuple[str, ...]


# ═══════════════════════════════════════════════════════════════════════════
# §3.10  ProgressEvent  (runner.py home, defined here) — NEW
# ═══════════════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════════════
# §3.11  FailureGroup  (failures.py home, defined here) — NEW
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class FailureGroup:
    """One cluster of related failures for failure reporting (§10).

    Groups failures by ``FailureCategory``.  Per-group: category, affected
    case count, % of evaluated, affected capabilities/datasets, severity,
    representative examples, suggested investigation.

    ``failure_class`` is the benchmark-vs-infrastructure distinction from
    §10.  ``severity`` is a ``str`` (not ``Literal``) to allow the classifier
    (P3) to assign graduated severity without type churn; P6 INV will check
    it's one of the four values.
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


# ═══════════════════════════════════════════════════════════════════════════
# §3.12  ComparisonResult  (comparisons.py home, defined here) — NEW
# ═══════════════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════════════
# §3.13  Regression  (comparisons.py home, defined here) — NEW
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Regression:
    """One detected regression between current and baseline runs (§16).

    A regression is a case or category whose outcome changed for the worse
    beyond a configurable threshold.

    ``severity`` is a ``str`` (not ``Literal``) for the same reason as
    ``FailureGroup.severity``; P6 INV checks membership.
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


# ═══════════════════════════════════════════════════════════════════════════
# §3.14  RunStatistics  (stats.py home, defined here) — NEW
# ═══════════════════════════════════════════════════════════════════════════


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
    # Variance flags as human-readable strings (§15: "flag high-variance categories,
    # unstable tests...")
    variance_flags: tuple[str, ...]


# ═══════════════════════════════════════════════════════════════════════════
# P3 Interfaces — function signatures (NO BODIES, P4 stubs only)
# ═══════════════════════════════════════════════════════════════════════════
#
# Per P3 §3.3, schema.py defines two new interfaces that bridge the scoring
# core (ModelRunResult) and the enriched schema (ResultRecord).  These are
# function signatures only — implementation belongs to P7.

# TODO(benchmark-upgrade): schema.py — implement result_to_record per P3 §3.3.
# Signature:
#   def result_to_record(
#       scored: ModelRunResult,
#       *,
#       schema_version: str,
#       test_id: str,
#       capability: str,
#       prompt_version: int,
#       random_seed: str = "",
#       provenance: ResultProvenance = "new",
#   ) -> ResultRecord:
# Converts a scored ModelRunResult into an enriched ResultRecord, deriving
# status/category/score from the scored core.  Logic is P7; this is the site.

# TODO(benchmark-upgrade): schema.py — implement record_to_result_core per
# P3 §3.3.
# Signature:
#   def record_to_result_core(record: ResultRecord) -> ModelRunResult | None:
# Extracts the embedded ModelRunResult from a ResultRecord (returns
# record.scored_result).  Convenience accessor — no recomputation.
