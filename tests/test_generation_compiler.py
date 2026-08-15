import inspect

import pytest

from harness.generation.compiler import compile_passage_draft, render_passage_tw
from harness.generation.contracts import (
    ChoiceSlot,
    FilledChoiceSlot,
    FilledNarrativeSlot,
    NarrativeFill,
    NarrativeSlot,
    PassagePlan,
    StateEffect,
    StateCondition,
    StateOperation,
    StateReferencePart,
    TextPart,
    assemble_passage_draft,
)
from harness.models import ParsedChoice, ParsedInputField, ParsedInputOption, SkillCheck
from harness.passage import _legacy_render_passage_tw


def _kwargs(passage_type: str):
    choice = ParsedChoice(text="Continue", hint="next", state_writes={"$flag": True})
    kwargs = dict(
        passage_id="intro__01_test",
        arc_name="intro",
        prose="A deterministic passage.",
        choices=[choice],
        state_assigns={"$seen": True},
        media_slot_ids=["slot_fixture"],
        location="hall",
        characters=["Mira"],
        passage_type=passage_type,
        entry_condition="$ready",
        fallback_passage="Start",
        exits={"north": "NorthRoom"},
        event_odds=37,
        dialogue_npc="Mira",
        loop_vars=["$item"] if passage_type == "loop" else None,
        loop_collection="$inventory" if passage_type == "loop" else "",
        inputs=(
            [ParsedInputField(kind="textbox", var="$name", label="Name")]
            if passage_type == "form" else []
        ),
    )
    return kwargs


@pytest.mark.parametrize("passage_type", [
    "normal", "conditional", "event", "random_event", "random", "hub",
    "room", "dialogue", "loop", "form", "ending", "widget", "include",
])
def test_extracted_renderer_has_exact_legacy_byte_parity(passage_type):
    kwargs = _kwargs(passage_type)
    assert render_passage_tw(**kwargs) == _legacy_render_passage_tw(**kwargs)


@pytest.mark.parametrize("variant", [
    "plain_link",
    "gated_link",
    "skill_check",
    "plain_hub",
    "weighted_random",
    "dialogue_exit",
    "loop_capture",
    "loop_index",
    "room_fallback",
    "raw_widget",
])
def test_extracted_renderer_has_exact_legacy_byte_parity_for_distinguishing_branches(variant):
    passage_type = {
        "plain_hub": "hub",
        "weighted_random": "random",
        "dialogue_exit": "dialogue",
        "loop_capture": "loop",
        "loop_index": "loop",
        "room_fallback": "room",
        "raw_widget": "widget",
    }.get(variant, "normal")
    kwargs = _kwargs(passage_type)

    if variant == "plain_link":
        kwargs["choices"] = [ParsedChoice(text="Go", hint="next")]
    elif variant == "gated_link":
        kwargs["choices"] = [
            ParsedChoice(text="Unlock", hint="door", requires="$has_key", blocks="$tired")
        ]
    elif variant == "skill_check":
        kwargs["choices"] = [
            ParsedChoice(
                text="Climb",
                hint="wall",
                skill_check=SkillCheck(stat="$strength", dc=12),
            )
        ]
    elif variant == "plain_hub":
        kwargs["choices"] = [ParsedChoice(text="Visit", hint="market")]
    elif variant == "weighted_random":
        kwargs["choices"] = [ParsedChoice(text="Rare route", hint="rare", weight=3)]
    elif variant == "dialogue_exit":
        kwargs["choices"] = [ParsedChoice(text="Leave", hint="exit")]
    elif variant == "loop_capture":
        kwargs["choices"] = [
            ParsedChoice(text="Choose", hint="item", state_writes={"$picked": "$item"})
        ]
    elif variant == "loop_index":
        kwargs["loop_vars"] = ["$item", "$unused"]
    elif variant == "room_fallback":
        kwargs["exits"] = {"north": ""}
    elif variant == "raw_widget":
        kwargs["prose"] = '<<widget "fixture">>Raw body.<</widget>>'

    actual = render_passage_tw(**kwargs)
    assert actual == _legacy_render_passage_tw(**kwargs)

    branch_markers = {
        "plain_link": "[[Go|UNRESOLVED_choice0_next]]",
        "gated_link": "<<if ($has_key) && !($tired)>>",
        "skill_check": "(roll $strength vs DC 12)",
        "plain_hub": '<<if not hasVisited("UNRESOLVED_choice0_market")>>',
        "weighted_random": 'either("UNRESOLVED_choice0_rare", "UNRESOLVED_choice0_rare", "UNRESOLVED_choice0_rare")',
        "dialogue_exit": '<<goto "UNRESOLVED_choice0_exit">>',
        "loop_capture": "<<capture $item>>",
        "loop_index": "<<for _i, $item range $inventory>>",
        "room_fallback": "[[North|UNRESOLVED_choice0_north]]",
        "raw_widget": '<<widget "fixture">>Raw body.<</widget>>',
    }
    assert branch_markers[variant] in actual


