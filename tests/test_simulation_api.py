import asyncio
import threading

import pytest
from fastapi import HTTPException

from harness.generation import (
    ExperienceProfile,
    ExperienceProfileStore,
    ChoiceSlot,
    NarrativeSlot,
    PassagePlan,
    StateCondition,
    StateEffect,
)
from harness.project import init_project
from harness.planning import add_scene, create_arc
from harness.server import app as server_app
from harness.simulation import (
    CharacterRuntimeState,
    CharacterStatDefinition,
    EncounterTemplate,
    FactionState,
    LocationAction,
    LocationNode,
    NeedState,
    Route,
    SimulationFixture,
    SystemCatalog,
    SystemRule,
)


def _enable_sandbox(paths):
    ExperienceProfileStore(paths.experience_profiles_dir).put(
        ExperienceProfile.sandbox().model_copy(update={"revision": 2}),
        expected_revision=1,
    )


def _enable_hybrid(paths):
    ExperienceProfileStore(paths.experience_profiles_dir).put(
        ExperienceProfile.hybrid().model_copy(update={"revision": 2}),
        expected_revision=1,
    )


def test_hybrid_planned_scene_anchors_progress_only_in_runtime(tmp_path, monkeypatch):
    paths = init_project(tmp_path)
    _enable_hybrid(paths)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    asyncio.run(server_app.add_topology_location(server_app.TopologyLocationRequest(
        expected_revision=0,
        location=LocationNode(id="harbor", name="Harbor", region_id="coast"),
    )))
    arc_name, _ = create_arc(paths, "main", "Find the envoy")
    add_scene(
        paths,
        arc_name,
        title="Meet the envoy",
        keywords=["anchor", "location:harbor"],
    )
    add_scene(
        paths,
        arc_name,
        title="Hear the warning",
        keywords=["anchor", "location:harbor"],
    )
    story_before = paths.story_json.read_bytes()

    created = asyncio.run(server_app.create_simulation(server_app.SimulationCreateRequest(
        start_location="harbor", seed=42,
    )))
    first = next(item for item in created["opportunities"] if item["kind"] == "authored_anchor")
    assert first["label"] == "Meet the envoy"

    advanced = asyncio.run(server_app.apply_simulation_action(
        created["session"]["session_id"],
        server_app.SimulationActionRequest(
            expected_revision=1,
            kind="authored_anchor",
            action_id=first["source_id"],
        ),
    ))
    assert advanced["trace"]["action_kind"] == "authored_anchor"
    assert advanced["session"]["completed_anchor_ids"] == [first["source_id"]]
    second = next(item for item in advanced["opportunities"] if item["kind"] == "authored_anchor")
    assert second["label"] == "Hear the warning"
    assert paths.story_json.read_bytes() == story_before


def test_topology_api_is_profile_gated_and_revisioned(tmp_path, monkeypatch):
    paths = init_project(tmp_path)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    request = server_app.TopologyLocationRequest(
        expected_revision=0,
        location=LocationNode(id="harbor", name="Harbor", region_id="coast"),
    )
    with pytest.raises(HTTPException) as gated:
        asyncio.run(server_app.add_topology_location(request))
    assert gated.value.detail["code"] == "systemic_profile_required"

    _enable_sandbox(paths)
    first = asyncio.run(server_app.add_topology_location(request))
    second = asyncio.run(server_app.add_topology_location(server_app.TopologyLocationRequest(
        expected_revision=1,
        location=LocationNode(id="island", name="Island", region_id="coast"),
    )))
    routed = asyncio.run(server_app.add_topology_route(server_app.TopologyRouteRequest(
        expected_revision=2,
        route=Route(id="ferry", source="harbor", destination="island", resource_cost={"coins": 2}),
    )))

    assert first["topology"]["revision"] == 1
    assert second["topology"]["revision"] == 2
    assert routed["topology"]["revision"] == 3
    assert asyncio.run(server_app.get_topology()) == routed

    with pytest.raises(HTTPException) as stale:
        asyncio.run(server_app.add_topology_location(server_app.TopologyLocationRequest(
            expected_revision=2,
            location=LocationNode(id="cave", name="Cave", region_id="depths"),
        )))
    assert stale.value.detail["code"] == "topology_revision_conflict"


