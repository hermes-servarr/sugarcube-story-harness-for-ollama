"""Planning layer — connect the overarching story (beats) to arcs and passages.

The harness owns the structured plan in ``story.json`` (``graph.plan`` +
``graph.arcs``). Beats are author intent; arcs declare which beats they advance;
passages tag the beats they actually deliver. Coverage and gaps are *derived* —
never stored — so they can't drift out of sync with the graph.

``story_points.md`` stays as the human's free-text scratchpad. :func:`import_story_points`
promotes its act/bullet structure into the canonical beat list on demand.
"""
from __future__ import annotations
import hashlib
import json
import re
import threading

from .models import ArcPlan, Beat, PlannedScene, StoryGraph
from .project import ProjectPaths, load_story, save_story


class StoryPlanConflict(ValueError):
    def __init__(self, expected: str, actual: str):
        self.expected = expected
        self.actual = actual
        super().__init__("story plan changed since it was loaded")


_PLAN_WRITE_LOCK = threading.RLock()


def story_fingerprint(graph: StoryGraph) -> str:
    payload = json.dumps(graph.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _expect_fingerprint(graph: StoryGraph, expected: str | None) -> None:
    actual = story_fingerprint(graph)
    if expected is not None and expected != actual:
        raise StoryPlanConflict(expected, actual)


# ── Beat id allocation ─────────────────────────────────────────────────────────

def _next_beat_id(graph: StoryGraph) -> str:
    """Lowest unused ``bN`` id."""
    used = set()
    for b in graph.plan.beats:
        m = re.fullmatch(r"b(\d+)", b.id)
        if m:
            used.add(int(m.group(1)))
    n = 1
    while n in used:
        n += 1
    return f"b{n}"


def _find_beat(graph: StoryGraph, beat_id: str) -> Beat | None:
    return next((b for b in graph.plan.beats if b.id == beat_id), None)


# ── Coverage derivation ────────────────────────────────────────────────────────

def _beat_passages(graph: StoryGraph, beat_id: str) -> list[str]:
    return sorted(
        pid for pid, e in graph.passages.items() if beat_id in e.plan_beats
    )


def _beat_arcs(graph: StoryGraph, beat_id: str) -> list[str]:
    return sorted(
        arc for arc, ap in graph.arcs.items() if beat_id in ap.beat_ids
    )


def recompute_beat_status(graph: StoryGraph) -> None:
    """Mark each beat ``covered`` iff at least one passage tags it. Mutates graph."""
    for beat in graph.plan.beats:
        beat.status = "covered" if _beat_passages(graph, beat.id) else "open"


def _all_arc_names(graph: StoryGraph) -> list[str]:
    """Arc names known from either the plan (graph.arcs) or any passage."""
    names = set(graph.arcs.keys())
    names.update(e.arc for e in graph.passages.values() if e.arc)
    return sorted(names)


def plan_overview(p: ProjectPaths) -> dict:
    """Full planning snapshot: acts, beats+coverage, arcs+status, and gaps.

    Pure read — recomputes beat status in-memory but does not persist.
    """
    graph = load_story(p)
    recompute_beat_status(graph)

    known_beat_ids = {b.id for b in graph.plan.beats}

    beats_out: list[dict] = []
    for b in graph.plan.beats:
        passages = _beat_passages(graph, b.id)
        arcs = _beat_arcs(graph, b.id)
        beats_out.append({
            "id": b.id, "text": b.text, "act": b.act,
            "status": b.status, "arcs": arcs, "passages": passages,
            "covered": bool(passages),
        })

    arcs_out: list[dict] = []
    for arc in _all_arc_names(graph):
        ap = graph.arcs.get(arc, ArcPlan())
        passages = sorted(pid for pid, e in graph.passages.items() if e.arc == arc)
        arcs_out.append({
            "arc": arc, "goal": ap.goal, "status": ap.status,
            "summary": ap.summary, "beat_ids": list(ap.beat_ids),
            "passage_count": len(passages), "passages": passages,
            "scenes": [s.model_dump() for s in ap.scenes],
        })

    # ── Gaps ─────────────────────────────────────────────────────────────────
    open_beats = [b["id"] for b in beats_out if not b["covered"]]
    beats_without_arc = [b["id"] for b in beats_out if not b["arcs"]]
    arcs_without_beats = [a["arc"] for a in arcs_out if not a["beat_ids"]]
    # beat ids referenced anywhere but missing from the plan
    referenced: set[str] = set()
    for e in graph.passages.values():
        referenced.update(e.plan_beats)
    for ap in graph.arcs.values():
        referenced.update(ap.beat_ids)
    unknown_refs = sorted(referenced - known_beat_ids)

    return {
        "acts": list(graph.plan.acts),
        "open_questions": list(graph.plan.open_questions),
        "beats": beats_out,
        "arcs": arcs_out,
        "gaps": {
            "open_beats": open_beats,
            "beats_without_arc": beats_without_arc,
            "arcs_without_beats": arcs_without_beats,
            "unknown_beat_refs": unknown_refs,
        },
    }


# ── Generation focus ───────────────────────────────────────────────────────────

def next_focus_beat(graph: StoryGraph, arc_name: str) -> Beat | None:
    """The beat generation should aim at next: first open beat the arc is meant
    to advance, else first open beat overall, else None."""
    recompute_beat_status(graph)
    ap = graph.arcs.get(arc_name)
    if ap:
        for bid in ap.beat_ids:
            b = _find_beat(graph, bid)
            if b and b.status == "open":
                return b
    return next((b for b in graph.plan.beats if b.status == "open"), None)


def plan_focus_text(p: ProjectPaths, arc_name: str) -> str:
    """Render a compact plan-focus block for the passage prompt, or ``""``.

    Shows the target beat plus the arc's goal so the model writes toward the
    plan rather than wandering.
    """
    graph = load_story(p)
    ap = graph.arcs.get(arc_name)
    beat = next_focus_beat(graph, arc_name)
    lines: list[str] = []
    if ap and ap.goal.strip():
        lines.append(f"Arc goal: {ap.goal.strip()}")
    if beat:
        act = f" [{beat.act}]" if beat.act else ""
        lines.append(f"Target beat{act}: {beat.text}")
    return "\n".join(lines)


# ── Mutations ──────────────────────────────────────────────────────────────────

def add_beat(
    p: ProjectPaths, text: str, act: str = "", *, expected_fingerprint: str | None = None
) -> Beat:
    with _PLAN_WRITE_LOCK:
        graph = load_story(p)
        _expect_fingerprint(graph, expected_fingerprint)
        beat = Beat(id=_next_beat_id(graph), text=text.strip(), act=act.strip())
        graph.plan.beats.append(beat)
        save_story(p, graph)
        return beat


def add_beats_bulk(p: ProjectPaths, beats: list[dict]) -> list[Beat]:
    """Append several beats at once (e.g. from an AI generation). Skips blanks
    and exact-text duplicates of existing beats."""
    graph = load_story(p)
    existing = {b.text.strip().lower() for b in graph.plan.beats}
    created: list[Beat] = []
    for raw in beats:
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text", "")).strip()
        if not text or text.lower() in existing:
            continue
        existing.add(text.lower())
        beat = Beat(id=_next_beat_id(graph), text=text, act=str(raw.get("act", "")).strip())
        graph.plan.beats.append(beat)
        created.append(beat)
    save_story(p, graph)
    return created


_ARC_NAME_RE = re.compile(r"^\d{2}_([a-z0-9_]+)$")
_MAX_ARC_NAME_LEN = 60


def normalize_arc_name(name: str, existing_arcs: list[str] | None = None) -> str:
    """Normalize an arc name to the canonical NN_short_name format.

    Rules:
    - Lowercase, underscores only, no leading/trailing underscores.
    - If the name already starts with NN_, keep it (after stripping
      a literal "nn_" prefix the model sometimes emits).
    - If no numeric prefix, auto-assign the next available two-digit number.
    - Max 60 characters.
    - Returns empty string for blank input.
    """
    raw = (name or "").strip().lower()
    # Strip a literal "nn_" prefix the model sometimes emits (e.g. "nn_01_atlantis")
    if raw.startswith("nn_"):
        raw = raw[3:]
    # Keep only valid chars
    raw = re.sub(r"[^a-z0-9_]", "_", raw).strip("_")
    # Collapse consecutive underscores
    raw = re.sub(r"_{2,}", "_", raw).strip("_")
    if not raw:
        return ""

    existing = set(existing_arcs or [])

    # Check if it already has a NN_ prefix
    m = re.match(r"^(\d{2})_(.+)$", raw)
    if m:
        short_name = m.group(2).strip("_")
        if not short_name:
            return ""
        norm = f"{m.group(1)}_{short_name}"[:_MAX_ARC_NAME_LEN]
        return norm

    # No numeric prefix — auto-assign the next available number
    used_nums: set[int] = set()
    for arc in existing:
        m2 = re.match(r"^(\d{2})_", arc)
        if m2:
            used_nums.add(int(m2.group(1)))
    n = 1
    while n in used_nums:
        n += 1
    norm = f"{n:02d}_{raw}"[:_MAX_ARC_NAME_LEN]
    return norm


def create_arc(
    p: ProjectPaths, name: str, goal: str = "", *, expected_fingerprint: str | None = None
) -> tuple[str, ArcPlan] | None:
    """Create a new (empty) arc plan under a normalised name. Returns
    (normalised_name, ArcPlan), or None if the name is blank.

    Arc names are normalized to NN_short_name format (e.g. "01_atlantis").
    """
    with _PLAN_WRITE_LOCK:
        graph = load_story(p)
        _expect_fingerprint(graph, expected_fingerprint)
        norm = normalize_arc_name(name, list(graph.arcs.keys()))
        if not norm:
            return None
        # If normalization produced a name that already exists (e.g. same number
        # different short name), bump to next available number.
        if norm in graph.arcs:
            used_nums = set()
            for arc in graph.arcs:
                m = re.match(r"^(\d{2})_", arc)
                if m:
                    used_nums.add(int(m.group(1)))
            m = re.match(r"^\d{2}_(.+)$", norm)
            short_name = m.group(1) if m else norm
            n = 1
            while n in used_nums:
                n += 1
            norm = f"{n:02d}_{short_name}"[:_MAX_ARC_NAME_LEN]
        ap = graph.arcs.get(norm) or ArcPlan()
        if goal.strip():
            ap.goal = goal.strip()
        graph.arcs[norm] = ap
        save_story(p, graph)
        return norm, ap


def add_arcs_bulk(p: ProjectPaths, arcs: list[dict]) -> list[str]:
    """Create several arcs from AI output [{name, goal}]. Returns created names."""
    created: list[str] = []
    for raw in arcs:
        if not isinstance(raw, dict):
            continue
        res = create_arc(p, str(raw.get("name", "")), str(raw.get("goal", "")))
        if res:
            created.append(res[0])
    return created


def update_beat(
    p: ProjectPaths, beat_id: str, text: str | None = None, act: str | None = None,
    *, expected_fingerprint: str | None = None,
) -> bool:
    with _PLAN_WRITE_LOCK:
        graph = load_story(p)
        _expect_fingerprint(graph, expected_fingerprint)
        beat = _find_beat(graph, beat_id)
        if beat is None:
            return False
        if text is not None:
            beat.text = text.strip()
        if act is not None:
            beat.act = act.strip()
        save_story(p, graph)
        return True


def delete_beat(
    p: ProjectPaths, beat_id: str, *, expected_fingerprint: str | None = None
) -> bool:
    """Remove a beat and scrub its id from every arc and passage reference."""
    with _PLAN_WRITE_LOCK:
        graph = load_story(p)
        _expect_fingerprint(graph, expected_fingerprint)
        before = len(graph.plan.beats)
        graph.plan.beats = [b for b in graph.plan.beats if b.id != beat_id]
        if len(graph.plan.beats) == before:
            return False
        for ap in graph.arcs.values():
            ap.beat_ids = [b for b in ap.beat_ids if b != beat_id]
        for e in graph.passages.values():
            e.plan_beats = [b for b in e.plan_beats if b != beat_id]
        save_story(p, graph)
        return True


def set_acts(p: ProjectPaths, acts: list[str]) -> None:
    graph = load_story(p)
    graph.plan.acts = [a.strip() for a in acts if a.strip()]
    save_story(p, graph)


def set_open_questions(p: ProjectPaths, questions: list[str]) -> None:
    graph = load_story(p)
    graph.plan.open_questions = [q.strip() for q in questions if q.strip()]
    save_story(p, graph)


def set_arc_plan(
    p: ProjectPaths,
    arc_name: str,
    *,
    goal: str | None = None,
    beat_ids: list[str] | None = None,
    status: str | None = None,
    summary: str | None = None,
    expected_fingerprint: str | None = None,
) -> ArcPlan:
    with _PLAN_WRITE_LOCK:
        graph = load_story(p)
        _expect_fingerprint(graph, expected_fingerprint)
        ap = graph.arcs.get(arc_name) or ArcPlan()
        if goal is not None:
            ap.goal = goal.strip()
        if status is not None:
            ap.status = status.strip() or "planned"
        if summary is not None:
            ap.summary = summary.strip()
        if beat_ids is not None:
            known = {b.id for b in graph.plan.beats}
            ap.beat_ids = [b for b in beat_ids if b in known]
        graph.arcs[arc_name] = ap
        save_story(p, graph)
        return ap


def set_passage_beats(p: ProjectPaths, passage_id: str, beat_ids: list[str]) -> bool:
    """Tag a passage with the plan beats it delivers (drops unknown ids)."""
    graph = load_story(p)
    entry = graph.passages.get(passage_id)
    if entry is None:
        return False
    known = {b.id for b in graph.plan.beats}
    entry.plan_beats = [b for b in beat_ids if b in known]
    save_story(p, graph)
    return True


# ── Planned scenes (per arc) ────────────────────────────────────────────────────

def _next_scene_id(ap: ArcPlan) -> str:
    """Lowest unused ``scN`` id within one arc."""
    used = set()
    for s in ap.scenes:
        m = re.fullmatch(r"sc(\d+)", s.id)
        if m:
            used.add(int(m.group(1)))
    n = 1
    while n in used:
        n += 1
    return f"sc{n}"


def _ensure_arc(graph: StoryGraph, arc_name: str) -> ArcPlan:
    ap = graph.arcs.get(arc_name)
    if ap is None:
        ap = ArcPlan()
        graph.arcs[arc_name] = ap
    return ap


def add_scene(
    p: ProjectPaths,
    arc_name: str,
    *,
    title: str = "",
    summary: str = "",
    keywords: list[str] | None = None,
    characters: list[str] | None = None,
    beat_ids: list[str] | None = None,
    expected_fingerprint: str | None = None,
) -> PlannedScene:
    with _PLAN_WRITE_LOCK:
        graph = load_story(p)
        _expect_fingerprint(graph, expected_fingerprint)
        ap = _ensure_arc(graph, arc_name)
        known = {b.id for b in graph.plan.beats}
        scene = PlannedScene(
            id=_next_scene_id(ap),
            title=title.strip(),
            summary=summary.strip(),
            keywords=[k.strip() for k in (keywords or []) if k.strip()],
            characters=[c.strip() for c in (characters or []) if c.strip()],
            beat_ids=[b for b in (beat_ids or []) if b in known],
        )
        ap.scenes.append(scene)
        save_story(p, graph)
        return scene


def update_scene(
    p: ProjectPaths,
    arc_name: str,
    scene_id: str,
    *,
    title: str | None = None,
    summary: str | None = None,
    keywords: list[str] | None = None,
    characters: list[str] | None = None,
    beat_ids: list[str] | None = None,
    passage_id: str | None = None,
    status: str | None = None,
    expected_fingerprint: str | None = None,
) -> bool:
    with _PLAN_WRITE_LOCK:
        graph = load_story(p)
        _expect_fingerprint(graph, expected_fingerprint)
        ap = graph.arcs.get(arc_name)
        if ap is None:
            return False
        scene = next((s for s in ap.scenes if s.id == scene_id), None)
        if scene is None:
            return False
        if title is not None:
            scene.title = title.strip()
        if summary is not None:
            scene.summary = summary.strip()
        if keywords is not None:
            scene.keywords = [k.strip() for k in keywords if k.strip()]
        if characters is not None:
            scene.characters = [c.strip() for c in characters if c.strip()]
        if beat_ids is not None:
            known = {b.id for b in graph.plan.beats}
            scene.beat_ids = [b for b in beat_ids if b in known]
        if passage_id is not None:
            scene.passage_id = passage_id.strip()
            scene.status = "drafted" if scene.passage_id else "planned"
        if status is not None:
            scene.status = status.strip() or "planned"
        save_story(p, graph)
        return True


def delete_scene(
    p: ProjectPaths, arc_name: str, scene_id: str,
    *, expected_fingerprint: str | None = None,
) -> bool:
    with _PLAN_WRITE_LOCK:
        graph = load_story(p)
        _expect_fingerprint(graph, expected_fingerprint)
        ap = graph.arcs.get(arc_name)
        if ap is None:
            return False
        before = len(ap.scenes)
        ap.scenes = [s for s in ap.scenes if s.id != scene_id]
        if len(ap.scenes) == before:
            return False
        save_story(p, graph)
        return True


def add_scenes_bulk(p: ProjectPaths, arc_name: str, scenes: list[dict]) -> list[PlannedScene]:
    """Append several scenes at once (e.g. from an AI generation). Each dict may
    carry title/summary/keywords/characters/beat_ids."""
    graph = load_story(p)
    ap = _ensure_arc(graph, arc_name)
    known = {b.id for b in graph.plan.beats}
    created: list[PlannedScene] = []
    for raw in scenes:
        if not isinstance(raw, dict):
            continue
        scene = PlannedScene(
            id=_next_scene_id(ap),
            title=str(raw.get("title", "")).strip(),
            summary=str(raw.get("summary", "")).strip(),
            keywords=[str(k).strip() for k in (raw.get("keywords") or []) if str(k).strip()],
            characters=[str(c).strip() for c in (raw.get("characters") or []) if str(c).strip()],
            beat_ids=[b for b in (raw.get("beat_ids") or []) if b in known],
        )
        if not (scene.title or scene.summary or scene.keywords):
            continue
        ap.scenes.append(scene)
        created.append(scene)
    save_story(p, graph)
    return created


# ── Import from story_points.md ─────────────────────────────────────────────────

_ACT_RE = re.compile(r"^#{1,6}\s*(act\s.*|act\b.*)$", re.IGNORECASE)
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.*)$")


