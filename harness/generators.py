"""High-level generation orchestration.

Composes :mod:`ollama_client` (transport) + :mod:`prompts` (templates) +
:mod:`parsers` (output decoding) into the workflow primitives the API layer
consumes: ``build_prompt``, ``generate_story_output``, entity/keyword
extractors, and the six story-init step generators.

Context assembly (snapshot/entity rendering, text trimming) lives here too,
since it only matters at prompt-build time.
"""
from __future__ import annotations
import re
from pathlib import Path

from .models import (
    ExtractedEntities,
    HarnessConfig,
    ModelOutput,
    Snapshot,
    StoryGraph,
)
from .ollama_client import (
    ModelProfile,
    call_ollama,
    model_profile,
)
from .parsers import (
    needs_repair,
    parse_entities_json,
    parse_json_object,
    parse_keywords_json,
    parse_model_output,
    parse_model_output_json,
    structured_score,
)
from .project import (
    ProjectPaths,
    list_characters,
    list_lore,
    load_character,
    load_config,
    load_lore_entity,
)
from .prompts import (
    build_characters_sketch_prompt,
    build_compact_passage_prompt,
    build_entity_extraction_prompt,
    build_full_passage_prompt,
    build_json_passage_prompt,
    build_arc_scenes_prompt,
    build_arcs_prompt,
    build_beats_prompt,
    build_inspiration_summary_prompt,
    build_keyword_extraction_prompt,
    build_locations_sketch_prompt,
    build_opening_prompt,
    build_premise_prompt,
    build_summary_prompt,
    build_repair_prompt,
    build_tone_themes_prompt,
    build_world_prompt,
)


# ── Context assembly helpers ─────────────────────────────────────────────────

def _load_text(path: Path, fallback: str = "") -> str:
    return path.read_text(encoding="utf-8").strip() if path.exists() else fallback


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _trim_text(text: str, max_chars: int, *, tail: bool = False) -> str:
    text = (text or "").strip()
    if not text or len(text) <= max_chars:
        return text
    if tail:
        clipped = text[-max_chars:]
        first_space = clipped.find(" ")
        if first_space > 0:
            clipped = clipped[first_space + 1:]
        return clipped.strip()
    clipped = text[:max_chars]
    last_space = clipped.rfind(" ")
    if last_space > max_chars // 2:
        clipped = clipped[:last_space]
    return clipped.rstrip(" ,;:-")


def _strip_frontmatter(text: str) -> str:
    text = text.strip()
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            text = parts[2]
    return text.strip()


def _render_snapshot(snap: Snapshot) -> str:
    lines = []
    if snap.characters_present:
        lines.append("Characters present:")
        for c in snap.characters_present:
            knows = "; ".join(c.knows) if c.knows else "—"
            lines.append(f"  - {c.id} ({c.status}) | knows: {knows} | rel: {c.relationship_to_player}")
    if snap.characters_offscreen:
        lines.append("Characters offscreen:")
        for c in snap.characters_offscreen:
            lines.append(f"  - {c.id}: {c.last_known}")
    if snap.world_state:
        lines.append("World state:")
        for f in snap.world_state:
            lines.append(f"  - {f}")
    if snap.open_threads:
        lines.append("Open threads:")
        for t in snap.open_threads:
            lines.append(f"  - {t}")
    return "\n".join(lines) if lines else "(empty snapshot)"


def _render_snapshot_compact(snap: Snapshot) -> str:
    parts: list[str] = []
    if snap.characters_present:
        parts.append(
            "Here: " + "; ".join(
                f"{c.id} ({c.status})" for c in snap.characters_present[:4]
            )
        )
    if snap.characters_offscreen:
        parts.append(
            "Away: " + "; ".join(
                f"{c.id} @ {c.last_known}" for c in snap.characters_offscreen[:4]
            )
        )
    if snap.world_state:
        parts.append("World: " + "; ".join(snap.world_state[:5]))
    if snap.open_threads:
        parts.append("Threads: " + "; ".join(snap.open_threads[:5]))
    return "\n".join(parts) if parts else "(empty snapshot)"