def test_topology_update_delete_and_concurrent_writes_are_revision_guarded(tmp_path, monkeypatch):
    paths = init_project(tmp_path)
    _enable_sandbox(paths)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    asyncio.run(server_app.add_topology_location(server_app.TopologyLocationRequest(
        expected_revision=0,
        location=LocationNode(id="harbor", name="Harbor", region_id="coast"),
    )))
    asyncio.run(server_app.add_topology_location(server_app.TopologyLocationRequest(
        expected_revision=1,
        location=LocationNode(id="island", name="Island", region_id="coast"),
    )))
    asyncio.run(server_app.add_topology_route(server_app.TopologyRouteRequest(
        expected_revision=2,
        route=Route(id="ferry", source="harbor", destination="island"),
    )))
    updated = asyncio.run(server_app.update_topology_location(
        "harbor",
        server_app.TopologyLocationRequest(
            expected_revision=3,
            location=LocationNode(id="harbor", name="Old Harbor", region_id="coast"),
        ),
    ))
    assert updated["topology"]["locations"][0]["name"] == "Old Harbor"

    with pytest.raises(HTTPException) as in_use:
        asyncio.run(server_app.delete_topology_location(
            "island", server_app.TopologyDeleteRequest(expected_revision=4),
        ))
    assert in_use.value.detail["code"] == "location_in_use"
    route_deleted = asyncio.run(server_app.delete_topology_route(
        "ferry", server_app.TopologyDeleteRequest(expected_revision=4),
    ))
    location_deleted = asyncio.run(server_app.delete_topology_location(
        "island", server_app.TopologyDeleteRequest(expected_revision=5),
    ))
    assert route_deleted["topology"]["routes"] == []
    assert [item["id"] for item in location_deleted["topology"]["locations"]] == ["harbor"]

    barrier = threading.Barrier(2)
    results = []

    def writer(name):
        barrier.wait()
        try:
            results.append(asyncio.run(server_app.update_topology_location(
                "harbor",
                server_app.TopologyLocationRequest(
                    expected_revision=6,
                    location=LocationNode(id="harbor", name=name, region_id="coast"),
                ),
            )))
        except HTTPException as exc:
            results.append(exc)

    threads = [threading.Thread(target=writer, args=(name,)) for name in ("North Harbor", "South Harbor")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(not isinstance(item, HTTPException) for item in results) == 1
    conflict = next(item for item in results if isinstance(item, HTTPException))
    assert conflict.detail["code"] == "topology_revision_conflict"


def test_system_and_encounter_catalog_endpoints_have_stable_empty_defaults(tmp_path, monkeypatch):
    init_project(tmp_path)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)

    systems = asyncio.run(server_app.get_systems())
    encounters = asyncio.run(server_app.get_encounters())

    assert systems["catalog"]["rules"] == []
    assert encounters["catalog"]["templates"] == []
    assert len(systems["fingerprint"]) == 64
    assert len(encounters["fingerprint"]) == 64


