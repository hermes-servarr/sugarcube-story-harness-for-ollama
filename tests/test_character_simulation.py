import pytest
from pydantic import ValidationError

from harness.simulation import (
    AgendaState,
    CharacterEffect,
    CharacterRuntimeState,
    CharacterStatDefinition,
    ConditionState,
    NeedState,
    SimulationError,
    advance_character_time,
    apply_character_effect,
    character_context,
    initialize_character,
    create_runtime_session,
    LocationNode,
    WorldTopology,
)


def _definitions():
    return (
        CharacterStatDefinition(
            id="energy",
            value_type="float",
            default=1.0,
            minimum=0,
            maximum=1,
            visibility="public",
            allowed_operations=("set", "add", "clamp"),
            decay_per_tick=-0.1,
        ),
        CharacterStatDefinition(
            id="suspicion",
            value_type="int",
            default=0,
            minimum=0,
            maximum=10,
            visibility="model",
            allowed_operations=("set", "add"),
        ),
        CharacterStatDefinition(
            id="secret_oath",
            value_type="bool",
            default=True,
            visibility="private",
        ),
    )


def test_stat_definitions_validate_types_and_bounds():
    with pytest.raises(ValidationError, match="does not match"):
        CharacterStatDefinition(id="energy", value_type="int", default="high")
    with pytest.raises(ValidationError, match="below minimum"):
        CharacterStatDefinition(id="energy", value_type="float", default=-1, minimum=0)


def test_character_effects_are_schema_authorized_and_revisioned():
    definitions = _definitions()
    original = initialize_character("captain", "harbor", definitions)
    updated = apply_character_effect(
        original,
        definitions,
        CharacterEffect(operation="add", character_id="captain", target="suspicion", value=3),
        expected_revision=1,
        tick=2,
    )

    assert original.stats["suspicion"] == 0
    assert updated.stats["suspicion"] == 3
    assert updated.revision == 2
    assert updated.last_updated_tick == 2

    with pytest.raises(SimulationError) as out_of_bounds:
        apply_character_effect(
            updated,
            definitions,
            CharacterEffect(operation="add", character_id="captain", target="suspicion", value=20),
            expected_revision=2,
            tick=3,
        )
    assert out_of_bounds.value.code == "character_stat_out_of_bounds"


def test_character_fact_location_condition_inventory_and_agenda_operations():
    definitions = _definitions()
    character = CharacterRuntimeState(
        character_id="captain",
        current_location="harbor",
        stats={item.id: item.default for item in definitions},
        inventory={"key": 1},
        agendas=(AgendaState(id="find_ship", goal="Find the ship", progress=0.8),),
    )
    effects = (
        CharacterEffect(operation="add_fact", character_id="captain", target="tide_known"),
        CharacterEffect(operation="move_character", character_id="captain", value="island"),
        CharacterEffect(operation="start_condition", character_id="captain", value={
            "id": "storm_fear", "kind": "mood", "severity": 0.4, "remaining_ticks": 2,
        }),
        CharacterEffect(operation="advance_agenda", character_id="captain", target="find_ship", value=0.2),
        CharacterEffect(operation="remove", character_id="captain", target="key", value=1),
    )
    for tick, effect in enumerate(effects, start=1):
        character = apply_character_effect(
            character, definitions, effect, expected_revision=character.revision, tick=tick
        )

    assert character.current_location == "island"
    assert character.known_facts == ("tide_known",)
    assert character.conditions[0].id == "storm_fear"
    assert character.agendas[0].status == "completed"
    assert character.inventory == {}


def test_character_time_updates_decay_needs_conditions_deadlines_and_cooldowns():
    definitions = _definitions()
    character = CharacterRuntimeState(
        character_id="captain",
        current_location="harbor",
        stats={item.id: item.default for item in definitions},
        needs=(NeedState(id="hunger", value=0.3, change_per_tick=0.2),),
        conditions=(
            ConditionState(id="brief_mood", kind="mood", remaining_ticks=2),
            ConditionState(id="scar", kind="injury", remaining_ticks=None),
        ),
        agendas=(AgendaState(id="depart", goal="Depart", deadline_tick=1),),
        cooldowns={"speak": 2, "trade": 5},
    )

    updated = advance_character_time(character, definitions, to_tick=3, expected_revision=1)

    assert updated.stats["energy"] == pytest.approx(0.7)
    assert updated.needs[0].value == pytest.approx(0.9)
    assert [item.id for item in updated.conditions] == ["scar"]
    assert updated.conditions[0].remaining_ticks is None
    assert updated.agendas[0].status == "failed"
    assert updated.cooldowns == {"trade": 5}


def test_private_character_state_is_excluded_unless_explicitly_authorized():
    definitions = _definitions()
    character = initialize_character("captain", "harbor", definitions)

    player = character_context(character, definitions, audience="player")
    model = character_context(character, definitions, audience="model")
    authorized = character_context(
        character, definitions, audience="model", authorized_private_stats=("secret_oath",)
    )

    assert player["stats"] == {"energy": 1.0}
    assert model["stats"] == {"energy": 1.0, "suspicion": 0}
    assert authorized["stats"]["secret_oath"] is True


def test_runtime_session_rejects_character_locations_outside_topology():
    topology = WorldTopology(locations=(LocationNode(id="harbor", name="Harbor", region_id="coast"),))
    with pytest.raises(SimulationError) as unknown:
        create_runtime_session(
            topology,
            session_id="simulation_test",
            experience_profile_fingerprint="a" * 64,
            start_location="harbor",
            time_model="turn",
            seed=1,
            character_stat_definitions=_definitions(),
            characters=(initialize_character("captain", "island", _definitions()),),
        )
    assert unknown.value.code == "character_location_unknown"
