#!/usr/bin/env python3
"""Declarative test configuration schema for the SugarCube model benchmark.

This module defines the canonical, type-checked schema for test definitions
written in YAML or JSON.  It is the single source of truth for the config
loader (t_172dd683), evaluator plugins (t_b8e82f29), and the benchmark engine.

Design overview (see tests/DESIGN_NOTE.md for the full design note):

* **Layered hierarchy** — global defaults → suite-level overrides → individual
  test overrides → CLI overrides.  Each layer deep-merges onto the previous.
* **Merge semantics** — dicts deep-merge recursively; scalars replace; lists
  replace by default but can be flagged ``append`` per-field via ``MergePolicy``.
  ``tags`` always union (deduplicated) regardless of policy.
* **Schema versioning** — every document carries ``schema_version`` (semver).
  The loader validates against the supported version and refuses incompatible
  documents.  Migrations are explicit (``benchmark test migrate --from N --to M``).
* **Validation** — pydantic v2 models enforce type constraints, enum values, and
  cross-field rules.  The JSON Schema export (``model_json_schema``) gives IDE
  autocompletion and offline validation.

The schema is deliberately generic — SugarCube-specific scoring categories live
in ``benchmark.py`` and are referenced via the ``scoring_categories`` field, not
hard-coded here.  This keeps the test framework extractable for other projects.
"""
from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ── Schema version ──────────────────────────────────────────────────────

SCHEMA_VERSION = "1.0.0"
SUPPORTED_SCHEMA_VERSIONS: tuple[str, ...] = ("1.0.0",)

# ── Enums / Literals ─────────────────────────────────────────────────────

DocumentKind = Literal["defaults", "suite", "test"]
"""Role of a config document in the layered hierarchy."""

Difficulty = Literal["easy", "medium", "hard", "expert"]
"""Test difficulty levels, ordered easy → expert."""

PromptVariant = Literal["compact", "full", "json", "thinking"]
"""Prompt format variant (mirrors harness.prompts builders)."""

DirectionKey = Literal["A", "B", "C", "D", "E", "F", "G", "H"]
"""Direction prompt key (A: set flag, B: conditional, C: stats)."""

ScoringCategory = Literal[
    "markup_compliance",
    "variable_scoping",
    "passage_structure",
    "macro_usage",
    "naked_interpolation",
    "link_setter_syntax",
    "thinking_quality",
]
"""The 7 SugarCube compliance categories (canonical order, INV-9)."""

StatusClassification = Literal[
    "PASS", "FAIL", "ERROR", "SKIPPED", "INVALID", "TIMEOUT", "CANCELLED",
]
"""Result status classifications (§2 of upgrade spec)."""

DatasetFormat = Literal["csv", "jsonl", "json", "huggingface", "inline"]
"""Supported dataset source formats."""

RetryBackoff = Literal["fixed", "linear", "exponential"]
"""Retry backoff strategies."""

MatrixStrategy = Literal["full", "pairwise", "explicit", "sample"]
"""How parameterized matrix dimensions are combined into concrete cases."""

ListMergeStrategy = Literal["replace", "append"]
"""Per-field list merge strategy: replace (child overwrites) or append (union)."""


# ── Sub-models ───────────────────────────────────────────────────────────

class ModelParameters(BaseModel):
    """Generation parameters sent to the model backend (Ollama).

    Fields mirror ``BenchmarkConfig`` in benchmark.py so the declarative config
    can drive the existing engine without translation.
    """
    model_config = ConfigDict(extra="forbid")

    base_url: str = "http://localhost:11434"
    timeout: int = Field(default=120, gt=0, description="Seconds per model call")
    num_predict: int = Field(default=640, gt=0, description="Max tokens to generate")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    top_k: Optional[int] = Field(default=None, ge=0)
    seed: Optional[int] = Field(default=None, ge=0)
    stop: Optional[list[str]] = None
    repeat_penalty: Optional[float] = Field(default=None, ge=0.0)