def test_system_and_encounter_catalog_updates_are_fingerprint_guarded(tmp_path, monkeypatch):
    paths = init_project(tmp_path)
    _enable_sandbox(paths)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    systems = asyncio.run(server_app.get_systems())
    rule = SystemRule(
        id="raise_tide",
        trigger="tick",
        effects=(StateEffect(component_id="tide_effect", target="tide", operation="set", value="high"),),
    )
    saved_systems = asyncio.run(server_app.update_systems(server_app.SystemCatalogRequest(
        expected_fingerprint=systems["fingerprint"],
        rules=(rule,),
    )))
    assert saved_systems["catalog"]["revision"] == 2
    assert paths.systems_json.exists()

    with pytest.raises(HTTPException) as stale:
        asyncio.run(server_app.update_systems(server_app.SystemCatalogRequest(
            expected_fingerprint=systems["fingerprint"],
            rules=(),
        )))
    assert stale.value.detail["code"] == "system_catalog_conflict"

    encounters = asyncio.run(server_app.get_encounters())
    template = EncounterTemplate(
        id="fog_bank",
        label="Fog bank",
        plan=PassagePlan(
            plan_id="fog_bank_plan",
            revision=1,
            passage_mode="normal",
            narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),),
            choice_slots=(ChoiceSlot(id="continue", destination="harbor"),),
        ),
        variation_slots=("body", "continue"),
    )
    saved_encounters = asyncio.run(server_app.update_encounters(server_app.EncounterCatalogRequest(
        expected_fingerprint=encounters["fingerprint"],
        templates=(template,),
    )))
    assert saved_encounters["catalog"]["revision"] == 2
    assert paths.encounters_json.exists()


def test_named_simulation_fixtures_are_persisted_guarded_and_start_exact_state(tmp_path, monkeypatch):
    paths = init_project(tmp_path)
    _enable_sandbox(paths)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    asyncio.run(server_app.add_topology_location(server_app.TopologyLocationRequest(
        expected_revision=0,
        location=LocationNode(id="harbor", name="Harbor", region_id="coast"),
    )))
    empty = asyncio.run(server_app.get_simulation_fixtures())
    definition = CharacterStatDefinition(
        id="energy", value_type="int", default=5, minimum=0, maximum=10,
        allowed_operations=("set", "add", "clamp"),
    )
    fixture = SimulationFixture(
        id="storm_watch",
        label="Storm watch",
        start_location="harbor",
        seed=91,
        world_state={"storm": True},
        resources={"coins": 4},
        factions=(FactionState(faction_id="wardens", influence=0.7),),
        character_stat_definitions=(definition,),
        characters=(CharacterRuntimeState(
            character_id="mara", current_location="harbor", stats={"energy": 3},
        ),),
    )
    saved = asyncio.run(server_app.update_simulation_fixtures(
        server_app.SimulationFixtureCatalogRequest(
            expected_fingerprint=empty["fingerprint"], fixtures=(fixture,),
        )
    ))
    assert saved["catalog"]["revision"] == 2
    assert paths.simulation_fixtures_json.exists()

    created = asyncio.run(server_app.create_simulation(
        server_app.SimulationCreateRequest(fixture_id="storm_watch")
    ))
    assert created["session"]["seed"] == 91
    assert created["session"]["world_state"] == {"storm": True}
    assert created["session"]["resources"] == {"coins": 4}
    assert created["session"]["characters"][0]["stats"] == {"energy": 3}
    assert created["session"]["factions"][0]["faction_id"] == "wardens"

    with pytest.raises(HTTPException) as stale:
        asyncio.run(server_app.update_simulation_fixtures(
            server_app.SimulationFixtureCatalogRequest(
                expected_fingerprint=empty["fingerprint"], fixtures=(),
            )
        ))
    assert stale.value.detail["code"] == "simulation_fixture_catalog_conflict"

    with pytest.raises(HTTPException) as mixed:
        asyncio.run(server_app.create_simulation(server_app.SimulationCreateRequest(
            fixture_id="storm_watch", seed=1,
        )))
    assert mixed.value.detail["code"] == "simulation_fixture_override_forbidden"


