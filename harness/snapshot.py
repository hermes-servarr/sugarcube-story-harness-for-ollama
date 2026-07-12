"""Snapshot derivation at commit time."""
from __future__ import annotations

from .models import (
    CharacterDelta,
    CharacterOffscreen,
    CharacterPresent,
    ModelOutput,
    Snapshot,
)
from .project import SNAPSHOT_MAX_THREADS, SNAPSHOT_MAX_WORLD_STATE


def _upsert_present(base: Snapshot, delta: CharacterDelta) -> None:
    """Add or update a character in ``characters_present``.

    Updating only overwrites fields the delta actually carries; ``knows`` is
    merged (deduped), never replaced. A character entering from offscreen is
    removed from ``characters_offscreen``.
    """
    cid = delta.id.strip()
    if not cid:
        return
    for c in base.characters_present:
        if c.id == cid:
            if delta.status:
                c.status = delta.status
            if delta.relationship_to_player:
                c.relationship_to_player = delta.relationship_to_player
            for k in delta.knows:
                k = k.strip()
                if k and k not in c.knows:
                    c.knows.append(k)
            return
    # not currently present — promote from offscreen if listed there
    base.characters_offscreen = [c for c in base.characters_offscreen if c.id != cid]
    knows: list[str] = []
    for k in delta.knows:
        k = k.strip()
        if k and k not in knows:
            knows.append(k)
    base.characters_present.append(CharacterPresent(
        id=cid,
        status=delta.status.strip() or "present",
        knows=knows,
        relationship_to_player=delta.relationship_to_player.strip(),
    ))


def _exit_character(base: Snapshot, delta: CharacterDelta) -> None:
    """Move a character out of the scene into ``characters_offscreen``."""
    cid = delta.id.strip()
    if not cid:
        return
    last_known = (delta.last_known or delta.status or "left the scene").strip()
    base.characters_present = [c for c in base.characters_present if c.id != cid]
    for c in base.characters_offscreen:
        if c.id == cid:
            c.last_known = last_known
            return
    base.characters_offscreen.append(CharacterOffscreen(id=cid, last_known=last_known))


def derive_snapshot(parent: Snapshot | None, output: ModelOutput) -> Snapshot:
    """Merge parent snapshot + model delta into new snapshot."""
    if parent is None:
        base = Snapshot()
    else:
        # deep copy
        base = Snapshot(
            characters_present=[
                CharacterPresent(**c.model_dump()) for c in parent.characters_present
            ],
            characters_offscreen=[
                CharacterOffscreen(**c.model_dump()) for c in parent.characters_offscreen
            ],
            world_state=list(parent.world_state),
            open_threads=list(parent.open_threads),
        )

    # open new threads (deduplicated)
    existing_threads = set(base.open_threads)
    for t in output.threads_open:
        t = t.strip()
        if t and t != "(none)" and t not in existing_threads:
            base.open_threads.append(t)
            existing_threads.add(t)

    # close threads
    to_close = {t.strip() for t in output.threads_close if t.strip() and t.strip() != "(none)"}
    base.open_threads = [t for t in base.open_threads if t not in to_close]

    # cap threads
    if len(base.open_threads) > SNAPSHOT_MAX_THREADS:
        base.open_threads = base.open_threads[:SNAPSHOT_MAX_THREADS]

    # world state add
    existing_ws = set(base.world_state)
    for fact in output.world_state_add:
        fact = fact.strip()
        if fact and fact not in existing_ws:
            base.world_state.append(fact)
            existing_ws.add(fact)

    # world state remove
    to_remove = {f.strip() for f in output.world_state_remove if f.strip()}
    base.world_state = [f for f in base.world_state if f not in to_remove]

    # cap world state
    if len(base.world_state) > SNAPSHOT_MAX_WORLD_STATE:
        base.world_state = base.world_state[:SNAPSHOT_MAX_WORLD_STATE]

    # ── Character presence deltas ────────────────────────────────────────────
    # Order: enter/restate, then status updates (so updates land on present
    # characters), then exits (so a character can enter and leave in one turn).
    for delta in output.characters_present:
        _upsert_present(base, delta)
    for delta in output.character_status:
        _upsert_present(base, delta)
    for delta in output.characters_exit:
        _exit_character(base, delta)

    # inject new characters from new_characters proposals into characters_offscreen
    # (they are offscreen until the prose explicitly puts them in scene)
    present_ids = {c.id for c in base.characters_present}
    offscreen_ids = {c.id for c in base.characters_offscreen}
    for nc in output.new_characters:
        if nc.id not in present_ids and nc.id not in offscreen_ids:
            base.characters_offscreen.append(
                CharacterOffscreen(id=nc.id, last_known="newly introduced")
            )

    return base
