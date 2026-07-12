"""Media slot management — record, resolve, validate, stage, embed.

Resolved media is **not** inlined into the compiled HTML. At compile time every
resolved file is copied into ``build/media/`` (a folder that sits next to
``build/story.html``) and passages reference it by the relative path
``media/<file>``. This keeps the playable game a portable folder: ship
``story.html`` + ``media/`` together and links just work.
"""
from __future__ import annotations
import html
import shutil
from pathlib import Path

from .models import MediaSlot, MediaSlots
from .project import ProjectPaths, load_slots, save_slots


# Folder name placed next to the compiled story.html holding all resolved media.
MEDIA_BUILD_DIRNAME = "media"

# Extensions recognised when listing the project media/ folder, by slot type.
MEDIA_EXTS: dict[str, set[str]] = {
    "image": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif", ".bmp"},
    "audio": {".mp3", ".ogg", ".wav", ".m4a", ".flac", ".aac"},
    "video": {".mp4", ".webm", ".ogv", ".mov", ".m4v"},
}

# Fields a caller may set via set_slot_meta. resolved_path/status go through
# resolve_slot/unresolve_slot so the on-disk existence check is never skipped.
_EDITABLE_META = (
    "description", "alt", "caption", "type",
    "lazy", "loop", "autoplay", "muted", "controls", "poster",
)


def _type_for_ext(ext: str) -> str:
    ext = ext.lower()
    for t, exts in MEDIA_EXTS.items():
        if ext in exts:
            return t
    return "image"


# ── Slot lookup ──────────────────────────────────────────────────────────────

def get_slot(p: ProjectPaths, slot_id: str) -> MediaSlot | None:
    slots = load_slots(p)
    return slots.slots.get(slot_id)


def resolve_slot(p: ProjectPaths, slot_id: str, resolved_path: str) -> tuple[bool, str]:
    """
    Assign resolved_path to a slot. Validates path exists.
    Returns (ok, message).
    """
    slots = load_slots(p)
    slot = slots.slots.get(slot_id)
    if slot is None:
        return False, f"Slot {slot_id!r} not found."

    rp = Path(resolved_path)
    if not rp.is_absolute():
        rp = p.root / rp
    if not rp.exists():
        return False, f"Path {resolved_path!r} does not exist."

    slot.resolved_path = str(rp)
    slot.status = "resolved"
    save_slots(p, slots)
    return True, f"Slot {slot_id!r} resolved to {slot.resolved_path!r}."


def unresolve_slot(p: ProjectPaths, slot_id: str) -> tuple[bool, str]:
    slots = load_slots(p)
    slot = slots.slots.get(slot_id)
    if slot is None:
        return False, f"Slot {slot_id!r} not found."
    slot.resolved_path = None
    slot.status = "pending"
    save_slots(p, slots)
    return True, f"Slot {slot_id!r} set back to pending."


def set_slot_meta(p: ProjectPaths, slot_id: str, **fields) -> tuple[bool, str]:
    """Update description / alt / caption / type / embed options on a slot.

    Unknown keys are ignored; resolved_path and status are intentionally not
    editable here. Returns (ok, message).
    """
    slots = load_slots(p)
    slot = slots.slots.get(slot_id)
    if slot is None:
        return False, f"Slot {slot_id!r} not found."

    changed: list[str] = []
    for key, val in fields.items():
        if key not in _EDITABLE_META or val is None:
            continue
        if key == "type" and val not in MEDIA_EXTS:
            return False, f"Unknown media type {val!r}."
        setattr(slot, key, val)
        changed.append(key)
    if "keywords" in fields and isinstance(fields["keywords"], list):
        slot.keywords = [str(k).strip() for k in fields["keywords"] if str(k).strip()]
        changed.append("keywords")

    save_slots(p, slots)
    return True, f"Updated {', '.join(changed) or 'nothing'} on {slot_id!r}."


def delete_slot(p: ProjectPaths, slot_id: str) -> bool:
    slots = load_slots(p)
    if slot_id in slots.slots:
        del slots.slots[slot_id]
        save_slots(p, slots)
        return True
    return False


# ── Listing / search ───────────────────────────────────────────────────────────

def list_pending_slots(p: ProjectPaths) -> list[tuple[str, MediaSlot]]:
    slots = load_slots(p)
    return [(sid, s) for sid, s in slots.slots.items() if s.status == "pending"]


def list_all_slots(p: ProjectPaths) -> dict[str, MediaSlot]:
    return load_slots(p).slots


def search_slots(p: ProjectPaths, query: str = "", status: str = "") -> dict[str, MediaSlot]:
    """Filter slots by free-text query (keywords/description/caption/passage)
    and/or status. Empty query + empty status returns all slots."""
    q = (query or "").strip().lower()
    out: dict[str, MediaSlot] = {}
    for sid, slot in load_slots(p).slots.items():
        if status and slot.status != status:
            continue
        if q:
            hay = " ".join([
                sid, slot.passage, slot.description, slot.caption, slot.alt,
                " ".join(slot.keywords),
            ]).lower()
            if q not in hay:
                continue
        out[sid] = slot
    return out


