"""Pydantic models for story.json and related data structures."""
from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field


# All recognised passage types. Renderer + validation branch on this.
#
# `widget` and `include` are SugarCube-template-aware types added so the
# harness can generate the reusable-macro and shared-content passages that the
# studied HTML templates lean on (Character Creator's <<widget>> grid,
# Space-Tech's <<widget "statsformat">>, Title Page's <<include "Menu
# Elements">>). See examples/html_templates/TEMPLATE_VERIFICATION_REPORT.md
# §2.3 and docs/sugarcube2-analysis.md §3.7-3.8.
# The 7 SugarCube input macros the "form" passage type can render.
# Each writes to a quoted target variable in real time as the player
# interacts; by submit time the variables are already set in story state.
# Source: docs/core/macros.md (P1 §2.3). No invented macros.
INPUT_MACRO_KINDS = (
    "textbox",      # <<textbox "$var" "default" [passage] [autofocus]>>
    "numberbox",    # <<numberbox "$var" default [passage] [autofocus]>>
    "textarea",     # <<textarea "$var" "default" [autofocus]>>
    "checkbox",     # <<checkbox "$var" uncheckedValue checkedValue [autocheck|checked]>>
    "radiobutton",  # <<radiobutton "$var" checkedValue [autocheck|checked]>>
    "listbox",      # <<listbox "$var" [autoselect]>><<option>>…<</listbox>>  (container)
    "cycle",        # <<cycle "$var" [once] [autoselect]>><<option>>…<</cycle>>  (container)
)
PASSAGE_TYPES = (
    "normal",         # plain choice node
    "hub",            # central node players return to
    "random",         # picks one of N children at random
    "conditional",    # entry gated by SugarCube state expression
    "dialogue",       # NPC exchange; choices loop back until "exit" choice
    "room",           # bidirectional navigation node with named exits
    "event",          # one-shot scripted scene (uses <<once>>)
    "random_event",   # triggers only if random roll <= event_odds
    "ending",         # terminal; no choices required
    "loop",           # choices emitted inside a SugarCube <<for>> loop; bodies
                      # reading a loop var wrapped in <<capture $v>> (§3.9)
    "widget",         # widget definition passage (tagged [widget]); not navigated to
    "include",        # shared-content passage meant to be <<include>>d, not navigated to
    "form",           # collects player input via <<textbox>>/<<checkbox>>/... + submit <<link>>
    # TODO(timed-narrative): append "timed" entry to PASSAGE_TYPES here, after
    # "include" (P2 §3.1, P1 §4). Exact code:
    #   "timed",          # time-based narrative: delayed reveals / countdowns / recurring events (<<timed>>/<<repeat>>)
    # Purely additive; no reordering. Existing type indices are stable. All timed
    # fields on PassageEntry default empty/None so a non-timed passage is unaffected.
    # See p2_data_structures.md §3.1, p3_interfaces.md §5.
)

# TODO(story-interface): define STORY_INTERFACE_LAYOUTS tuple here, after
# PASSAGE_TYPES (P2 D1, P1 3.1). Mirrors the PASSAGE_TYPES tuple convention.
# Metadata-only constant enumerating valid layout preset ids; the HTML bodies
# each id resolves to are P7 module constants (logic/assets), NOT P2 data.
# Exact code:
#   STORY_INTERFACE_LAYOUTS = (
#       "vn",          # visual-novel: header + #passages + portrait panel
#       "rpg_stats",   # RPG: #passages + persistent stats side panel
#       "minimal",     # bare <div id="passages"></div> — SugarCube minimum
#       "custom",      # author-supplied raw HTML in StoryInterfaceConfig.html
#   )
# See p2_data_structures.md D1, p1_research.md 3.1.


class SkillCheck(BaseModel):
    stat: str                  # e.g. "$strength"
    dc: int                    # difficulty class
    success_target: str = ""   # passage_id resolved at commit time
    fail_target: str = ""
    success_hint: str = ""
    fail_hint: str = ""


class CharacterPresent(BaseModel):
    id: str
    status: str
    knows: list[str] = Field(default_factory=list)
    relationship_to_player: str = ""