@pytest.mark.parametrize("kind", [
    "textbox", "numberbox", "textarea", "checkbox", "radiobutton", "listbox", "cycle",
])
def test_form_input_variants_have_exact_legacy_byte_parity(kind):
    kwargs = _kwargs("form")
    kwargs["inputs"] = [ParsedInputField(
        kind=kind,
        var="$answer",
        label="Answer",
        default="7",
        unchecked_value="no",
        checked_value="yes",
        options=[ParsedInputOption(label="One", value="1", selected=True)],
        autofocus=True,
        autocheck=True,
        once=True,
        autoselect=True,
    )]
    assert render_passage_tw(**kwargs) == _legacy_render_passage_tw(**kwargs)


def test_compiler_module_has_no_project_or_network_dependencies():
    source = inspect.getsource(inspect.getmodule(render_passage_tw))
    assert "ProjectPaths" not in source
    assert "ollama" not in source.lower()
    assert "write_text(" not in source
    assert "open(" not in source


def test_typed_draft_compiles_with_exact_transactions_and_destinations():
    plan = PassagePlan(
        plan_id="typed_plan",
        revision=1,
        passage_mode="normal",
        narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),),
        choice_slots=(ChoiceSlot(id="leave", destination="intro__02_next"),),
        allowed_state_refs=("gold",),
        fixed_effects=(StateEffect(
            component_id="spend_gold",
            target="gold",
            operation=StateOperation.SUBTRACT,
            value=5,
        ),),
        required_components=("scene_effect:add_gold_-5",),
    )
    fill = NarrativeFill(
        plan_id=plan.plan_id,
        plan_revision=plan.revision,
        narrative=(FilledNarrativeSlot(
            slot_id="body",
            kind="paragraph",
            parts=(TextPart(text="You count "), StateReferencePart(target="gold")),
        ),),
        choices=(FilledChoiceSlot(slot_id="leave", text="Leave"),),
        summary="The player leaves.",
        beats=("Gold is counted.",),
    )
    draft = assemble_passage_draft(plan, fill)
    artifact = compile_passage_draft(
        draft,
        passage_id="intro__01_typed",
        arc_name="intro",
    )

    assert "<<print $gold>>" in artifact.twee_source
    assert "intro__02_next" in artifact.twee_source
    assert "UNRESOLVED_" not in artifact.twee_source
    assert "<<set $gold -= 5>>" in artifact.twee_source
    assert artifact.twee_source.index("<<set $gold -= 5>>") < artifact.twee_source.index(
        '<<link "Leave" "intro__02_next">>'
    )
    assert artifact.state_reads == ("gold",)
    assert artifact.state_writes == draft.resolved_effects
    assert artifact.link_targets == ("intro__02_next",)
    assert artifact.source_draft_fingerprint == draft.fingerprint()
    assert artifact.diagnostics == ()


