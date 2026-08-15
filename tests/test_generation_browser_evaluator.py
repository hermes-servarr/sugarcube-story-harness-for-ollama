import os
import threading
from pathlib import Path

import pytest

import harness.generation.browser_evaluator as browser_evaluator_module

from harness.generation import (
    BrowserChoiceExpectation,
    BrowserFormExpectation,
    BrowserGuardExpectation,
    BrowserScenario,
    ChoiceSlot,
    FormField,
    FormOption,
    LoopBinding,
    NarrativeFill,
    NarrativeSlot,
    PassagePlan,
    RouteSlot,
    StateCondition,
    StateEffect,
    StateOperation,
    assemble_passage_draft,
    compile_passage_draft,
    evaluate_compile_artifact,
)


def _runtime_paths():
    tweego = Path(os.environ.get("TWEEGO_BIN", ""))
    formats = Path(os.environ.get("TWEEGO_FORMATS", ""))
    if not tweego.is_file() or not formats.is_dir():
        pytest.skip("set TWEEGO_BIN and TWEEGO_FORMATS to run browser gates")
    return tweego, formats


def test_writable_temp_environment_serializes_concurrent_callers(monkeypatch):
    for key in ("TMPDIR", "TEMP", "TMP"):
        monkeypatch.setenv(key, "original-temp")
    monkeypatch.setattr(
        browser_evaluator_module.tempfile,
        "gettempdir",
        lambda: f"temp-{threading.current_thread().name}",
    )
    first_entered = threading.Event()
    second_started = threading.Event()
    second_entered = threading.Event()
    release_first = threading.Event()
    observed: list[tuple[str, tuple[str | None, ...]]] = []
    errors: list[BaseException] = []

    def run_first() -> None:
        try:
            with browser_evaluator_module._writable_temp_environment():
                observed.append(("first", tuple(os.environ.get(key) for key in ("TMPDIR", "TEMP", "TMP"))))
                first_entered.set()
                if not release_first.wait(5):
                    raise AssertionError("timed out waiting to release first caller")
        except BaseException as error:  # pragma: no cover - surfaced below
            errors.append(error)

    def run_second() -> None:
        try:
            if not first_entered.wait(5):
                raise AssertionError("first caller did not enter")
            second_started.set()
            with browser_evaluator_module._writable_temp_environment():
                observed.append(("second", tuple(os.environ.get(key) for key in ("TMPDIR", "TEMP", "TMP"))))
                second_entered.set()
        except BaseException as error:  # pragma: no cover - surfaced below
            errors.append(error)

    first = threading.Thread(target=run_first, name="first")
    second = threading.Thread(target=run_second, name="second")
    first.start()
    assert first_entered.wait(5)
    second.start()
    assert second_started.wait(5)
    try:
        assert not second_entered.wait(0.1)
    finally:
        release_first.set()
    first.join(5)
    second.join(5)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors == []
    assert observed == [
        ("first", ("temp-first",) * 3),
        ("second", ("temp-second",) * 3),
    ]
    assert tuple(os.environ.get(key) for key in ("TMPDIR", "TEMP", "TMP")) == (
        "original-temp",
    ) * 3


