"""Snapshot deltas: compute and apply incremental changes between snapshots.

Each story generation step records only what changed from the previous
snapshot, rather than a full copy. This keeps story.json lean for long
branching narratives with many passages.

Delta format::

    {
        "characters_present": {
            "added":   [{... CharacterPresent ...}],
            "modified": {"<id>": {<field>: <new_val>, ...}},
            "removed": ["<id>", ...],
        },
        "characters_offscreen": {
            "added":   [{... CharacterOffscreen ...}],
            "modified": {"<id>": {"last_known": "..."}},
            "removed": ["<id>", ...],
        },
        "world_state": {
            "added":   ["fact", ...],
            "removed": ["fact", ...],
        },
        "open_threads": {
            "added":   ["thread", ...],
            "removed": ["thread", ...],
        },
    }

``world_state`` and ``open_threads`` are lists of strings with no inner
structure, so a delta on those is just added/removed sets. Lists modified
in place (insertions, removals) are represented as add/remove pairs.
"""
from __future__ import annotations

from typing import Any

from .models import (
    CharacterOffscreen,
    CharacterPresent,
    CharacterSectionDelta,
    ListSectionDelta,
    Snapshot,
    SnapshotDelta,
)


# ── Diff ──────────────────────────────────────────────────────────────────────

def _diff_character_present(
    old: list[CharacterPresent],
    new: list[CharacterPresent],
) -> CharacterSectionDelta:
    old_map = {c.id: c for c in old}
    new_map = {c.id: c for c in new}

    added: list[dict[str, Any]] = []
    modified: dict[str, dict[str, Any]] = {}
    removed: list[str] = []

    for cid, c in new_map.items():
        if cid not in old_map:
            added.append(c.model_dump())
        else:
            oc = old_map[cid]
            changes: dict[str, Any] = {}
            if c.status != oc.status:
                changes["status"] = c.status
            if c.knows != oc.knows:
                changes["knows"] = list(c.knows)
            if c.relationship_to_player != oc.relationship_to_player:
                changes["relationship_to_player"] = c.relationship_to_player
            if changes:
                modified[cid] = changes

    for cid in old_map:
        if cid not in new_map:
            removed.append(cid)

    return CharacterSectionDelta(added=added, modified=modified, removed=removed)


def _diff_character_offscreen(
    old: list[CharacterOffscreen],
    new: list[CharacterOffscreen],
) -> CharacterSectionDelta:
    old_map = {c.id: c for c in old}
    new_map = {c.id: c for c in new}

    added: list[dict[str, Any]] = []
    modified: dict[str, dict[str, Any]] = {}
    removed: list[str] = []

    for cid, c in new_map.items():
        if cid not in old_map:
            added.append(c.model_dump())
        else:
            oc = old_map[cid]
            if c.last_known != oc.last_known:
                modified[cid] = {"last_known": c.last_known}

    for cid in old_map:
        if cid not in new_map:
            removed.append(cid)

    return CharacterSectionDelta(added=added, modified=modified, removed=removed)


def _diff_list(old: list[str], new: list[str]) -> ListSectionDelta:
    old_set = set(old)
    new_set = set(new)
    added = [item for item in new if item not in old_set]
    removed = [item for item in old if item not in new_set]
    return ListSectionDelta(added=added, removed=removed)


def diff_snapshots(old: Snapshot, new: Snapshot) -> SnapshotDelta:
    """Compute the delta between two full snapshots.

    Returns a :class:`SnapshotDelta` that, when applied to *old*, produces
    a snapshot equal to *new*.
    """
    return SnapshotDelta(
        characters_present=_diff_character_present(
            old.characters_present, new.characters_present,
        ),
        characters_offscreen=_diff_character_offscreen(
            old.characters_offscreen, new.characters_offscreen,
        ),
        world_state=_diff_list(old.world_state, new.world_state),
        open_threads=_diff_list(old.open_threads, new.open_threads),
    )


# ── Apply ─────────────────────────────────────────────────────────────────────