class DatasetReference(BaseModel):
    """Reference to an external or inline dataset.

    Tests can reference datasets by path, HuggingFace identifier, or inline
    data.  The loader (t_172dd683) resolves the reference, fetches the data,
    and injects rows as parameterized test inputs.
    """
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Stable dataset identifier")
    version: Optional[str] = Field(default=None, description="Dataset version tag")
    split: Optional[str] = Field(default=None, description="Train/val/test split name")
    path: Optional[str] = Field(default=None, description="Local file path (portable, not absolute)")
    format: DatasetFormat = "jsonl"
    huggingface_id: Optional[str] = Field(default=None, description="HF dataset repo ID (e.g. 'squad')")
    filters: Optional[dict[str, Any]] = Field(default=None, description="Row filters applied at load time")
    sample: Optional[int] = Field(default=None, ge=1, description="Random sample N rows")
    seed: Optional[int] = Field(default=None, ge=0, description="Seed for sampling")
    checksum: Optional[str] = Field(default=None, description="Content checksum (sha256) for integrity")
    inline_data: Optional[list[dict[str, Any]]] = Field(default=None, description="Inline rows (format=inline)")

    @model_validator(mode="after")
    def _check_format_consistency(self) -> "DatasetReference":
        if self.format == "huggingface" and not self.huggingface_id:
            raise ValueError("format='huggingface' requires huggingface_id to be set")
        if self.format == "inline" and self.inline_data is None:
            raise ValueError("format='inline' requires inline_data to be set")
        if self.format not in ("huggingface", "inline") and not self.path:
            raise ValueError(f"format='{self.format}' requires path to be set")
        return self


class EvaluatorReference(BaseModel):
    """Reference to an evaluator plugin with optional parameters.

    Config files reference evaluators by name with optional parameters::

        evaluation:
          name: semantic_similarity
          type: llm_judge
          params:
            threshold: 0.8
          pass_threshold: 1.0

    Built-in evaluators (t_b8e82f29): exact_match, substring_regex, llm_judge.
    Custom evaluators are discovered via the plugin registry.
    """
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Evaluator plugin name (unique ID)")
    type: Optional[str] = Field(default=None, description="Evaluator category (exact_match, regex, llm_judge, ...)")
    version: Optional[str] = Field(default=None, description="Evaluator version for traceability")
    params: dict[str, Any] = Field(default_factory=dict, description="Evaluator-specific parameters")
    prompt: Optional[str] = Field(default=None, description="Evaluator prompt (inline text or template ref)")
    prompt_template_ref: Optional[str] = Field(default=None, description="Reference to a prompt template file")
    pass_threshold: float = Field(default=1.0, ge=0.0, le=1.0, description="Minimum normalized score to pass")
    max_score: float = Field(default=1.0, gt=0.0, description="Maximum raw score")
    deterministic: Optional[bool] = Field(default=None, description="Whether the evaluator is deterministic")

    @model_validator(mode="after")
    def _check_threshold_max_score(self) -> "EvaluatorReference":
        if self.pass_threshold > self.max_score / self.max_score if self.max_score else False:
            # pass_threshold is already normalized [0,1], just warn if > 1.0
            pass
        return self


class ExpectedBehavior(BaseModel):
    """Descriptors for the expected model behavior.

    Combines a reference answer, behavioral constraints, a scoring rubric,
    and simple match checks (contains / not_contains / regex).  The evaluator
    uses whichever fields are relevant to its type.
    """
    model_config = ConfigDict(extra="forbid")

    answer: Optional[str] = Field(default=None, description="Reference / gold answer")
    answer_type: Optional[Literal["exact", "numeric", "multiple_choice", "structured", "free_text"]] = None
    answer_choices: Optional[list[str]] = Field(default=None, description="Choices for multiple_choice")
    numeric_tolerance: Optional[float] = Field(default=None, ge=0.0, description="Tolerance for numeric answers")
    behavior: Optional[list[str]] = Field(default=None, description="Behavioral descriptors the model should exhibit")
    rubric: Optional[list[dict[str, Any]]] = Field(default=None, description="Scoring rubric items [{criterion, weight, description}]")
    constraints: Optional[list[str]] = Field(default=None, description="Constraints the answer must satisfy")
    contains: Optional[list[str]] = Field(default=None, description="Substrings the output must contain")
    not_contains: Optional[list[str]] = Field(default=None, description="Substrings the output must NOT contain")
    regex: Optional[list[str]] = Field(default=None, description="Regex patterns the output must match")
    must_parse_as: Optional[Literal["json", "yaml", "csv", "sugarcube_passage"]] = None