def test_simulation_api_persists_runtime_revisions_without_touching_canon(tmp_path, monkeypatch):
    paths = init_project(tmp_path)
    _enable_sandbox(paths)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    story_before = paths.story_json.read_bytes()
    asyncio.run(server_app.add_topology_location(server_app.TopologyLocationRequest(
        expected_revision=0,
        location=LocationNode(
            id="harbor",
            name="Harbor",
            region_id="coast",
            actions=(LocationAction(
                id="watch_tide",
                label="Watch the tide",
                eligibility=(StateCondition(target="weather_safe", operation="truthy"),),
            ),),
        ),
    )))
    asyncio.run(server_app.add_topology_location(server_app.TopologyLocationRequest(
        expected_revision=1,
        location=LocationNode(id="island", name="Island", region_id="coast"),
    )))
    asyncio.run(server_app.add_topology_route(server_app.TopologyRouteRequest(
        expected_revision=2,
        route=Route(id="ferry", source="harbor", destination="island", resource_cost={"coins": 2}),
    )))
    paths.systems_json.write_text(SystemCatalog(rules=(SystemRule(
        id="mark_travel",
        trigger="travel",
        effects=(StateEffect(
            component_id="mark_departure",
            target="has_traveled",
            operation="set",
            value=True,
        ),),
    ),)).model_dump_json(), encoding="utf-8")

    created = asyncio.run(server_app.create_simulation(server_app.SimulationCreateRequest(
        start_location="harbor",
        seed=17,
        world_state={"weather_safe": True},
        resources={"coins": 3},
    )))
    simulation_id = created["session"]["session_id"]
    assert {item["source_id"] for item in created["opportunities"]} == {"watch_tide", "ferry"}

    acted = asyncio.run(server_app.apply_simulation_action(
        simulation_id,
        server_app.SimulationActionRequest(
            expected_revision=1,
            kind="travel",
            action_id="ferry",
        ),
    ))
    loaded = asyncio.run(server_app.get_simulation(simulation_id))

    assert acted == loaded
    assert acted["session"]["revision"] == 2
    assert acted["session"]["current_location"] == "island"
    assert acted["session"]["resources"]["coins"] == 1
    assert acted["session"]["world_state"]["has_traveled"] is True
    assert acted["trace"]["applied_effects"] == ["mark_departure"]
    assert paths.story_json.read_bytes() == story_before

    with pytest.raises(HTTPException) as stale:
        asyncio.run(server_app.apply_simulation_action(
            simulation_id,
            server_app.SimulationActionRequest(
                expected_revision=1,
                kind="travel",
                action_id="ferry",
            ),
        ))
    assert stale.value.detail["code"] == "simulation_revision_conflict"


def test_simulation_api_persists_and_advances_character_state(tmp_path, monkeypatch):
    paths = init_project(tmp_path)
    _enable_sandbox(paths)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    asyncio.run(server_app.add_topology_location(server_app.TopologyLocationRequest(
        expected_revision=0,
        location=LocationNode(
            id="harbor",
            name="Harbor",
            region_id="coast",
            actions=(LocationAction(id="wait", label="Wait", time_cost=2),),
        ),
    )))
    definitions = (CharacterStatDefinition(
        id="energy",
        value_type="float",
        default=1.0,
        minimum=0,
        maximum=1,
        allowed_operations=("set", "add", "clamp"),
        decay_per_tick=-0.1,
    ),)
    character = CharacterRuntimeState(
        character_id="captain",
        current_location="harbor",
        stats={"energy": 1.0},
        needs=(NeedState(id="hunger", value=0.2, change_per_tick=0.1),),
    )

    created = asyncio.run(server_app.create_simulation(server_app.SimulationCreateRequest(
        start_location="harbor",
        seed=11,
        character_stat_definitions=definitions,
        characters=(character,),
    )))
    advanced = asyncio.run(server_app.apply_simulation_action(
        created["session"]["session_id"],
        server_app.SimulationActionRequest(expected_revision=1, kind="local_action", action_id="wait"),
    ))
    loaded = asyncio.run(server_app.get_simulation(created["session"]["session_id"]))

    persisted = advanced["session"]["characters"][0]
    assert persisted["stats"]["energy"] == pytest.approx(0.8)
    assert persisted["needs"][0]["value"] == pytest.approx(0.4)
    assert persisted["last_updated_tick"] == 2
    assert persisted["revision"] == 2
    assert loaded == advanced
