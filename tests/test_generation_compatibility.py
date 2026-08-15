import pytest

from harness.generation import (
    build_legacy_passage_plan,
    compile_passage_draft,
    fill_to_model_output,
    model_output_to_draft,
    model_output_to_fill,
)
from harness.generation.contracts import NarrativeSlot, PassagePlan
from harness.models import ModelOutput, ParsedChoice


def _output():
    return ModelOutput(
        prose="The merchant counts {{state:gold}} before naming a price.",
        choices=[
            ParsedChoice(text="Buy", hint="Pay", state_writes={"$gold": 5}),
            ParsedChoice(text="Leave", hint="Walk away"),
        ],
        state={"$visited_market": True},
        summary="The merchant makes an offer.",
        beats=["An offer is made."],
    )


def test_legacy_plan_constructor_is_deterministic_and_story_driven():
    first = build_legacy_passage_plan(_output(), plan_id="legacy_plan")
    second = build_legacy_passage_plan(_output(), plan_id="legacy_plan")

    assert first == second
    assert first.fingerprint() == second.fingerprint()
    assert first.experience_profile_fingerprint
    assert [slot.id for slot in first.choice_slots] == ["choice_0", "choice_1"]
    assert set(first.allowed_state_refs) == {"gold", "visited_market"}


def test_model_output_crosses_one_typed_draft_boundary():
    output = _output()
    plan = build_legacy_passage_plan(
        output,
        plan_id="legacy_plan",
        choice_destinations=("market__buy", "market__exit"),
    )
    draft = model_output_to_draft(plan, output)
    artifact = compile_passage_draft(
        draft,
        passage_id="market__offer",
        arc_name="market",
    )

    assert draft.plan == plan
    assert artifact.link_targets == ("market__buy", "market__exit")
    assert "market__buy" in artifact.twee_source
    assert "market__exit" in artifact.twee_source
    assert "<<print $gold>>" in artifact.twee_source


def test_fill_legacy_projection_round_trips_copy_and_markers():
    plan = build_legacy_passage_plan(_output(), plan_id="legacy_plan")
    fill = model_output_to_fill(plan, _output())
    projection = fill_to_model_output(fill)

    assert projection.prose == _output().prose
    assert [choice.text for choice in projection.choices] == ["Buy", "Leave"]
    assert projection.summary == _output().summary


def test_legacy_adapter_rejects_cardinality_mismatch():
    output = _output()
    plan = build_legacy_passage_plan(output, plan_id="legacy_plan")
    bad = output.model_copy(update={"choices": output.choices[:-1]})
    with pytest.raises(ValueError, match="choice slot cardinality"):
        model_output_to_fill(plan, bad)

    two_slot_plan = PassagePlan(
        plan_id="two_slots",
        revision=1,
        passage_mode="normal",
        narrative_slots=(
            NarrativeSlot(id="first", kind="paragraph"),
            NarrativeSlot(id="second", kind="paragraph"),
        ),
        choice_slots=("choice_0", "choice_1"),
    )
    with pytest.raises(ValueError, match="narrative slot cardinality"):
        model_output_to_fill(two_slot_plan, output)