@pytest.mark.e2e
def test_production_artifact_executes_guard_effect_continuity_and_safe_text():
    tweego, formats = _runtime_paths()
    hostile = (
        "Café Æsir — 'glass & snow' Visible $secret and _private. "
        "<script>window.__HARNESS_HOSTILE_EXECUTED=true</script> "
        "<<set $gold to 999>> [[Hack|evil]]"
    )
    plan = PassagePlan(
        plan_id="browser_plan",
        revision=1,
        passage_mode="normal",
        narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),),
        choice_slots=(
            ChoiceSlot(
                id="go",
                destination="target_go",
                conditions=(StateCondition(target="has_key", operation="truthy"),),
                effects=(StateEffect(
                    component_id="spend_gold",
                    target="gold",
                    operation=StateOperation.SUBTRACT,
                    value=2,
                ),),
            ),
            ChoiceSlot(id="wait", destination="target_wait"),
        ),
        allowed_state_refs=("has_key", "gold"),
        fixed_effects=(StateEffect(
            component_id="arrival_cost",
            target="gold",
            operation=StateOperation.ADD,
            value=-1,
        ),),
    )
    fill = NarrativeFill.model_validate({
        "plan_id": plan.plan_id,
        "plan_revision": plan.revision,
        "narrative": [{
            "slot_id": "body",
            "kind": "paragraph",
            "speaker": "",
            "parts": [{"kind": "text", "text": hostile}],
        }],
        "choices": [
            {"slot_id": "go", "text": "Go now", "hint": "Use the key."},
            {"slot_id": "wait", "text": "Return it to Thorne's study", "hint": "Remain here."},
        ],
        "summary": "A guarded route.",
        "beats": ["The player decides."],
    })
    draft = assemble_passage_draft(plan, fill)
    artifact = compile_passage_draft(
        draft,
        passage_id="browser_start",
        arc_name="browser",
    )
    evaluation = evaluate_compile_artifact(
        artifact,
        BrowserScenario(
            passage_id="browser_start",
            expected_text=("Café Æsir — 'glass & snow' Visible $secret and _private.", "Go now", "Return it to Thorne's study"),
            initial_state=(("gold", 10), ("has_key", True)),
            choices=(
                BrowserChoiceExpectation(
                    label="Go now",
                    target="target_go",
                    state_after=(("gold", 7),),
                    return_label="Return",
                    state_after_return=(("gold", 6),),
                ),
                BrowserChoiceExpectation(
                    label="Return it to Thorne's study",
                    state_after=(("gold", 9),),
                    target="target_wait",
                ),
            ),
            guards=(
                BrowserGuardExpectation("Go now", "has_key", True, True),
                BrowserGuardExpectation("Go now", "has_key", False, False),
            ),
            hostile_marker="Café Æsir — 'glass & snow'",
        ),
        tweego_path=tweego,
        story_format_path=formats,
    )
    assert evaluation.tweego_compile, evaluation
    assert evaluation.browser_load, evaluation
    assert evaluation.choice_reachability, evaluation
    assert evaluation.choice_effect_execution, evaluation
    assert evaluation.runtime_state_transaction, evaluation
    assert evaluation.continuity_after_navigation, evaluation
    assert evaluation.hostile_text_safe, evaluation


@pytest.mark.e2e
def test_production_hub_hides_visited_route_after_return():
    tweego, formats = _runtime_paths()
    plan = PassagePlan(
        plan_id="browser_hub",
        revision=1,
        passage_mode="hub",
        narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),),
        choice_slots=(
            ChoiceSlot(id="tower", destination="hub_tower"),
            ChoiceSlot(id="market", destination="hub_market"),
        ),
    )
    fill = NarrativeFill.model_validate({
        "plan_id": plan.plan_id,
        "plan_revision": 1,
        "narrative": [{
            "slot_id": "body", "kind": "paragraph", "speaker": "",
            "parts": [{"kind": "text", "text": "The crossroads waits."}],
        }],
        "choices": [
            {"slot_id": "tower", "text": "Visit tower", "hint": "Climb."},
            {"slot_id": "market", "text": "Visit market", "hint": "Trade."},
        ],
        "summary": "A hub.",
        "beats": ["Choose a route."],
    })
    artifact = compile_passage_draft(
        assemble_passage_draft(plan, fill), passage_id="hub_start", arc_name="browser"
    )
    evaluation = evaluate_compile_artifact(
        artifact,
        BrowserScenario(
            passage_id="hub_start",
            expected_text=("The crossroads waits.", "Visit tower", "Visit market"),
            choices=(BrowserChoiceExpectation(
                label="Visit tower",
                target="hub_tower",
                return_label="Return",
                hidden_after_return=True,
            ),),
        ),
        tweego_path=tweego,
        story_format_path=formats,
    )
    assert evaluation.tweego_compile, evaluation
    assert evaluation.browser_load, evaluation
    assert evaluation.choice_reachability, evaluation
    assert evaluation.continuity_after_navigation, evaluation


