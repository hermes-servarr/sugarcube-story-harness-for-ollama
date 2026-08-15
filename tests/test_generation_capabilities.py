import asyncio
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from harness.generation.capabilities import (
    CapabilityCard,
    CapabilityIdentity,
    MECHANICAL_GATE_NAMES,
    StrategyCapability,
    compatible_cards,
    evidence_hashes_match,
    load_capability_cards,
    select_default_strategy,
    source_hashes_match,
)
from harness.server import app as server_app


ROOT = Path(__file__).resolve().parents[1]
CARD_DIRECTORY = ROOT / "benchmark_outputs" / "capability_cards"
OBSERVATION_WINDOW = datetime(2026, 8, 15, tzinfo=timezone.utc)


def _card(version: str = "v2") -> CapabilityCard:
    cards = load_capability_cards(CARD_DIRECTORY)
    by_id = {card.card_id: card for card in cards}
    assert set(by_id) == {
        "qwen35-9b-q4_k_m-mechanical-v1",
        "qwen35-9b-q4_k_m-mechanical-v2",
    }
    return by_id[f"qwen35-9b-q4_k_m-mechanical-{version}"]


def _current_source_hashes(card):
    return {
        relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        for relative in card.source_sha256
    }


def _card_with_report(card, tmp_path, report):
    relative_report = Path(card.evidence.confirmation_report)
    target_report = tmp_path / relative_report
    target_report.parent.mkdir(parents=True, exist_ok=True)
    target_report.write_text(json.dumps(report, sort_keys=True), encoding="utf-8")
    for relative in (
        card.evidence.parent_manifest,
        card.evidence.browser_manifest,
        str(Path(report["parent_path"]) / "results_internal.jsonl"),
        str(Path(report["child_path"]) / "results_internal.jsonl"),
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    evidence = card.evidence.model_copy(update={
        "confirmation_report_sha256": hashlib.sha256(target_report.read_bytes()).hexdigest(),
    })
    return card.model_copy(update={"evidence": evidence})


def test_compiler_change_preserves_evidence_but_invalidates_historical_v1_card():
    card = _card("v1")
    assert evidence_hashes_match(card, ROOT)
    assert not source_hashes_match(card, ROOT)
    assert compatible_cards(
        (card,), card.identity, repository_root=ROOT, now=OBSERVATION_WINDOW,
    ) == ()


def test_evidence_validation_rechecks_bound_result_files(tmp_path):
    card = _card()
    report = json.loads((ROOT / card.evidence.confirmation_report).read_text(encoding="utf-8"))
    relatives = [
        card.evidence.confirmation_report,
        card.evidence.parent_manifest,
        card.evidence.browser_manifest,
        str(Path(report["parent_path"]) / "results_internal.jsonl"),
        str(Path(report["child_path"]) / "results_internal.jsonl"),
    ]
    for relative in relatives:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    assert evidence_hashes_match(card, tmp_path)
    parent_results = tmp_path / report["parent_path"] / "results_internal.jsonl"
    parent_results.write_bytes(parent_results.read_bytes() + b"\n")
    assert not evidence_hashes_match(card, tmp_path)


@pytest.mark.parametrize("failed_gate", (None, *MECHANICAL_GATE_NAMES))
def test_mechanical_claim_must_clear_every_frozen_confirmation_gate(
    tmp_path, failed_gate,
):
    card = _card()
    report_path = ROOT / card.evidence.confirmation_report
    report = json.loads(report_path.read_text(encoding="utf-8"))
    key = failed_gate or "mechanical_and_latency_gates_pass"
    report["automated_promotion_gates"]["flat_fill"][key] = False
    changed = _card_with_report(card, tmp_path, report)
    assert not evidence_hashes_match(changed, tmp_path)


@pytest.mark.parametrize(("field", "value"), (
    ("schema_version", "promotion-confirmation-v0"),
    ("legacy_architecture", "typed_fill"),
    ("repeat_count", 9),
    ("required_margin_percentage_points", 4.99),
))
def test_mechanical_claim_requires_frozen_confirmation_policy(
    tmp_path, field, value,
):
    card = _card()
    report = json.loads(
        (ROOT / card.evidence.confirmation_report).read_text(encoding="utf-8")
    )
    report[field] = value
    changed = _card_with_report(card, tmp_path, report)
    assert not evidence_hashes_match(changed, tmp_path)


def test_mechanical_claim_rechecks_zero_call_browser_manifest(tmp_path):
    card = _card()
    report = json.loads(
        (ROOT / card.evidence.confirmation_report).read_text(encoding="utf-8")
    )
    unchanged = _card_with_report(card, tmp_path, report)
    manifest_path = tmp_path / card.evidence.browser_manifest
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["browser_rescore"]["model_calls"] = 1
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    evidence = unchanged.evidence.model_copy(update={
        "browser_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    })
    changed = unchanged.model_copy(update={"evidence": evidence})
    assert not evidence_hashes_match(changed, tmp_path)


def test_mechanical_only_card_cannot_promote_a_default():
    frozen = _card()
    card = frozen.model_copy(update={"source_sha256": _current_source_hashes(frozen)})
    assert all(item.mechanically_qualified for item in card.strategies)
    assert all(item.narrative_review == "not_assessed" for item in card.strategies)
    assert select_default_strategy(
        (card,), card.identity, repository_root=ROOT, now=OBSERVATION_WINDOW,
    ) == "legacy_delimited"


def test_exact_identity_source_and_age_changes_invalidate_routing():
    frozen = _card()
    card = frozen.model_copy(update={"source_sha256": _current_source_hashes(frozen)})
    wrong_identity = card.identity.model_copy(update={"ollama_version": "0.32.6"})
    assert compatible_cards(
        (card,), wrong_identity, repository_root=ROOT, now=OBSERVATION_WINDOW,
    ) == ()
    assert compatible_cards(
        (card,), card.identity, repository_root=ROOT,
        now=datetime(2026, 11, 13, tzinfo=timezone.utc),
    ) == ()
    changed_source = card.model_copy(update={
        "source_sha256": {**card.source_sha256, "harness/generation/compiler.py": "0" * 64}
    })
    assert compatible_cards(
        (changed_source,), card.identity, repository_root=ROOT, now=OBSERVATION_WINDOW,
    ) == ()


def test_fully_reviewed_exact_card_can_route_by_preference(tmp_path):
    card = _card()
    confirmation = json.loads((ROOT / card.evidence.confirmation_report).read_text(encoding="utf-8"))
    for relative in (
        card.evidence.confirmation_report,
        card.evidence.parent_manifest,
        card.evidence.browser_manifest,
        str(Path(confirmation["parent_path"]) / "results_internal.jsonl"),
        str(Path(confirmation["child_path"]) / "results_internal.jsonl"),
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    source_hashes = {}
    for relative in card.source_sha256:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
        source_hashes[relative] = hashlib.sha256(target.read_bytes()).hexdigest()
    dimensions = (
        "coherence_with_immediate_context", "continuity_accuracy",
        "specificity_over_generic_filler", "distinct_meaningful_choices",
        "dialogue_voice", "pacing_readability", "tone_style_compliance",
    )
    reviewed = []
    for item in card.strategies:
        report_path = Path("benchmark_outputs") / f"narrative_{item.strategy}.json"
        control = "legacy_json"
        report = {
            "schema_version": "narrative-review-results-v1",
            "source_results_sha256": confirmation["child_results_sha256"],
            "architectures": [item.strategy, control],
            "completed_items": 30,
            "preference_counts": {item.strategy: 16, control: 14, "tie": 0},
            "dimension_results": {
                dimension: {
                    item.strategy: {"mean": 4.0}, control: {"mean": 4.0},
                    f"paired_delta_{item.strategy}_minus_{control}": 0.0,
                }
                for dimension in dimensions
            },
        }
        target = tmp_path / report_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, sort_keys=True), encoding="utf-8")
        reviewed.append(item.model_copy(update={
            "narrative_review": "pass",
            "default_eligible": True,
            "narrative_report": report_path.as_posix(),
            "narrative_report_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        }))
    eligible = card.model_copy(update={
        "source_sha256": source_hashes,
        "strategies": tuple(reviewed),
    })
    assert select_default_strategy(
        (eligible,), eligible.identity, repository_root=tmp_path, now=OBSERVATION_WINDOW,
    ) == "flat_fill"
    assert select_default_strategy(
        (eligible,), eligible.identity, repository_root=tmp_path,
        preference=("typed_fill", "flat_fill"), now=OBSERVATION_WINDOW,
    ) == "typed_fill"


def test_default_eligibility_cannot_bypass_narrative_review():
    with pytest.raises(ValidationError, match="narrative pass"):
        StrategyCapability(
            strategy="flat_fill",
            mechanically_qualified=True,
            narrative_review="not_assessed",
            default_eligible=True,
        )


def test_assessed_narrative_claim_requires_hashed_report():
    with pytest.raises(ValidationError, match="hashed review report"):
        StrategyCapability(
            strategy="flat_fill",
            mechanically_qualified=True,
            narrative_review="pass",
        )


def test_identity_rejects_non_exact_digests():
    with pytest.raises(ValidationError):
        CapabilityIdentity(
            model_digest="unknown",
            quantization="Q4_K_M",
            prompt_profile_sha256="0" * 64,
            ollama_version="0.32.5",
            contract_schema_version=1,
            compiler_version="generation-compiler-v1",
            generation_settings_sha256="0" * 64,
        )


def test_capability_api_exposes_valid_mechanical_only_card():
    payload = asyncio.run(server_app.get_capability_cards())
    response = server_app.CapabilityCardsResponse.model_validate(payload)
    assert len(response.cards) == 2
    by_id = {item.card.card_id: item for item in response.cards}
    historical = by_id["qwen35-9b-q4_k_m-mechanical-v1"]
    assert historical.evidence_valid is True
    assert historical.source_valid is False
    current = by_id["qwen35-9b-q4_k_m-mechanical-v2"]
    assert current.evidence_valid is True
    assert current.source_valid is True
    assert current.expired is False
    assert all(not strategy.default_eligible for strategy in current.card.strategies)