def test_typed_plan_owns_conditional_fallback_and_random_event_odds():
    def compile_mode(mode, **plan_values):
        plan = PassagePlan(
            plan_id=f"{mode}_plan", revision=1, passage_mode=mode,
            narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),),
            choice_slots=(ChoiceSlot(id="continue", destination="next_scene"),),
            **plan_values,
        )
        fill = NarrativeFill(
            plan_id=plan.plan_id, plan_revision=1,
            narrative=(FilledNarrativeSlot(
                slot_id="body", kind="paragraph", parts=(TextPart(text="A scene."),),
            ),),
            choices=(FilledChoiceSlot(slot_id="continue", text="Continue"),),
            summary="A scene.", beats=("Continue.",),
        )
        return compile_passage_draft(
            assemble_passage_draft(plan, fill), passage_id="scene", arc_name="main",
        ).twee_source

    conditional = compile_mode(
        "conditional",
        allowed_state_refs=("door_open",),
        eligibility=(StateCondition(target="door_open", operation="truthy"),),
        fallback_passage="locked_door",
    )
    random_event = compile_mode("random_event", event_odds=37)

    assert '<<if not ($door_open)>><<goto "locked_door">><</if>>' in conditional
    assert "event_odds: 37" in random_event
    assert "<<if random(1,100) gt 37>><<goto previous()>><</if>>" in random_event


def test_compiler_is_deterministic_for_identical_draft():
    plan = PassagePlan(
        plan_id="deterministic_plan",
        revision=1,
        passage_mode="ending",
        narrative_slots=(NarrativeSlot(id="ending", kind="paragraph"),),
        choice_slots=(ChoiceSlot(id="restart", destination="Start", restart=True),),
    )
    fill = NarrativeFill(
        plan_id=plan.plan_id,
        plan_revision=plan.revision,
        narrative=(FilledNarrativeSlot(
            slot_id="ending", kind="paragraph", parts=(TextPart(text="The end."),),
        ),),
        choices=(FilledChoiceSlot(slot_id="restart", text="Restart"),),
        summary="The story ends.",
        beats=("The ending resolves.",),
    )
    draft = assemble_passage_draft(plan, fill)

    first = compile_passage_draft(draft, passage_id="ending", arc_name="finale")
    second = compile_passage_draft(draft, passage_id="ending", arc_name="finale")
    assert first == second
    assert first.fingerprint() == second.fingerprint()
    assert "<<run UI.restart()>>" in first.twee_source
    assert '<<link "Restart" "Start">>' not in first.twee_source


def test_model_text_cannot_interpolate_story_or_temporary_variables():
    plan = PassagePlan(
        plan_id="literal_variable_plan", revision=1, passage_mode="normal",
        narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),),
        choice_slots=(ChoiceSlot(id="continue", destination="next"),),
    )
    fill = NarrativeFill(
        plan_id=plan.plan_id, plan_revision=1,
        narrative=(FilledNarrativeSlot(
            slot_id="body", kind="paragraph",
            parts=(TextPart(text="Literal $secret and _private values."),),
        ),),
        choices=(FilledChoiceSlot(slot_id="continue", text="Continue"),),
        summary="Literal variables.", beats=("Text remains inert.",),
    )
    artifact = compile_passage_draft(
        assemble_passage_draft(plan, fill), passage_id="literal_variables", arc_name="tests"
    )
    assert "&#36;secret" in artifact.twee_source
    assert "&#95;private" in artifact.twee_source
    assert "Literal $secret" not in artifact.twee_source


def test_model_text_escaping_covers_markup_delimiters_and_preserves_unicode_and_newlines():
    plan = PassagePlan(
        plan_id="escaping_plan", revision=1, passage_mode="normal",
        narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),),
        choice_slots=(ChoiceSlot(id="continue", destination="next"),),
    )
    hostile = 'Quote " slash \\ link [[target]] </script> & snowman ☃\nNext line.'
    fill = NarrativeFill(
        plan_id=plan.plan_id, plan_revision=1,
        narrative=(FilledNarrativeSlot(
            slot_id="body", kind="paragraph", parts=(TextPart(text=hostile),),
        ),),
        choices=(FilledChoiceSlot(slot_id="continue", text="Continue"),),
        summary="Escaping fixture.", beats=("Markup remains inert.",),
    )
    source = compile_passage_draft(
        assemble_passage_draft(plan, fill), passage_id="escaping", arc_name="tests"
    ).twee_source

    assert "&quot;" in source
    assert "&#92;" in source
    assert "&#91;&#91;target&#93;&#93;" in source
    assert "&lt;/script&gt;" in source
    assert "&amp;" in source
    assert "snowman ☃\nNext line." in source
    assert "[[target]]" not in source
    assert "</script>" not in source