class CharacterOffscreen(BaseModel):
    id: str
    last_known: str


class CharacterDelta(BaseModel):
    """A per-turn change to a character's presence/status in the snapshot.

    Used by the three model-output delta sections:
    - CHARACTERS_PRESENT: upsert into ``characters_present`` (enter / restate).
    - CHARACTER_STATUS:   update an already-present character's status/knowledge.
    - CHARACTERS_EXIT:    move a character to ``characters_offscreen``.

    Only ``id`` is required. ``knows`` entries are *added* to the character's
    existing knowledge (deduped), never replace it. ``last_known`` is the
    offscreen note used on exit.
    """
    id: str
    status: str = ""
    knows: list[str] = Field(default_factory=list)
    relationship_to_player: str = ""
    last_known: str = ""


class Snapshot(BaseModel):
    characters_present: list[CharacterPresent] = Field(default_factory=list)
    characters_offscreen: list[CharacterOffscreen] = Field(default_factory=list)
    world_state: list[str] = Field(default_factory=list)
    open_threads: list[str] = Field(default_factory=list)


# ── Snapshot deltas ───────────────────────────────────────────────────────────
# Defined here (not in snapshot_delta.py) to avoid a circular import:
# PassageEntry references SnapshotDelta, and snapshot_delta.py's functions
# operate on Snapshot/CharacterPresent/etc from this module.

class CharacterSectionDelta(BaseModel):
    """Delta for one of the two character lists (present/offscreen)."""
    added: list[dict[str, Any]] = Field(default_factory=list)
    modified: dict[str, dict[str, Any]] = Field(default_factory=dict)
    removed: list[str] = Field(default_factory=list)


class ListSectionDelta(BaseModel):
    """Delta for a plain list-of-strings section (world_state, open_threads)."""
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)


class SnapshotDelta(BaseModel):
    """The full delta between two consecutive snapshots."""
    characters_present: CharacterSectionDelta = Field(default_factory=CharacterSectionDelta)
    characters_offscreen: CharacterSectionDelta = Field(default_factory=CharacterSectionDelta)
    world_state: ListSectionDelta = Field(default_factory=ListSectionDelta)
    open_threads: ListSectionDelta = Field(default_factory=ListSectionDelta)


# TODO(timed-narrative): define TimedReveal(BaseModel) and TimedConfig(BaseModel)
# here, BEFORE class PassageEntry (after SnapshotDelta), so the sub-models are
# defined before the model that references them (P2 §2.1, §2.2, P2 §5 placement).
# Both are pure field-bags — no methods, no validators (P2 is strict: schemas only).
# Exact code:
#   class TimedReveal(BaseModel):
#       """One block in a delayed-reveal chain (<<timed>>/<<next>> sequence).
#
#       `delay` is a CSS time string per SugarCube ("2s", "500ms"); minimum 40ms
#       enforced as a P6 invariant, not here. `content` is the SugarCube markup
#       block shown when the delay elapses.
#       """
#       delay: str            # CSS time, e.g. "2s", "500ms"
#       content: str          # SugarCube markup revealed when this block fires
#
#   class TimedConfig(BaseModel):
#       """Configuration for countdown and recurring timed modes.
#
#       - `reveal` mode ignores this (uses `timed_reveals` list instead).
#       - `countdown` mode uses interval, counter_var, start_value, final_content, anchor_id.
#       - `recurring` mode uses only interval and content.
#       Fields not relevant to the active mode are left at their defaults.
#       """
#       interval: str = ""            # CSS time for the <<repeat>> loop
#       counter_var: str = ""         # countdown: SugarCube variable name
#       start_value: int = 0          # countdown: starting counter value
#       final_content: str = ""       # countdown: content shown when counter reaches 0
#       anchor_id: str = ""           # countdown: DOM id for <<replace "#anchor_id">>
#       content: str = ""             # recurring: SugarCube markup executed each interval
# See p2_data_structures.md §2.1/§2.2, p3_interfaces.md §2.1.


