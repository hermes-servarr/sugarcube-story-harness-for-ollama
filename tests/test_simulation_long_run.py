from harness.generation import ExperienceProfile
from harness.simulation import (
    LocationNode,
    Route,
    WorldTopology,
    available_opportunities,
    create_runtime_session,
    travel,
)


def _loop_topology(*, cost: int = 0) -> WorldTopology:
    return WorldTopology(
        locations=(
            LocationNode(id="east", name="East", region_id="ring"),
            LocationNode(id="west", name="West", region_id="ring"),
        ),
        routes=(
            Route(id="east_west", source="east", destination="west", resource_cost={"energy": cost}),
            Route(id="west_east", source="west", destination="east", resource_cost={"energy": cost}),
        ),
    )


def _run_trace(seed: int, turns: int = 100):
    topology = _loop_topology()
    session = create_runtime_session(
        topology,
        session_id="long_run",
        experience_profile_fingerprint=ExperienceProfile.sandbox().fingerprint(),
        start_location="east",
        time_model="turn",
        seed=seed,
        resources={"energy": 10},
    )
    traces = []
    for _ in range(turns):
        opportunities = available_opportunities(topology, session)
        assert opportunities, "cyclic sandbox fixture starved"
        route = next(item for item in opportunities if item.kind == "travel")
        session, trace = travel(
            topology, session, route.source_id, expected_revision=session.revision
        )
        traces.append(trace.model_dump(mode="json"))
    return session, traces


def test_same_seed_state_and_action_sequence_produces_identical_long_trace():
    first_session, first_trace = _run_trace(8341)
    second_session, second_trace = _run_trace(8341)

    assert first_trace == second_trace
    assert first_session == second_session
    assert first_session.revision == 101
    assert len(first_session.visits) == 101


def test_disposable_long_run_does_not_mutate_authored_topology():
    topology = _loop_topology()
    before = topology.model_dump_json()
    _run_trace(9, turns=25)

    assert topology.model_dump_json() == before


def test_resource_bound_prevents_underflow_and_removes_unaffordable_route():
    topology = _loop_topology(cost=1)
    session = create_runtime_session(
        topology,
        session_id="bounded_run",
        experience_profile_fingerprint=ExperienceProfile.sandbox().fingerprint(),
        start_location="east",
        time_model="turn",
        seed=4,
        resources={"energy": 2},
    )
    session, _ = travel(topology, session, "east_west", expected_revision=1)
    session, _ = travel(topology, session, "west_east", expected_revision=2)

    assert session.resources["energy"] == 0
    assert not any(item.kind == "travel" for item in available_opportunities(topology, session))
