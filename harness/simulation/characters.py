"""Pure, schema-authorized persistent-character transitions."""
from __future__ import annotations

from typing import Any

from .contracts import (
    AgendaState,
    CharacterEffect,
    CharacterRuntimeState,
    CharacterStatDefinition,
    ConditionState,
)
from .engine import SimulationError


def initialize_character(
    character_id: str,
    current_location: str,
    definitions: tuple[CharacterStatDefinition, ...],
) -> CharacterRuntimeState:
    _definition_map(definitions)
    return CharacterRuntimeState(
        character_id=character_id,
        current_location=current_location,
        stats={definition.id: definition.default for definition in definitions},
    )


def apply_character_effect(
    character: CharacterRuntimeState,
    definitions: tuple[CharacterStatDefinition, ...],
    effect: CharacterEffect,
    *,
    expected_revision: int,
    tick: int,
) -> CharacterRuntimeState:
    if character.revision != expected_revision:
        raise SimulationError(
            "character_revision_conflict",
            f"expected character revision {expected_revision}, found {character.revision}",
        )
    if character.character_id != effect.character_id:
        raise SimulationError("character_effect_target_conflict", "effect belongs to another character")
    definitions_by_id = _definition_map(definitions)
    update: dict[str, Any] = {"revision": character.revision + 1, "last_updated_tick": tick}
    if effect.operation in {"set", "add", "clamp"}:
        definition = definitions_by_id.get(effect.target)
        if definition is None:
            raise SimulationError("character_stat_unknown", "effect targets an undefined character stat")
        if effect.operation not in definition.allowed_operations:
            raise SimulationError("character_operation_forbidden", "stat definition does not allow this operation")
        stats = dict(character.stats)
        current = stats.get(definition.id, definition.default)
        if effect.operation == "set":
            value = effect.value
        elif effect.operation == "add":
            if isinstance(current, bool) or not isinstance(current, (int, float)) or isinstance(effect.value, bool) or not isinstance(effect.value, (int, float)):
                raise SimulationError("character_stat_type_mismatch", "add requires numeric stat and value")
            value = current + effect.value
        else:
            if not isinstance(current, (int, float)) or isinstance(current, bool):
                raise SimulationError("character_stat_type_mismatch", "clamp requires a numeric stat")
            value = current
        stats[definition.id] = _validate_stat_value(definition, value, clamp=effect.operation == "clamp")
        update["stats"] = stats
    elif effect.operation == "remove":
        inventory = dict(character.inventory)
        quantity = effect.value if isinstance(effect.value, int) and not isinstance(effect.value, bool) else 1
        if quantity < 1 or inventory.get(effect.target, 0) < quantity:
            raise SimulationError("character_inventory_underflow", "inventory removal exceeds available quantity")
        remaining = inventory[effect.target] - quantity
        if remaining:
            inventory[effect.target] = remaining
        else:
            inventory.pop(effect.target)
        update["inventory"] = inventory
    elif effect.operation in {"add_fact", "remove_fact"}:
        facts = list(character.known_facts)
        if effect.operation == "add_fact" and effect.target not in facts:
            facts.append(effect.target)
        if effect.operation == "remove_fact":
            facts = [fact for fact in facts if fact != effect.target]
        update["known_facts"] = tuple(facts)
    elif effect.operation == "move_character":
        if not isinstance(effect.value, str):
            raise SimulationError("character_location_invalid", "move_character requires a location id")
        update["current_location"] = effect.value
    elif effect.operation == "start_condition":
        condition = effect.value if isinstance(effect.value, ConditionState) else ConditionState.model_validate(effect.value)
        update["conditions"] = tuple(item for item in character.conditions if item.id != condition.id) + (condition,)
    elif effect.operation == "advance_agenda":
        agendas = list(character.agendas)
        index = next((index for index, item in enumerate(agendas) if item.id == effect.target), None)
        if index is None or isinstance(effect.value, bool) or not isinstance(effect.value, (int, float)):
            raise SimulationError("character_agenda_invalid", "advance_agenda needs an existing agenda and numeric delta")
        agenda = agendas[index]
        progress = min(1.0, max(0.0, agenda.progress + effect.value))
        agendas[index] = agenda.model_copy(update={
            "progress": progress,
            "status": "completed" if progress >= 1 else agenda.status,
        })
        update["agendas"] = tuple(agendas)
    elif effect.operation == "schedule_activity":
        if not isinstance(effect.value, str) or not effect.value.strip():
            raise SimulationError("character_activity_invalid", "schedule_activity requires activity text")
        update["activity"] = effect.value.strip()
    return CharacterRuntimeState.model_validate(character.model_copy(update=update).model_dump())