class PassageEntry(BaseModel):
    file: str
    arc: str
    parents: list[str] = Field(default_factory=list)
    children: list[str] = Field(default_factory=list)
    state_writes: list[str] = Field(default_factory=list)
    state_reads: list[str] = Field(default_factory=list)
    media_slots: list[str] = Field(default_factory=list)
    location: str = ""
    summary: str = ""
    beats: list[str] = Field(default_factory=list)  # 2-5 scene-level events; high-signal RAG keys
    plan_beats: list[str] = Field(default_factory=list)  # StoryPlan beat ids this passage advances
    snapshot: Snapshot = Field(default_factory=Snapshot)
    snapshot_delta: Optional[SnapshotDelta] = None  # diff from parent snapshot
    passage_type: str = "normal"           # see PASSAGE_TYPES
    # type-specific fields — empty/default for normal passages
    entry_condition: str = ""              # conditional: SugarCube expr e.g. "$has_key"
    fallback_passage: str = ""             # conditional: target if condition false
    exits: dict[str, str] = Field(default_factory=dict)   # room: {"north": pid, ...}
    event_odds: int = 100                  # random_event: 1-100 trigger %
    dialogue_npc: str = ""                 # dialogue: character id
    # TODO(passage-tags): PassageEntry — add field after dialogue_npc, closing
    # the type-specific fields block (P2 §2). Exact:
    #   tags: list[str] = Field(default_factory=list)
    # Sanitized mood tags for this passage (e.g. ["tense", "rainy"]). Rendered
    # into the Twee header after the arc and type tags. Holds ONLY mood tags —
    # never the structural `arc` or `passage_type` values, and never `nobr`
    # (nobr is config-derived, see HarnessConfig). After rebuild_story this list
    # round-trips exactly the mood tags that were in the original header. See
    # p2_data_structures.md §2, p3_interfaces.md §S4 (rebuild_story tag round-trip).
    # TODO(timed-narrative): add three timed fields here, after dialogue_npc,
    # following the "flat optional field, default empty/None" convention (P2 §3.2).
    # Exact code:
    #   # ── timed passage type ────────────────────────────────────────────────
    #   # Models the three §3.11 time-based behaviors via a timed_mode discriminator:
    #   #   reveal    -> timed_reveals list renders a <<timed>>/<<next>> chain
    #   #   countdown -> timed_config renders a <<repeat>>/<<stop>> loop + <<replace>>
    #   #   recurring -> timed_config renders a <<repeat>> loop (no stop)
    #   # All default empty/None so a normal passage is unaffected.
    #   timed_mode: str = "reveal"                                     # "reveal" | "countdown" | "recurring"
    #   timed_reveals: list[TimedReveal] = Field(default_factory=list)  # reveal mode
    #   timed_config: Optional[TimedConfig] = None                      # countdown/recurring; None for reveal
    # Optional and Field are already imported (models.py L3-4). Appended at the
    # end of the type-specific block — no existing field touched. See
    # p2_data_structures.md §3.2, p3_interfaces.md §3.1.


class StateVariable(BaseModel):
    type: str  # bool, int, str, float
    default: Any = None
    declared_in: str = ""


# TODO(settings-api): S1 — define SettingDef(BaseModel) here, between StateVariable
# and BranchEntry (P2 §"Change 1"). 9 fields: name: str, kind: str, label: str,
# desc: str = "", default: Any = None, list: list[str] = Field(default_factory=list),
# min: float = 0, max: float = 100, step: float = 1. Pure schema, no methods (P2 is
# strict: no to_js, no validators, no __init__); the "list"|"range"|"toggle" literal
# union for `kind` is documented in the docstring and enforced as a P6 invariant,
# not a model constraint (matches codebase convention — passage_type/StateVariable.type
# are bare str). Analogous to StateVariable: a declared default that becomes a runtime
# value (settings.<name>). See p2_data_structures.md §"Change 1", p3_interfaces.md §1.
# class SettingDef(BaseModel): ...


class BranchEntry(BaseModel):
    head: str
    diverges_at: Optional[str] = None