def _sheet_summary(text: str, max_chars: int) -> str:
    text = _strip_frontmatter(text)
    text = re.sub(r"^#.*$", "", text, flags=re.MULTILINE)
    return _trim_text(_collapse_ws(text), max_chars)


def _entities_in_context(
    p: ProjectPaths,
    snap: Snapshot,
    human_prompt: str,
    *,
    compact: bool = False,
    summary_chars: int = 220,
    arc_name: str = "",
) -> str:
    """Load full character/lore sheets for entities named in snapshot or prompt.

    Lore matching uses three signals, not just the prompt text:
    1. Direct keyword match: lore ID appears in the human prompt.
    2. Arc-context match: lore ID shares the arc name as a prefix (e.g. arc
       "atlantis" matches "atlantis_ruins", "atlantis_undersea_city"). This
       is the primary fix for mismatched lore — without it, Atlantis lore
       was never injected unless the author happened to type the slug.
    3. Arc-name-as-lore-id: the arc name itself is a lore entry ID.
    """
    char_ids: set[str] = set()
    for c in snap.characters_present:
        char_ids.add(c.id)
    for c in snap.characters_offscreen:
        char_ids.add(c.id)

    prompt_low = (human_prompt or "").lower()
    for ch in list_characters(p):
        cid = ch["id"]
        if cid.lower() in prompt_low:
            char_ids.add(cid)

    # Normalise arc name for matching: strip leading NN_ prefix, keep the
    # short_name portion (e.g. "01_atlantis" -> "atlantis").
    arc_key = (arc_name or "").strip().lower()
    arc_key = re.sub(r"^\d+_", "", arc_key)

    lore_refs: set[tuple[str, str]] = set()
    all_lore = list_lore(p)
    for lore in all_lore:
        lid = lore["id"].lower()
        cat = lore["category"]

        # Signal 1: lore ID appears directly in the prompt text.
        if lid in prompt_low:
            lore_refs.add((cat, lore["id"]))
            continue

        # Signal 2: lore ID shares the arc's short_name as a prefix.
        # e.g. arc_key="atlantis" matches lid="atlantis_ruins".
        if arc_key and lid.startswith(arc_key + "_"):
            lore_refs.add((cat, lore["id"]))
            continue

        # Signal 3: lore ID is exactly the arc's short_name.
        if arc_key and lid == arc_key:
            lore_refs.add((cat, lore["id"]))
            continue

        # Signal 4: arc name appears in the lore's title or summary text.
        if arc_key and arc_key in (lore.get("title", "") or "").lower():
            lore_refs.add((cat, lore["id"]))

    sheets: list[str] = []
    for eid in sorted(char_ids):
        text = load_character(p, eid)
        if text:
            if compact:
                summary = _sheet_summary(text, summary_chars)
                if summary:
                    sheets.append(f"- character {eid}: {summary}")
            else:
                sheets.append(f"--- character: {eid} ---\n{text}")
    for cat, lid in sorted(lore_refs):
        text = load_lore_entity(p, cat, lid)
        if text:
            if compact:
                summary = _sheet_summary(text, summary_chars)
                if summary:
                    sheets.append(f"- lore {cat}/{lid}: {summary}")
            else:
                sheets.append(f"--- lore: {cat}/{lid} ---\n{text}")
    return "\n\n".join(sheets) if sheets else "(no entity sheets loaded)"


# ── Compact + repair wrappers (delegate to prompts module) ───────────────────