def advance_character_time(
    character: CharacterRuntimeState,
    definitions: tuple[CharacterStatDefinition, ...],
    *,
    to_tick: int,
    expected_revision: int,
) -> CharacterRuntimeState:
    if character.revision != expected_revision:
        raise SimulationError("character_revision_conflict", "character changed since it was loaded")
    if to_tick < character.last_updated_tick:
        raise SimulationError("character_clock_reversed", "character time cannot move backwards")
    elapsed = to_tick - character.last_updated_tick
    definitions_by_id = _definition_map(definitions)
    stats = dict(character.stats)
    for stat_id, definition in definitions_by_id.items():
        if definition.decay_per_tick is not None:
            stats[stat_id] = _validate_stat_value(
                definition, stats.get(stat_id, definition.default) + definition.decay_per_tick * elapsed,
                clamp=True,
            )
    needs = tuple(item.model_copy(update={
        "value": min(1.0, max(0.0, item.value + item.change_per_tick * elapsed)),
    }) for item in character.needs)
    conditions = tuple(
        item.model_copy(update={
            "remaining_ticks": None if item.remaining_ticks is None else item.remaining_ticks - elapsed,
        })
        for item in character.conditions
        if item.remaining_ticks is None or item.remaining_ticks > elapsed
    )
    agendas: list[AgendaState] = []
    for agenda in character.agendas:
        status = "failed" if agenda.deadline_tick is not None and to_tick > agenda.deadline_tick and agenda.status == "active" else agenda.status
        agendas.append(agenda.model_copy(update={"status": status}))
    return CharacterRuntimeState.model_validate(character.model_copy(update={
        "revision": character.revision + 1,
        "stats": stats,
        "needs": needs,
        "conditions": conditions,
        "agendas": tuple(agendas),
        "last_updated_tick": to_tick,
        "cooldowns": {key: value for key, value in character.cooldowns.items() if value > to_tick},
    }).model_dump())


def character_context(
    character: CharacterRuntimeState,
    definitions: tuple[CharacterStatDefinition, ...],
    *,
    audience: str,
    authorized_private_stats: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Project only visibility-authorized state into narrative/model context."""
    if audience not in {"player", "model"}:
        raise SimulationError("character_context_audience_invalid", "audience must be player or model")
    definitions_by_id = _definition_map(definitions)
    allowed = {
        stat_id for stat_id, definition in definitions_by_id.items()
        if definition.visibility == "public"
        or audience == "model" and definition.visibility == "model"
        or stat_id in authorized_private_stats
    }
    return {
        "character_id": character.character_id,
        "current_location": character.current_location,
        "activity": character.activity,
        "stats": {key: value for key, value in character.stats.items() if key in allowed},
        "known_facts": list(character.known_facts),
    }


def _definition_map(definitions: tuple[CharacterStatDefinition, ...]) -> dict[str, CharacterStatDefinition]:
    mapped = {definition.id: definition for definition in definitions}
    if len(mapped) != len(definitions):
        raise SimulationError("character_stat_definition_duplicate", "duplicate character stat definition")
    return mapped


def _validate_stat_value(definition: CharacterStatDefinition, value: Any, *, clamp: bool) -> Any:
    expected = {"bool": bool, "int": int, "float": (int, float), "string": str}[definition.value_type]
    if not isinstance(value, expected) or definition.value_type in {"int", "float"} and isinstance(value, bool):
        raise SimulationError("character_stat_type_mismatch", "character stat value has the wrong type")
    if definition.value_type in {"int", "float"}:
        if clamp:
            if definition.minimum is not None:
                value = max(definition.minimum, value)
            if definition.maximum is not None:
                value = min(definition.maximum, value)
        elif (definition.minimum is not None and value < definition.minimum) or (definition.maximum is not None and value > definition.maximum):
            raise SimulationError("character_stat_out_of_bounds", "character stat value exceeds declared bounds")
        if definition.value_type == "int" and not isinstance(value, int):
            if float(value).is_integer():
                value = int(value)
            else:
                raise SimulationError("character_stat_type_mismatch", "integer stat cannot hold a fractional value")
    return value


__all__ = [
    "advance_character_time",
    "apply_character_effect",
    "character_context",
    "initialize_character",
]
