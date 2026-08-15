"""Pure deterministic transition engine for typed Sandbox topology."""
from __future__ import annotations

import hashlib
from typing import Any

from ..generation.contracts import StateCondition, StateEffect, StateOperation
from .contracts import (
    AuthoredAnchor,
    CharacterRuntimeState,
    CharacterStatDefinition,
    EncounterSelection,
    EncounterTemplate,
    LocationAction,
    Opportunity,
    Route,
    RuntimeSession,
    SimulationClock,
    SimulationTrace,
    SystemRule,
    VisitRecord,
    WorldTopology,
    FactionState,
)


class SimulationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def create_runtime_session(
    topology: WorldTopology,
    *,
    session_id: str,
    experience_profile_fingerprint: str,
    start_location: str,
    time_model: str,
    seed: int,
    world_state: dict[str, Any] | None = None,
    resources: dict[str, float | int] | None = None,
    factions: tuple[FactionState, ...] = (),
    character_stat_definitions: tuple[CharacterStatDefinition, ...] = (),
    characters: tuple[CharacterRuntimeState, ...] = (),
) -> RuntimeSession:
    if start_location not in {location.id for location in topology.locations}:
        raise SimulationError("start_location_unknown", "start location is not in the topology")
    location_ids = {location.id for location in topology.locations}
    unknown_locations = sorted({item.current_location for item in characters} - location_ids)
    if unknown_locations:
        raise SimulationError(
            "character_location_unknown",
            f"character locations are not in the topology: {unknown_locations}",
        )
    return RuntimeSession(
        session_id=session_id,
        topology_fingerprint=topology.fingerprint(),
        experience_profile_fingerprint=experience_profile_fingerprint,
        seed=seed,
        current_location=start_location,
        clock=SimulationClock(model=time_model, tick=0),
        world_state=world_state or {},
        resources=resources or {},
        visits=(VisitRecord(visit_index=0, location_id=start_location, entered_tick=0),),
        factions=factions,
        character_stat_definitions=character_stat_definitions,
        characters=characters,
    )


def eligible(condition: StateCondition, state: dict[str, Any]) -> bool:
    actual = state.get(condition.target)
    operation = condition.operation
    if operation == "truthy":
        return bool(actual)
    if operation == "falsy":
        return not actual
    if operation == "eq":
        return actual == condition.value
    if operation == "ne":
        return actual != condition.value
    if actual is None:
        return False
    try:
        return {
            "gt": actual > condition.value,
            "gte": actual >= condition.value,
            "lt": actual < condition.value,
            "lte": actual <= condition.value,
        }[operation]
    except (KeyError, TypeError):
        return False


def available_opportunities(
    topology: WorldTopology,
    session: RuntimeSession,
    authored_anchors: tuple[AuthoredAnchor, ...] = (),
) -> tuple[Opportunity, ...]:
    _bind(topology, session)
    state = _eligibility_state(session)
    location = _location(topology, session.current_location)
    opportunities: list[Opportunity] = []
    for action in location.actions:
        if all(eligible(condition, state) for condition in action.eligibility):
            opportunities.append(_opportunity(
                "local_action", action.id, action.label, location.id, session.clock.tick
            ))
    for route in topology.routes:
        if route.source != location.id:
            continue
        if not all(eligible(condition, state) for condition in route.eligibility):
            continue
        if any(session.resources.get(resource, 0) < amount for resource, amount in route.resource_cost.items()):
            continue
        destination = _location(topology, route.destination)
        opportunities.append(_opportunity(
            "travel", route.id, f"Travel to {destination.name}", location.id, session.clock.tick
        ))
    completed = set(session.completed_anchor_ids)
    for anchor in authored_anchors:
        if anchor.location_id != location.id or anchor.id in completed:
            continue
        if not set(anchor.prerequisite_ids).issubset(completed):
            continue
        if not all(eligible(condition, state) for condition in anchor.eligibility):
            continue
        opportunities.append(_opportunity(
            "authored_anchor", anchor.id, anchor.label, location.id, session.clock.tick
        ))
    return tuple(sorted(opportunities, key=lambda item: (item.kind, item.id)))