# TODO(achievements): D1 — add MetadataKey(BaseModel) here, after BranchEntry and
# before StoryGraph, so the registry entry model is defined before the graph that
# references it (P2 §2 D1; matches StateVariable-before-StoryGraph ordering).
# Pure data, no methods. Exact code:
#   class MetadataKey(BaseModel):
#       """Declarative registry entry for a SugarCube metadata-store key.
#
#       The metadata store (memorize/recall/forget) persists across browser
#       restarts but is NOT part of saves — ideal for achievements, playthrough
#       stats, and NG+ flags. Each MetadataKey tells the StoryInit generator
#       to emit a hydration line that reads (never writes) the store on startup,
#       defaulting to `default` when the key is absent.
#       """
#       id: str                         # store key name, e.g. "achievements", "ngplus"
#       default: Any                    # hydration default: {} for maps, false for flags, 0 for counters
#       description: str = ""           # optional human-readable note
# `id` and `default` are required (no pydantic default); `description` defaults "".
# `default: Any` (not str/int/bool) because metadata values are heterogeneous —
# mirrors StateVariable.default: Any. See p2_data_structures.md §2 D1.

# ── Planning: connect overarching story (beats) ⇄ arcs ⇄ passages ──────────────

class Beat(BaseModel):
    """One plot beat in the overarching story plan — author intent, not prose."""
    id: str                       # stable short id, e.g. "b1"
    text: str                     # one-line description of the beat
    act: str = ""                 # act label this beat belongs to (free text)
    status: str = "open"          # open | covered  (derived from passage links)


class PlannedScene(BaseModel):
    """A lightweight scene sketch inside an arc — author intent before the
    passage is written in the graph. Realized into a real passage on demand."""
    id: str                       # arc-scoped short id, e.g. "sc1"
    title: str = ""               # short scene title
    summary: str = ""             # one-line what-happens
    keywords: list[str] = Field(default_factory=list)   # mood/imagery/action tags
    characters: list[str] = Field(default_factory=list) # character ids/names in the scene
    beat_ids: list[str] = Field(default_factory=list)   # plan beats this scene delivers
    passage_id: str = ""          # set once the scene is realized into the graph
    status: str = "planned"       # planned | drafted


class ArcPlan(BaseModel):
    """Structured plan for one arc, linking it to overarching beats."""
    goal: str = ""                # what this arc accomplishes in the story
    beat_ids: list[str] = Field(default_factory=list)  # plan beats this arc advances
    status: str = "planned"       # planned | active | done
    summary: str = ""             # short arc summary (mirrors _arc.md heading)
    scenes: list[PlannedScene] = Field(default_factory=list)  # planned scenes in order


class StoryPlan(BaseModel):
    """Overarching, structured story outline. Canonical, harness-owned."""
    acts: list[str] = Field(default_factory=list)        # ordered act labels
    beats: list[Beat] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class TextTemplate(BaseModel):
    """One SugarCube ``Template.add()`` registration — a named text template
    expandable in passage prose as ``?name``.

    The ``definition`` list holds one or more string bodies.  A single-element
    list is SugarCube's plain-string form (always expands to that string); a
    multi-element list is SugarCube's "pick one member at random per reference"
    array form.  Function-template definitions are deferred (see P1 D2 / OQ-2).

    The ``name`` field MUST match ``^[A-Za-z][A-Za-z0-9_-]*$`` (basic Latin,
    start with a letter, then letters/digits/underscore/hyphen) per the
    SugarCube Template API spec (docs/api/api-template.md).  This rule is NOT
    enforced here — it is an invariant (P6, INV-T2) checked at add-time and
    validation.
    """
    name: str                 # template name; SugarCube name rule enforced in P6
    definition: list[str]     # one or more expansion strings; >=2 elements = random pick