@pytest.mark.e2e
def test_production_room_exits_and_local_actions_do_not_conflict():
    tweego, formats = _runtime_paths()
    plan = PassagePlan(
        plan_id="browser_room",
        revision=1,
        passage_mode="room",
        narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),),
        choice_slots=(ChoiceSlot(
            id="search",
            effects=(StateEffect(
                component_id="mark_searched",
                target="searched",
                operation=StateOperation.SET,
                value=True,
            ),),
        ),),
        allowed_state_refs=("searched",),
        exits=(
            RouteSlot(label="north", destination="room_north"),
            RouteSlot(label="west", destination="room_west"),
        ),
    )
    fill = NarrativeFill.model_validate({
        "plan_id": plan.plan_id,
        "plan_revision": 1,
        "narrative": [{
            "slot_id": "body", "kind": "paragraph", "speaker": "",
            "parts": [{"kind": "text", "text": "A cold room surrounds you."}],
        }],
        "choices": [{"slot_id": "search", "text": "Search room", "hint": "Search."}],
        "summary": "A room.",
        "beats": ["Explore."],
    })
    artifact = compile_passage_draft(
        assemble_passage_draft(plan, fill), passage_id="room_start", arc_name="browser"
    )
    evaluation = evaluate_compile_artifact(
        artifact,
        BrowserScenario(
            passage_id="room_start",
            expected_text=("North", "West", "Search room"),
            initial_state=(("searched", False),),
            choices=(
                BrowserChoiceExpectation(
                    label="North", target="room_north", return_label="Return"
                ),
                BrowserChoiceExpectation(
                    label="Search room",
                    target="room_start",
                    state_after=(("searched", True),),
                ),
            ),
        ),
        tweego_path=tweego,
        story_format_path=formats,
    )
    assert evaluation.tweego_compile, evaluation
    assert evaluation.browser_load, evaluation
    assert evaluation.choice_reachability, evaluation
    assert evaluation.choice_effect_execution, evaluation


@pytest.mark.e2e
def test_production_random_route_only_reaches_weighted_allowed_targets():
    tweego, formats = _runtime_paths()
    plan = PassagePlan(
        plan_id="browser_random",
        revision=1,
        passage_mode="random",
        narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),),
        choice_slots=(
            ChoiceSlot(id="signal", destination="random_signal", weight=3),
            ChoiceSlot(id="silence", destination="random_silence", weight=2),
            ChoiceSlot(id="attack", destination="random_attack", weight=1),
        ),
    )
    fill = NarrativeFill.model_validate({
        "plan_id": plan.plan_id,
        "plan_revision": 1,
        "narrative": [{
            "slot_id": "body", "kind": "paragraph", "speaker": "",
            "parts": [{"kind": "text", "text": "The signal resolves."}],
        }],
        "choices": [
            {"slot_id": "signal", "text": "Signal", "hint": "Signal."},
            {"slot_id": "silence", "text": "Silence", "hint": "Silence."},
            {"slot_id": "attack", "text": "Attack", "hint": "Attack."},
        ],
        "summary": "A weighted route.",
        "beats": ["An outcome is selected."],
    })
    artifact = compile_passage_draft(
        assemble_passage_draft(plan, fill),
        passage_id="random_start",
        arc_name="browser",
    )
    allowed = ("random_signal", "random_silence", "random_attack")
    evaluation = evaluate_compile_artifact(
        artifact,
        BrowserScenario(
            passage_id="random_start",
            allowed_initial_targets=allowed,
            random_runs=12,
        ),
        tweego_path=tweego,
        story_format_path=formats,
    )
    assert evaluation.tweego_compile, evaluation
    assert evaluation.browser_load, evaluation
    assert evaluation.choice_reachability, evaluation


