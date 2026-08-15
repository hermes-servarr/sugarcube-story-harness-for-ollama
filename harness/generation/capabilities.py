"""Exact-evidence capability cards and conservative default routing."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .contracts import StrictFrozenModel


StrategyName = Literal["legacy_delimited", "legacy_json", "typed_fill", "flat_fill"]
NARRATIVE_DIMENSIONS = {
    "coherence_with_immediate_context",
    "continuity_accuracy",
    "specificity_over_generic_filler",
    "distinct_meaningful_choices",
    "dialogue_voice",
    "pacing_readability",
    "tone_style_compliance",
}
MECHANICAL_GATE_NAMES = (
    "semantic_accepted_compile_100_percent",
    "normalized_handoff_at_least_90_percent",
    "state_transaction_at_least_90_percent",
    "compiled_playability_at_least_95_percent",
    "request_playable_margin_exceeded",
    "p95_latency_within_25_percent",
)
MECHANICAL_SOURCE_FILENAMES = frozenset({
    "compiler.py",
    "contracts.py",
    "browser_evaluator.py",
    "capabilities.py",
    "models.py",
    "parsers.py",
    "refactor_benchmark.py",
    "refactor_cases.json",
    "scoring.py",
    "browser_rescore.py",
    "promotion_confirmation.py",
    "capability_card.py",
})


class CapabilityIdentity(StrictFrozenModel):
    model_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    quantization: str = Field(min_length=1)
    prompt_profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    ollama_version: str = Field(min_length=1)
    contract_schema_version: int = Field(ge=1)
    compiler_version: str = Field(min_length=1)
    generation_settings_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CapabilityEvidence(StrictFrozenModel):
    confirmation_report: str
    confirmation_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parent_manifest: str
    parent_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    browser_manifest: str
    browser_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class StrategyCapability(StrictFrozenModel):
    strategy: StrategyName
    mechanically_qualified: bool
    narrative_review: Literal["not_assessed", "pass", "fail"]
    default_eligible: bool = False
    narrative_report: str = ""
    narrative_report_sha256: str = Field(default="", pattern=r"^(?:|[0-9a-f]{64})$")
    notes: str = ""

    @model_validator(mode="after")
    def eligible_requires_all_gates(self) -> "StrategyCapability":
        if self.default_eligible and (
            not self.mechanically_qualified or self.narrative_review != "pass"
        ):
            raise ValueError(
                "default eligibility requires mechanical qualification and narrative pass"
            )
        has_report = bool(self.narrative_report and self.narrative_report_sha256)
        if self.narrative_review == "not_assessed" and has_report:
            raise ValueError("unassessed narrative capability cannot bind a review report")
        if self.narrative_review != "not_assessed" and not has_report:
            raise ValueError("assessed narrative capability requires a hashed review report")
        return self


class CapabilityCard(StrictFrozenModel):
    card_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,127}$")
    observed_at: datetime
    valid_until: datetime
    identity: CapabilityIdentity
    evidence: CapabilityEvidence
    source_sha256: dict[str, str]
    strategies: tuple[StrategyCapability, ...]

    @model_validator(mode="after")
    def validate_card(self) -> "CapabilityCard":
        if self.observed_at.tzinfo is None or self.valid_until.tzinfo is None:
            raise ValueError("capability timestamps must include a timezone")
        if self.valid_until <= self.observed_at:
            raise ValueError("valid_until must be after observed_at")
        if self.valid_until - self.observed_at > timedelta(days=90):
            raise ValueError("capability validity cannot exceed 90 days")
        names = [item.strategy for item in self.strategies]
        if len(names) != len(set(names)):
            raise ValueError("capability strategies must be unique")
        for path, digest in self.source_sha256.items():
            if not path or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise ValueError("source hashes require a path and lowercase SHA-256")
        return self

    def fingerprint(self) -> str:
        value = self.model_dump(mode="json")
        for strategy in value["strategies"]:
            if not strategy.get("narrative_report"):
                strategy.pop("narrative_report", None)
                strategy.pop("narrative_report_sha256", None)
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_capability_cards(directory: Path) -> tuple[CapabilityCard, ...]:
    cards = []
    if directory.is_dir():
        for path in sorted(directory.glob("*.json")):
            cards.append(CapabilityCard.model_validate_json(path.read_text(encoding="utf-8")))
    ids = [card.card_id for card in cards]
    if len(ids) != len(set(ids)):
        raise ValueError("capability card IDs must be unique")
    return tuple(cards)


def source_hashes_match(card: CapabilityCard, repository_root: Path) -> bool:
    if (
        any(item.mechanically_qualified for item in card.strategies)
        and not MECHANICAL_SOURCE_FILENAMES.issubset(
            Path(relative).name for relative in card.source_sha256
        )
    ):
        return False
    for relative, expected in card.source_sha256.items():
        path = _repository_file(repository_root, relative)
        if path is None:
            return False
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            return False
    return True


def evidence_hashes_match(card: CapabilityCard, repository_root: Path) -> bool:
    evidence = card.evidence
    for relative, expected in (
        (evidence.confirmation_report, evidence.confirmation_report_sha256),
        (evidence.parent_manifest, evidence.parent_manifest_sha256),
        (evidence.browser_manifest, evidence.browser_manifest_sha256),
    ):
        path = _repository_file(repository_root, relative)
        if path is None:
            return False
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            return False
    report_path = _repository_file(repository_root, evidence.confirmation_report)
    if report_path is None:
        return False
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(report, dict):
        return False
    margin = report.get("required_margin_percentage_points")
    repeat_count = report.get("repeat_count")
    if (
        report.get("schema_version") != "promotion-confirmation-v1"
        or report.get("legacy_architecture") != "legacy_json"
        or not isinstance(repeat_count, int)
        or isinstance(repeat_count, bool)
        or repeat_count < 10
        or not isinstance(margin, (int, float))
        or isinstance(margin, bool)
        or margin < 5.0
    ):
        return False
    bound_analyzer = next((
        digest for relative, digest in card.source_sha256.items()
        if Path(relative).name == "promotion_confirmation.py"
    ), None)
    if (
        bound_analyzer is not None
        and report.get("analyzer_source_sha256") != bound_analyzer
    ):
        return False
    expected_parent_manifest = (Path(str(report.get("parent_path", ""))) / "run_manifest.json").as_posix()
    expected_browser_manifest = (Path(str(report.get("child_path", ""))) / "run_manifest.json").as_posix()
    if expected_parent_manifest != evidence.parent_manifest or expected_browser_manifest != evidence.browser_manifest:
        return False
    for run_key, digest_key in (
        ("parent_path", "parent_results_sha256"),
        ("child_path", "child_results_sha256"),
    ):
        results_path = _repository_file(
            repository_root,
            (Path(str(report.get(run_key, ""))) / "results_internal.jsonl").as_posix(),
        )
        expected = report.get(digest_key)
        if (
            results_path is None
            or not results_path.is_file()
            or not isinstance(expected, str)
            or hashlib.sha256(results_path.read_bytes()).hexdigest() != expected
        ):
            return False
    if (
        report.get("model_calls") != 0
        or report.get("generation_fields_preserved") is not True
        or report.get("compatibility_fields_verified") is not True
    ):
        return False
    browser_manifest_path = _repository_file(repository_root, evidence.browser_manifest)
    if browser_manifest_path is None:
        return False
    try:
        browser_manifest = json.loads(browser_manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    browser_rescore = (
        browser_manifest.get("browser_rescore")
        if isinstance(browser_manifest, dict) else None
    )
    if (
        not isinstance(browser_rescore, dict)
        or browser_rescore.get("model_calls") != 0
        or browser_rescore.get("source_results_sha256")
        != report.get("parent_results_sha256")
    ):
        return False
    gates = report.get("automated_promotion_gates")
    if not isinstance(gates, dict):
        return False
    for strategy in card.strategies:
        if strategy.mechanically_qualified:
            strategy_gates = gates.get(strategy.strategy)
            if (
                not isinstance(strategy_gates, dict)
                or strategy_gates.get("mechanical_and_latency_gates_pass") is not True
                or any(strategy_gates.get(name) is not True for name in MECHANICAL_GATE_NAMES)
            ):
                return False
        if strategy.narrative_review != "not_assessed":
            narrative_path = _repository_file(repository_root, strategy.narrative_report)
            if (
                narrative_path is None
                or not narrative_path.is_file()
                or hashlib.sha256(narrative_path.read_bytes()).hexdigest() != strategy.narrative_report_sha256
            ):
                return False
            try:
                narrative = json.loads(narrative_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return False
            if not _narrative_report_supports(
                narrative,
                strategy.strategy,
                expected_result_hashes={
                    str(report.get("parent_results_sha256", "")),
                    str(report.get("child_results_sha256", "")),
                },
                expected_pass=strategy.narrative_review == "pass",
            ):
                return False
    return True


def _repository_file(repository_root: Path, relative: str) -> Path | None:
    """Resolve a card path without permitting evidence to escape the repository."""
    root = repository_root.resolve()
    try:
        path = (root / relative).resolve()
        path.relative_to(root)
    except (OSError, ValueError):
        return None
    return path


def _narrative_report_supports(
    report: object,
    strategy: str,
    *,
    expected_result_hashes: set[str],
    expected_pass: bool,
) -> bool:
    if not isinstance(report, dict) or report.get("schema_version") != "narrative-review-results-v1":
        return False
    if report.get("source_results_sha256") not in expected_result_hashes:
        return False
    architectures = report.get("architectures")
    if not isinstance(architectures, list) or strategy not in architectures or len(architectures) != 2:
        return False
    controls = [item for item in architectures if item != strategy]
    if len(controls) != 1 or controls[0] not in {"legacy_json", "legacy_delimited"}:
        return False
    if not isinstance(report.get("completed_items"), int) or report["completed_items"] < 30:
        return False
    control = controls[0]
    dimensions = report.get("dimension_results")
    if not isinstance(dimensions, dict) or set(dimensions) != NARRATIVE_DIMENSIONS:
        return False
    delta_key = f"paired_delta_{strategy}_minus_{control}"
    dimension_pass = all(
        isinstance(result, dict)
        and isinstance(result.get(delta_key), (int, float))
        and not isinstance(result.get(delta_key), bool)
        and result[delta_key] >= -0.25
        for result in dimensions.values()
    )
    preferences = report.get("preference_counts")
    preference_pass = (
        isinstance(preferences, dict)
        and isinstance(preferences.get(strategy), int)
        and isinstance(preferences.get(control), int)
        and preferences[control] - preferences[strategy] <= 3
    )
    return (dimension_pass and preference_pass) is expected_pass


def compatible_cards(
    cards: tuple[CapabilityCard, ...],
    identity: CapabilityIdentity,
    *,
    repository_root: Path,
    now: datetime | None = None,
) -> tuple[CapabilityCard, ...]:
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("routing time must include a timezone")
    matches = [
        card for card in cards
        if card.identity == identity
        and card.observed_at <= instant <= card.valid_until
        and source_hashes_match(card, repository_root)
        and evidence_hashes_match(card, repository_root)
    ]
    return tuple(sorted(matches, key=lambda card: card.observed_at, reverse=True))


def select_default_strategy(
    cards: tuple[CapabilityCard, ...],
    identity: CapabilityIdentity,
    *,
    repository_root: Path,
    preference: tuple[StrategyName, ...] = ("flat_fill", "typed_fill"),
    now: datetime | None = None,
) -> StrategyName:
    """Choose only a fully eligible exact match; otherwise preserve legacy."""
    for card in compatible_cards(
        cards, identity, repository_root=repository_root, now=now,
    ):
        by_name = {item.strategy: item for item in card.strategies}
        for strategy in preference:
            capability = by_name.get(strategy)
            if capability is not None and capability.default_eligible:
                return strategy
    return "legacy_delimited"


__all__ = [
    "CapabilityCard",
    "CapabilityEvidence",
    "CapabilityIdentity",
    "MECHANICAL_GATE_NAMES",
    "MECHANICAL_SOURCE_FILENAMES",
    "StrategyCapability",
    "compatible_cards",
    "evidence_hashes_match",
    "load_capability_cards",
    "select_default_strategy",
    "source_hashes_match",
]