class StoryGraph(BaseModel):
    version: int = 1
    start_passage: str = ""
    passages: dict[str, PassageEntry] = Field(default_factory=dict)
    state_variables: dict[str, StateVariable] = Field(default_factory=dict)
    branches: dict[str, BranchEntry] = Field(default_factory=dict)
    plan: StoryPlan = Field(default_factory=StoryPlan)
    arcs: dict[str, ArcPlan] = Field(default_factory=dict)  # keyed by arc name
    # ── SugarCube Template API registrations (per-story) ───────────────────
    # Named ``?name`` text templates registered via ``Template.add()`` and
    # emitted as ``<<run Template.add(...)>>`` lines in StoryInit at compile
    # time. Per-story (story.json), not per-project (config.yaml) — see P1
    # OQ-1. Empty list = no templates (default; greenfield-safe).
    text_templates: list[TextTemplate] = Field(default_factory=list)
    # TODO(achievements): D3 — add metadata_keys field here, after arcs.
    # A list (not dict) so StoryInit emission order is deterministic; the `id`
    # is an explicit field on MetadataKey. Default empty → zero regression.
    # Exact code:
    #   metadata_keys: list[MetadataKey] = Field(default_factory=list)
    # See p2_data_structures.md §3 D3, p1_research.md §4A.
    # TODO(settings-api): S2 — add settings_defs field here, after arcs. A list
    # (not dict) because settings display in declaration order and name uniqueness
    # is a P6 invariant, not a structural constraint (matches Beats = list[Beat]).
    # Default empty → every existing story.json loads with [] → no StorySettings
    # passage emitted → zero regression (P2 §"Change 2", §"Backward Compatibility").
    # Exact code:
    #   settings_defs: list[SettingDef] = Field(default_factory=list)
    # Per-story in story.json (NOT HarnessConfig — settings vary per story, P1 §52).
    # See p2_data_structures.md §"Change 2", p3_interfaces.md §1/§2.


class MediaSlot(BaseModel):
    passage: str
    keywords: list[str] = Field(default_factory=list)
    type: str = "image"  # image, audio, video
    status: str = "pending"  # pending, resolved
    resolved_path: Optional[str] = None
    # ── Description / accessibility ──────────────────────────────────────────
    description: str = ""   # human/bot description of intended media; alt fallback
    alt: str = ""           # explicit alt text (overrides description/keywords)
    caption: str = ""       # visible caption rendered beneath the media
    # ── Embed options ────────────────────────────────────────────────────────
    lazy: bool = True       # images: loading="lazy"
    loop: bool = False      # audio/video: loop playback
    autoplay: bool = False  # audio/video: autoplay (implies muted for video)
    muted: bool = False     # audio/video: start muted
    controls: bool = True   # audio/video: show controls
    poster: str = ""        # video: poster frame path (resolved like resolved_path)

    def effective_alt(self) -> str:
        """Alt text to embed: explicit alt, else description, else keywords."""
        if self.alt.strip():
            return self.alt.strip()
        if self.description.strip():
            return self.description.strip()
        return ", ".join(self.keywords)


class MediaSlots(BaseModel):
    slots: dict[str, MediaSlot] = Field(default_factory=dict)


# TODO(story-interface): define StoryInterfaceConfig(BaseModel) here, between
# MediaSlots and HarnessConfig (P2 D2, P1 3.1). Pydantic needs the class
# defined before the HarnessConfig field annotation that references it,
# matching the existing SkillCheck->ParsedChoice / MediaSlot->MediaSlots forward-
# reference ordering. Pure schema — 2 fields, docstrings only, NO methods,
# NO validators (those are P3/P7). Optional and BaseModel/Field are
# already imported (line 3/4). Exact code:
#   class StoryInterfaceConfig(BaseModel):
#       """Config for the compile-time `StoryInterface` special passage."""
#       # Preset layout id. One of STORY_INTERFACE_LAYOUTS; "custom" uses `html`.
#       layout: str = "minimal"
#       # Raw HTML body, used only when layout == "custom"; must contain id="passages".
#       html: str = ""
# See p2_data_structures.md D2, p1_research.md 3.1.