def _build_compact_prompt(
    profile: ModelProfile,
    premise: str,
    story_points: str,
    arc_notes: str,
    entities_text: str,
    parent_prose: str,
    snapshot_text: str,
    human_prompt: str,
    inspiration: str = "",
    story_recall: str = "",
    plan_focus: str = "",
) -> str:
    return build_compact_passage_prompt(
        premise=_trim_text(_collapse_ws(premise), profile.premise_chars),
        story_points=_trim_text(_collapse_ws(story_points), profile.story_points_chars),
        arc_notes=_trim_text(_collapse_ws(arc_notes), profile.arc_chars),
        entities_text=_trim_text(entities_text, profile.entities_chars),
        parent_prose=(
            _trim_text(parent_prose, profile.parent_chars, tail=True)
            if parent_prose else "(start of story)"
        ),
        snapshot_text=_trim_text(snapshot_text, profile.snapshot_chars),
        human_prompt=_trim_text(_collapse_ws(human_prompt or ""), 420),
        inspiration=_trim_text(inspiration, profile.inspiration_chars),
        story_recall=_trim_text(story_recall, profile.inspiration_chars),
        plan_focus=_trim_text(_collapse_ws(plan_focus), profile.arc_chars),
    )


# ── Main prompt builder ──────────────────────────────────────────────────────

