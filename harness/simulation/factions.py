"""Pure bounded faction-state transitions."""
from __future__ import annotations

from .contracts import FactionEffect, FactionState
from .engine import SimulationError


def apply_faction_effect(faction: FactionState, effect: FactionEffect) -> FactionState:
    if faction.faction_id != effect.faction_id:
        raise SimulationError("faction_effect_target_conflict", "effect belongs to another faction")
    if effect.operation == "influence":
        return faction.model_copy(update={"influence": min(1.0, max(0.0, faction.influence + effect.delta))})
    if effect.operation == "disposition":
        return faction.model_copy(update={"disposition": min(1.0, max(-1.0, faction.disposition + effect.delta))})
    if effect.operation == "resource":
        resources = dict(faction.resources)
        value = resources.get(effect.target, 0) + effect.delta
        if value < 0:
            raise SimulationError("faction_resource_underflow", "faction resource cannot fall below zero")
        resources[effect.target] = value
        return faction.model_copy(update={"resources": resources})
    relationships = dict(faction.relationships)
    relationships[effect.target] = min(1.0, max(-1.0, relationships.get(effect.target, 0) + effect.delta))
    return faction.model_copy(update={"relationships": relationships})


__all__ = ["apply_faction_effect"]