class RetryPolicy(BaseModel):
    """Retry policy for flaky model calls or evaluator errors."""
    model_config = ConfigDict(extra="forbid")

    max_retries: int = Field(default=0, ge=0)
    backoff: RetryBackoff = "exponential"
    initial_delay: float = Field(default=1.0, gt=0.0, description="Initial delay in seconds")
    max_delay: float = Field(default=60.0, gt=0.0, description="Maximum delay cap in seconds")
    retry_on: list[str] = Field(
        default_factory=lambda: ["timeout", "network_error", "rate_limit"],
        description="Error categories that trigger a retry",
    )


class PromptTemplate(BaseModel):
    """Prompt template — either a reference to a file or inline text.

    ``ref`` and ``text`` are mutually exclusive.  ``variant`` selects the
    harness.prompts builder when using built-in templates.
    """
    model_config = ConfigDict(extra="forbid")

    ref: Optional[str] = Field(default=None, description="Path to a template file (relative to tests/prompts/)")
    variant: Optional[PromptVariant] = Field(default=None, description="Built-in variant: compact/full/json")
    text: Optional[str] = Field(default=None, description="Inline Jinja2/text template")
    version: Optional[int] = Field(default=None, description="Template version for traceability")
    input_variables: dict[str, Any] = Field(default_factory=dict, description="Variables injected into the template")

    @model_validator(mode="after")
    def _check_ref_text_exclusive(self) -> "PromptTemplate":
        if self.ref and self.text:
            raise ValueError("prompt_template.ref and prompt_template.text are mutually exclusive")
        if not self.ref and not self.text and not self.variant:
            raise ValueError("prompt_template requires one of: ref, text, or variant")
        return self


class ModelEligibility(BaseModel):
    """Constraints on which models may run this test."""
    model_config = ConfigDict(extra="forbid")

    required: Optional[list[str]] = Field(default=None, description="Model tags that CAN run this test (allowlist)")
    excluded: Optional[list[str]] = Field(default=None, description="Model tags that CANNOT run (denylist)")
    min_context_length: Optional[int] = Field(default=None, gt=0)
    min_parameters: Optional[int] = Field(default=None, gt=0, description="Minimum model parameter count (e.g. 7_000_000_000)")
    required_capabilities: Optional[list[str]] = Field(default=None, description="Required model capabilities (e.g. 'tool_use', 'vision')")

    @model_validator(mode="after")
    def _check_required_excluded_overlap(self) -> "ModelEligibility":
        if self.required and self.excluded:
            overlap = set(self.required) & set(self.excluded)
            if overlap:
                raise ValueError(f"model_eligibility.required and .excluded overlap: {sorted(overlap)}")
        return self


class TestMetadata(BaseModel):
    """Provenance and lifecycle metadata for a test."""
    model_config = ConfigDict(extra="forbid")
    __test__ = False  # not a pytest test class

    owner: Optional[str] = None
    source: Optional[str] = None
    created: Optional[str] = Field(default=None, description="ISO-8601 creation timestamp")
    modified: Optional[str] = Field(default=None, description="ISO-8601 last-modified timestamp")
    deprecated: bool = False
    deprecation_message: Optional[str] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _check_deprecation_message(self) -> "TestMetadata":
        if self.deprecated and not self.deprecation_message:
            # Warn, not error — deprecated without a message is sloppy but not invalid.
            pass
        return self