def list_media_files(p: ProjectPaths) -> list[dict]:
    """Scan the project media/ folder for usable files the human can resolve to.

    Returns dicts {name, rel_path, type, size} sorted by name. rel_path is
    relative to the project root so it can be passed straight to resolve_slot.
    """
    if not p.media_dir.exists():
        return []
    out: list[dict] = []
    valid = {e for exts in MEDIA_EXTS.values() for e in exts}
    for f in sorted(p.media_dir.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in valid:
            continue
        out.append({
            "name": f.name,
            "rel_path": f.relative_to(p.root).as_posix(),
            "type": _type_for_ext(f.suffix),
            "size": f.stat().st_size,
        })
    return out


def import_media_file(p: ProjectPaths, src_path: str, dest_name: str = "") -> tuple[bool, str]:
    """Copy an external file into the project media/ folder (the human's library).

    Does not move or rename the original. Returns (ok, rel_path_or_error).
    """
    src = Path(src_path)
    if not src.is_absolute():
        src = p.root / src
    if not src.exists() or not src.is_file():
        return False, f"Source {src_path!r} does not exist."
    p.media_dir.mkdir(parents=True, exist_ok=True)
    name = dest_name.strip() or src.name
    dest = _dedupe_path(p.media_dir / name)
    shutil.copy2(src, dest)
    return True, dest.relative_to(p.root).as_posix()


# ── Build staging + embed markup ───────────────────────────────────────────────

def _dedupe_path(target: Path) -> Path:
    """Return target, or target with a numeric suffix if it already exists."""
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    i = 1
    while True:
        cand = target.with_name(f"{stem}_{i}{suffix}")
        if not cand.exists():
            return cand
        i += 1


def _stage_one(src: Path, media_out: Path, used: set[str]) -> str:
    """Copy src into media_out under a collision-free name. Return that name."""
    name = src.name
    if name in used:
        name = _dedupe_path(media_out / name).name
    used.add(name)
    media_out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, media_out / name)
    return name


def stage_media_for_build(p: ProjectPaths, build_dir: Path) -> dict[str, dict[str, str]]:
    """Copy every resolved slot's file (and video poster) into ``build_dir/media``.

    Returns {slot_id: {"src": "media/<file>", "poster": "media/<file>"|""}}.
    The media folder is wiped first so stale files from prior builds don't leak.
    """
    media_out = build_dir / MEDIA_BUILD_DIRNAME
    if media_out.exists():
        shutil.rmtree(media_out)

    rel_map: dict[str, dict[str, str]] = {}
    used: set[str] = set()
    for sid, slot in load_slots(p).slots.items():
        if slot.status != "resolved" or not slot.resolved_path:
            continue
        src = Path(slot.resolved_path)
        if not src.is_absolute():
            src = p.root / src
        if not src.exists():
            continue
        name = _stage_one(src, media_out, used)
        entry = {"src": f"{MEDIA_BUILD_DIRNAME}/{name}", "poster": ""}

        if slot.type == "video" and slot.poster:
            poster = Path(slot.poster)
            if not poster.is_absolute():
                poster = p.root / poster
            if poster.exists():
                pname = _stage_one(poster, media_out, used)
                entry["poster"] = f"{MEDIA_BUILD_DIRNAME}/{pname}"

        rel_map[sid] = entry
    return rel_map


def _av_opts(slot: MediaSlot) -> str:
    """Boolean audio/video attributes as a leading-space string."""
    parts: list[str] = []
    if slot.controls:
        parts.append("controls")
    if slot.loop:
        parts.append("loop")
    if slot.autoplay:
        parts.append("autoplay")
    # Browsers block autoplay with sound; force muted on autoplaying video.
    if slot.muted or (slot.autoplay and slot.type == "video"):
        parts.append("muted")
    return (" " + " ".join(parts)) if parts else ""


def media_markup(slot: MediaSlot, src_rel: str, poster_rel: str = "") -> str:
    """Build the HTML tag for a resolved slot, referencing a relative path.

    Wraps in <figure> with <figcaption> when the slot has a caption.
    """
    alt = html.escape(slot.effective_alt(), quote=True)
    cls = "story-media"
    if slot.type == "image":
        attrs = f'src="{src_rel}" alt="{alt}" class="{cls}"'
        if slot.lazy:
            attrs += ' loading="lazy"'
        media = f"<img {attrs} />"
    elif slot.type == "audio":
        media = f'<audio src="{src_rel}" class="{cls}"{_av_opts(slot)}></audio>'
    elif slot.type == "video":
        poster = f' poster="{poster_rel}"' if poster_rel else ""
        media = f'<video src="{src_rel}" class="{cls}"{poster}{_av_opts(slot)}></video>'
    else:
        return ""

    if slot.caption.strip():
        cap = html.escape(slot.caption.strip())
        return f'<figure class="story-media-fig">{media}<figcaption>{cap}</figcaption></figure>'
    return media
