"""Project initialisation and file-layout management."""
from __future__ import annotations
import json
import os
import re
import tempfile
import uuid
from pathlib import Path

import yaml

from .models import (
    HarnessConfig,
    MediaSlots,
    SessionState,
    StoryGraph,
)

SNAPSHOT_MAX_THREADS = 10
SNAPSHOT_MAX_WORLD_STATE = 20


def _atomic_write_text(path: Path, data: str) -> None:
    """Write text durably: temp file in the same dir, fsync, then os.replace.

    os.replace is atomic on a single filesystem (Windows + POSIX), so a reader
    never sees a half-written file and a crash mid-write leaves the previous
    version intact. Critical for story.json — the single source of truth for the
    whole graph.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _jdump(obj, path: Path) -> None:
    _atomic_write_text(path, json.dumps(obj, indent=2, ensure_ascii=False))


def _jload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ── Paths ──────────────────────────────────────────────────────────────────────

class ProjectPaths:
    def __init__(self, root: Path):
        self.root = root
        self.story_json = root / "story.json"
        self.premise_md = root / "premise.md"
        self.story_points_md = root / "story_points.md"
        self.characters_dir = root / "characters"
        self.lore_dir = root / "lore"
        self.notes_dir = root / "notes"
        self.arcs_dir = root / "arcs"
        self.media_dir = root / "media"
        self.build_dir = root / "build"
        self.harness_dir = root / ".harness"
        self.config_yaml = root / ".harness" / "config.yaml"
        self.cache_dir = root / ".harness" / "cache"
        self.experience_profiles_dir = root / ".harness" / "experience_profiles"
        self.passage_plans_dir = root / ".harness" / "passage_plans"
        self.topology_dir = root / ".harness" / "topology"
        self.simulations_dir = root / ".harness" / "simulations"
        self.systems_json = root / ".harness" / "systems.json"
        self.encounters_json = root / ".harness" / "encounters.json"
        self.simulation_fixtures_json = root / ".harness" / "simulation_fixtures.json"
        self.session_json = root / ".harness" / "session.json"
        self.slots_json = root / "media" / "_slots.json"
        self.inspiration_dir = root / "inspiration"

    def arc_dir(self, arc_name: str) -> Path:
        return self.arcs_dir / arc_name

    def arc_md(self, arc_name: str) -> Path:
        return self.arcs_dir / arc_name / "_arc.md"

    def passage_file(self, arc_name: str, filename: str) -> Path:
        if not filename.endswith(".tw"):
            filename += ".tw"
        return self.arcs_dir / arc_name / filename

    def character_file(self, char_id: str) -> Path:
        return self.characters_dir / f"{char_id}.md"

    def lore_file(self, category: str, lore_id: str) -> Path:
        return self.lore_dir / category / f"{lore_id}.md"

    def note_file(self, note_id: str) -> Path:
        return self.notes_dir / f"{note_id}.md"


# ── Init ───────────────────────────────────────────────────────────────────────

def init_project(root: Path, title: str = "Untitled Story") -> ProjectPaths:
    """Create skeleton layout for a new story project."""
    p = ProjectPaths(root)

    for d in [
        p.characters_dir,
        p.lore_dir / "locations",
        p.lore_dir / "factions",
        p.notes_dir,
        p.arcs_dir,
        p.media_dir,
        p.build_dir,
        p.cache_dir,
        p.inspiration_dir,
    ]:
        d.mkdir(parents=True, exist_ok=True)

    # README for inspiration corpus
    insp_readme = p.inspiration_dir / "README.md"
    if not insp_readme.exists():
        insp_readme.write_text(
            "# Inspiration corpus\n\n"
            "Drop reference material here. The RAG indexer scans this folder and\n"
            "retrieves the most relevant chunks at generate time.\n\n"
            "## Supported file types\n"
            "- `.tw` / `.twee` — raw Twee passages (macros stripped before embed)\n"
            "- `.md` / `.txt` / `.rst` — prose notes, world bibles, etc.\n"
            "- `.json` — parsed SugarCube reports from the html-parser project\n"
            "  (one chunk per passage, media refs preserved)\n"
            "- `.png`/`.jpg`/`.webp`/... — indexed only if a sidecar caption file\n"
            "  exists next to it (`scene.jpg` + `scene.caption.txt`)\n\n"
            "## Rebuild index\n"
            "POST `/api/rag/reindex` from the UI, or call:\n"
            "  `harness rag-reindex`\n\n"
            "Indexed vectors are stored in `.harness/cache/inspiration_index.json`\n"
            "(gitignored). Inspiration files themselves are NOT compiled into your game.\n",
            encoding="utf-8",
        )

    # .gitignore build/
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("build/\n.harness/cache/\n", encoding="utf-8")
    else:
        text = gitignore.read_text(encoding="utf-8")
        lines = set(text.splitlines())
        additions = [l for l in ["build/", ".harness/cache/"] if l not in lines]
        if additions:
            gitignore.write_text(text.rstrip() + "\n" + "\n".join(additions) + "\n", encoding="utf-8")

    # premise.md
    if not p.premise_md.exists():
        p.premise_md.write_text(
            "# Premise\n\n(What is this story about?)\n\n"
            "## Tone\n\n(Dark fantasy / cozy mystery / etc.)\n\n"
            "## Themes\n\n(What the story explores)\n\n"
            "## World Overview\n\n(Setting, geography, history in a few paragraphs)\n\n"
            "## Opening Situation\n\n(Where does the player start, what is happening)\n",
            encoding="utf-8",
        )

    # story_points.md
    if not p.story_points_md.exists():
        p.story_points_md.write_text(
            "# Story Points\n\n"
            "High-level plot beats — not passage prose, just author intent.\n\n"
            "## Act 1\n\n- \n\n"
            "## Act 2\n\n- \n\n"
            "## Act 3\n\n- \n\n"
            "## Open Questions\n\n- \n",
            encoding="utf-8",
        )

    # story.json
    if not p.story_json.exists():
        graph = StoryGraph()
        _jdump(graph.model_dump(), p.story_json)

    # characters/_index.json
    char_index = p.characters_dir / "_index.json"
    if not char_index.exists():
        _jdump([], char_index)

    # lore/_index.json
    lore_index = p.lore_dir / "_index.json"
    if not lore_index.exists():
        _jdump([], lore_index)

    # media/_slots.json
    if not p.slots_json.exists():
        _jdump({}, p.slots_json)

    # .harness/config.yaml — generate stable IFID once so SugarCube save files
    # remain compatible across rebuilds.
    new_config = not p.config_yaml.exists()
    if new_config:
        config = HarnessConfig(
            story_title=title,
            story_ifid=str(uuid.uuid4()).upper(),
        )
        _atomic_write_text(p.config_yaml, yaml.dump(config.model_dump(), allow_unicode=True))

        # New projects make their selected experience an explicit, immutable
        # capability. Existing projects intentionally keep compatibility fallback
        # semantics until an author previews and saves a revision.
        from .generation.experience import ExperienceProfileStore, preset_for_mode
        ExperienceProfileStore(p.experience_profiles_dir).ensure_baseline(
            preset_for_mode(config.experience_mode)
        )

    # .harness/session.json
    if not p.session_json.exists():
        session = SessionState()
        _jdump(session.model_dump(), p.session_json)

    return p


# ── Load / Save ────────────────────────────────────────────────────────────────

def load_story(p: ProjectPaths) -> StoryGraph:
    return StoryGraph.model_validate(_jload(p.story_json))


def save_story(p: ProjectPaths, graph: StoryGraph) -> None:
    _jdump(graph.model_dump(), p.story_json)


def load_config(p: ProjectPaths) -> HarnessConfig:
    if not p.config_yaml.exists():
        return HarnessConfig()
    raw = yaml.safe_load(p.config_yaml.read_text(encoding="utf-8")) or {}
    cfg = HarnessConfig.model_validate(raw)
    # Backfill IFID for projects created before stable-IFID support landed.
    # Persist immediately so subsequent builds reuse the same id.
    if not cfg.story_ifid:
        cfg.story_ifid = str(uuid.uuid4()).upper()
        save_config(p, cfg)
    return cfg


def save_config(p: ProjectPaths, cfg: HarnessConfig) -> None:
    _atomic_write_text(p.config_yaml, yaml.dump(cfg.model_dump(), allow_unicode=True))


def load_session(p: ProjectPaths) -> SessionState:
    if not p.session_json.exists():
        return SessionState()
    return SessionState.model_validate(_jload(p.session_json))


def save_session(p: ProjectPaths, session: SessionState) -> None:
    _jdump(session.model_dump(), p.session_json)


def load_slots(p: ProjectPaths) -> MediaSlots:
    if not p.slots_json.exists():
        return MediaSlots()
    raw = _jload(p.slots_json)
    return MediaSlots(slots=raw)


def save_slots(p: ProjectPaths, slots: MediaSlots) -> None:
    _jdump({k: v.model_dump() for k, v in slots.slots.items()}, p.slots_json)


# ── Arc management ─────────────────────────────────────────────────────────────

def ensure_arc(p: ProjectPaths, arc_name: str) -> Path:
    arc_dir = p.arc_dir(arc_name)
    arc_dir.mkdir(parents=True, exist_ok=True)
    arc_md = p.arc_md(arc_name)
    if not arc_md.exists():
        arc_md.write_text(
            f"# Arc: {arc_name}\n\n## Themes\n\n## Summary\n\n## Open Threads\n",
            encoding="utf-8",
        )
    return arc_dir


# ── Passage ID utilities ───────────────────────────────────────────────────────

def make_passage_id(arc_name: str, slug: str) -> str:
    """arc__NN_slug — double underscore separates arc from passage slug."""
    clean_arc = re.sub(r"[^a-z0-9_]", "_", arc_name.lower())
    clean_slug = re.sub(r"[^a-z0-9_]", "_", slug.lower())
    return f"{clean_arc}__{clean_slug}"


def passage_filename_from_slug(slug: str) -> str:
    clean = re.sub(r"[^a-z0-9_]", "_", slug.lower())
    if not clean.endswith(".tw"):
        clean += ".tw"
    return clean


# ── Entity loading ─────────────────────────────────────────────────────────────

def load_character(p: ProjectPaths, char_id: str) -> str | None:
    f = p.character_file(char_id)
    return f.read_text(encoding="utf-8") if f.exists() else None


def load_lore_entity(p: ProjectPaths, category: str, lore_id: str) -> str | None:
    f = p.lore_file(category, lore_id)
    return f.read_text(encoding="utf-8") if f.exists() else None


def write_character(p: ProjectPaths, char_id: str, prose_sheet: str) -> None:
    f = p.character_file(char_id)
    f.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(f, prose_sheet)
    # update _index.json
    index_path = p.characters_dir / "_index.json"
    index: list = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
    if char_id not in index:
        index.append(char_id)
        _jdump(index, index_path)


def delete_character(p: ProjectPaths, char_id: str) -> bool:
    """Delete a character sheet and remove it from the character index."""
    f = p.character_file(char_id)
    deleted = False
    if f.exists():
        f.unlink()
        deleted = True

    index_path = p.characters_dir / "_index.json"
    if index_path.exists():
        index: list = json.loads(index_path.read_text(encoding="utf-8"))
        cleaned = [cid for cid in index if cid != char_id]
        if cleaned != index:
            _jdump(cleaned, index_path)

    return deleted


def write_lore_entity(p: ProjectPaths, category: str, lore_id: str, prose_sheet: str) -> None:
    f = p.lore_file(category, lore_id)
    f.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(f, prose_sheet)
    index_path = p.lore_dir / "_index.json"
    index: list = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
    entry = f"{category}/{lore_id}"
    if entry not in index:
        index.append(entry)
        _jdump(index, index_path)


# ── Character listing ──────────────────────────────────────────────────────────

def parse_yaml_frontmatter(text: str) -> tuple[dict, str]:
    """Split YAML frontmatter from body. Returns (meta, body)."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1]) or {}
            except Exception:
                meta = {}
            return meta, parts[2].strip()
    return {}, text.strip()


