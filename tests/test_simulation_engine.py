import hashlib
import json

import pytest
from pydantic import ValidationError

from harness.generation import (
    ExperienceProfile,
    NarrativeSlot,
    PassagePlan,
    StateCondition,
    StateEffect,
)
from harness.simulation import (
    AuthoredAnchor,
    CharacterEffect,
    CharacterStatDefinition,
    EncounterTemplate,
    FactionEffect,
    FactionState,
    LocationAction,
    LocationNode,
    Route,
    SimulationError,
    WorldTopology,
    SystemRule,
    advance_systems,
    apply_local_action,
    available_opportunities,
    complete_authored_anchor,
    create_runtime_session,
    reachable_locations,
    record_encounter,
    select_encounter,
    travel,
    initialize_character,
    RuntimeSessionStore,
    SimulationRecord,
)


def _topology() -> WorldTopology:
    return WorldTopology(
        locations=(
            LocationNode(
                id="harbor",
                name="Harbor",
                region_id="coast",
                actions=(LocationAction(
                    id="ask_dockmaster",
                    label="Ask the dockmaster",
                    eligibility=(StateCondition(target="dockmaster_present", operation="truthy"),),
                    effects=(StateEffect(
                        component_id="learn_tide",
                        target="knows_tide",
                        operation="set",
                        value=True,
                    ),),
                    time_cost=2,
                ),),
            ),
            LocationNode(id="island", name="Island", region_id="coast"),
            LocationNode(id="cave", name="Cave", region_id="depths"),
        ),
        routes=(
            Route(
                id="ferry",
                source="harbor",
                destination="island",
                eligibility=(StateCondition(target="weather_safe", operation="eq", value=True),),
                resource_cost={"coins": 2},
                travel_effects=(StateEffect(
                    component_id="mark_crossing",
                    target="crossed_sea",
                    operation="set",
                    value=True,
                ),),
                time_cost=3,
            ),
            Route(id="island_cave", source="island", destination="cave"),
            Route(id="cave_island", source="cave", destination="island"),
        ),
    )


def _session(topology: WorldTopology):
    return create_runtime_session(
        topology,
        session_id="sandbox_fixture",
        experience_profile_fingerprint=ExperienceProfile.sandbox().fingerprint(),
        start_location="harbor",
        time_model="turn",
        seed=42,
        world_state={"dockmaster_present": True, "weather_safe": True},
        resources={"coins": 3},
    )


def test_topology_rejects_unknown_routes_and_duplicate_authority():
    with pytest.raises(ValidationError, match="unknown location"):
        WorldTopology(
            locations=(LocationNode(id="harbor", name="Harbor", region_id="coast"),),
            routes=(Route(id="bad_route", source="harbor", destination="missing"),),
        )

    action = LocationAction(id="wait", label="Wait")
    with pytest.raises(ValidationError, match="duplicate location action"):
        LocationNode(id="harbor", name="Harbor", region_id="coast", actions=(action, action))


def test_available_opportunities_are_eligible_affordable_and_stable():
    topology = _topology()
    session = _session(topology)

    first = available_opportunities(topology, session)
    second = available_opportunities(topology, session)

    assert first == second
    assert [(item.kind, item.source_id) for item in first] == [
        ("local_action", "ask_dockmaster"),
        ("travel", "ferry"),
    ]


