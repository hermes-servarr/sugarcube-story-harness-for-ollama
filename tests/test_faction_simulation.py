import pytest

from harness.simulation import FactionEffect, FactionState, SimulationError, apply_faction_effect


def test_faction_effects_are_bounded_pure_and_resource_safe():
    original = FactionState(
        faction_id="guild", influence=0.9, disposition=-0.8,
        resources={"coin": 2}, relationships={"guard": 0.8},
    )
    influence = apply_faction_effect(original, FactionEffect(
        faction_id="guild", operation="influence", delta=0.5,
    ))
    disposition = apply_faction_effect(influence, FactionEffect(
        faction_id="guild", operation="disposition", delta=-0.5,
    ))
    related = apply_faction_effect(disposition, FactionEffect(
        faction_id="guild", operation="relationship", target="guard", delta=0.5,
    ))
    spent = apply_faction_effect(related, FactionEffect(
        faction_id="guild", operation="resource", target="coin", delta=-2,
    ))

    assert original.influence == 0.9
    assert spent.influence == 1
    assert spent.disposition == -1
    assert spent.relationships["guard"] == 1
    assert spent.resources["coin"] == 0

    with pytest.raises(SimulationError) as underflow:
        apply_faction_effect(spent, FactionEffect(
            faction_id="guild", operation="resource", target="coin", delta=-1,
        ))
    assert underflow.value.code == "faction_resource_underflow"
