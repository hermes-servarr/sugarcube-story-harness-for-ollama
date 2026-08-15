"""Exact persisted-draft commit through a recoverable project transaction."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from ..models import BranchEntry, PassageEntry, Snapshot, StateVariable
from ..project import ProjectPaths, load_slots, load_story
from ..snapshot_delta import diff_snapshots
from .contracts import DraftLifecycle, DraftRecord
from .drafts import DraftConflict, DraftStore
from .transaction import FailureInjector, ProjectTransaction


def parent_fingerprint(p: ProjectPaths, parent_passage_id: str) -> str:
    if not parent_passage_id:
        return ""
    graph = load_story(p)
    entry = graph.passages.get(parent_passage_id)
    if entry is None:
        raise DraftConflict("parent_missing", "parent passage no longer exists")
    path = p.root / entry.file
    if not path.exists():
        raise DraftConflict("parent_file_missing", "parent passage file no longer exists")
    digest = hashlib.sha256()
    digest.update(json.dumps(
        entry.model_dump(mode="json"), sort_keys=True, separators=(",", ":"),
    ).encode("utf-8"))
    digest.update(b"\0")
    digest.update(path.read_bytes())
    return digest.hexdigest()


def commit_typed_draft(
    p: ProjectPaths,
    store: DraftStore,
    *,
    draft_id: str,
    revision: int,
    expected_plan_revision: int,
    expected_draft_fingerprint: str,
    expected_parent_fingerprint: str,
    failure_injector: FailureInjector | None = None,
) -> DraftRecord:
    """Commit the artifact bytes stored with one validated immutable revision."""
    # Lazy import avoids passage -> generation.compiler -> generation package
    # initialization cycling back through this commit service.
    from ..passage import _passage_lock, scan_state_reads, scan_state_writes
    from .compiler import compile_passage_draft

    with _passage_lock(p.root):
        ProjectTransaction.recover_pending(p.root, p.harness_dir / "transactions")
        record = store.get(draft_id, revision)
        if store.latest_revision(draft_id) != revision:
            raise DraftConflict("draft_superseded", "a newer draft revision exists")
        if record.draft.plan.revision != expected_plan_revision:
            raise DraftConflict("plan_revision_conflict", "plan revision differs from reviewed draft")
        if record.lifecycle_state == DraftLifecycle.COMMITTED:
            raise DraftConflict("draft_already_committed", "draft revision is already committed")
        if record.lifecycle_state != DraftLifecycle.VALIDATED:
            raise DraftConflict("draft_not_validated", "draft must be validated before commit")
        if record.draft.fingerprint() != expected_draft_fingerprint:
            raise DraftConflict("draft_fingerprint_conflict", "draft differs from reviewed content")
        if record.compile_artifact is None:
            raise DraftConflict("compile_artifact_missing", "draft has no persisted compile artifact")
        artifact = record.compile_artifact
        if artifact.source_draft_fingerprint != record.draft.fingerprint():
            raise DraftConflict("compile_artifact_mismatch", "compile artifact belongs to another draft")
        reproduced = compile_passage_draft(
            record.draft,
            passage_id=record.passage_id,
            arc_name=record.arc_name,
        )
        if artifact.fingerprint() != reproduced.fingerprint():
            raise DraftConflict(
                "compile_artifact_conflict",
                "persisted compile artifact does not reproduce from the exact draft",
            )
        if expected_parent_fingerprint != record.parent_fingerprint:
            raise DraftConflict("parent_expectation_conflict", "parent expectation differs from draft")
        live_parent_fingerprint = parent_fingerprint(p, record.parent_passage_id)
        if live_parent_fingerprint != record.parent_fingerprint:
            raise DraftConflict("parent_fingerprint_conflict", "parent changed after generation")

        graph = load_story(p)
        if not record.passage_id or not record.arc_name:
            raise DraftConflict("draft_destination_missing", "draft lacks passage destination metadata")
        if record.passage_id in graph.passages:
            raise DraftConflict("passage_exists", "passage id already exists")
        passage_path = p.passage_file(record.arc_name, f"{record.passage_id}.tw")
        used_files = {entry.file for entry in graph.passages.values()}
        relative_passage = passage_path.relative_to(p.root).as_posix()
        if passage_path.exists() or relative_passage in used_files:
            raise DraftConflict("passage_file_exists", "passage file already exists")
        if not re.match(rf"^::\s*{re.escape(record.passage_id)}(?:\s|$)", artifact.twee_source):
            raise DraftConflict("compile_identity_mismatch", "compiled passage header differs")

        parent_snapshot = Snapshot()
        if record.parent_passage_id:
            parent = graph.passages.get(record.parent_passage_id)
            if parent is None:
                raise DraftConflict("parent_missing", "parent passage no longer exists")
            parent_snapshot = parent.snapshot.model_copy(deep=True)
        snapshot = parent_snapshot.model_copy(deep=True)
        state_reads = scan_state_reads(artifact.twee_source)
        state_writes = scan_state_writes(artifact.twee_source)
        for effect in artifact.state_writes:
            key = f"${effect.target}"
            if key not in graph.state_variables:
                value = effect.value
                kind = "bool" if isinstance(value, bool) else "int" if isinstance(value, int) else "str"
                graph.state_variables[key] = StateVariable(
                    type=kind,
                    default=None,
                    declared_in=record.passage_id,
                )

        graph.passages[record.passage_id] = PassageEntry(
            file=relative_passage,
            arc=record.arc_name,
            parents=[record.parent_passage_id] if record.parent_passage_id else [],
            children=[],
            state_writes=state_writes,
            state_reads=state_reads,
            media_slots=list(artifact.media_placeholders),
            summary=record.draft.fill.summary,
            beats=list(record.draft.fill.beats),
            snapshot=snapshot,
            snapshot_delta=diff_snapshots(parent_snapshot, snapshot),
            passage_type=record.draft.plan.passage_mode.value,
        )
        parent_path: Path | None = None
        parent_content = ""
        if record.parent_passage_id:
            parent = graph.passages[record.parent_passage_id]
            if record.passage_id not in parent.children:
                parent.children.append(record.passage_id)
            parent_path = p.root / parent.file
            parent_content = _resolve_parent_link_content(
                parent_path.read_text(encoding="utf-8"),
                record.parent_choice_index,
                record.passage_id,
            )
        if not graph.start_passage:
            graph.start_passage = record.passage_id
        if record.branch_name not in graph.branches:
            graph.branches[record.branch_name] = BranchEntry(
                head=record.passage_id,
                diverges_at=record.parent_passage_id or None,
            )
        else:
            graph.branches[record.branch_name].head = record.passage_id

        slots = load_slots(p)
        unknown_slots = set(artifact.media_placeholders) - set(slots.slots)
        if unknown_slots:
            raise DraftConflict(
                "media_slot_missing",
                f"compiled media slots are not registered: {', '.join(sorted(unknown_slots))}",
            )
        state_path, committed_state = store.prepare_transition(
            draft_id,
            revision,
            expected=DraftLifecycle.VALIDATED,
            target=DraftLifecycle.COMMITTED,
        )
        transaction = ProjectTransaction(p.root, p.harness_dir / "transactions")
        transaction.add_text(passage_path, artifact.twee_source)
        if parent_path is not None and parent_content != parent_path.read_text(encoding="utf-8"):
            transaction.add_text(parent_path, parent_content)
        transaction.add_text(
            p.story_json,
            json.dumps(graph.model_dump(mode="json"), indent=2, ensure_ascii=False),
        )
        transaction.add_text(
            p.slots_json,
            json.dumps(
                {key: value.model_dump(mode="json") for key, value in slots.slots.items()},
                indent=2,
                ensure_ascii=False,
            ),
        )
        transaction.add_text(state_path, committed_state)
        transaction.commit(failure_injector)
        return store.get(draft_id, revision)


def _resolve_parent_link_content(content: str, choice_index: int | None, passage_id: str) -> str:
    wikilinks = list(re.finditer(r"(\[\[[^\|]+\|)(UNRESOLVED_[^\]]+)(\]\])", content))
    quoted = list(re.finditer(r'"(UNRESOLVED_[^"]+)"', content))
    matches = [(match, 2) for match in wikilinks] + [(match, 1) for match in quoted]
    selected = None
    if choice_index is not None:
        prefix = f"UNRESOLVED_choice{choice_index}_"
        selected = next((item for item in matches if item[0].group(item[1]).startswith(prefix)), None)
    selected = selected or (matches[0] if matches else None)
    if selected is None:
        raise DraftConflict("parent_link_missing", "parent has no unresolved link for this draft")
    match, group = selected
    start, end = match.span(group)
    return content[:start] + passage_id + content[end:]


__all__ = ["commit_typed_draft", "parent_fingerprint"]