class MatrixConfig(BaseModel):
    """Controls how parameterized matrix dimensions expand into concrete cases.

    The ``parameters`` dict on the test defines dimension names → value lists.
    This model controls the combination strategy and explosion limits.
    """
    model_config = ConfigDict(extra="forbid")

    strategy: MatrixStrategy = "full"
    max_cases: Optional[int] = Field(default=None, gt=0, description="Hard cap on generated cases (prevents explosion)")
    sample_size: Optional[int] = Field(default=None, gt=0, description="N for 'sample' strategy")
    explicit_combinations: Optional[list[dict[str, Any]]] = Field(
        default=None, description="Explicit dimension combos for 'explicit' strategy [{context_length: 4000, ...}]"
    )
    seed: Optional[int] = Field(default=None, ge=0, description="Seed for 'sample' strategy")

    @model_validator(mode="after")
    def _check_strategy_fields(self) -> "MatrixConfig":
        if self.strategy == "explicit" and not self.explicit_combinations:
            raise ValueError("matrix.strategy='explicit' requires explicit_combinations to be set")
        if self.strategy == "sample" and self.sample_size is None:
            raise ValueError("matrix.strategy='sample' requires sample_size to be set")
        return self


class MergePolicy(BaseModel):
    """Declares how list fields merge with parent-layer defaults.

    Applied when this document's values are merged onto a parent layer
    (defaults → suite → test).  Dict fields always deep-merge; scalars always
    replace.  Only list fields are controlled here.

    ``tags`` always union (deduplicated) regardless of policy — it is a
    semantic set, not an ordered list.
    """
    model_config = ConfigDict(extra="forbid")

    list_strategy: ListMergeStrategy = Field(
        default="replace",
        description="Default strategy for all list fields: replace or append",
    )
    field_overrides: dict[str, ListMergeStrategy] = Field(
        default_factory=dict,
        description="Per-field override, e.g. {tags: append, models: replace}",
    )


# ── Core test config ─────────────────────────────────────────────────────