def build_prompt(
    p: ProjectPaths,
    graph: StoryGraph,
    parent_passage_id: str | None,
    human_prompt: str,
    mode: str,
    arc_name: str,
    cfg: HarnessConfig | None = None,
    inspiration: str = "",
    output_format: str | None = None,
    story_recall: str = "",
) -> str:
    if cfg is None:
        cfg = load_config(p)

    profile = model_profile(cfg.ollama_model)
    premise = _load_text(p.premise_md, "(no premise written yet)")
    story_points = _load_text(p.story_points_md, "(no story points yet)")
    arc_md = _load_text(p.arc_md(arc_name), "(no arc notes yet)")

    # Plan focus: the next open beat this arc should advance, plus the arc goal.
    try:
        from .planning import plan_focus_text
        plan_focus = plan_focus_text(p, arc_name)
    except Exception:
        plan_focus = ""

    parent_snap: Snapshot = Snapshot()
    parent_prose = "(start of story)"
    if parent_passage_id and parent_passage_id in graph.passages:
        entry = graph.passages[parent_passage_id]
        parent_snap = entry.snapshot
        tw_path = p.root / entry.file
        if tw_path.exists():
            raw = tw_path.read_text(encoding="utf-8")
            stripped = re.sub(r'<!--.*?-->', '', raw, flags=re.DOTALL)
            stripped = re.sub(r'<<[^>]+>>', '', stripped)
            stripped = re.sub(r'\[\[[^\]]+\]\]', '', stripped)
            stripped = re.sub(r'^::.*?$', '', stripped, count=1, flags=re.MULTILINE)
            parent_prose = stripped.strip()[-2000:]

    use_compact = (
        cfg.model_mode == "compact"
        or (cfg.model_mode == "auto" and profile.use_compact_prompt)
    )
    fmt = output_format or getattr(cfg, "output_format", "delimited")
    entities_text = _entities_in_context(
        p,
        parent_snap,
        human_prompt,
        compact=use_compact,
        summary_chars=max(120, profile.entities_chars // 2),
        arc_name=arc_name,
    )
    snapshot_text = _render_snapshot_compact(parent_snap) if use_compact else _render_snapshot(parent_snap)

    if fmt == "json":
        return build_json_passage_prompt(
            premise=_trim_text(_collapse_ws(premise), profile.premise_chars),
            story_points=_trim_text(_collapse_ws(story_points), profile.story_points_chars),
            arc_md=_trim_text(_collapse_ws(arc_md), profile.arc_chars),
            snapshot_text=_trim_text(snapshot_text, profile.snapshot_chars),
            entities_text=_trim_text(entities_text, profile.entities_chars),
            inspiration=_trim_text(inspiration, profile.inspiration_chars),
            parent_prose=_trim_text(parent_prose, profile.parent_chars, tail=True) if parent_prose else "(start of story)",
            human_prompt=_trim_text(_collapse_ws(human_prompt or ""), 420),
            mode=mode,
            story_recall=_trim_text(story_recall, profile.inspiration_chars),
            plan_focus=_trim_text(_collapse_ws(plan_focus), profile.arc_chars),
            template_id=getattr(cfg, "template_id", ""),
        )

    if use_compact:
        return _build_compact_prompt(
            profile,
            premise,
            story_points,
            arc_md,
            entities_text,
            parent_prose,
            snapshot_text,
            human_prompt,
            inspiration,
            story_recall,
            plan_focus,
        )

    return build_full_passage_prompt(
        premise=premise,
        story_points=story_points,
        arc_md=arc_md,
        snapshot_text=snapshot_text,
        entities_text=entities_text,
        inspiration=inspiration,
        parent_prose=parent_prose,
        human_prompt=human_prompt,
        mode=mode,
        story_recall=story_recall,
        plan_focus=plan_focus,
        template_id=getattr(cfg, "template_id", ""),
    )


# ── Passage generation (with auto-repair) ────────────────────────────────────

def _model_output_schema() -> dict:
    """JSON schema passed to Ollama's ``format`` field for strict JSON mode."""
    return ModelOutput.model_json_schema()


def _strip_summary_warnings(warnings: list[str]) -> list[str]:
    return [w for w in warnings if "summary" not in w.lower()]


async def _regenerate_summary(cfg: HarnessConfig, prose: str) -> str:
    prompt = build_summary_prompt(prose)
    try:
        raw = await call_ollama(
            cfg, prompt,
            timeout=20.0,
            temperature=0.2,
            num_predict=80,
            label="summary",
        )
    except Exception:
        return ""
    text = (raw or "").strip().strip("\"'")
    first = re.split(r'(?<=[.!?])\s', text)[0].strip()
    return first[:150]


async def _ensure_summary(cfg: HarnessConfig, parsed: ModelOutput) -> None:
    if parsed.summary.strip() or not parsed.prose.strip():
        return
    summary = await _regenerate_summary(cfg, parsed.prose)
    if summary:
        parsed.summary = summary
        parsed.parse_warnings = _strip_summary_warnings(parsed.parse_warnings)


async def generate_story_output(
    cfg: HarnessConfig,
    prompt: str,
    timeout: float = 120.0,
) -> tuple[str, ModelOutput]:
    fmt = getattr(cfg, "output_format", "delimited")
    if fmt == "json":
        format_spec: str | dict | None = _model_output_schema()
        raw = await call_ollama(cfg, prompt, timeout=timeout, format_spec=format_spec, label="passage")
        parsed = parse_model_output_json(raw)
    else:
        raw = await call_ollama(cfg, prompt, timeout=timeout, label="passage")
        parsed = parse_model_output(raw)

    if not needs_repair(parsed):
        await _ensure_summary(cfg, parsed)
        return raw, parsed

    # Auto-repair: short prompt, delimited parser (more permissive than JSON).
    try:
        repaired_raw = await call_ollama(
            cfg,
            build_repair_prompt(_trim_text(raw.strip(), 2400, tail=True)),
            timeout=min(timeout, 60.0),
            temperature=0.2,
            label="repair",
        )
    except Exception as e:
        parsed.parse_warnings.append(f"Auto-repair skipped after Ollama error: {e}")
        await _ensure_summary(cfg, parsed)
        return raw, parsed

    repaired = parse_model_output(repaired_raw)
    repaired_score = structured_score(repaired)
    original_score = structured_score(parsed)
    if repaired_score > original_score:
        repaired.parse_warnings.insert(0, "Auto-repair reformatted weak first draft.")
        await _ensure_summary(cfg, repaired)
        return repaired_raw, repaired

    parsed.parse_warnings.append("Auto-repair tried, but original draft parsed better.")
    await _ensure_summary(cfg, parsed)
    return raw, parsed


# ── Entity / keyword extraction ──────────────────────────────────────────────

async def extract_entities(
    cfg: HarnessConfig,
    prose: str,
    timeout: float = 45.0,
    direction: str = "",
) -> ExtractedEntities:
    """Second-pass entity extraction. Returns empty struct on any failure."""
    if not prose or not prose.strip():
        return ExtractedEntities()
    prompt = build_entity_extraction_prompt(prose, direction=direction)
    schema = ExtractedEntities.model_json_schema()
    try:
        raw = await call_ollama(
            cfg, prompt, timeout=timeout,
            temperature=0.2, num_predict=512,
            format_spec=schema,
        )
    except Exception:
        return ExtractedEntities()
    return parse_entities_json(raw)


_INSPIRATION_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "game_type": {"type": "string"},
        "themes": {"type": "array", "items": {"type": "string"}},
        "characters": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["game_type", "themes", "characters", "summary"],
}