def complete_authored_anchor(
    topology: WorldTopology,
    session: RuntimeSession,
    anchor: AuthoredAnchor,
    *,
    expected_revision: int,
) -> tuple[RuntimeSession, SimulationTrace]:
    """Complete one eligible Hybrid anchor without mutating authored planning."""
    _expect_revision(session, expected_revision)
    _bind(topology, session)
    available = {
        item.source_id
        for item in available_opportunities(topology, session, (anchor,))
        if item.kind == "authored_anchor"
    }
    if anchor.id not in available:
        raise SimulationError("authored_anchor_ineligible", "authored anchor is not currently eligible")
    visits = list(session.visits)
    visits[-1] = visits[-1].model_copy(update={
        "selected_actions": (*visits[-1].selected_actions, anchor.id),
    })
    updated = session.model_copy(update={
        "revision": session.revision + 1,
        "completed_anchor_ids": (*session.completed_anchor_ids, anchor.id),
        "occurrence_counts": _increment(session.occurrence_counts, anchor.id),
        "visits": tuple(visits),
    })
    return updated, _trace(session, updated, "authored_anchor", anchor.id, (), {})


def apply_local_action(
    topology: WorldTopology,
    session: RuntimeSession,
    action_id: str,
    *,
    expected_revision: int,
    system_rules: tuple[SystemRule, ...] = (),
) -> tuple[RuntimeSession, SimulationTrace]:
    _expect_revision(session, expected_revision)
    _bind(topology, session)
    location = _location(topology, session.current_location)
    action = next((item for item in location.actions if item.id == action_id), None)
    if action is None:
        raise SimulationError("action_unknown", "action is not available at the current location")
    if not all(eligible(condition, _eligibility_state(session)) for condition in action.eligibility):
        raise SimulationError("action_ineligible", "action eligibility conditions are not satisfied")
    world_state, applied = _apply_effects(session.world_state, action.effects)
    tick = session.clock.tick + action.time_cost
    visits = list(session.visits)
    current = visits[-1]
    visits[-1] = current.model_copy(update={
        "selected_actions": (*current.selected_actions, action.id),
        "applied_effects": (*current.applied_effects, *applied),
    })
    updated = session.model_copy(update={
        "revision": session.revision + 1,
        "clock": session.clock.model_copy(update={"tick": tick}),
        "world_state": world_state,
        "occurrence_counts": _increment(session.occurrence_counts, action.id),
        "visits": tuple(visits),
    })
    updated = _advance_characters(updated, tick)
    updated, rule_effects = _run_system_rules(updated, system_rules, ("local_action",))
    return updated, _trace(session, updated, "local_action", action.id, (*applied, *rule_effects), {})