def test_hybrid_authored_anchors_progress_without_blocking_free_exploration():
    topology = _topology()
    session = _session(topology)
    anchors = (
        AuthoredAnchor(id="anchor_arrival", label="Meet the envoy", location_id="harbor"),
        AuthoredAnchor(
            id="anchor_revelation",
            label="Learn the island secret",
            location_id="island",
            prerequisite_ids=("anchor_arrival",),
        ),
    )

    available = available_opportunities(topology, session, anchors)
    assert [(item.kind, item.source_id) for item in available] == [
        ("authored_anchor", "anchor_arrival"),
        ("local_action", "ask_dockmaster"),
        ("travel", "ferry"),
    ]

    advanced, trace = complete_authored_anchor(
        topology, session, anchors[0], expected_revision=1
    )
    assert session.completed_anchor_ids == ()
    assert advanced.completed_anchor_ids == ("anchor_arrival",)
    assert advanced.visits[-1].selected_actions == ("anchor_arrival",)
    assert trace.action_kind == "authored_anchor"
    with pytest.raises(SimulationError) as repeated:
        complete_authored_anchor(topology, advanced, anchors[0], expected_revision=2)
    assert repeated.value.code == "authored_anchor_ineligible"

    island, _ = travel(topology, advanced, "ferry", expected_revision=2)
    island_opportunities = available_opportunities(topology, island, anchors)
    assert ("authored_anchor", "anchor_revelation") in {
        (item.kind, item.source_id) for item in island_opportunities
    }