_BEATS_SCHEMA = {
    "type": "object",
    "properties": {
        "beats": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "act": {"type": "string"},
                },
                "required": ["text"],
            },
        }
    },
    "required": ["beats"],
}

_ARCS_SCHEMA = {
    "type": "object",
    "properties": {
        "arcs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "goal": {"type": "string"},
                },
                "required": ["name"],
            },
        }
    },
    "required": ["arcs"],
}


async def generate_beats(
    cfg: HarnessConfig,
    premise: str,
    story_points: str,
    existing_beats: str,
    count: int = 5,
    direction: str = "",
    timeout: float = 75.0,
) -> list[dict]:
    """Propose new plot beats. Returns [{text, act}], [] on failure."""
    prompt = build_beats_prompt(premise, story_points, existing_beats, count, direction)
    try:
        raw = await call_ollama(
            cfg, prompt, timeout=timeout,
            temperature=0.5, num_predict=700,
            format_spec=_BEATS_SCHEMA, label="beats",
        )
    except Exception:
        return []
    data = parse_json_object(raw)
    if not isinstance(data, dict) or not isinstance(data.get("beats"), list):
        return []
    out: list[dict] = []
    for raw_beat in data["beats"][:max(1, min(count, 50))]:
        if not isinstance(raw_beat, dict):
            continue
        text = str(raw_beat.get("text", "")).strip()
        if not text:
            continue
        out.append({"text": text, "act": str(raw_beat.get("act", "")).strip()})
    return out


async def generate_arcs(
    cfg: HarnessConfig,
    premise: str,
    beats_text: str,
    existing_arcs: str,
    count: int = 3,
    direction: str = "",
    timeout: float = 75.0,
) -> list[dict]:
    """Propose new arcs. Returns [{name, goal}], [] on failure."""
    prompt = build_arcs_prompt(premise, beats_text, existing_arcs, count, direction)
    try:
        raw = await call_ollama(
            cfg, prompt, timeout=timeout,
            temperature=0.5, num_predict=600,
            format_spec=_ARCS_SCHEMA, label="arcs",
        )
    except Exception:
        return []
    data = parse_json_object(raw)
    if not isinstance(data, dict) or not isinstance(data.get("arcs"), list):
        return []
    # Import normalize_arc_name for consistent NN_short_name formatting
    from .planning import normalize_arc_name
    out: list[dict] = []
    existing_names: list[str] = []
    for raw_arc in data["arcs"][:max(1, min(count, 50))]:
        if not isinstance(raw_arc, dict):
            continue
        name = normalize_arc_name(str(raw_arc.get("name", "")).strip(), existing_names)
        if not name:
            continue
        existing_names.append(name)
        out.append({"name": name, "goal": str(raw_arc.get("goal", "")).strip()})
    return out


_ARC_SCENES_SCHEMA = {
    "type": "object",
    "properties": {
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                    "characters": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "summary"],
            },
        }
    },
    "required": ["scenes"],
}


async def generate_arc_scenes(
    cfg: HarnessConfig,
    premise: str,
    arc_goal: str,
    arc_notes: str,
    beats_text: str,
    existing_scenes: str,
    count: int = 4,
    direction: str = "",
    timeout: float = 75.0,
) -> list[dict]:
    """Outline planned scenes for an arc. Returns [] on failure.

    Each item: {title, summary, keywords[], characters[]} — sketches, not prose.
    """
    prompt = build_arc_scenes_prompt(
        premise, arc_goal, arc_notes, beats_text, existing_scenes, count, direction,
    )
    try:
        raw = await call_ollama(
            cfg, prompt, timeout=timeout,
            temperature=0.5, num_predict=900,
            format_spec=_ARC_SCENES_SCHEMA,
            label="arc-scenes",
        )
    except Exception:
        return []
    data = parse_json_object(raw)
    if not isinstance(data, dict) or not isinstance(data.get("scenes"), list):
        return []
    out: list[dict] = []
    for raw_scene in data["scenes"][:max(1, min(count, 50))]:
        if not isinstance(raw_scene, dict):
            continue
        title = str(raw_scene.get("title", "")).strip()
        summary = str(raw_scene.get("summary", "")).strip()
        if not (title or summary):
            continue
        out.append({
            "title": title,
            "summary": summary,
            "keywords": [str(k).strip() for k in (raw_scene.get("keywords") or []) if str(k).strip()][:8],
            "characters": [str(c).strip() for c in (raw_scene.get("characters") or []) if str(c).strip()][:8],
        })
    return out