def _apply_character_section(
    base_present: list[CharacterPresent],
    base_offscreen: list[CharacterOffscreen],
    delta: CharacterSectionDelta,
    *,
    is_present: bool,
) -> tuple[list[CharacterPresent], list[CharacterOffscreen]]:
    """Apply a character section delta, handling present <-> offscreen moves.

    When *is_present* is True, the delta operates on the present list and
    removals move characters to offscreen (last_known = "" since the delta
    does not carry that info for removals). When False, the delta operates
    on the offscreen list and removals simply drop the character.

    Returns the (present, offscreen) tuple.
    """
    if is_present:
        present = list(base_present)
        offscreen = list(base_offscreen)
        present_map = {c.id: c for c in present}
        offscreen_map = {c.id: c for c in offscreen}

        # removals -> move to offscreen
        for cid in delta.removed:
            if cid in present_map:
                c = present_map.pop(cid)
                present = [ch for ch in present if ch.id != cid]
                if cid not in offscreen_map:
                    offscreen.append(CharacterOffscreen(
                        id=cid, last_known="",
                    ))
                    offscreen_map[cid] = offscreen[-1]

        # modifications
        for cid, changes in delta.modified.items():
            if cid in present_map:
                c = present_map[cid]
                if "status" in changes:
                    c.status = changes["status"]
                if "knows" in changes:
                    c.knows = list(changes["knows"])
                if "relationship_to_player" in changes:
                    c.relationship_to_player = changes["relationship_to_player"]

        # additions
        for entry in delta.added:
            cid = entry.get("id", "")
            if not cid:
                continue
            # remove from offscreen if present there
            offscreen = [c for c in offscreen if c.id != cid]
            if cid not in present_map:
                cp = CharacterPresent(
                    id=cid,
                    status=entry.get("status", "present"),
                    knows=list(entry.get("knows", [])),
                    relationship_to_player=entry.get("relationship_to_player", ""),
                )
                present.append(cp)
                present_map[cid] = cp

        return present, offscreen

    else:
        present = list(base_present)
        offscreen = list(base_offscreen)
        offscreen_map = {c.id: c for c in offscreen}

        # removals -> just drop
        for cid in delta.removed:
            offscreen = [c for c in offscreen if c.id != cid]
            offscreen_map.pop(cid, None)

        # modifications
        for cid, changes in delta.modified.items():
            if cid in offscreen_map:
                c = offscreen_map[cid]
                if "last_known" in changes:
                    c.last_known = changes["last_known"]

        # additions
        for entry in delta.added:
            cid = entry.get("id", "")
            if not cid:
                continue
            if cid not in offscreen_map:
                co = CharacterOffscreen(
                    id=cid,
                    last_known=entry.get("last_known", ""),
                )
                offscreen.append(co)
                offscreen_map[cid] = co

        return present, offscreen


def apply_delta(base: Snapshot, delta: SnapshotDelta) -> Snapshot:
    """Reconstruct a full snapshot from a base + one delta.

    Returns a new :class:`Snapshot`; *base* is not mutated.
    """
    # Deep-copy base to avoid mutation
    present = [CharacterPresent(**c.model_dump()) for c in base.characters_present]
    offscreen = [CharacterOffscreen(**c.model_dump()) for c in base.characters_offscreen]
    world_state = list(base.world_state)
    open_threads = list(base.open_threads)

    # Character present delta
    present, offscreen = _apply_character_section(
        present, offscreen, delta.characters_present, is_present=True,
    )

    # Character offscreen delta
    present, offscreen = _apply_character_section(
        present, offscreen, delta.characters_offscreen, is_present=False,
    )

    # world_state
    existing_ws = set(world_state)
    for fact in delta.world_state.added:
        if fact not in existing_ws:
            world_state.append(fact)
            existing_ws.add(fact)
    rm_ws = set(delta.world_state.removed)
    world_state = [f for f in world_state if f not in rm_ws]

    # open_threads
    existing_t = set(open_threads)
    for t in delta.open_threads.added:
        if t not in existing_t:
            open_threads.append(t)
            existing_t.add(t)
    rm_t = set(delta.open_threads.removed)
    open_threads = [t for t in open_threads if t not in rm_t]

    return Snapshot(
        characters_present=present,
        characters_offscreen=offscreen,
        world_state=world_state,
        open_threads=open_threads,
    )


def apply_deltas(base: Snapshot, deltas: list[SnapshotDelta]) -> Snapshot:
    """Apply a sequence of deltas to a base snapshot.

    Equivalent to folding ``apply_delta`` over *deltas* starting from *base*.
    """
    snap = base
    for d in deltas:
        snap = apply_delta(snap, d)
    return snap


# ── Reconstruction from passage chain ──────────────────────────────────────────

def reconstruct_snapshot_from_deltas(
    base: Snapshot | None,
    deltas: list[SnapshotDelta],
) -> Snapshot:
    """Reconstruct a snapshot from a base (parent) + ordered deltas.

    If *base* is None, an empty Snapshot is used (root passage case).
    """
    if base is None:
        base = Snapshot()
    return apply_deltas(base, deltas)


def is_empty_delta(delta: SnapshotDelta) -> bool:
    """True when the delta carries no changes."""
    return (
        not delta.characters_present.added
        and not delta.characters_present.modified
        and not delta.characters_present.removed
        and not delta.characters_offscreen.added
        and not delta.characters_offscreen.modified
        and not delta.characters_offscreen.removed
        and not delta.world_state.added
        and not delta.world_state.removed
        and not delta.open_threads.added
        and not delta.open_threads.removed
    )