class HarnessConfig(BaseModel):
    ollama_model: str = "llama3.2"
    ollama_base_url: str = "http://localhost:11434"
    tweego_path: str = "tweego"
    sugarcube_path: str = ""
    story_title: str = "Untitled Story"
    story_format: str = "SugarCube2"
    # Stable Interactive Fiction ID. Generated once at project init and never
    # rewritten — keeps SugarCube save files compatible across rebuilds.
    story_ifid: str = ""
    # SugarCube major.minor.patch. Tweego picks the highest installed format
    # matching the major release if the exact version isn't present.
    # Bumped to 2.37.3 to match 6/7 studied templates and enable
    # <<silent>>/<<do>>/<<done>> + hasVisited() (P2 §4 / P1 §4.2 #7). Affects new
    # inits only; existing config.yaml files keep their persisted value — no
    # migration code (avoids regressions).
    format_version: str = "2.37.3"
    model_mode: str = "compact"   # auto | standard | compact
    # delimited = legacy PROSE:/CHOICES:/... text; json = strict JSON via Ollama format param
    output_format: str = "delimited"   # delimited | json
    # ── Ollama sampling — tuned for small/medium local models ─────────────────
    temperature: float = 0.7
    repeat_penalty: float = 1.15
    num_predict: int = 1024
    num_ctx: int = 4096
    # ── RAG / inspiration corpus ─────────────────────────────────────────────
    embed_model: str = "nomic-embed-text"
    rag_enabled: bool = True
    rag_top_k: int = 3
    rag_min_score: float = 0.3
    # ── Tweego build options ─────────────────────────────────────────────────
    # Pass `-l` to print passage/word stats; surfaced in compile output.
    tweego_log_stats: bool = False
    # Pass `-t` to enable story-format test mode (debug bar, visible script
    # passages). Twine 2 formats only.
    tweego_test_mode: bool = False
    # File appended verbatim into the compiled HTML <head> via `--head=FILE`.
    tweego_head_file: str = ""
    # Module directories passed via `-m` — every .css/.js inside is wrapped
    # and injected into <head>.
    tweego_module_dirs: list[str] = Field(default_factory=list)
    # ── Template awareness ───────────────────────────────────────────────────
    # Registry id of an active SugarCube HTML template (see harness.templates).
    # When set, the harness injects the template's CSS/JS into compiled
    # stories and adds a style hint to passage prompts. Empty = no template.
    # Valid ids: character-creator, one-page, settings, simple-book,
    # space-tech, title-page, vn-lite-rpg.
    template_id: str = ""
    # TODO(story-interface): HarnessConfig — add one field after template_id,
    # opening a "Story interface" config section (P2 D3, P1 3.1). The field is
    # an Optional structured sub-config; None = no StoryInterface passage emitted
    # (default SugarCube UI bar preserved). Matches the template_id precedent
    # (plain string) and the Optional[SkillCheck]=None convention for optional
    # structured sub-config. No migration code (pydantic default covers absent
    # keys; load_config/save_config round-trip via model_dump). Exact code:
    #   # ── Story interface ──────────────────────────────────────────────────
    #   # Optional custom UI layout. When set, compile emits a `:: StoryInterface`
    #   # special passage (raw HTML replacing SugarCube's default UI bar; MUST
    #   # contain an element with id="passages"). None = default UI bar. See
    #   # docs/sugarcube2-analysis.md 3.19.
    #   story_interface: Optional[StoryInterfaceConfig] = None
    # See p2_data_structures.md D3, p1_research.md 3.1/3.5.
    # TODO(achievements): D5 — add achievements_enabled field here, after
    # template_id. Opt-in flag defaulting False for zero regression. Exact code:
    #   # ── Achievement tracking ─────────────────────────────────────────────
    #   achievements_enabled: bool = False
    # See p2_data_structures.md §5 D5, p1_research.md §4B/§5 #2.
    # ── PRNG seeding for deterministic playthroughs ────────────────────────────
    # Optional seed string written verbatim into StoryInit as
    # <<run State.prng.init("...")>> so random()/either() calls produce a
    # reproducible sequence across rebuilds. Empty (default) = seeding off;
    # the StoryInit body and empty-return guard are unchanged. The seed is
    # stored as-is; escaping is applied at emit time (_escape_sc_string in
    # compile.py) so no validation/normalization is needed here (YAGNI — P1
    # §2.4, P2 §4). useEntropy is NOT exposed (out of scope per P1 §2.4).
    # No schema migration needed: pydantic's ``default=""`` covers absent
    # keys in existing config.yaml files. See p1_research.md §3.1,
    # p2_data_structures.md §2.1/§3, p3_interfaces.md §3.2 I2.
    # TODO(prng-seed): S1 — add `prng_seed: str = ""` field here, opening the
    # "PRNG seeding" config section as the last optional-feature field on
    # HarnessConfig. Type str, default "" (empty = off). Placement after
    # template_id preserves P2 §2.1's "last optional-feature field" intent.
    # P7 will uncomment the field line below.
    # prng_seed: str = ""
    # TODO(passage-tags): HarnessConfig — add two fields after prng_seed (P2 §3/§4).
    # Exact:
    #   nobr_tag: bool = False
    #   nobr_passage_types: list[str] = Field(default_factory=list)
    # `nobr_tag`: when true, the special `nobr` SugarCube tag is appended to
    # every passage header, collapsing newlines in passage content to spaces.
    # Default false so existing stories are unaffected. `nobr_passage_types`:
    # passage types (members of PASSAGE_TYPES) that should get the `nobr` tag
    # even when nobr_tag is globally false. Unioned with nobr_tag: a passage
    # gets nobr if nobr_tag is true OR its passage_type is in this list. Empty
    # list = no per-type scoping. See p2_data_structures.md §3/§4, p3_interfaces.md §S3,
    # p1_research.md §3c.