async def summarize_inspiration(
    cfg: HarnessConfig,
    text: str,
    timeout: float = 60.0,
) -> dict:
    """Short digest of a reference item: {game_type, themes[], characters[], summary}.

    Returns empty fields on failure rather than raising.
    """
    empty = {"game_type": "", "themes": [], "characters": [], "summary": ""}
    if not text or not text.strip():
        return empty
    prompt = build_inspiration_summary_prompt(text)
    try:
        raw = await call_ollama(
            cfg, prompt, timeout=timeout,
            temperature=0.2, num_predict=400,
            format_spec=_INSPIRATION_SUMMARY_SCHEMA,
            label="inspiration-digest",
        )
    except Exception:
        return empty
    data = parse_json_object(raw)
    if not isinstance(data, dict):
        return empty
    return {
        "game_type": str(data.get("game_type", "")).strip(),
        "themes": [str(t).strip() for t in (data.get("themes") or []) if str(t).strip()][:6],
        "characters": [str(c).strip() for c in (data.get("characters") or []) if str(c).strip()][:8],
        "summary": str(data.get("summary", "")).strip(),
    }


async def extract_keywords(
    cfg: HarnessConfig,
    content: str,
    kind: str = "character",
    timeout: float = 30.0,
    max_keywords: int = 12,
    direction: str = "",
) -> list[str]:
    """AI-generate keywords for a character or lore sheet. Returns [] on failure."""
    if not content or not content.strip():
        return []
    prompt = build_keyword_extraction_prompt(content, kind, direction=direction)
    schema = {
        "type": "object",
        "properties": {
            "keywords": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["keywords"],
    }
    try:
        raw = await call_ollama(
            cfg, prompt, timeout=timeout,
            temperature=0.2, num_predict=256,
            format_spec=schema,
        )
    except Exception:
        return []
    return parse_keywords_json(raw, max_keywords)


# ── Story-init generation helpers ────────────────────────────────────────────

# Schemas passed to Ollama's `format` field. Pure dicts so they're JSON-serializable.
_PREMISE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "premise": {"type": "string"},
    },
    "required": ["title", "premise"],
}
_TONE_THEMES_SCHEMA = {
    "type": "object",
    "properties": {
        "tone": {"type": "string"},
        "themes": {"type": "string"},
    },
    "required": ["tone", "themes"],
}
_WORLD_SCHEMA = {
    "type": "object",
    "properties": {"world_overview": {"type": "string"}},
    "required": ["world_overview"],
}
_OPENING_SCHEMA = {
    "type": "object",
    "properties": {"opening_situation": {"type": "string"}},
    "required": ["opening_situation"],
}
_SKETCH_ITEM = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": "string"},
        "physical": {"type": "string"},
        "personality": {"type": "string"},
        "motivation": {"type": "string"},
        "backstory": {"type": "string"},
        "relationships": {"type": "string"},
        "speech": {"type": "string"},
    },
    "required": ["id", "name", "description"],
}
_CHARACTERS_SCHEMA = {
    "type": "object",
    "properties": {"characters": {"type": "array", "items": _SKETCH_ITEM}},
    "required": ["characters"],
}
_LOCATIONS_SCHEMA = {
    "type": "object",
    "properties": {"locations": {"type": "array", "items": _SKETCH_ITEM}},
    "required": ["locations"],
}