def import_story_points(p: ProjectPaths, *, replace: bool = False) -> dict:
    """Parse ``story_points.md`` headings/bullets into structured beats.

    Markdown headings containing "Act" become act labels; bullets under them
    become beats. Bullets under an "Open Questions" heading become open
    questions. Existing beats are kept unless ``replace`` is True. Returns the
    resulting :func:`plan_overview`.
    """
    graph = load_story(p)
    text = p.story_points_md.read_text(encoding="utf-8") if p.story_points_md.exists() else ""

    if replace:
        graph.plan.beats = []
        graph.plan.acts = []
        graph.plan.open_questions = []
        # also drop dangling references
        for ap in graph.arcs.values():
            ap.beat_ids = []
        for e in graph.passages.values():
            e.plan_beats = []

    existing_texts = {b.text.strip().lower() for b in graph.plan.beats}
    acts: list[str] = list(graph.plan.acts)
    questions: list[str] = list(graph.plan.open_questions)
    current_act = ""
    in_questions = False

    def _alloc_id() -> str:
        return _next_beat_id(graph)

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        heading = re.match(r"^#{1,6}\s*(.+)$", line)
        if heading:
            title = heading.group(1).strip()
            low = title.lower()
            in_questions = "open question" in low
            if _ACT_RE.match(line):
                current_act = title
                if title not in acts:
                    acts.append(title)
            elif not in_questions:
                # non-act heading still acts as a grouping label
                current_act = title
            continue
        bullet = _BULLET_RE.match(line)
        if not bullet:
            continue
        content = bullet.group(1).strip()
        if not content or content in ("", "-"):
            continue
        if in_questions:
            if content not in questions:
                questions.append(content)
            continue
        if content.lower() in existing_texts:
            continue
        existing_texts.add(content.lower())
        graph.plan.beats.append(Beat(id=_alloc_id(), text=content, act=current_act))

    graph.plan.acts = acts
    graph.plan.open_questions = questions
    recompute_beat_status(graph)
    save_story(p, graph)
    return plan_overview(p)
