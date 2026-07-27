"""Pydantic models for story.json and related data structures."""
from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field


# All recognised passage types. Renderer + validation branch on this.
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
)


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


class StateVariable(BaseModel):
    type: str  # bool, int, str, float
    default: Any = None
    declared_in: str = ""


class BranchEntry(BaseModel):
    head: str
    diverges_at: Optional[str] = None


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


class StoryGraph(BaseModel):
    version: int = 1
    start_passage: str = ""
    passages: dict[str, PassageEntry] = Field(default_factory=dict)
    state_variables: dict[str, StateVariable] = Field(default_factory=dict)
    branches: dict[str, BranchEntry] = Field(default_factory=dict)
    plan: StoryPlan = Field(default_factory=StoryPlan)
    arcs: dict[str, ArcPlan] = Field(default_factory=dict)  # keyed by arc name


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
    format_version: str = "2.36.1"
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


class SessionState(BaseModel):
    current_passage: Optional[str] = None
    current_branch: str = "main"
    active_mode: str = "co-author"  # director, co-author, editor


# ── Parsed model output ────────────────────────────────────────────────────────

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


class ModelOutput(BaseModel):
    prose: str = ""
    choices: list[ParsedChoice] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)
    media: list[ParsedMediaSlot] = Field(default_factory=list)
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
