import dataclasses
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from harness.generation.contracts import (
    CompileArtifact,
    ContractError,
    ContinuityProposal,
    DraftLifecycle,
    DraftRecord,
    EntityReferencePart,
    ExperienceMode,
    ExperienceOverride,
    ExperienceProfile,
    FilledChoiceSlot,
    FilledNarrativeSlot,
    GenerationProvenance,
    MechanicProposal,
    MechanicSlot,
    MechanicValue,
    NarrativeBlockKind,
    NarrativeFill,
    PassagePlan,
    StateOperation,
    StateReferencePart,
    TextPart,
    assemble_passage_draft,
)


CASES_PATH = Path(__file__).parents[1] / "model_benchmark" / "refactor_cases.json"


def _state_plan() -> PassagePlan:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    raw = next(item["plan"] for item in cases if item["id"] == "R1-STATE-REFERENCE")
    return PassagePlan.model_validate(raw)


def _fill(plan: PassagePlan) -> NarrativeFill:
    return NarrativeFill(
        plan_id=plan.plan_id,
        plan_revision=plan.revision,
        narrative=(FilledNarrativeSlot(
            slot_id=plan.narrative_slots[0].id,
            kind=plan.narrative_slots[0].kind,
            speaker=plan.narrative_slots[0].speaker,
            parts=(TextPart(text="The merchant counts "), StateReferencePart(target="gold")),
        ),),
        choices=tuple(
            FilledChoiceSlot(slot_id=slot.id, text=f"Choose {index}")
            for index, slot in enumerate(plan.choice_slots, start=1)
        ),
        summary="The merchant offers a choice.",
        beats=("An offer is made.",),
    )


def test_all_24_benchmark_plan_payloads_validate_without_benchmark_imports():
    raw_cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    plans = [PassagePlan.model_validate(item["plan"]) for item in raw_cases]

    assert len(plans) == 24
    assert len({plan.plan_id for plan in plans}) == 24
    assert all(len(plan.fingerprint()) == 64 for plan in plans)


def test_contract_package_never_imports_benchmark_code():
    root = Path(__file__).parents[1] / "harness" / "generation"
    for path in root.glob("*.py"):
        assert "model_benchmark" not in path.read_text(encoding="utf-8")


def test_fingerprint_is_canonical_and_round_trips():
    plan = _state_plan()
    differently_ordered = dict(reversed(list(plan.model_dump(mode="json").items())))
    restored = PassagePlan.model_validate(differently_ordered)

    assert restored.fingerprint() == plan.fingerprint()
    assert PassagePlan.model_validate_json(plan.model_dump_json()).fingerprint() == plan.fingerprint()


def test_continuity_proposals_must_cite_slots_owned_by_the_plan():
    plan = _state_plan()
    fill = _fill(plan).model_copy(update={
        "continuity_proposals": (
            ContinuityProposal(key="merchant_rumor", value="The merchant fears bells.", evidence_slot_ids=("missing",)),
        ),
    })
    with pytest.raises(ContractError, match="unknown evidence slots"):
        assemble_passage_draft(plan, fill)


def test_experience_profiles_use_stable_mode_values_and_safe_defaults():
    story = ExperienceProfile.story_driven()
    hybrid = ExperienceProfile.hybrid()
    sandbox = ExperienceProfile.sandbox()

    assert [item.mode.value for item in (story, hybrid, sandbox)] == [
        "story_driven", "hybrid", "sandbox",
    ]
    assert story.ending_policy.value == "required"
    assert story.story_guidance.value == "directed"
    assert hybrid.encounter_reuse is True
    assert sandbox.goal_model.value == "player_directed"
    assert sandbox.character_simulation.value == "full_agendas"
    assert sandbox.main_plot_required is False
    assert ExperienceProfile.model_validate_json(story.model_dump_json()).fingerprint() == story.fingerprint()


def test_experience_profile_applies_only_the_named_override_scope():
    profile = ExperienceProfile.hybrid().model_copy(update={
        "overrides": (
            ExperienceOverride(
                scope_kind="arc",
                scope_id="dream_arc",
                narrative_pressure=0.9,
                story_guidance="directed",
            ),
        ),
    })

    effective = profile.effective_for("arc", "dream_arc")
    untouched = profile.effective_for("arc", "other_arc")

    assert effective.narrative_pressure == 0.9
    assert effective.story_guidance.value == "directed"
    assert effective.overrides == ()
    assert untouched.narrative_pressure == profile.narrative_pressure


def test_contracts_are_frozen_and_forbid_extra_fields():
    plan = _state_plan()
    with pytest.raises(ValidationError):
        PassagePlan.model_validate({**plan.model_dump(), "model_authority": True})
    with pytest.raises(ValidationError):
        plan.revision = 2


@pytest.mark.parametrize("revision", [True, 0, -1])
def test_plan_rejects_invalid_revisions(revision):
    raw = _state_plan().model_dump(mode="json")
    raw["revision"] = revision
    with pytest.raises(ValidationError):
        PassagePlan.model_validate(raw)