def _emit_frontmatter(meta: dict, body: str) -> str:
    """Re-emit a sheet with frontmatter + body. Preserves trailing newline."""
    if not meta:
        return body.rstrip() + "\n"
    fm = yaml.dump(meta, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{fm}\n---\n{body.rstrip()}\n"


def set_character_keywords(p: ProjectPaths, char_id: str, keywords: list[str]) -> bool:
    """Persist keywords into the character sheet's YAML frontmatter."""
    f = p.character_file(char_id)
    if not f.exists():
        return False
    meta, body = parse_yaml_frontmatter(f.read_text(encoding="utf-8"))
    meta["keywords"] = list(keywords)
    f.write_text(_emit_frontmatter(meta, body), encoding="utf-8")
    return True


def set_lore_keywords(p: ProjectPaths, category: str, lore_id: str, keywords: list[str]) -> bool:
    """Persist keywords into the lore sheet's YAML frontmatter."""
    f = p.lore_file(category, lore_id)
    if not f.exists():
        return False
    meta, body = parse_yaml_frontmatter(f.read_text(encoding="utf-8"))
    meta["keywords"] = list(keywords)
    f.write_text(_emit_frontmatter(meta, body), encoding="utf-8")
    return True


def list_characters(p: ProjectPaths) -> list[dict]:
    """Return list of {id, name, tags, summary} for all characters."""
    results = []
    index_path = p.characters_dir / "_index.json"
    ids: list = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
    # also scan disk for any not in index
    for f in sorted(p.characters_dir.glob("*.md")):
        cid = f.stem
        if cid not in ids:
            ids.append(cid)
    for cid in ids:
        f = p.character_file(cid)
        if not f.exists():
            continue
        meta, body = parse_yaml_frontmatter(f.read_text(encoding="utf-8"))
        # first non-blank line of body as summary
        summary = next((l.lstrip("#").strip() for l in body.splitlines() if l.strip()), "")
        results.append({
            "id": cid,
            "name": meta.get("name", cid),
            "tags": meta.get("tags", []),
            "keywords": meta.get("keywords", []),
            "summary": summary[:120],
        })
    return results


def list_lore(p: ProjectPaths) -> list[dict]:
    """Return list of {category, id, title, summary} for all lore entries."""
    results = []
    for md_file in sorted(p.lore_dir.rglob("*.md")):
        if md_file.name.startswith("_"):
            continue
        category = md_file.parent.name if md_file.parent != p.lore_dir else "misc"
        lore_id = md_file.stem
        meta, body = parse_yaml_frontmatter(md_file.read_text(encoding="utf-8"))
        summary = next((l.lstrip("#").strip() for l in body.splitlines() if l.strip()), "")
        results.append({
            "category": category,
            "id": lore_id,
            "title": meta.get("title", lore_id),
            "keywords": meta.get("keywords", []),
            "summary": summary[:120],
        })
    return results


# ── Notes CRUD ─────────────────────────────────────────────────────────────────

def list_notes(p: ProjectPaths) -> list[dict]:
    """Return list of {id, title, preview} for all notes."""
    results = []
    p.notes_dir.mkdir(parents=True, exist_ok=True)
    for f in sorted(p.notes_dir.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        title = next((l.lstrip("#").strip() for l in text.splitlines() if l.strip()), f.stem)
        preview = " ".join(text.splitlines()[:3])[:160]
        results.append({"id": f.stem, "title": title, "preview": preview})
    return results


def load_note(p: ProjectPaths, note_id: str) -> str | None:
    f = p.note_file(note_id)
    return f.read_text(encoding="utf-8") if f.exists() else None


def save_note(p: ProjectPaths, note_id: str, content: str) -> None:
    p.notes_dir.mkdir(parents=True, exist_ok=True)
    p.note_file(note_id).write_text(content, encoding="utf-8")


def delete_note(p: ProjectPaths, note_id: str) -> bool:
    f = p.note_file(note_id)
    if f.exists():
        f.unlink()
        return True
    return False