@pytest.mark.e2e
def test_production_dialogue_exit_uses_the_trusted_destination_not_copy_wording():
    tweego, formats = _runtime_paths()
    plan = PassagePlan(
        plan_id="browser_dialogue",
        revision=1,
        passage_mode="dialogue_loop",
        narrative_slots=(NarrativeSlot(id="line", kind="dialogue", speaker="Mira"),),
        choice_slots=(
            ChoiceSlot(id="continue", destination=""),
            ChoiceSlot(id="exit", destination="dialogue_exit"),
        ),
    )
    fill = NarrativeFill.model_validate({
        "plan_id": plan.plan_id,
        "plan_revision": 1,
        "narrative": [{
            "slot_id": "line", "kind": "dialogue", "speaker": "Mira",
            "parts": [{"kind": "text", "text": "We should keep talking."}],
        }],
        "choices": [
            {"slot_id": "continue", "text": "Ask about the gala", "hint": "Continue."},
            {"slot_id": "exit", "text": "Approach someone else", "hint": "Change focus."},
        ],
        "summary": "A conversation.",
        "beats": ["The player chooses whether to continue."],
    })
    artifact = compile_passage_draft(
        assemble_passage_draft(plan, fill), passage_id="dialogue_start", arc_name="browser"
    )
    evaluation = evaluate_compile_artifact(
        artifact,
        BrowserScenario(
            passage_id="dialogue_start",
            choices=(
                BrowserChoiceExpectation(label="Ask about the gala", target="dialogue_start"),
                BrowserChoiceExpectation(label="Approach someone else", target="dialogue_exit"),
            ),
        ),
        tweego_path=tweego,
        story_format_path=formats,
    )
    assert evaluation.tweego_compile, evaluation
    assert evaluation.browser_load, evaluation
    assert evaluation.choice_reachability, evaluation


@pytest.mark.e2e
def test_production_ending_restart_restores_start_state():
    tweego, formats = _runtime_paths()
    plan = PassagePlan(
        plan_id="browser_ending",
        revision=1,
        passage_mode="ending",
        narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),),
        choice_slots=(ChoiceSlot(
            id="restart",
            destination="Start",
            restart=True,
        ),),
        allowed_state_refs=("score",),
        fixed_effects=(StateEffect(
            component_id="ending_score",
            target="score",
            operation=StateOperation.SET,
            value=99,
        ),),
    )
    fill = NarrativeFill.model_validate({
        "plan_id": plan.plan_id,
        "plan_revision": 1,
        "narrative": [{
            "slot_id": "body", "kind": "paragraph", "speaker": "",
            "parts": [{"kind": "text", "text": "The story reaches its end."}],
        }],
        "choices": [{"slot_id": "restart", "text": "Restart", "hint": "Start over."}],
        "summary": "An ending.",
        "beats": ["The story ends."],
    })
    artifact = compile_passage_draft(
        assemble_passage_draft(plan, fill),
        passage_id="ending_scene",
        arc_name="browser",
    )
    evaluation = evaluate_compile_artifact(
        artifact,
        BrowserScenario(
            passage_id="ending_scene",
            story_start="Start",
            expected_text=("The story reaches its end.", "Restart"),
            initial_state=(("score", 0),),
            choices=(BrowserChoiceExpectation(
                label="Restart",
                target="Start",
                state_after=(("score", 0),),
                accept_dialog=True,
            ),),
        ),
        tweego_path=tweego,
        story_format_path=formats,
    )
    assert evaluation.tweego_compile, evaluation
    assert evaluation.browser_load, evaluation
    assert evaluation.choice_reachability, evaluation
    assert evaluation.choice_effect_execution, evaluation


