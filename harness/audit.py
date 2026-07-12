"""Durable generation audit log.

Every model generation (and every commit) is written as one JSON file under
``.harness/cache/generations/`` so raw outputs survive a server restart. The
in-memory ring buffer in :mod:`ollama_client` is for live debugging; this is the
recoverable record — useful when a good draft is lost before commit, or when a
local model emits garbage worth inspecting later.

Files are named ``<utc-timestamp>__<kind>__<shortid>.json`` so a lexical sort is
also chronological. The directory is pruned to the most recent ``max_keep``
records on each write to bound disk use. ``.harness/cache/`` is gitignored.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .project import ProjectPaths, _atomic_write_text

DEFAULT_MAX_KEEP = 500


def generations_dir(p: ProjectPaths) -> Path:
    return p.cache_dir / "generations"


def _ts_prefix() -> str:
    # e.g. 20260602T141233_004217 — filesystem-safe, sorts chronologically.
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%f")


def record_generation(
    p: ProjectPaths,
    record: dict,
    *,
    kind: str = "draft",
    max_keep: int = DEFAULT_MAX_KEEP,
) -> str:
    """Persist one generation record. Returns its generation id (filename stem).

    ``kind`` is a short tag (e.g. ``"draft"`` at generate time, ``"commit"`` at
    commit time). Failures are swallowed — audit logging must never break a
    generation or commit.
    """
    try:
        d = generations_dir(p)
        d.mkdir(parents=True, exist_ok=True)
        gen_id = f"{_ts_prefix()}__{kind}__{uuid.uuid4().hex[:8]}"
        payload = {
            "id": gen_id,
            "kind": kind,
            "ts": datetime.now(timezone.utc).isoformat(),
            **record,
        }
        _atomic_write_text(d / f"{gen_id}.json", json.dumps(payload, indent=2, ensure_ascii=False))
        _prune(d, max_keep)
        return gen_id
    except Exception:
        return ""


def _prune(d: Path, max_keep: int) -> None:
    files = sorted(d.glob("*.json"))
    excess = len(files) - max_keep
    for f in files[:max(0, excess)]:
        try:
            f.unlink()
        except OSError:
            pass


def list_generations(p: ProjectPaths, limit: int = 50) -> list[dict]:
    """Return recent generation records (newest first), prose/prompt truncated
    so the index stays cheap to load. Use :func:`read_generation` for full text.
    """
    d = generations_dir(p)
    if not d.exists():
        return []
    out: list[dict] = []
    for f in sorted(d.glob("*.json"), reverse=True)[:max(0, limit)]:
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        raw = rec.get("raw_output") or ""
        out.append({
            "id": rec.get("id", f.stem),
            "kind": rec.get("kind", ""),
            "ts": rec.get("ts", ""),
            "label": rec.get("label", ""),
            "model": rec.get("model", ""),
            "arc_name": rec.get("arc_name", ""),
            "passage_slug": rec.get("passage_slug", ""),
            "passage_id": rec.get("passage_id", ""),
            "parent_passage_id": rec.get("parent_passage_id", ""),
            "warnings": rec.get("warnings", []),
            "raw_preview": raw[:280],
            "raw_chars": len(raw),
        })
    return out


def read_generation(p: ProjectPaths, gen_id: str) -> dict | None:
    """Return the full record for a generation id, or None if not found."""
    # Reject path traversal — gen_id must be a bare stem.
    if not gen_id or "/" in gen_id or "\\" in gen_id or ".." in gen_id:
        return None
    f = generations_dir(p) / f"{gen_id}.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
