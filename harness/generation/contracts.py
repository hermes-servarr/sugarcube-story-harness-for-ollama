"""Versioned contracts for trusted passage planning and deterministic generation.

These models form the production authority boundary.  Model-authored fills may
populate only slots exposed by a :class:`PassagePlan`; mechanics, topology, and
state targets remain harness-owned.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


SCHEMA_VERSION = 1
_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")


class ContractError(ValueError):
    """Raised when assembly would violate trusted plan authority."""


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    def fingerprint(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


class VersionedModel(StrictFrozenModel):
    schema_version: int = SCHEMA_VERSION

    @field_validator("schema_version", mode="before")
    @classmethod
    def _validate_schema_version(cls, value: Any) -> int:
        if isinstance(value, bool) or value != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
        return value


class ExperienceMode(str, Enum):
    STORY_DRIVEN = "story_driven"
    HYBRID = "hybrid"
    SANDBOX = "sandbox"


class PassageMode(str, Enum):
    NORMAL = "normal"
    CONDITIONAL = "conditional"
    EVENT = "event"
    RANDOM_EVENT = "random_event"
    DIALOGUE = "dialogue"
    DIALOGUE_LOOP = "dialogue_loop"
    ENDING = "ending"
    FORM = "form"
    HUB = "hub"
    LOOP = "loop"
    RANDOM = "random"
    ROOM = "room"
    WIDGET = "widget"
    INCLUDE = "include"


class NarrativeBlockKind(str, Enum):
    PARAGRAPH = "paragraph"
    DIALOGUE = "dialogue"
    THOUGHT = "thought"


class StateOperation(str, Enum):
    SET = "set"
    ADD = "add"
    SUBTRACT = "subtract"
    TOGGLE = "toggle"


class TimeModel(str, Enum):
    NONE = "none"
    TURN = "turn"
    PHASE = "phase"
    DAY = "day"
    AUTHORED_CLOCK = "authored_clock"


class GoalModel(str, Enum):
    AUTHORED = "authored"
    MIXED = "mixed"
    PLAYER_DIRECTED = "player_directed"


class EndingPolicy(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    NONE = "none"


class StoryGuidance(str, Enum):
    OFF = "off"
    LIGHT = "light"
    ANCHORS = "anchors"
    DIRECTED = "directed"


class CharacterSimulation(str, Enum):
    NONE = "none"
    RELATIONSHIPS = "relationships"
    PERSISTENT_STATS = "persistent_stats"
    FULL_AGENDAS = "full_agendas"


class DraftLifecycle(str, Enum):
    GENERATED = "generated"
    EDITED = "edited"
    VALIDATED = "validated"
    COMMITTED = "committed"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class DiagnosticLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class DiagnosticStage(str, Enum):
    PLAN = "plan"
    NARRATIVE = "narrative"
    MECHANICS = "mechanics"
    COMPILE = "compile"
    PLAYTEST = "playtest"
    COMMIT = "commit"


class DiagnosticOwner(str, Enum):
    PLAN = "plan"
    MODEL_FILL = "model_fill"
    HARNESS_COMPILER = "harness_compiler"
    RUNTIME = "runtime"
    COMMIT = "commit"


class ExperienceOverride(StrictFrozenModel):
    scope_kind: Literal["arc", "region", "scenario"]
    scope_id: str
    narrative_pressure: float | None = Field(default=None, ge=0, le=1)
    story_guidance: StoryGuidance | None = None
    world_reactivity: float | None = Field(default=None, ge=0, le=1)
    encounter_reuse: bool | None = None
    time_model: TimeModel | None = None
    goal_model: GoalModel | None = None
    ending_policy: EndingPolicy | None = None
    failure_persistence: bool | None = None
    character_simulation: CharacterSimulation | None = None
    main_plot_required: bool | None = None

    @field_validator("scope_id")
    @classmethod
    def _scope_id(cls, value: str) -> str:
        return _stable_id(value, "scope_id")


class ExperienceProfile(VersionedModel):
    revision: int = 1
    mode: ExperienceMode
    narrative_pressure: float = Field(ge=0, le=1)
    story_guidance: StoryGuidance
    world_reactivity: float = Field(ge=0, le=1)
    encounter_reuse: bool
    time_model: TimeModel
    goal_model: GoalModel
    ending_policy: EndingPolicy
    failure_persistence: bool
    character_simulation: CharacterSimulation
    main_plot_required: bool
    overrides: tuple[ExperienceOverride, ...] = ()

    @field_validator("revision", mode="before")
    @classmethod
    def _positive_revision(cls, value: Any) -> int:
        return _positive_int(value, "experience profile revision")

    @model_validator(mode="after")
    def _unique_overrides(self) -> "ExperienceProfile":
        keys = [(item.scope_kind, item.scope_id) for item in self.overrides]
        _reject_duplicates(keys, "experience override")
        return self

    def effective_for(
        self,
        scope_kind: Literal["arc", "region", "scenario"],
        scope_id: str,
    ) -> "ExperienceProfile":
        """Return the deterministic profile effective at one explicit scope."""
        normalized_id = _stable_id(scope_id, "scope_id")
        override = next(
            (
                item for item in self.overrides
                if item.scope_kind == scope_kind and item.scope_id == normalized_id
            ),
            None,
        )
        if override is None:
            return self.model_copy(update={"overrides": ()})
        changes = {
            name: value
            for name, value in override.model_dump().items()
            if name not in {"scope_kind", "scope_id"} and value is not None
        }
        return self.model_copy(update={**changes, "overrides": ()})

    @classmethod
    def story_driven(cls) -> "ExperienceProfile":
        return cls(
            mode=ExperienceMode.STORY_DRIVEN,
            narrative_pressure=1.0,
            story_guidance=StoryGuidance.DIRECTED,
            world_reactivity=0.2,
            encounter_reuse=False,
            time_model=TimeModel.NONE,
            goal_model=GoalModel.AUTHORED,
            ending_policy=EndingPolicy.REQUIRED,
            failure_persistence=False,
            character_simulation=CharacterSimulation.RELATIONSHIPS,
            main_plot_required=True,
        )

    @classmethod
    def hybrid(cls) -> "ExperienceProfile":
        return cls(
            mode=ExperienceMode.HYBRID,
            narrative_pressure=0.6,
            story_guidance=StoryGuidance.ANCHORS,
            world_reactivity=0.6,
            encounter_reuse=True,
            time_model=TimeModel.PHASE,
            goal_model=GoalModel.MIXED,
            ending_policy=EndingPolicy.OPTIONAL,
            failure_persistence=True,
            character_simulation=CharacterSimulation.PERSISTENT_STATS,
            main_plot_required=True,
        )

    @classmethod
    def sandbox(cls) -> "ExperienceProfile":
        return cls(
            mode=ExperienceMode.SANDBOX,
            narrative_pressure=0.1,
            story_guidance=StoryGuidance.OFF,
            world_reactivity=1.0,
            encounter_reuse=True,
            time_model=TimeModel.TURN,
            goal_model=GoalModel.PLAYER_DIRECTED,
            ending_policy=EndingPolicy.NONE,
            failure_persistence=True,
            character_simulation=CharacterSimulation.FULL_AGENDAS,
            main_plot_required=False,
        )


class NarrativeSlot(StrictFrozenModel):
    id: str
    kind: NarrativeBlockKind
    speaker: str = ""

    @field_validator("id")
    @classmethod
    def _id(cls, value: str) -> str:
        return _stable_id(value, "narrative slot id")

    @model_validator(mode="after")
    def _speaker_matches_kind(self) -> "NarrativeSlot":
        if self.kind != NarrativeBlockKind.DIALOGUE and self.speaker.strip():
            raise ValueError("only dialogue slots may fix a speaker")
        if self.kind == NarrativeBlockKind.DIALOGUE and self.speaker != self.speaker.strip():
            raise ValueError("speaker cannot have surrounding whitespace")
        return self


class StateCondition(StrictFrozenModel):
    target: str
    operation: Literal["eq", "ne", "gt", "gte", "lt", "lte", "truthy", "falsy"]
    value: Any = None

    @field_validator("target")
    @classmethod
    def _target(cls, value: str) -> str:
        return _stable_id(value, "condition target")


class StateEffect(StrictFrozenModel):
    component_id: str
    target: str
    operation: StateOperation
    value: Any = None
    source: str = ""

    @field_validator("component_id", "target")
    @classmethod
    def _ids(cls, value: str, info: Any) -> str:
        return _stable_id(value, info.field_name)

    @field_validator("source")
    @classmethod
    def _source(cls, value: str) -> str:
        return _stable_id(value, "effect source") if value else value


class ChoiceSlot(StrictFrozenModel):
    id: str
    destination: str = ""
    conditions: tuple[StateCondition, ...] = ()
    effects: tuple[StateEffect, ...] = ()
    weight: int = Field(default=1, ge=1)
    restart: bool = False

    @field_validator("id")
    @classmethod
    def _id(cls, value: str) -> str:
        return _stable_id(value, "choice slot id")


class FormOption(StrictFrozenModel):
    label: str
    value: str = ""
    selected: bool = False


class FormField(StrictFrozenModel):
    id: str
    kind: Literal[
        "textbox", "numberbox", "textarea", "checkbox", "radiobutton",
        "listbox", "cycle",
    ]
    label: str = ""
    default: Any = None
    unchecked_value: str = ""
    checked_value: str = ""
    options: tuple[FormOption, ...] = ()
    autofocus: bool = False
    autocheck: bool = False
    checked: bool = False
    once: bool = False
    autoselect: bool = False

    @field_validator("id")
    @classmethod
    def _id(cls, value: str) -> str:
        return _stable_id(value, "form field id")


class RouteSlot(StrictFrozenModel):
    label: str
    destination: str

    @field_validator("label", "destination")
    @classmethod
    def _non_blank(cls, value: str, info: Any) -> str:
        if not value.strip():
            raise ValueError(f"{info.field_name} cannot be blank")
        return value


class LoopBinding(StrictFrozenModel):
    variable: str
    collection: str

    @field_validator("variable", "collection")
    @classmethod
    def _state_id(cls, value: str, info: Any) -> str:
        return _stable_id(value, info.field_name)


class MechanicSlot(StrictFrozenModel):
    id: str
    required: bool = False
    allowed_operations: tuple[StateOperation, ...] = ()
    allowed_targets: tuple[str, ...] = ()

    @field_validator("id")
    @classmethod
    def _id(cls, value: str) -> str:
        return _stable_id(value, "mechanic slot id")

    @field_validator("allowed_targets")
    @classmethod
    def _targets(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        for value in values:
            _stable_id(value, "allowed mechanic target")
        _reject_duplicates(values, "allowed mechanic target")
        return values


class PassagePlan(VersionedModel):
    plan_id: str
    revision: int
    passage_mode: PassageMode
    narrative_slots: tuple[NarrativeSlot, ...]
    choice_slots: tuple[ChoiceSlot, ...]
    allowed_state_refs: tuple[str, ...] = ()
    allowed_entity_refs: tuple[str, ...] = ()
    allowed_effects: tuple[StateEffect, ...] = ()
    fixed_effects: tuple[StateEffect, ...] = ()
    required_components: tuple[str, ...] = ()
    mechanic_slots: tuple[MechanicSlot, ...] = ()
    form_fields: tuple[FormField, ...] = ()
    exits: tuple[RouteSlot, ...] = ()
    loop_binding: LoopBinding | None = None
    context_fingerprint: str = ""
    experience_profile_fingerprint: str = ""
    repeatable: bool = False
    reentry_policy: Literal["forbid", "allow", "refresh"] = "forbid"
    time_cost: int | None = Field(default=None, ge=0)
    cooldown: int | None = Field(default=None, ge=0)
    eligibility: tuple[StateCondition, ...] = ()
    expiry: int | None = Field(default=None, ge=0)
    fallback_passage: str = ""
    event_odds: int = Field(default=100, ge=1, le=100)

    @field_validator("plan_id")
    @classmethod
    def _plan_id(cls, value: str) -> str:
        return _stable_id(value, "plan_id")

    @field_validator("revision", mode="before")
    @classmethod
    def _revision(cls, value: Any) -> int:
        return _positive_int(value, "revision")

    @field_validator("choice_slots", mode="before")
    @classmethod
    def _legacy_choice_slots(cls, value: Any) -> Any:
        if isinstance(value, (list, tuple)):
            return [{"id": item} if isinstance(item, str) else item for item in value]
        return value

    @field_validator("allowed_state_refs", "allowed_entity_refs")
    @classmethod
    def _references(cls, values: tuple[str, ...], info: Any) -> tuple[str, ...]:
        for value in values:
            _stable_id(value, info.field_name)
        _reject_duplicates(values, info.field_name)
        return values

    @field_validator("required_components")
    @classmethod
    def _components(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values):
            raise ValueError("required components cannot be blank")
        _reject_duplicates(values, "required component")
        return values

    @field_validator("context_fingerprint", "experience_profile_fingerprint")
    @classmethod
    def _fingerprints(cls, value: str, info: Any) -> str:
        if value and not _FINGERPRINT_RE.fullmatch(value):
            raise ValueError(f"{info.field_name} must be a SHA-256 hex digest")
        return value

    @model_validator(mode="after")
    def _authority_is_unambiguous(self) -> "PassagePlan":
        if not self.narrative_slots:
            raise ValueError("plan needs narrative slots")
        if not self.choice_slots:
            raise ValueError("plan needs choice slots")
        _reject_duplicates([item.id for item in self.narrative_slots], "narrative slot")
        _reject_duplicates([item.id for item in self.choice_slots], "choice slot")
        _reject_duplicates([item.id for item in self.mechanic_slots], "mechanic slot")
        _reject_duplicates([item.id for item in self.form_fields], "form field")
        _reject_duplicates([item.label for item in self.exits], "exit label")
        allowed_targets = set(self.allowed_state_refs)
        for effect in (*self.allowed_effects, *self.fixed_effects):
            if effect.target not in allowed_targets:
                raise ValueError("effect target must be an allowed state reference")
            if effect.source and effect.source not in allowed_targets:
                raise ValueError("effect source must be an allowed state reference")
        for choice in self.choice_slots:
            for effect in choice.effects:
                if effect.target not in allowed_targets:
                    raise ValueError("choice effect target must be an allowed state reference")
                if effect.source and effect.source not in allowed_targets:
                    raise ValueError("choice effect source must be an allowed state reference")
        return self

    @property
    def allowed_state_reads(self) -> tuple[str, ...]:
        return self.allowed_state_refs


class TextPart(StrictFrozenModel):
    kind: Literal["text"] = "text"
    text: str

    @field_validator("text")
    @classmethod
    def _text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text part cannot be blank")
        return value


class StateReferencePart(StrictFrozenModel):
    kind: Literal["state_ref"] = "state_ref"
    target: str

    @field_validator("target")
    @classmethod
    def _target(cls, value: str) -> str:
        return _stable_id(value, "state reference target")


class EntityReferencePart(StrictFrozenModel):
    kind: Literal["entity_ref"] = "entity_ref"
    target: str

    @field_validator("target")
    @classmethod
    def _target(cls, value: str) -> str:
        return _stable_id(value, "entity reference target")


InlinePart = Annotated[
    TextPart | StateReferencePart | EntityReferencePart,
    Field(discriminator="kind"),
]


class FilledNarrativeSlot(StrictFrozenModel):
    slot_id: str
    kind: NarrativeBlockKind
    speaker: str = ""
    parts: tuple[InlinePart, ...]

    @field_validator("slot_id")
    @classmethod
    def _slot_id(cls, value: str) -> str:
        return _stable_id(value, "filled narrative slot id")

    @model_validator(mode="after")
    def _not_empty(self) -> "FilledNarrativeSlot":
        if not self.parts:
            raise ValueError("filled narrative slot needs parts")
        if self.kind != NarrativeBlockKind.DIALOGUE and self.speaker:
            raise ValueError("only dialogue fills may name a speaker")
        return self


class FilledChoiceSlot(StrictFrozenModel):
    slot_id: str
    text: str
    hint: str = ""

    @field_validator("slot_id")
    @classmethod
    def _slot_id(cls, value: str) -> str:
        return _stable_id(value, "filled choice slot id")

    @field_validator("text")
    @classmethod
    def _text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("choice text cannot be blank")
        return value


class ContinuityProposal(StrictFrozenModel):
    key: str
    value: str
    evidence_slot_ids: tuple[str, ...] = ()

    @field_validator("key")
    @classmethod
    def _key(cls, value: str) -> str:
        return _stable_id(value, "continuity proposal key")

    @field_validator("value")
    @classmethod
    def _value(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("continuity proposal value cannot be blank")
        return value.strip()

    @field_validator("evidence_slot_ids")
    @classmethod
    def _evidence_slots(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        for value in values:
            _stable_id(value, "continuity evidence slot")
        _reject_duplicates(values, "continuity evidence slot")
        return values


class MediaProposal(StrictFrozenModel):
    slot_id: str
    keywords: tuple[str, ...]
    description: str = ""

    @field_validator("slot_id")
    @classmethod
    def _slot_id(cls, value: str) -> str:
        return _stable_id(value, "media proposal slot id")


class NarrativeFill(VersionedModel):
    plan_id: str
    plan_revision: int
    revision: int = 1
    narrative: tuple[FilledNarrativeSlot, ...]
    choices: tuple[FilledChoiceSlot, ...]
    summary: str
    beats: tuple[str, ...]
    continuity_proposals: tuple[ContinuityProposal, ...] = ()
    media_proposals: tuple[MediaProposal, ...] = ()

    @field_validator("plan_id")
    @classmethod
    def _plan_id(cls, value: str) -> str:
        return _stable_id(value, "fill plan_id")

    @field_validator("plan_revision", "revision", mode="before")
    @classmethod
    def _revisions(cls, value: Any, info: Any) -> int:
        return _positive_int(value, info.field_name)

    @field_validator("summary")
    @classmethod
    def _summary(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("summary cannot be blank")
        return value

    @model_validator(mode="after")
    def _unique_slots(self) -> "NarrativeFill":
        _reject_duplicates([item.slot_id for item in self.narrative], "filled narrative slot")
        _reject_duplicates([item.slot_id for item in self.choices], "filled choice slot")
        _reject_duplicates([item.key for item in self.continuity_proposals], "continuity proposal")
        return self


class MechanicValue(StrictFrozenModel):
    slot_id: str
    operation: StateOperation
    target: str
    value: Any = None

    @field_validator("slot_id", "target")
    @classmethod
    def _ids(cls, value: str, info: Any) -> str:
        return _stable_id(value, info.field_name)


class MechanicProposal(VersionedModel):
    plan_id: str
    plan_revision: int
    revision: int = 1
    values: tuple[MechanicValue, ...]

    @field_validator("plan_id")
    @classmethod
    def _plan_id(cls, value: str) -> str:
        return _stable_id(value, "mechanic proposal plan_id")

    @field_validator("plan_revision", "revision", mode="before")
    @classmethod
    def _revisions(cls, value: Any, info: Any) -> int:
        return _positive_int(value, info.field_name)

    @model_validator(mode="after")
    def _unique_slots(self) -> "MechanicProposal":
        _reject_duplicates([item.slot_id for item in self.values], "mechanic proposal slot")
        return self


class Diagnostic(StrictFrozenModel):
    code: str
    level: DiagnosticLevel
    stage: DiagnosticStage
    owner: DiagnosticOwner
    message: str
    path: tuple[str | int, ...] = ()


class PassageDraft(VersionedModel):
    draft_id: str
    revision: int
    plan: PassagePlan
    fill: NarrativeFill
    mechanic_proposal: MechanicProposal | None = None
    resolved_effects: tuple[StateEffect, ...] = ()
    resolved_required_components: tuple[str, ...] = ()

    @field_validator("draft_id")
    @classmethod
    def _draft_id(cls, value: str) -> str:
        return _stable_id(value, "draft_id")

    @field_validator("revision", mode="before")
    @classmethod
    def _revision(cls, value: Any) -> int:
        return _positive_int(value, "draft revision")


class SourceMapEntry(StrictFrozenModel):
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    source_path: tuple[str | int, ...]

    @model_validator(mode="after")
    def _ordered(self) -> "SourceMapEntry":
        if self.end < self.start:
            raise ValueError("source map end cannot precede start")
        return self


class CompileArtifact(VersionedModel):
    twee_source: str
    state_reads: tuple[str, ...] = ()
    state_writes: tuple[StateEffect, ...] = ()
    link_targets: tuple[str, ...] = ()
    media_placeholders: tuple[str, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
    compiler_version: str
    source_draft_fingerprint: str
    source_map: tuple[SourceMapEntry, ...] = ()

    @field_validator("source_draft_fingerprint")
    @classmethod
    def _source_fingerprint(cls, value: str) -> str:
        if not _FINGERPRINT_RE.fullmatch(value):
            raise ValueError("source draft fingerprint must be SHA-256 hex")
        return value


class GenerationProvenance(StrictFrozenModel):
    raw_model_output: str = ""
    rendered_prompt: str = ""
    model_name: str = ""
    model_digest: str = ""
    ingestion_profile_fingerprint: str = ""
    effective_configuration: dict[str, Any] = Field(default_factory=dict)
    seed: int | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    latency_seconds: float | None = Field(default=None, ge=0)
    finish_reason: str = ""

    @field_validator("seed", mode="before")
    @classmethod
    def _seed(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("seed must be an integer")
        return value


class DraftRecord(VersionedModel):
    generation_id: str
    draft: PassageDraft
    lifecycle_state: DraftLifecycle
    provenance: GenerationProvenance
    diagnostics: tuple[Diagnostic, ...] = ()
    compile_artifact: CompileArtifact | None = None
    parent_passage_id: str = ""
    parent_choice_index: int | None = Field(default=None, ge=0)
    branch_name: str = "main"
    passage_id: str = ""
    arc_name: str = ""
    parent_revision: int | None = Field(default=None, ge=1)
    parent_fingerprint: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("generation_id")
    @classmethod
    def _generation_id(cls, value: str) -> str:
        return _stable_id(value, "generation_id")

    @field_validator("passage_id", "arc_name")
    @classmethod
    def _safe_destination(cls, value: str, info: Any) -> str:
        if value and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", value):
            raise ValueError(f"invalid {info.field_name}")
        return value

    @field_validator("branch_name")
    @classmethod
    def _branch_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("branch_name cannot be blank")
        return value

    @field_validator("parent_revision", mode="before")
    @classmethod
    def _parent_revision(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("parent_revision must be an integer")
        return value


def assemble_passage_draft(
    plan: PassagePlan,
    fill: NarrativeFill,
    proposal: MechanicProposal | None = None,
    *,
    draft_id: str | None = None,
    revision: int = 1,
) -> PassageDraft:
    """Strictly assemble model-owned copy with harness-owned plan authority."""
    if fill.plan_id != plan.plan_id or fill.plan_revision != plan.revision:
        raise ContractError("fill references a stale or different plan revision")

    expected_narrative = {slot.id: slot for slot in plan.narrative_slots}
    actual_narrative = {slot.slot_id: slot for slot in fill.narrative}
    _require_exact_slots(expected_narrative, actual_narrative, "narrative")
    for slot_id, filled in actual_narrative.items():
        planned = expected_narrative[slot_id]
        if filled.kind != planned.kind:
            raise ContractError(f"narrative slot {slot_id} has the wrong kind")
        if filled.speaker != planned.speaker:
            raise ContractError(f"narrative slot {slot_id} has the wrong speaker")
        for part in filled.parts:
            if isinstance(part, StateReferencePart) and part.target not in plan.allowed_state_refs:
                raise ContractError(f"unauthorized state reference: {part.target}")
            if isinstance(part, EntityReferencePart) and part.target not in plan.allowed_entity_refs:
                raise ContractError(f"unauthorized entity reference: {part.target}")

    evidence_slots = set(expected_narrative)
    for continuity in fill.continuity_proposals:
        unknown_evidence = set(continuity.evidence_slot_ids) - evidence_slots
        if unknown_evidence:
            raise ContractError(
                f"continuity proposal {continuity.key} has unknown evidence slots: "
                f"{', '.join(sorted(unknown_evidence))}"
            )

    expected_choices = {slot.id: slot for slot in plan.choice_slots}
    actual_choices = {slot.slot_id: slot for slot in fill.choices}
    _require_exact_slots(expected_choices, actual_choices, "choice")

    mechanic_slots = {slot.id: slot for slot in plan.mechanic_slots}
    proposed = {} if proposal is None else {item.slot_id: item for item in proposal.values}
    if proposal is not None and (
        proposal.plan_id != plan.plan_id or proposal.plan_revision != plan.revision
    ):
        raise ContractError("mechanic proposal references a stale or different plan revision")
    unknown = set(proposed) - set(mechanic_slots)
    if unknown:
        raise ContractError(f"unknown mechanic slots: {', '.join(sorted(unknown))}")
    missing = {slot.id for slot in plan.mechanic_slots if slot.required} - set(proposed)
    if missing:
        raise ContractError(f"unresolved required mechanic slots: {', '.join(sorted(missing))}")
    resolved_effects = list(plan.fixed_effects)
    for slot_id, value in proposed.items():
        authority = mechanic_slots[slot_id]
        if authority.allowed_operations and value.operation not in authority.allowed_operations:
            raise ContractError(f"unauthorized mechanic operation for slot {slot_id}")
        if authority.allowed_targets and value.target not in authority.allowed_targets:
            raise ContractError(f"unauthorized mechanic target for slot {slot_id}")
        resolved_effects.append(StateEffect(
            component_id=slot_id,
            target=value.target,
            operation=value.operation,
            value=value.value,
        ))

    return PassageDraft(
        draft_id=draft_id or f"draft_{plan.plan_id}",
        revision=revision,
        plan=plan,
        fill=fill,
        mechanic_proposal=proposal,
        resolved_effects=tuple(resolved_effects),
        resolved_required_components=plan.required_components,
    )


def _stable_id(value: str, field: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise ValueError(f"invalid {field}")
    return value


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _reject_duplicates(values: list[Any] | tuple[Any, ...], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate {label}")


def _require_exact_slots(expected: dict[str, Any], actual: dict[str, Any], label: str) -> None:
    missing = set(expected) - set(actual)
    unknown = set(actual) - set(expected)
    if unknown:
        raise ContractError(f"unknown {label} slots: {', '.join(sorted(unknown))}")
    if missing:
        raise ContractError(f"missing {label} slots: {', '.join(sorted(missing))}")


__all__ = [
    "SCHEMA_VERSION",
    "ChoiceSlot",
    "CharacterSimulation",
    "CompileArtifact",
    "ContinuityProposal",
    "ContractError",
    "Diagnostic",
    "DiagnosticLevel",
    "DiagnosticOwner",
    "DiagnosticStage",
    "DraftLifecycle",
    "DraftRecord",
    "EndingPolicy",
    "EntityReferencePart",
    "ExperienceMode",
    "ExperienceOverride",
    "ExperienceProfile",
    "FilledChoiceSlot",
    "FilledNarrativeSlot",
    "FormField",
    "FormOption",
    "GenerationProvenance",
    "GoalModel",
    "InlinePart",
    "MechanicProposal",
    "MechanicSlot",
    "MechanicValue",
    "MediaProposal",
    "NarrativeBlockKind",
    "NarrativeFill",
    "NarrativeSlot",
    "LoopBinding",
    "PassageDraft",
    "PassageMode",
    "PassagePlan",
    "SourceMapEntry",
    "RouteSlot",
    "StateCondition",
    "StateEffect",
    "StateOperation",
    "StateReferencePart",
    "StoryGuidance",
    "StrictFrozenModel",
    "TextPart",
    "TimeModel",
    "VersionedModel",
    "assemble_passage_draft",
]
