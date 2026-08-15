"""Typed authority contracts for deterministic Hybrid/Sandbox simulation."""
from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from ..generation.contracts import PassagePlan, StateCondition, StateEffect, StrictFrozenModel, TimeModel


def _id(value: str, label: str) -> str:
    import re
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value):
        raise ValueError(f"invalid {label}")
    return value


def _positive_revision(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("revision must be a positive integer")
    return value


def _finite_number(value: Any, label: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return value


class LocationAction(StrictFrozenModel):
    id: str
    label: str
    eligibility: tuple[StateCondition, ...] = ()
    effects: tuple[StateEffect, ...] = ()
    time_cost: int = Field(default=1, ge=0)
    encounter_table_refs: tuple[str, ...] = ()

    @field_validator("id")
    @classmethod
    def _valid_id(cls, value: str) -> str:
        return _id(value, "location action id")

    @field_validator("encounter_table_refs")
    @classmethod
    def _encounter_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_id(value, "encounter table reference") for value in values)

    @field_validator("label")
    @classmethod
    def _label(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("location action label cannot be blank")
        return value.strip()


class LocationNode(StrictFrozenModel):
    id: str
    name: str
    region_id: str
    tags: tuple[str, ...] = ()
    actions: tuple[LocationAction, ...] = ()
    encounter_table_refs: tuple[str, ...] = ()

    @field_validator("id", "region_id")
    @classmethod
    def _ids(cls, value: str, info: Any) -> str:
        return _id(value, info.field_name)

    @field_validator("tags", "encounter_table_refs")
    @classmethod
    def _stable_ids(cls, values: tuple[str, ...], info: Any) -> tuple[str, ...]:
        checked = tuple(_id(value, info.field_name) for value in values)
        if len(checked) != len(set(checked)):
            raise ValueError(f"duplicate {info.field_name}")
        return checked

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("location name cannot be blank")
        return value.strip()

    @model_validator(mode="after")
    def _unique_actions(self) -> "LocationNode":
        ids = [action.id for action in self.actions]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate location action")
        return self


class Route(StrictFrozenModel):
    id: str
    source: str
    destination: str
    eligibility: tuple[StateCondition, ...] = ()
    resource_cost: dict[str, float | int] = Field(default_factory=dict)
    travel_effects: tuple[StateEffect, ...] = ()
    risk_tags: tuple[str, ...] = ()
    time_cost: int = Field(default=1, ge=0)

    @field_validator("id", "source", "destination")
    @classmethod
    def _ids(cls, value: str, info: Any) -> str:
        return _id(value, info.field_name)

    @field_validator("risk_tags")
    @classmethod
    def _risks(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_id(value, "risk tag") for value in values)

    @field_validator("resource_cost")
    @classmethod
    def _costs(cls, values: dict[str, float | int]) -> dict[str, float | int]:
        checked: dict[str, float | int] = {}
        for key, value in values.items():
            checked[_id(key, "resource id")] = _finite_number(value, "resource cost")
            if value < 0:
                raise ValueError("resource cost cannot be negative")
        return checked

    @model_validator(mode="after")
    def _not_self_route(self) -> "Route":
        if self.source == self.destination:
            raise ValueError("route source and destination must differ")
        return self


class WorldTopology(StrictFrozenModel):
    schema_version: int = 1
    revision: int = 1
    locations: tuple[LocationNode, ...]
    routes: tuple[Route, ...] = ()

    @field_validator("schema_version")
    @classmethod
    def _schema(cls, value: int) -> int:
        if isinstance(value, bool) or value != 1:
            raise ValueError("schema_version must be 1")
        return value

    @field_validator("revision", mode="before")
    @classmethod
    def _revision(cls, value: Any) -> int:
        return _positive_revision(value)

    @model_validator(mode="after")
    def _valid_graph(self) -> "WorldTopology":
        location_ids = [location.id for location in self.locations]
        route_ids = [route.id for route in self.routes]
        if not location_ids:
            raise ValueError("topology needs at least one location")
        if len(location_ids) != len(set(location_ids)):
            raise ValueError("duplicate location")
        if len(route_ids) != len(set(route_ids)):
            raise ValueError("duplicate route")
        known = set(location_ids)
        for route in self.routes:
            if route.source not in known or route.destination not in known:
                raise ValueError("route references an unknown location")
        return self


class SimulationClock(StrictFrozenModel):
    model: TimeModel
    tick: int = Field(default=0, ge=0)


class VisitRecord(StrictFrozenModel):
    visit_index: int = Field(ge=0)
    location_id: str
    entered_tick: int = Field(ge=0)
    exited_tick: int | None = Field(default=None, ge=0)
    selected_actions: tuple[str, ...] = ()
    applied_effects: tuple[str, ...] = ()

    @field_validator("location_id")
    @classmethod
    def _location(cls, value: str) -> str:
        return _id(value, "visit location")


class CharacterStatDefinition(StrictFrozenModel):
    id: str
    value_type: Literal["bool", "int", "float", "string"]
    default: Any
    minimum: float | int | None = None
    maximum: float | int | None = None
    visibility: Literal["public", "model", "private"] = "model"
    allowed_operations: tuple[Literal["set", "add", "clamp"], ...] = ("set",)
    decay_per_tick: float | None = None
    description: str = ""

    @field_validator("id")
    @classmethod
    def _stat_id(cls, value: str) -> str:
        return _id(value, "character stat id")

    @model_validator(mode="after")
    def _valid_default_and_bounds(self) -> "CharacterStatDefinition":
        expected = {"bool": bool, "int": int, "float": (int, float), "string": str}[self.value_type]
        if not isinstance(self.default, expected) or self.value_type in {"int", "float"} and isinstance(self.default, bool):
            raise ValueError("character stat default does not match value_type")
        if self.value_type not in {"int", "float"} and (self.minimum is not None or self.maximum is not None):
            raise ValueError("only numeric stats may declare bounds")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("character stat minimum exceeds maximum")
        if self.minimum is not None and self.default < self.minimum:
            raise ValueError("character stat default is below minimum")
        if self.maximum is not None and self.default > self.maximum:
            raise ValueError("character stat default is above maximum")
        if self.decay_per_tick is not None and self.value_type not in {"int", "float"}:
            raise ValueError("only numeric stats may decay")
        return self


class RelationshipState(StrictFrozenModel):
    target_character_id: str
    values: dict[str, float] = Field(default_factory=dict)

    @field_validator("target_character_id")
    @classmethod
    def _target_character(cls, value: str) -> str:
        return _id(value, "relationship target")

    @field_validator("values")
    @classmethod
    def _relationship_values(cls, values: dict[str, float]) -> dict[str, float]:
        checked: dict[str, float] = {}
        for key, value in values.items():
            _id(key, "relationship value id")
            numeric = float(_finite_number(value, "relationship value"))
            if numeric < -1 or numeric > 1:
                raise ValueError("relationship values must be between -1 and 1")
            checked[key] = numeric
        return checked


class NeedState(StrictFrozenModel):
    id: str
    value: float = Field(ge=0, le=1)
    change_per_tick: float = 0

    @field_validator("id")
    @classmethod
    def _need_id(cls, value: str) -> str:
        return _id(value, "need id")


class AgendaState(StrictFrozenModel):
    id: str
    goal: str
    priority: int = 0
    progress: float = Field(default=0, ge=0, le=1)
    eligibility: tuple[StateCondition, ...] = ()
    deadline_tick: int | None = Field(default=None, ge=0)
    current_step: str = ""
    blocked_reason: str = ""
    status: Literal["active", "blocked", "completed", "failed"] = "active"

    @field_validator("id")
    @classmethod
    def _agenda_id(cls, value: str) -> str:
        return _id(value, "agenda id")


class ScheduleRule(StrictFrozenModel):
    id: str
    start_tick: int = Field(ge=0)
    end_tick: int | None = Field(default=None, ge=0)
    location_id: str
    activity: str
    priority: int = 0

    @field_validator("id", "location_id")
    @classmethod
    def _schedule_ids(cls, value: str, info: Any) -> str:
        return _id(value, info.field_name)

    @model_validator(mode="after")
    def _valid_range(self) -> "ScheduleRule":
        if self.end_tick is not None and self.end_tick < self.start_tick:
            raise ValueError("schedule end precedes start")
        return self


class ConditionState(StrictFrozenModel):
    id: str
    kind: Literal["injury", "illness", "mood", "buff", "debuff"]
    severity: float = Field(default=0, ge=0, le=1)
    remaining_ticks: int | None = Field(default=None, ge=0)
    source: str = ""

    @field_validator("id")
    @classmethod
    def _condition_id(cls, value: str) -> str:
        return _id(value, "condition id")


class CharacterMemory(StrictFrozenModel):
    id: str
    fact: str
    source_visit: int | None = Field(default=None, ge=0)
    salience: float = Field(default=0.5, ge=0, le=1)
    expires_at_tick: int | None = Field(default=None, ge=0)

    @field_validator("id")
    @classmethod
    def _memory_id(cls, value: str) -> str:
        return _id(value, "memory id")


class CharacterRuntimeState(StrictFrozenModel):
    character_id: str
    revision: int = 1
    current_location: str
    activity: str = "idle"
    stats: dict[str, Any] = Field(default_factory=dict)
    needs: tuple[NeedState, ...] = ()
    relationships: tuple[RelationshipState, ...] = ()
    faction_standings: dict[str, float] = Field(default_factory=dict)
    inventory: dict[str, int] = Field(default_factory=dict)
    known_facts: tuple[str, ...] = ()
    agendas: tuple[AgendaState, ...] = ()
    schedules: tuple[ScheduleRule, ...] = ()
    conditions: tuple[ConditionState, ...] = ()
    memories: tuple[CharacterMemory, ...] = ()
    cooldowns: dict[str, int] = Field(default_factory=dict)
    last_updated_tick: int = Field(default=0, ge=0)

    @field_validator("character_id", "current_location")
    @classmethod
    def _character_ids(cls, value: str, info: Any) -> str:
        return _id(value, info.field_name)

    @field_validator("revision", mode="before")
    @classmethod
    def _character_revision(cls, value: Any) -> int:
        return _positive_revision(value)

    @model_validator(mode="after")
    def _unique_character_collections(self) -> "CharacterRuntimeState":
        for label, values in (
            ("need", self.needs), ("relationship", self.relationships),
            ("agenda", self.agendas), ("schedule", self.schedules),
            ("condition", self.conditions), ("memory", self.memories),
        ):
            ids = [getattr(item, "id", getattr(item, "target_character_id", "")) for item in values]
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate character {label}")
        return self


class CharacterEffect(StrictFrozenModel):
    operation: Literal[
        "set", "add", "remove", "clamp", "add_fact", "remove_fact",
        "move_character", "start_condition", "advance_agenda", "schedule_activity",
    ]
    character_id: str
    target: str = ""
    value: Any = None
    source: str = ""

    @field_validator("character_id")
    @classmethod
    def _effect_character(cls, value: str) -> str:
        return _id(value, "effect character id")

    @field_validator("target")
    @classmethod
    def _effect_target(cls, value: str) -> str:
        return _id(value, "character effect target") if value else value


class RuntimeSession(StrictFrozenModel):
    schema_version: int = 1
    session_id: str
    revision: int = 1
    topology_fingerprint: str
    experience_profile_fingerprint: str
    seed: int
    current_location: str
    clock: SimulationClock
    world_state: dict[str, Any] = Field(default_factory=dict)
    resources: dict[str, float | int] = Field(default_factory=dict)
    occurrence_counts: dict[str, int] = Field(default_factory=dict)
    cooldowns: dict[str, int] = Field(default_factory=dict)
    completed_anchor_ids: tuple[str, ...] = ()
    visits: tuple[VisitRecord, ...]
    factions: tuple["FactionState", ...] = ()
    character_stat_definitions: tuple[CharacterStatDefinition, ...] = ()
    characters: tuple[CharacterRuntimeState, ...] = ()

    @field_validator("session_id", "current_location")
    @classmethod
    def _ids(cls, value: str, info: Any) -> str:
        return _id(value, info.field_name)

    @field_validator("revision", mode="before")
    @classmethod
    def _revision(cls, value: Any) -> int:
        return _positive_revision(value)

    @field_validator("topology_fingerprint", "experience_profile_fingerprint")
    @classmethod
    def _fingerprints(cls, value: str) -> str:
        import re
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("invalid fingerprint")
        return value

    @field_validator("resources")
    @classmethod
    def _resources(cls, values: dict[str, float | int]) -> dict[str, float | int]:
        return {_id(key, "resource id"): _finite_number(value, "resource") for key, value in values.items()}

    @field_validator("occurrence_counts", "cooldowns")
    @classmethod
    def _nonnegative_maps(cls, values: dict[str, int], info: Any) -> dict[str, int]:
        checked: dict[str, int] = {}
        for key, value in values.items():
            _id(key, info.field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{info.field_name} values must be nonnegative integers")
            checked[key] = value
        return checked

    @field_validator("completed_anchor_ids")
    @classmethod
    def _completed_anchors(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        checked = tuple(_id(value, "completed anchor id") for value in values)
        if len(checked) != len(set(checked)):
            raise ValueError("duplicate completed anchor id")
        return checked

    @model_validator(mode="after")
    def _unique_runtime_entities(self) -> "RuntimeSession":
        for label, identifiers in (
            ("faction", [item.faction_id for item in self.factions]),
            ("character stat definition", [item.id for item in self.character_stat_definitions]),
            ("character", [item.character_id for item in self.characters]),
        ):
            if len(identifiers) != len(set(identifiers)):
                raise ValueError(f"duplicate runtime {label}")
        known_stats = {item.id for item in self.character_stat_definitions}
        for character in self.characters:
            unknown = set(character.stats) - known_stats
            if unknown:
                raise ValueError(f"character {character.character_id} has undefined stats: {sorted(unknown)}")
        return self

    @model_validator(mode="after")
    def _visit_tail_matches_location(self) -> "RuntimeSession":
        if not self.visits:
            raise ValueError("runtime session needs an initial visit")
        if self.visits[-1].location_id != self.current_location:
            raise ValueError("current location must match the latest visit")
        if self.visits[-1].exited_tick is not None:
            raise ValueError("latest visit must remain open")
        faction_ids = [item.faction_id for item in self.factions]
        character_ids = [item.character_id for item in self.characters]
        if len(faction_ids) != len(set(faction_ids)):
            raise ValueError("duplicate runtime faction")
        if len(character_ids) != len(set(character_ids)):
            raise ValueError("duplicate runtime character")
        return self


class Opportunity(StrictFrozenModel):
    id: str
    kind: Literal["local_action", "travel", "world_event", "character_agenda", "authored_anchor"]
    label: str
    location_id: str
    source_id: str
    eligible_at_tick: int = Field(ge=0)
    provenance: str
    expires_at_tick: int | None = Field(default=None, ge=0)

    @field_validator("id", "location_id", "source_id")
    @classmethod
    def _ids(cls, value: str, info: Any) -> str:
        return _id(value, info.field_name)


class AuthoredAnchor(StrictFrozenModel):
    """One optional Hybrid story anchor projected from authored planning data."""

    id: str
    label: str
    location_id: str
    prerequisite_ids: tuple[str, ...] = ()
    eligibility: tuple[StateCondition, ...] = ()

    @field_validator("id", "location_id")
    @classmethod
    def _ids(cls, value: str, info: Any) -> str:
        return _id(value, info.field_name)

    @field_validator("prerequisite_ids")
    @classmethod
    def _prerequisites(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        checked = tuple(_id(value, "anchor prerequisite id") for value in values)
        if len(checked) != len(set(checked)):
            raise ValueError("duplicate anchor prerequisite id")
        return checked

    @field_validator("label")
    @classmethod
    def _label(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("anchor label cannot be blank")
        return value.strip()

    @model_validator(mode="after")
    def _not_self_dependent(self) -> "AuthoredAnchor":
        if self.id in self.prerequisite_ids:
            raise ValueError("anchor cannot depend on itself")
        return self


class SystemRule(StrictFrozenModel):
    id: str
    trigger: Literal["tick", "local_action", "travel", "enter_location", "encounter"]
    conditions: tuple[StateCondition, ...] = ()
    effects: tuple[StateEffect, ...] = ()
    character_effects: tuple[CharacterEffect, ...] = ()
    faction_effects: tuple["FactionEffect", ...] = ()
    priority: int = 0
    cooldown_ticks: int = Field(default=0, ge=0)
    occurrence_limit: int | None = Field(default=None, ge=1)

    @field_validator("id")
    @classmethod
    def _valid_id(cls, value: str) -> str:
        return _id(value, "system rule id")

    @model_validator(mode="after")
    def _has_effect(self) -> "SystemRule":
        if not (self.effects or self.character_effects or self.faction_effects):
            raise ValueError("system rule needs at least one effect")
        return self


class FactionState(StrictFrozenModel):
    faction_id: str
    influence: float = Field(default=0, ge=0, le=1)
    disposition: float = Field(default=0, ge=-1, le=1)
    resources: dict[str, float | int] = Field(default_factory=dict)
    relationships: dict[str, float] = Field(default_factory=dict)

    @field_validator("faction_id")
    @classmethod
    def _faction(cls, value: str) -> str:
        return _id(value, "faction id")

    @field_validator("resources")
    @classmethod
    def _faction_resources(cls, values: dict[str, float | int]) -> dict[str, float | int]:
        return {_id(key, "faction resource id"): _finite_number(value, "faction resource") for key, value in values.items()}

    @field_validator("relationships")
    @classmethod
    def _relationships(cls, values: dict[str, float]) -> dict[str, float]:
        checked: dict[str, float] = {}
        for key, value in values.items():
            _id(key, "related faction id")
            numeric = float(_finite_number(value, "faction relationship"))
            if numeric < -1 or numeric > 1:
                raise ValueError("faction relationship must be between -1 and 1")
            checked[key] = numeric
        return checked


class FactionEffect(StrictFrozenModel):
    faction_id: str
    operation: Literal["influence", "disposition", "resource", "relationship"]
    target: str = ""
    delta: float

    @field_validator("faction_id")
    @classmethod
    def _faction_id(cls, value: str) -> str:
        return _id(value, "faction effect id")

    @field_validator("target")
    @classmethod
    def _target(cls, value: str) -> str:
        return _id(value, "faction effect target") if value else value

    @model_validator(mode="after")
    def _required_target(self) -> "FactionEffect":
        if self.operation in {"resource", "relationship"} and not self.target:
            raise ValueError("faction resource and relationship effects require a target")
        return self


class EncounterTemplate(StrictFrozenModel):
    id: str
    label: str
    plan: PassagePlan
    location_ids: tuple[str, ...] = ()
    required_tags: tuple[str, ...] = ()
    eligibility: tuple[StateCondition, ...] = ()
    cooldown_ticks: int = Field(default=0, ge=0)
    occurrence_limit: int | None = Field(default=None, ge=1)
    weight: int = Field(default=1, ge=1)
    variation_slots: tuple[str, ...] = ()

    @field_validator("id")
    @classmethod
    def _valid_id(cls, value: str) -> str:
        return _id(value, "encounter template id")

    @field_validator("location_ids", "required_tags", "variation_slots")
    @classmethod
    def _tuple_ids(cls, values: tuple[str, ...], info: Any) -> tuple[str, ...]:
        checked = tuple(_id(value, info.field_name) for value in values)
        if len(checked) != len(set(checked)):
            raise ValueError(f"duplicate {info.field_name}")
        return checked

    @field_validator("label")
    @classmethod
    def _encounter_label(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("encounter label cannot be blank")
        return value.strip()

    @model_validator(mode="after")
    def _variation_slots_exist(self) -> "EncounterTemplate":
        plan_slots = {
            *(item.id for item in self.plan.narrative_slots),
            *(item.id for item in self.plan.choice_slots),
        }
        unknown = set(self.variation_slots) - plan_slots
        if unknown:
            raise ValueError("encounter variation slot is not declared by its plan")
        return self


class EncounterSelection(StrictFrozenModel):
    template_id: str
    location_id: str
    eligible_template_ids: tuple[str, ...]
    deterministic_roll: int = Field(ge=0)
    total_weight: int = Field(ge=1)
    seed_material_fingerprint: str

    @field_validator("template_id", "location_id", "eligible_template_ids")
    @classmethod
    def _selection_ids(cls, value: Any, info: Any):
        if isinstance(value, tuple):
            return tuple(_id(item, info.field_name) for item in value)
        return _id(value, info.field_name)


class SystemCatalog(StrictFrozenModel):
    schema_version: int = 1
    revision: int = 1
    rules: tuple[SystemRule, ...] = ()

    @model_validator(mode="after")
    def _unique_rules(self) -> "SystemCatalog":
        ids = [rule.id for rule in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate system rule")
        return self


class EncounterCatalog(StrictFrozenModel):
    schema_version: int = 1
    revision: int = 1
    templates: tuple[EncounterTemplate, ...] = ()

    @model_validator(mode="after")
    def _unique_templates(self) -> "EncounterCatalog":
        ids = [template.id for template in self.templates]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate encounter template")
        return self


class SimulationFixture(StrictFrozenModel):
    """Named, authored initial state for a disposable simulation."""

    id: str
    label: str
    start_location: str
    seed: int = 1
    world_state: dict[str, Any] = Field(default_factory=dict)
    resources: dict[str, float | int] = Field(default_factory=dict)
    factions: tuple[FactionState, ...] = ()
    character_stat_definitions: tuple[CharacterStatDefinition, ...] = ()
    characters: tuple[CharacterRuntimeState, ...] = ()

    @field_validator("id", "start_location")
    @classmethod
    def _fixture_ids(cls, value: str, info: Any) -> str:
        return _id(value, info.field_name)

    @field_validator("label")
    @classmethod
    def _fixture_label(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("simulation fixture label cannot be blank")
        return value.strip()

    @field_validator("resources")
    @classmethod
    def _fixture_resources(cls, values: dict[str, float | int]) -> dict[str, float | int]:
        checked: dict[str, float | int] = {}
        for key, value in values.items():
            checked[_id(key, "fixture resource id")] = _finite_number(value, "fixture resource")
        return checked

    @model_validator(mode="after")
    def _valid_fixture_entities(self) -> "SimulationFixture":
        faction_ids = [item.faction_id for item in self.factions]
        character_ids = [item.character_id for item in self.characters]
        definition_ids = [item.id for item in self.character_stat_definitions]
        for label, identifiers in (
            ("faction", faction_ids),
            ("character", character_ids),
            ("character stat definition", definition_ids),
        ):
            if len(identifiers) != len(set(identifiers)):
                raise ValueError(f"duplicate fixture {label}")
        known_stats = set(definition_ids)
        for character in self.characters:
            unknown = set(character.stats) - known_stats
            if unknown:
                raise ValueError(
                    f"character {character.character_id} has undefined stats: {sorted(unknown)}"
                )
        return self


class SimulationFixtureCatalog(StrictFrozenModel):
    schema_version: int = 1
    revision: int = 1
    fixtures: tuple[SimulationFixture, ...] = ()

    @model_validator(mode="after")
    def _unique_fixtures(self) -> "SimulationFixtureCatalog":
        ids = [fixture.id for fixture in self.fixtures]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate simulation fixture")
        return self


class SimulationTrace(StrictFrozenModel):
    action_kind: Literal["local_action", "travel", "system_tick", "encounter", "authored_anchor"]
    action_id: str
    from_revision: int
    to_revision: int
    from_location: str
    to_location: str
    tick_before: int
    tick_after: int
    applied_effects: tuple[str, ...] = ()
    resource_delta: dict[str, float | int] = Field(default_factory=dict)


class SimulationRecord(StrictFrozenModel):
    session: RuntimeSession
    trace: SimulationTrace | None = None


RuntimeSession.model_rebuild()


__all__ = [
    "AuthoredAnchor",
    "LocationAction",
    "LocationNode",
    "EncounterSelection",
    "EncounterTemplate",
    "EncounterCatalog",
    "FactionState",
    "FactionEffect",
    "AgendaState",
    "CharacterEffect",
    "CharacterMemory",
    "CharacterRuntimeState",
    "CharacterStatDefinition",
    "ConditionState",
    "NeedState",
    "Opportunity",
    "Route",
    "RelationshipState",
    "RuntimeSession",
    "SimulationClock",
    "SimulationRecord",
    "SimulationFixture",
    "SimulationFixtureCatalog",
    "SimulationTrace",
    "ScheduleRule",
    "SystemRule",
    "SystemCatalog",
    "VisitRecord",
    "WorldTopology",
]