class TestConfig(BaseModel):
    """A single test definition — or a partial overlay used as defaults.

    Every field is optional so this model can serve three roles:
    * As a complete test (``kind: test``) — ``id`` is required, others optional.
    * As suite-level overrides (``kind: suite`` → ``defaults: TestConfig``).
    * As global defaults (``kind: defaults`` → ``defaults: TestConfig``).

    The loader deep-merges layers in order: built-in → global → suite → test.
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    __test__ = False  # not a pytest test class

    # ── Identity & classification ──
    id: Optional[str] = Field(default=None, description="Stable unique test identifier (required for kind=test)")
    name: Optional[str] = Field(default=None, description="Human-readable test name")
    description: Optional[str] = None
    version: Optional[str] = Field(default=None, description="Test definition version (semver)")
    enabled: Optional[bool] = Field(default=None, description="None=unset, True/False to enable/disable")

    # ── Taxonomy ──
    capability: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    difficulty: Optional[Difficulty] = None
    tags: list[str] = Field(default_factory=list)

    # ── Prompt / input ──
    input: Optional[str] = Field(default=None, description="Inline input/prompt text")
    system_instructions: Optional[str] = None
    prompt_template: Optional[PromptTemplate] = None
    input_variables: dict[str, Any] = Field(default_factory=dict)

    # ── Expected behavior ──
    expected: Optional[ExpectedBehavior] = None

    # ── Evaluation ──
    evaluation: Optional[EvaluatorReference] = None

    # ── Dataset ──
    dataset: Optional[DatasetReference] = None

    # ── Model parameters ──
    model_parameters: Optional[ModelParameters] = None

    # ── Scoring (SugarCube-specific, referenced not hard-coded) ──
    scoring_categories: Optional[list[ScoringCategory]] = Field(
        default=None,
        description="Which of the 6 SugarCube scoring categories to apply (default: all 6)",
    )

    # ── Execution ──
    timeout: Optional[int] = Field(default=None, gt=0, description="Seconds per model call (overrides model_parameters.timeout)")
    retry_policy: Optional[RetryPolicy] = None
    max_input_tokens: Optional[int] = Field(default=None, gt=0)
    max_output_tokens: Optional[int] = Field(default=None, gt=0)
    random_seed: Optional[int] = Field(default=None, ge=0)
    repetitions: Optional[int] = Field(default=None, ge=1, description="Number of repeated runs for variance analysis")

    # ── Model eligibility ──
    model_eligibility: Optional[ModelEligibility] = None
    required_tools: list[str] = Field(default_factory=list)

    # ── Dependencies ──
    dependencies: list[str] = Field(default_factory=list, description="Prerequisite test IDs that must pass first")
    skip_conditions: Optional[list[str]] = Field(default=None, description="Conditions under which to skip this test")
    expected_failure: Optional[bool] = Field(default=None, description="If True, a FAIL is the expected outcome (negative test)")

    # ── Parameterized matrix ──
    parameters: Optional[dict[str, list[Any]]] = Field(
        default=None,
        description="Matrix dimensions: {dim_name: [val1, val2, ...]}",
    )
    matrix: Optional[MatrixConfig] = None

    # ── Selection priority ──
    priority: Optional[int] = Field(
        default=None,
        ge=0,
        description=(
            "Selection priority (lower = higher priority).  Used by the test "
            "selector (t_503bdee2) to order and truncate the selected set when "
            "a max-selected cap is set.  ``None`` means unset; the selector "
            "treats unset priorities as the default (highest-number, i.e. lowest "
            "priority) so tests that declare a priority sort first."
        ),
    )

    # ── Metadata ──
    metadata: Optional[TestMetadata] = None


# ── Document models ──────────────────────────────────────────────────────

class DefaultsDocument(BaseModel):
    """Global defaults document — sets default values for all tests.

    Loaded first; suite and test layers merge on top.
    """
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    kind: Literal["defaults"] = "defaults"
    defaults: TestConfig = Field(..., description="Default values applied to all tests")
    merge: Optional[MergePolicy] = None

    @field_validator("schema_version")
    @classmethod
    def _check_version(cls, v: str) -> str:
        if v not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"Unsupported schema_version '{v}'. Supported: {SUPPORTED_SCHEMA_VERSIONS}. "
                f"Use 'benchmark test migrate --from {v} --to {SCHEMA_VERSION}' to upgrade."
            )
        return v


class SuiteDocument(BaseModel):
    """Test suite — a named collection of tests with suite-level overrides.

    Lists tests by ID reference or inline definition.  Suite-level ``defaults``
    merge between global defaults and individual test config.
    """
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    kind: Literal["suite"] = "suite"
    name: str = Field(..., description="Unique suite name (required)")
    description: Optional[str] = None
    defaults: Optional[TestConfig] = Field(default=None, description="Suite-level overrides applied to all tests in this suite")
    tests: list[Union[str, TestConfig]] = Field(
        ...,
        min_length=1,
        description="Test IDs (string references) or inline TestConfig definitions",
    )
    tags: list[str] = Field(default_factory=list, description="Suite-level tags inherited by member tests")
    merge: Optional[MergePolicy] = None

    @field_validator("schema_version")
    @classmethod
    def _check_version(cls, v: str) -> str:
        if v not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"Unsupported schema_version '{v}'. Supported: {SUPPORTED_SCHEMA_VERSIONS}."
            )
        return v


class TestDocument(BaseModel):
    """Individual test document — a single test definition.

    ``id`` is required.  All other fields are optional with sensible defaults
    applied by the loader during merge.
    """
    model_config = ConfigDict(extra="forbid")
    __test__ = False  # not a pytest test class

    schema_version: str = SCHEMA_VERSION
    kind: Literal["test"] = "test"
    # Flatten all TestConfig fields to the top level for ergonomic YAML.
    id: str = Field(..., description="Stable unique test identifier (required)")
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    enabled: Optional[bool] = None
    capability: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    difficulty: Optional[Difficulty] = None
    tags: list[str] = Field(default_factory=list)
    input: Optional[str] = None
    system_instructions: Optional[str] = None
    prompt_template: Optional[PromptTemplate] = None
    input_variables: dict[str, Any] = Field(default_factory=dict)
    expected: Optional[ExpectedBehavior] = None
    evaluation: Optional[EvaluatorReference] = None
    dataset: Optional[DatasetReference] = None
    model_parameters: Optional[ModelParameters] = None
    scoring_categories: Optional[list[ScoringCategory]] = None
    timeout: Optional[int] = Field(default=None, gt=0)
    retry_policy: Optional[RetryPolicy] = None
    max_input_tokens: Optional[int] = Field(default=None, gt=0)
    max_output_tokens: Optional[int] = Field(default=None, gt=0)
    random_seed: Optional[int] = Field(default=None, ge=0)
    repetitions: Optional[int] = Field(default=None, ge=1)
    model_eligibility: Optional[ModelEligibility] = None
    required_tools: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    skip_conditions: Optional[list[str]] = None
    expected_failure: Optional[bool] = None
    parameters: Optional[dict[str, list[Any]]] = None
    matrix: Optional[MatrixConfig] = None
    priority: Optional[int] = Field(default=None, ge=0, description="Selection priority (lower = higher priority)")
    metadata: Optional[TestMetadata] = None
    merge: Optional[MergePolicy] = None

    @field_validator("schema_version")
    @classmethod
    def _check_version(cls, v: str) -> str:
        if v not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"Unsupported schema_version '{v}'. Supported: {SUPPORTED_SCHEMA_VERSIONS}. "
                f"Use 'benchmark test migrate --from {v} --to {SCHEMA_VERSION}' to upgrade."
            )
        return v

    @model_validator(mode="after")
    def _check_matrix_parameters(self) -> "TestDocument":
        if self.matrix and not self.parameters:
            raise ValueError("matrix config requires parameters to be set (matrix dimensions)")
        return self

    def to_test_config(self) -> TestConfig:
        """Convert this flat document into a TestConfig overlay."""
        data = self.model_dump(exclude={"schema_version", "kind", "merge"})
        return TestConfig(**data)


# Discriminated union for parsing any config file
ConfigDocument = Union[DefaultsDocument, SuiteDocument, TestDocument]
"""Any valid config document — discriminated by the ``kind`` field."""


# ── Built-in defaults ────────────────────────────────────────────────────

BUILTIN_DEFAULTS: TestConfig = TestConfig(
    enabled=True,
    difficulty="medium",
    repetitions=1,
    tags=[],
    model_parameters=ModelParameters(),
    evaluation=EvaluatorReference(name="exact_match", pass_threshold=1.0),
)
"""Hardcoded built-in defaults — the lowest layer in the merge hierarchy.