def test_plan_rejects_duplicate_authority():
    raw = _state_plan().model_dump(mode="json")
    raw["choice_slots"].append(raw["choice_slots"][0])
    with pytest.raises(ValidationError, match="duplicate choice slot"):
        PassagePlan.model_validate(raw)


def test_assembly_accepts_exact_authorized_fill():
    plan = _state_plan()
    fill = _fill(plan)
    draft = assemble_passage_draft(plan, fill)

    assert draft.plan == plan
    assert draft.fill == fill
    assert draft.resolved_required_components == plan.required_components


def test_assembly_rejects_stale_plan_revision():
    plan = _state_plan()
    fill = _fill(plan).model_copy(update={"plan_revision": plan.revision + 1})
    with pytest.raises(ContractError, match="stale"):
        assemble_passage_draft(plan, fill)


def test_assembly_rejects_missing_and_unknown_slots():
    plan = _state_plan()
    fill = _fill(plan)
    missing = fill.model_copy(update={"choices": fill.choices[:-1]})
    with pytest.raises(ContractError, match="missing choice"):
        assemble_passage_draft(plan, missing)
    unknown_choice = fill.choices[0].model_copy(update={"slot_id": "model_added"})
    unknown = fill.model_copy(update={"choices": (unknown_choice, *fill.choices[1:])})
    with pytest.raises(ContractError, match="unknown choice"):
        assemble_passage_draft(plan, unknown)


def test_assembly_rejects_wrong_kind_and_speaker():
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    raw = next(item["plan"] for item in cases if item["id"] == "R2-DIALOGUE-THOUGHT")
    plan = PassagePlan.model_validate(raw)
    narrative = tuple(
        FilledNarrativeSlot(
            slot_id=slot.id,
            kind=slot.kind,
            speaker=slot.speaker,
            parts=(TextPart(text="A line of prose."),),
        )
        for slot in plan.narrative_slots
    )
    fill = NarrativeFill(
        plan_id=plan.plan_id,
        plan_revision=plan.revision,
        narrative=narrative,
        choices=tuple(FilledChoiceSlot(slot_id=slot.id, text="Continue") for slot in plan.choice_slots),
        summary="An interrogation continues.",
        beats=("A question is asked.",),
    )
    wrong_kind = fill.model_copy(update={
        "narrative": (narrative[0].model_copy(update={"kind": NarrativeBlockKind.THOUGHT}), *narrative[1:]),
    })
    with pytest.raises(ContractError, match="wrong kind"):
        assemble_passage_draft(plan, wrong_kind)
    wrong_speaker = fill.model_copy(update={
        "narrative": (narrative[0].model_copy(update={"speaker": "Impostor"}), *narrative[1:]),
    })
    with pytest.raises(ContractError, match="wrong speaker"):
        assemble_passage_draft(plan, wrong_speaker)


def test_assembly_rejects_unauthorized_cross_typed_references():
    plan = _state_plan()
    fill = _fill(plan)
    slot = fill.narrative[0]
    unauthorized = slot.model_copy(update={"parts": (EntityReferencePart(target="gold"),)})
    bad_fill = fill.model_copy(update={"narrative": (unauthorized,)})
    with pytest.raises(ContractError, match="unauthorized entity"):
        assemble_passage_draft(plan, bad_fill)


def test_required_mechanic_slots_must_resolve_with_allowlisted_values():
    plan = _state_plan().model_copy(update={
        "mechanic_slots": (MechanicSlot(
            id="price_change",
            required=True,
            allowed_operations=(StateOperation.SUBTRACT,),
            allowed_targets=("gold",),
        ),),
    })
    fill = _fill(plan)
    with pytest.raises(ContractError, match="unresolved required mechanic"):
        assemble_passage_draft(plan, fill)
    proposal = MechanicProposal(
        plan_id=plan.plan_id,
        plan_revision=plan.revision,
        values=(MechanicValue(
            slot_id="price_change",
            operation=StateOperation.SUBTRACT,
            target="gold",
            value=5,
        ),),
    )
    assert len(assemble_passage_draft(plan, fill, proposal).resolved_effects) == 1
    bad = proposal.model_copy(update={
        "values": (proposal.values[0].model_copy(update={"target": "health"}),),
    })
    with pytest.raises(ContractError, match="unauthorized mechanic target"):
        assemble_passage_draft(plan, fill, bad)


def test_compile_artifact_and_draft_record_round_trip():
    draft = assemble_passage_draft(_state_plan(), _fill(_state_plan()))
    artifact = CompileArtifact(
        twee_source=":: Test\nText",
        compiler_version="1",
        source_draft_fingerprint=draft.fingerprint(),
    )
    record = DraftRecord(
        generation_id="generation_1",
        draft=draft,
        lifecycle_state=DraftLifecycle.VALIDATED,
        provenance=GenerationProvenance(seed=42, model_name="fixture"),
        compile_artifact=artifact,
    )

    restored = DraftRecord.model_validate_json(record.model_dump_json())
    assert restored == record
    assert restored.compile_artifact.source_draft_fingerprint == draft.fingerprint()