def travel(
    topology: WorldTopology,
    session: RuntimeSession,
    route_id: str,
    *,
    expected_revision: int,
    system_rules: tuple[SystemRule, ...] = (),
) -> tuple[RuntimeSession, SimulationTrace]:
    _expect_revision(session, expected_revision)
    _bind(topology, session)
    route = next((item for item in topology.routes if item.id == route_id), None)
    if route is None or route.source != session.current_location:
        raise SimulationError("route_unavailable", "route does not depart from the current location")
    state = _eligibility_state(session)
    if not all(eligible(condition, state) for condition in route.eligibility):
        raise SimulationError("route_ineligible", "route eligibility conditions are not satisfied")
    for resource, cost in route.resource_cost.items():
        if session.resources.get(resource, 0) < cost:
            raise SimulationError("route_cost_unaffordable", f"route requires {cost} {resource}")
    resources = dict(session.resources)
    delta: dict[str, float | int] = {}
    for resource, cost in route.resource_cost.items():
        resources[resource] = resources.get(resource, 0) - cost
        delta[resource] = -cost
    world_state, applied = _apply_effects(session.world_state, route.travel_effects)
    tick = session.clock.tick + route.time_cost
    visits = list(session.visits)
    visits[-1] = visits[-1].model_copy(update={"exited_tick": tick})
    visits.append(VisitRecord(
        visit_index=len(visits),
        location_id=route.destination,
        entered_tick=tick,
        applied_effects=applied,
    ))
    updated = session.model_copy(update={
        "revision": session.revision + 1,
        "current_location": route.destination,
        "clock": session.clock.model_copy(update={"tick": tick}),
        "world_state": world_state,
        "resources": resources,
        "occurrence_counts": _increment(session.occurrence_counts, route.id),
        "visits": tuple(visits),
    })
    updated = _advance_characters(updated, tick)
    updated, rule_effects = _run_system_rules(updated, system_rules, ("travel", "enter_location"))
    return updated, _trace(session, updated, "travel", route.id, (*applied, *rule_effects), delta)


def reachable_locations(topology: WorldTopology, start_location: str) -> frozenset[str]:
    if start_location not in {location.id for location in topology.locations}:
        raise SimulationError("start_location_unknown", "start location is not in the topology")
    reached = {start_location}
    pending = [start_location]
    while pending:
        source = pending.pop()
        for route in topology.routes:
            if route.source == source and route.destination not in reached:
                reached.add(route.destination)
                pending.append(route.destination)
    return frozenset(reached)


def advance_systems(
    session: RuntimeSession,
    rules: tuple[SystemRule, ...],
    *,
    trigger: str = "tick",
    expected_revision: int,
    ticks: int = 1,
) -> tuple[RuntimeSession, SimulationTrace]:
    """Advance time and apply eligible rules in stable priority/id order."""
    _expect_revision(session, expected_revision)
    if trigger not in {"tick", "local_action", "travel", "enter_location", "encounter"}:
        raise SimulationError("system_trigger_invalid", "unknown system trigger")
    if isinstance(ticks, bool) or not isinstance(ticks, int) or ticks < 0:
        raise SimulationError("simulation_ticks_invalid", "ticks must be a nonnegative integer")
    tick = session.clock.tick + ticks
    updated = session.model_copy(update={
        "revision": session.revision + 1,
        "clock": session.clock.model_copy(update={"tick": tick}),
    })
    updated = _advance_characters(updated, tick)
    updated, applied = _run_system_rules(updated, rules, (trigger,))
    return updated, _trace(session, updated, "system_tick", "system_tick", tuple(applied), {})


def select_encounter(
    session: RuntimeSession,
    templates: tuple[EncounterTemplate, ...],
    *,
    location: Any,
) -> EncounterSelection | None:
    """Select one eligible weighted template from stable seed/revision material."""
    state = _eligibility_state(session)
    location_tags = set(location.tags)
    candidates = [
        template for template in templates
        if (not template.location_ids or location.id in template.location_ids)
        and set(template.required_tags).issubset(location_tags)
        and all(eligible(condition, state) for condition in template.eligibility)
        and session.cooldowns.get(template.id, 0) <= session.clock.tick
        and (
            template.occurrence_limit is None
            or session.occurrence_counts.get(template.id, 0) < template.occurrence_limit
        )
        and (
            not template.plan.experience_profile_fingerprint
            or template.plan.experience_profile_fingerprint == session.experience_profile_fingerprint
        )
    ]
    candidates.sort(key=lambda item: item.id)
    if not candidates:
        return None
    seed_material = ":".join((
        str(session.seed), str(session.revision), str(session.clock.tick),
        location.id, *[item.id for item in candidates],
    ))
    digest = hashlib.sha256(seed_material.encode()).hexdigest()
    total = sum(item.weight for item in candidates)
    roll = int(digest, 16) % total
    cursor = 0
    chosen = candidates[-1]
    for candidate in candidates:
        cursor += candidate.weight
        if roll < cursor:
            chosen = candidate
            break
    return EncounterSelection(
        template_id=chosen.id,
        location_id=location.id,
        eligible_template_ids=tuple(item.id for item in candidates),
        deterministic_roll=roll,
        total_weight=total,
        seed_material_fingerprint=digest,
    )