@pytest.mark.e2e
def test_production_form_binds_exact_variables_and_submits():
    tweego, formats = _runtime_paths()
    plan = PassagePlan(
        plan_id="browser_form",
        revision=1,
        passage_mode="form",
        narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),),
        choice_slots=(ChoiceSlot(id="submit", destination="form_done"),),
        allowed_state_refs=("name", "class_name"),
        form_fields=(
            FormField(id="name", kind="textbox", label="Name"),
            FormField(
                id="class_name",
                kind="listbox",
                label="Class",
                options=(FormOption(label="Warrior"), FormOption(label="Scholar")),
            ),
        ),
    )
    fill = NarrativeFill.model_validate({
        "plan_id": plan.plan_id,
        "plan_revision": 1,
        "narrative": [{
            "slot_id": "body", "kind": "paragraph", "speaker": "",
            "parts": [{"kind": "text", "text": "Choose your identity."}],
        }],
        "choices": [{"slot_id": "submit", "text": "Begin", "hint": "Submit."}],
        "summary": "Identity form.",
        "beats": ["Identity is chosen."],
    })
    artifact = compile_passage_draft(
        assemble_passage_draft(plan, fill),
        passage_id="form_start",
        arc_name="browser",
    )
    evaluation = evaluate_compile_artifact(
        artifact,
        BrowserScenario(
            passage_id="form_start",
            expected_text=("Choose your identity.", "Name", "Class", "Begin"),
            initial_state=(("name", ""), ("class_name", "")),
            forms=(
                BrowserFormExpectation(
                    'input[type="text"]', "Ada", "name", "Ada"
                ),
                BrowserFormExpectation(
                    "select", "Scholar", "class_name", "Scholar"
                ),
            ),
            submit_label="Begin",
        ),
        tweego_path=tweego,
        story_format_path=formats,
    )
    assert evaluation.tweego_compile, evaluation
    assert evaluation.browser_load, evaluation
    assert evaluation.form_binding, evaluation


@pytest.mark.e2e
def test_production_loop_renders_per_item_and_captures_clicked_value():
    tweego, formats = _runtime_paths()
    plan = PassagePlan(
        plan_id="browser_loop",
        revision=1,
        passage_mode="loop",
        narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),),
        choice_slots=(ChoiceSlot(
            id="inspect",
            effects=(StateEffect(
                component_id="select_item",
                target="selected_item",
                operation=StateOperation.SET,
                source="item_id",
            ),),
        ),),
        allowed_state_refs=("inventory_items", "item_id", "selected_item"),
        loop_binding=LoopBinding(variable="item_id", collection="inventory_items"),
    )
    fill = NarrativeFill.model_validate({
        "plan_id": plan.plan_id,
        "plan_revision": 1,
        "narrative": [{
            "slot_id": "body", "kind": "paragraph", "speaker": "",
            "parts": [{"kind": "text", "text": "Inspect the inventory."}],
        }],
        "choices": [{"slot_id": "inspect", "text": "Inspect", "hint": "Inspect item."}],
        "summary": "Inventory loop.",
        "beats": ["An item is selected."],
    })
    artifact = compile_passage_draft(
        assemble_passage_draft(plan, fill),
        passage_id="loop_start",
        arc_name="browser",
    )
    evaluation = evaluate_compile_artifact(
        artifact,
        BrowserScenario(
            passage_id="loop_start",
            expected_text=("Inspect the inventory.",),
            initial_state=(
                ("inventory_items", ["orb", "key", "map"]),
                ("selected_item", ""),
            ),
            expected_choice_counts=(("Inspect", 3),),
            choices=(BrowserChoiceExpectation(
                label="Inspect",
                occurrence=1,
                target="loop_start",
                state_after=(("selected_item", "key"),),
            ),),
        ),
        tweego_path=tweego,
        story_format_path=formats,
    )
    assert evaluation.tweego_compile, evaluation
    assert evaluation.browser_load, evaluation
    assert evaluation.choice_reachability, evaluation
    assert evaluation.choice_effect_execution, evaluation