class SessionState(BaseModel):
    current_passage: Optional[str] = None
    current_branch: str = "main"
    active_mode: str = "co-author"  # director, co-author, editor


# ── Parsed model output ────────────────────────────────────────────────────────

class ParsedInputOption(BaseModel):
    """One <<option>> child inside a <<listbox>> or <<cycle>> container.

    SugarCube syntax: <<option label [value [selected]]>>.
    When ``value`` is omitted SugarCube uses ``label`` as the value.
    """
    label: str                        # visible option text
    value: str = ""                   # stored value; defaults to label when empty
    selected: bool = False            # pre-select this option (SugarCube `selected` keyword)


class ParsedInputField(BaseModel):
    """One SugarCube input macro to render in a form passage.

    ``kind`` selects the macro; only the fields relevant to that kind
    are populated (others stay default). See INPUT_MACRO_KINDS for the
    7 supported macros and their exact SugarCube syntax.
    """
    kind: str                         # one of INPUT_MACRO_KINDS
    var: str                           # quoted target variable, e.g. "$name", "$mc.gender"
    label: str = ""                   # visible prompt/label shown before the macro
    # ── textbox / numberbox / textarea ─────────────────────────────────────
    default: Any = None               # default value (str for textbox/textarea, num for numberbox)
    # ── checkbox / radiobutton ────────────────────────────────────────────
    unchecked_value: str = ""         # checkbox: value when unchecked
    checked_value: str = ""           # checkbox/radiobutton: value when checked/selected
    # ── listbox / cycle ───────────────────────────────────────────────────
    options: list[ParsedInputOption] = Field(default_factory=list)
    # ── keyword flags (all default off) ────────────────────────────────────
    autofocus: bool = False            # textbox/numberbox/textarea
    autocheck: bool = False           # checkbox/radiobutton
    checked: bool = False             # checkbox/radiobutton: pre-checked
    once: bool = False                # cycle: each option selectable only once
    autoselect: bool = False          # listbox/cycle: auto-select first option


class ParsedChoice(BaseModel):
    text: str
    hint: str = ""
    # Optional gating + side-effects. Empty/default = plain link.
    requires: str = ""                                 # SugarCube expr; hides choice when false
    blocks: str = ""                                   # SugarCube expr; hides choice when true
    state_writes: dict[str, Any] = Field(default_factory=dict)  # set when choice taken
    weight: int = 1                                    # for random passages: pick weight
    skill_check: Optional[SkillCheck] = None           # if set, choice rolls $stat vs dc


class ParsedMediaSlot(BaseModel):
    type: str
    keywords: list[str]
    description: str = ""


class ParsedCharacter(BaseModel):
    id: str
    prose_sheet: str
    # Enrichment fields (optional — not all models provide them)
    physical: str = ""
    personality: str = ""
    motivation: str = ""
    backstory: str = ""
    relationships: str = ""
    speech: str = ""


class ParsedLore(BaseModel):
    category: str
    id: str
    prose_sheet: str


class ExtractedEntities(BaseModel):
    characters: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    items: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)