def record_encounter(
    session: RuntimeSession,
    template: EncounterTemplate,
    selection: EncounterSelection,
    *,
    expected_revision: int,
) -> tuple[RuntimeSession, SimulationTrace]:
    _expect_revision(session, expected_revision)
    if selection.template_id != template.id or selection.location_id != session.current_location:
        raise SimulationError("encounter_selection_conflict", "selection does not match this session")
    counts = _increment(session.occurrence_counts, template.id)
    cooldowns = dict(session.cooldowns)
    cooldowns[template.id] = session.clock.tick + template.cooldown_ticks
    updated = session.model_copy(update={
        "revision": session.revision + 1,
        "occurrence_counts": counts,
        "cooldowns": cooldowns,
    })
    return updated, _trace(session, updated, "encounter", template.id, (), {})


def _bind(topology: WorldTopology, session: RuntimeSession) -> None:
    if topology.fingerprint() != session.topology_fingerprint:
        raise SimulationError("topology_fingerprint_conflict", "session belongs to another topology revision")


def _advance_characters(session: RuntimeSession, to_tick: int) -> RuntimeSession:
    if not session.characters:
        return session
    # Local import avoids the character reducer's SimulationError dependency
    # forming an import cycle at module initialization.
    from .characters import advance_character_time

    characters = tuple(
        advance_character_time(
            character,
            session.character_stat_definitions,
            to_tick=to_tick,
            expected_revision=character.revision,
        )
        if to_tick > character.last_updated_tick else character
        for character in session.characters
    )
    return session.model_copy(update={"characters": characters})


def _expect_revision(session: RuntimeSession, expected: int) -> None:
    if session.revision != expected:
        raise SimulationError(
            "simulation_revision_conflict",
            f"expected session revision {expected}, found {session.revision}",
        )


def _location(topology: WorldTopology, location_id: str):
    location = next((item for item in topology.locations if item.id == location_id), None)
    if location is None:
        raise SimulationError("location_unknown", "location is not in the topology")
    return location


def _eligibility_state(session: RuntimeSession) -> dict[str, Any]:
    return {
        **session.world_state,
        **{f"resource_{key}": value for key, value in session.resources.items()},
        "simulation_tick": session.clock.tick,
    }


def _apply_effects(
    initial: dict[str, Any], effects: tuple[StateEffect, ...]
) -> tuple[dict[str, Any], tuple[str, ...]]:
    state = dict(initial)
    applied: list[str] = []
    for effect in effects:
        current = state.get(effect.target)
        if effect.operation == StateOperation.SET:
            state[effect.target] = effect.value
        elif effect.operation in {StateOperation.ADD, StateOperation.SUBTRACT}:
            if isinstance(current, bool) or not isinstance(current, (int, float)):
                raise SimulationError("effect_type_mismatch", f"{effect.target} is not numeric")
            if isinstance(effect.value, bool) or not isinstance(effect.value, (int, float)):
                raise SimulationError("effect_type_mismatch", "numeric effect requires a numeric value")
            direction = 1 if effect.operation == StateOperation.ADD else -1
            state[effect.target] = current + direction * effect.value
        elif effect.operation == StateOperation.TOGGLE:
            if not isinstance(current, bool):
                raise SimulationError("effect_type_mismatch", f"{effect.target} is not boolean")
            state[effect.target] = not current
        applied.append(effect.component_id)
    return state, tuple(applied)


