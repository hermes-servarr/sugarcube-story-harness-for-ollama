"""Trusted passage-generation contracts and pure assembly."""

from .contracts import *  # noqa: F401,F403
from .contracts import __all__
from .compiler import COMPILER_VERSION, compile_passage_draft, render_passage_tw
from .compatibility import fill_to_model_output, model_output_to_draft, model_output_to_fill
from .planning import build_legacy_passage_plan
from .normalize import normalize_flat_fill, normalize_typed_fill
from .schemas import build_flat_fill_schema, build_typed_fill_schema
from .strategies import StrategyRequest, build_strategy_request
from .context import ContextPack
from .pipeline import TypedGenerationOutcome, generate_typed_draft
from .drafts import DraftConflict, DraftNotFound, DraftStore, DraftStoreError
from .plans import PassagePlanStore, PlanConflict, PlanNotFound, PlanStoreError
from .experience import (
    ExperienceMigrationPreview,
    ExperienceProfileConflict,
    ExperienceProfileError,
    ExperienceProfileStore,
    MigrationImpact,
    preset_for_mode,
    preview_experience_migration,
)
from .transaction import ProjectTransaction
from .typed_commit import commit_typed_draft, parent_fingerprint
from .browser_evaluator import (
    BrowserChoiceExpectation,
    BrowserEvaluation,
    BrowserFormExpectation,
    BrowserGuardExpectation,
    BrowserScenario,
    evaluate_compile_artifact,
)
from .capabilities import (
    CapabilityCard,
    CapabilityEvidence,
    CapabilityIdentity,
    StrategyCapability,
    compatible_cards,
    evidence_hashes_match,
    load_capability_cards,
    select_default_strategy,
    source_hashes_match,
)

__all__ = [
    *__all__,
    "COMPILER_VERSION",
    "build_legacy_passage_plan",
    "compile_passage_draft",
    "fill_to_model_output",
    "model_output_to_draft",
    "model_output_to_fill",
    "render_passage_tw",
    "normalize_flat_fill",
    "normalize_typed_fill",
    "build_flat_fill_schema",
    "build_typed_fill_schema",
    "StrategyRequest",
    "build_strategy_request",
    "ContextPack",
    "TypedGenerationOutcome",
    "generate_typed_draft",
    "DraftConflict",
    "DraftNotFound",
    "DraftStore",
    "DraftStoreError",
    "PassagePlanStore",
    "PlanConflict",
    "PlanNotFound",
    "PlanStoreError",
    "ExperienceMigrationPreview",
    "ExperienceProfileConflict",
    "ExperienceProfileError",
    "ExperienceProfileStore",
    "MigrationImpact",
    "preset_for_mode",
    "preview_experience_migration",
    "ProjectTransaction",
    "commit_typed_draft",
    "parent_fingerprint",
    "BrowserChoiceExpectation",
    "BrowserEvaluation",
    "BrowserFormExpectation",
    "BrowserGuardExpectation",
    "BrowserScenario",
    "evaluate_compile_artifact",
    "CapabilityCard",
    "CapabilityEvidence",
    "CapabilityIdentity",
    "StrategyCapability",
    "compatible_cards",
    "evidence_hashes_match",
    "load_capability_cards",
    "select_default_strategy",
    "source_hashes_match",
]