async def _generate_json(
    cfg: HarnessConfig,
    prompt: str,
    schema: dict,
    timeout: float = 60.0,
    num_predict: int = 768,
    temperature: float = 0.6,
    label: str = "init",
) -> dict | None:
    raw = await call_ollama(
        cfg, prompt, timeout=timeout,
        temperature=temperature,
        num_predict=num_predict,
        format_spec=schema,
        label=label,
    )
    data = parse_json_object(raw)
    if data is None:
        raise ValueError("Model response was not valid JSON.")
    return data


def _normalise_sketch_list(items, count: int) -> list[dict]:
    out: list[dict] = []
    seen_ids: set[str] = set()
    if not isinstance(items, list):
        return out
    # Enrichment fields that are passed through if the model provided them.
    enrichment_fields = ("physical", "personality", "motivation", "backstory", "relationships", "speech")
    for raw in items[: max(1, min(count, 12))]:
        if not isinstance(raw, dict):
            continue
        rid = re.sub(r'[^a-z0-9_]', '_', str(raw.get("id", "")).strip().lower())[:40]
        name = str(raw.get("name", "")).strip()
        desc = str(raw.get("description", "")).strip()
        if not rid or not name or not desc or rid in seen_ids:
            continue
        seen_ids.add(rid)
        entry = {"id": rid, "name": name, "description": desc}
        for field in enrichment_fields:
            val = str(raw.get(field, "")).strip()
            if val:
                entry[field] = val
        out.append(entry)
    return out


async def generate_premise(cfg: HarnessConfig, seed: str, direction: str = "") -> dict:
    data = await _generate_json(
        cfg, build_premise_prompt(seed, direction), _PREMISE_SCHEMA,
    )
    if not data:
        return {"title": "", "premise": ""}
    return {
        "title": str(data.get("title", "")).strip(),
        "premise": str(data.get("premise", "")).strip(),
    }


async def generate_tone_themes(cfg: HarnessConfig, premise: str, direction: str = "") -> dict:
    data = await _generate_json(
        cfg, build_tone_themes_prompt(premise, direction), _TONE_THEMES_SCHEMA,
    )
    if not data:
        return {"tone": "", "themes": ""}
    return {
        "tone": str(data.get("tone", "")).strip(),
        "themes": str(data.get("themes", "")).strip(),
    }


async def generate_world(
    cfg: HarnessConfig, premise: str, tone: str = "", themes: str = "", direction: str = "",
) -> dict:
    data = await _generate_json(
        cfg, build_world_prompt(premise, tone, themes, direction), _WORLD_SCHEMA,
    )
    if not data:
        return {"world_overview": ""}
    return {"world_overview": str(data.get("world_overview", "")).strip()}


async def generate_opening(
    cfg: HarnessConfig, premise: str, world_overview: str = "", direction: str = "",
) -> dict:
    data = await _generate_json(
        cfg, build_opening_prompt(premise, world_overview, direction), _OPENING_SCHEMA,
    )
    if not data:
        return {"opening_situation": ""}
    return {"opening_situation": str(data.get("opening_situation", "")).strip()}


async def generate_characters_sketch(
    cfg: HarnessConfig, premise: str, world_overview: str = "", count: int = 3, direction: str = "",
) -> dict:
    data = await _generate_json(
        cfg,
        build_characters_sketch_prompt(premise, world_overview, count, direction),
        _CHARACTERS_SCHEMA,
        num_predict=1024,
    )
    if not data:
        return {"characters": []}
    return {"characters": _normalise_sketch_list(data.get("characters"), count)}


async def generate_locations_sketch(
    cfg: HarnessConfig, premise: str, world_overview: str = "", count: int = 3, direction: str = "",
) -> dict:
    data = await _generate_json(
        cfg,
        build_locations_sketch_prompt(premise, world_overview, count, direction),
        _LOCATIONS_SCHEMA,
        num_predict=1024,
    )
    if not data:
        return {"locations": []}
    return {"locations": _normalise_sketch_list(data.get("locations"), count)}