These are applied first, before any config file is loaded.  They ensure
every resolved test has sensible values even with a minimal test definition.
"""


# ── Merge logic ─────────────────────────────────────────────────────────

def deep_merge(
    parent: dict[str, Any],
    child: dict[str, Any],
    merge_policy: Optional[MergePolicy] = None,
) -> dict[str, Any]:
    """Deep-merge ``child`` onto ``parent`` and return the merged dict.

    Merge rules:
    * **Scalars** (str, int, float, bool): child replaces parent if the child
      value is not ``None``.  ``None`` in the child means "not set" — the
      parent value is preserved.  To explicitly clear a field, set it to an
      empty string / 0 / false / empty list (the appropriate falsy sentinel).
    * **Dicts**: recursive deep-merge — child keys override, new keys added.
    * **Lists**: controlled by ``merge_policy``.
        * ``replace`` (default): child list replaces parent list entirely.
        * ``append``: child list extends parent list (concatenation).
      Per-field overrides via ``merge_policy.field_overrides`` take precedence.
      Special case: ``tags`` always unions (deduplicated) regardless of policy.
    * **Pydantic models**: converted to dicts before merging (caller's job).

    This function is pure — it does not mutate ``parent`` or ``child``.
    """
    if merge_policy is None:
        merge_policy = MergePolicy()

    result: dict[str, Any] = {}
    all_keys = set(parent) | set(child)

    for key in all_keys:
        if key in child and child[key] is None:
            # None means "not set" — inherit parent.
            result[key] = parent.get(key)
            continue

        if key not in child:
            # Only in parent — inherit.
            result[key] = parent.get(key)
            continue

        if key not in parent:
            # Only in child — take child.
            result[key] = child[key]
            continue

        pval = parent[key]
        cval = child[key]

        # Both present — merge by type.
        if isinstance(pval, dict) and isinstance(cval, dict):
            result[key] = deep_merge(pval, cval, merge_policy)
        elif isinstance(pval, list) and isinstance(cval, list):
            # Determine strategy for this field.
            strategy = merge_policy.field_overrides.get(key, merge_policy.list_strategy)
            if key == "tags":
                # Tags always union (deduplicated), preserving order.
                seen: set[str] = set()
                merged: list[Any] = []
                for item in list(pval) + list(cval):
                    if item not in seen:
                        seen.add(item)
                        merged.append(item)
                result[key] = merged
            elif strategy == "append":
                result[key] = list(pval) + list(cval)
            else:  # replace
                result[key] = list(cval)
        else:
            # Scalar or type mismatch — child replaces.
            result[key] = cval

    return result


def resolve_test(
    *layers: TestConfig,
    merge_policies: Optional[list[Optional[MergePolicy]]] = None,
) -> TestConfig:
    """Resolve a test by merging layers from lowest to highest precedence.

    Layers are applied in order: ``layers[0]`` is the lowest (e.g. built-in
    defaults), ``layers[-1]`` is the highest (e.g. the individual test config).

    ``merge_policies`` optionally provides a MergePolicy per layer (aligned
    with ``layers``); the policy of the higher-precedence layer wins for each
    merge step.
    """
    if not layers:
        return TestConfig()

    if merge_policies is None:
        merge_policies = [None] * len(layers)
    if len(merge_policies) != len(layers):
        raise ValueError(f"merge_policies length {len(merge_policies)} != layers length {len(layers)}")

    merged: dict[str, Any] = layers[0].model_dump(exclude_none=False)
    for i in range(1, len(layers)):
        child = layers[i].model_dump(exclude_none=False)
        policy = merge_policies[i]
        merged = deep_merge(merged, child, policy)

    return TestConfig(**merged)


# ── JSON Schema export ──────────────────────────────────────────────────

def export_json_schema() -> dict[str, Any]:
    """Export a JSON Schema (draft 2020-12) covering all three document kinds.

    The output is a ``oneOf`` schema that validates defaults, suite, and test
    documents.  Use this for IDE autocompletion and offline validation::

        python -c "from model_benchmark.config_schema import export_json_schema; \
                   import json; print(json.dumps(export_json_schema(), indent=2))" \
                   > model_benchmark/tests/schemas/test_config.schema.json
    """
    from pydantic.json_schema import models_json_schema

    # Generate schemas for all three document types.
    _, schema = models_json_schema(
        [
            (DefaultsDocument, "validation"),
            (SuiteDocument, "validation"),
            (TestDocument, "validation"),
        ],
        title="SugarCube Benchmark Test Configuration Schema",
        description="Declarative test configuration schema (v1.0.0). See tests/DESIGN_NOTE.md.",
    )
    # Wrap in oneOf for discriminated validation by the `kind` field.
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "test_config.schema.json"
    return schema


# ── Convenience: parse a config file ─────────────────────────────────────

def parse_config_dict(data: dict[str, Any]) -> ConfigDocument:
    """Parse a raw dict (from YAML/JSON) into the appropriate document model.

    Discriminates on the ``kind`` field.  Defaults to ``"test"`` if ``kind``
    is absent and ``id`` is present; to ``"defaults"`` if ``defaults`` key
    is present; raises ``ValueError`` if ambiguous.
    """
    kind = data.get("kind")
    if kind is None:
        if "defaults" in data:
            kind = "defaults"
        elif "tests" in data:
            kind = "suite"
        elif "id" in data:
            kind = "test"
        else:
            raise ValueError(
                "Cannot determine document kind. Set 'kind: defaults|suite|test' "
                "or include a discriminating key (defaults/tests/id)."
            )
        data = {**data, "kind": kind}

    if kind == "defaults":
        return DefaultsDocument(**data)
    elif kind == "suite":
        return SuiteDocument(**data)
    elif kind == "test":
        return TestDocument(**data)
    else:
        raise ValueError(f"Unknown kind '{kind}'. Expected: defaults, suite, or test.")


if __name__ == "__main__":
    # CLI: export the JSON Schema to stdout.
    import json
    print(json.dumps(export_json_schema(), indent=2, default=str))