# TODO(achievements): D2 — add ParsedAchievement(BaseModel) here, after
# ExtractedEntities and before ModelOutput. Pure data, no methods (P2 §2 D2).
# Exact code:
#   class ParsedAchievement(BaseModel):
#       """One achievement proposed by the model for the current passage."""
#       id: str                         # achievement id, e.g. "ateYellowSnow"
#       description: str = ""           # human-readable achievement text
# See p2_data_structures.md §2 D2.


# TODO(timed-narrative): define TimedProposal(BaseModel) here, after
# ExtractedEntities / ParsedAchievement and before ModelOutput, so the
# proposal sub-model is defined before the model that references it (P2 §2.3,
# P2 §5 placement — parallel to ParsedChoice/ParsedCharacter). Pure field-bag.
# Exact code:
#   class TimedProposal(BaseModel):
#       """Model-proposed timed passage structure, parsed from the TIMED section.
#
#       Mirrors the PassageEntry timed fields (timed_mode + timed_reveals +
#       timed_config) so create_passage can forward them with no translation.
#       """
#       timed_mode: str = "reveal"                      # "reveal" | "countdown" | "recurring"
#       timed_reveals: list[TimedReveal] = Field(default_factory=list)
#       timed_config: Optional[TimedConfig] = None
# See p2_data_structures.md §2.3, p3_interfaces.md §4.1.


class ModelOutput(BaseModel):
    prose: str = ""
    choices: list[ParsedChoice] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)
    media: list[ParsedMediaSlot] = Field(default_factory=list)
    inputs: list[ParsedInputField] = Field(default_factory=list)  # form: input macros + their target vars
    new_characters: list[ParsedCharacter] = Field(default_factory=list)
    new_lore: list[ParsedLore] = Field(default_factory=list)
    threads_open: list[str] = Field(default_factory=list)
    threads_close: list[str] = Field(default_factory=list)
    world_state_add: list[str] = Field(default_factory=list)
    world_state_remove: list[str] = Field(default_factory=list)
    # ── Character snapshot deltas ────────────────────────────────────────────
    characters_present: list[CharacterDelta] = Field(default_factory=list)  # enter / restate
    character_status: list[CharacterDelta] = Field(default_factory=list)    # status/knows update
    characters_exit: list[CharacterDelta] = Field(default_factory=list)     # leave the scene
    summary: str = ""
    beats: list[str] = Field(default_factory=list)
    # TODO(achievements): D4 — add achievements field here, after beats,
    # before parse_warnings. Default empty → zero regression. Exact code:
    #   achievements: list[ParsedAchievement] = Field(default_factory=list)
    # See p2_data_structures.md §4 D4, p3_interfaces.md §2 I2/I3.
    # TODO(timed-narrative): add `timed: Optional[TimedProposal] = None` field
    # here, after beats/achievements, before parse_warnings (P2 §3.3). Optional +
    # None default because the TIMED section is optional in model output (most
    # passages are not timed); None = section absent. Exact code:
    #   # ── Timed passage proposal (from TIMED section) ───────────────────────
    #   timed: Optional[TimedProposal] = None     # parsed from the TIMED section; None if absent
    # Positioned immediately before parse_warnings so the cross-cutting warnings
    # field remains the final field (parsing code appends to it). See
    # p2_data_structures.md §3.3, p3_interfaces.md §4.1/§4.2.
    # TODO(passage-tags): ModelOutput — add field after beats/timed, before
    # parse_warnings (P2 §1). Exact:
    #   tags: list[str] = Field(default_factory=list)
    # Zero-to-three short mood/atmosphere tags the model suggests for the passage
    # (e.g. "tense", "rainy", "hopeful"). Sanitized before rendering into the Twee
    # header `:: id [arc type mood1 mood2]`. Excludes structural arc/type tags and
    # nobr. Populated by parse_model_output (TAGS: section) /
    # parse_model_output_json (tags key). Empty = none. See p2_data_structures.md §1,
    # p3_interfaces.md §S10/§S11.
    parse_warnings: list[str] = Field(default_factory=list)


# ── Validation result ──────────────────────────────────────────────────────────

class ValidationIssue(BaseModel):
    level: str  # error, warning
    code: str
    message: str
    passage: Optional[str] = None


class ValidationResult(BaseModel):
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0