def _run_system_rules(
    session: RuntimeSession,
    rules: tuple[SystemRule, ...],
    triggers: tuple[str, ...],
) -> tuple[RuntimeSession, tuple[str, ...]]:
    state = dict(session.world_state)
    counts = dict(session.occurrence_counts)
    cooldowns = dict(session.cooldowns)
    characters = list(session.characters)
    factions = list(session.factions)
    applied: list[str] = []
    for trigger in triggers:
        matching = sorted(
            (rule for rule in rules if rule.trigger == trigger),
            key=lambda rule: (-rule.priority, rule.id),
        )
        for rule in matching:
            if cooldowns.get(rule.id, 0) > session.clock.tick:
                continue
            if rule.occurrence_limit is not None and counts.get(rule.id, 0) >= rule.occurrence_limit:
                continue
            eligibility_state = {
                **state,
                **{f"resource_{key}": value for key, value in session.resources.items()},
                "simulation_tick": session.clock.tick,
            }
            if not all(eligible(condition, eligibility_state) for condition in rule.conditions):
                continue
            state, effect_ids = _apply_effects(state, rule.effects)
            applied.extend(effect_ids)
            if rule.character_effects:
                from .characters import apply_character_effect
                for index, effect in enumerate(rule.character_effects):
                    position = next((i for i, item in enumerate(characters) if item.character_id == effect.character_id), None)
                    if position is None:
                        raise SimulationError("character_effect_target_unknown", "system rule targets an unknown character")
                    character = characters[position]
                    characters[position] = apply_character_effect(
                        character,
                        session.character_stat_definitions,
                        effect,
                        expected_revision=character.revision,
                        tick=session.clock.tick,
                    )
                    applied.append(f"character:{rule.id}:{index}")
            if rule.faction_effects:
                from .factions import apply_faction_effect
                for index, effect in enumerate(rule.faction_effects):
                    position = next((i for i, item in enumerate(factions) if item.faction_id == effect.faction_id), None)
                    if position is None:
                        raise SimulationError("faction_effect_target_unknown", "system rule targets an unknown faction")
                    factions[position] = apply_faction_effect(factions[position], effect)
                    applied.append(f"faction:{rule.id}:{index}")
            counts[rule.id] = counts.get(rule.id, 0) + 1
            cooldowns[rule.id] = session.clock.tick + rule.cooldown_ticks
    return session.model_copy(update={
        "world_state": state,
        "occurrence_counts": counts,
        "cooldowns": cooldowns,
        "characters": tuple(characters),
        "factions": tuple(factions),
    }), tuple(applied)


def _increment(values: dict[str, int], key: str) -> dict[str, int]:
    updated = dict(values)
    updated[key] = updated.get(key, 0) + 1
    return updated


def _opportunity(kind: str, source_id: str, label: str, location_id: str, tick: int) -> Opportunity:
    suffix = hashlib.sha256(f"{kind}:{source_id}:{location_id}".encode()).hexdigest()[:12]
    return Opportunity(
        id=f"opportunity_{suffix}",
        kind=kind,
        label=label,
        location_id=location_id,
        source_id=source_id,
        eligible_at_tick=tick,
        provenance=f"topology:{source_id}",
    )


def _trace(
    before: RuntimeSession,
    after: RuntimeSession,
    kind: str,
    action_id: str,
    effects: tuple[str, ...],
    resource_delta: dict[str, float | int],
) -> SimulationTrace:
    return SimulationTrace(
        action_kind=kind,
        action_id=action_id,
        from_revision=before.revision,
        to_revision=after.revision,
        from_location=before.current_location,
        to_location=after.current_location,
        tick_before=before.clock.tick,
        tick_after=after.clock.tick,
        applied_effects=effects,
        resource_delta=resource_delta,
    )


__all__ = [
    "SimulationError",
    "advance_systems",
    "apply_local_action",
    "available_opportunities",
    "create_runtime_session",
    "eligible",
    "reachable_locations",
    "record_encounter",
    "select_encounter",
    "travel",
]