def test_runtime_store_reads_pre_anchor_session_fingerprints(tmp_path):
    session = _session(_topology())
    legacy_payload = session.model_dump(mode="json")
    legacy_payload.pop("completed_anchor_ids")
    legacy_fingerprint = hashlib.sha256(json.dumps(
        legacy_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    target = tmp_path / session.session_id / "1.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({
        "record": {"session": legacy_payload, "trace": None},
        "fingerprint": "placeholder",
    }), encoding="utf-8")
    record_payload = json.loads(target.read_text(encoding="utf-8"))["record"]
    record_fingerprint = hashlib.sha256(json.dumps(
        record_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    target.write_text(json.dumps({
        "record": record_payload, "fingerprint": record_fingerprint,
    }), encoding="utf-8")

    restored = RuntimeSessionStore(tmp_path).get(session.session_id)

    assert legacy_fingerprint != restored.session.fingerprint()
    assert restored.session.completed_anchor_ids == ()


def test_local_action_is_pure_revisioned_and_applies_typed_effects():
    topology = _topology()
    original = _session(topology)

    updated, trace = apply_local_action(
        topology, original, "ask_dockmaster", expected_revision=1
    )

    assert original.revision == 1
    assert original.world_state.get("knows_tide") is None
    assert updated.revision == 2
    assert updated.clock.tick == 2
    assert updated.world_state["knows_tide"] is True
    assert updated.visits[-1].selected_actions == ("ask_dockmaster",)
    assert trace.applied_effects == ("learn_tide",)


def test_travel_records_revisit_history_cost_and_deterministic_trace():
    topology = _topology()
    original = _session(topology)
    island, first_trace = travel(topology, original, "ferry", expected_revision=1)
    cave, _ = travel(topology, island, "island_cave", expected_revision=2)
    revisited, _ = travel(topology, cave, "cave_island", expected_revision=3)

    assert island.resources["coins"] == 1
    assert island.world_state["crossed_sea"] is True
    assert island.clock.tick == 3
    assert first_trace.resource_delta == {"coins": -2}
    assert [visit.location_id for visit in revisited.visits] == [
        "harbor", "island", "cave", "island",
    ]
    assert all(visit.exited_tick is not None for visit in revisited.visits[:-1])
    assert revisited.visits[-1].exited_tick is None


def test_transitions_reject_stale_revision_unaffordable_route_and_topology_change():
    topology = _topology()
    session = _session(topology)
    with pytest.raises(SimulationError) as stale:
        travel(topology, session, "ferry", expected_revision=2)
    assert stale.value.code == "simulation_revision_conflict"

    poor = session.model_copy(update={"resources": {"coins": 1}})
    with pytest.raises(SimulationError) as poor_route:
        travel(topology, poor, "ferry", expected_revision=1)
    assert poor_route.value.code == "route_cost_unaffordable"

    changed = topology.model_copy(update={"revision": 2})
    with pytest.raises(SimulationError) as changed_topology:
        available_opportunities(changed, session)
    assert changed_topology.value.code == "topology_fingerprint_conflict"


def test_reachability_handles_expected_sandbox_cycles():
    assert reachable_locations(_topology(), "harbor") == {"harbor", "island", "cave"}


def test_system_rules_apply_by_priority_with_cooldowns_and_limits():
    topology = _topology()
    session = _session(topology).model_copy(update={"world_state": {
        "dockmaster_present": True, "weather_safe": True, "pressure": 0,
    }})
    rules = (
        SystemRule(
            id="pressure_low",
            trigger="tick",
            priority=1,
            conditions=(StateCondition(target="pressure", operation="eq", value=1),),
            effects=(StateEffect(component_id="add_ten", target="pressure", operation="add", value=10),),
            occurrence_limit=1,
        ),
        SystemRule(
            id="pressure_high",
            trigger="tick",
            priority=10,
            effects=(StateEffect(component_id="add_one", target="pressure", operation="add", value=1),),
            cooldown_ticks=2,
        ),
    )

    first, trace = advance_systems(session, rules, expected_revision=1)
    second, _ = advance_systems(first, rules, expected_revision=2)
    third, _ = advance_systems(second, rules, expected_revision=3)

    assert first.world_state["pressure"] == 11
    assert trace.applied_effects == ("add_one", "add_ten")
    assert second.world_state["pressure"] == 11
    assert third.world_state["pressure"] == 12
    assert third.occurrence_counts == {"pressure_high": 2, "pressure_low": 1}


def test_system_rules_apply_persistent_character_and_faction_effects():
    topology = _topology()
    definitions = (CharacterStatDefinition(
        id="trust", value_type="int", default=0, minimum=0, maximum=10,
        allowed_operations=("set", "add"),
    ),)
    session = create_runtime_session(
        topology,
        session_id="domain_effect_fixture",
        experience_profile_fingerprint=ExperienceProfile.sandbox().fingerprint(),
        start_location="harbor",
        time_model="turn",
        seed=9,
        character_stat_definitions=definitions,
        characters=(initialize_character("captain", "harbor", definitions),),
        factions=(FactionState(faction_id="guild", influence=0.4),),
    )
    rule = SystemRule(
        id="guild_rises",
        trigger="tick",
        character_effects=(CharacterEffect(
            operation="add", character_id="captain", target="trust", value=2,
        ),),
        faction_effects=(FactionEffect(
            faction_id="guild", operation="influence", delta=0.2,
        ),),
    )

    updated, trace = advance_systems(session, (rule,), expected_revision=1)

    assert updated.characters[0].stats["trust"] == 2
    assert updated.characters[0].last_updated_tick == 1
    assert updated.factions[0].influence == pytest.approx(0.6)
    assert trace.applied_effects == ("character:guild_rises:0", "faction:guild_rises:0")


def _encounter(template_id: str, weight: int = 1, *, limit: int | None = None) -> EncounterTemplate:
    return EncounterTemplate(
        id=template_id,
        label=template_id.replace("_", " "),
        plan=PassagePlan(
            plan_id=f"{template_id}_plan",
            revision=1,
            passage_mode="normal",
            narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),),
            choice_slots=("continue",),
        ),
        location_ids=("harbor",),
        occurrence_limit=limit,
        weight=weight,
        variation_slots=("body",),
    )


def test_encounter_selection_is_seeded_weighted_and_limit_safe():
    topology = _topology()
    session = _session(topology)
    location = topology.locations[0]
    templates = (_encounter("quiet_tide"), _encounter("smuggler_offer", 3, limit=1))

    first = select_encounter(session, templates, location=location)
    repeated = select_encounter(session, templates, location=location)
    assert first == repeated
    assert first is not None
    chosen = next(item for item in templates if item.id == first.template_id)

    recorded, trace = record_encounter(session, chosen, first, expected_revision=1)
    assert trace.action_kind == "encounter"
    assert recorded.occurrence_counts[chosen.id] == 1
    if chosen.occurrence_limit == 1:
        next_selection = select_encounter(recorded, (chosen,), location=location)
        assert next_selection is None
