"""Immutable draft revision persistence with atomic lifecycle pointers."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from ..project import _atomic_write_text
from .contracts import DraftLifecycle, DraftRecord


class DraftStoreError(RuntimeError):
    code = "draft_store_error"


class DraftNotFound(DraftStoreError):
    code = "draft_not_found"


class DraftConflict(DraftStoreError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


_TRANSITIONS = {
    DraftLifecycle.GENERATED: {
        DraftLifecycle.EDITED,
        DraftLifecycle.VALIDATED,
        DraftLifecycle.REJECTED,
    },
    DraftLifecycle.EDITED: {DraftLifecycle.VALIDATED, DraftLifecycle.REJECTED},
    DraftLifecycle.VALIDATED: {DraftLifecycle.COMMITTED, DraftLifecycle.REJECTED},
    DraftLifecycle.COMMITTED: set(),
    DraftLifecycle.REJECTED: set(),
}


class DraftStore:
    """Store immutable JSON records under ``.harness/drafts``."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def put(self, record: DraftRecord) -> DraftRecord:
        draft_id = record.draft.draft_id
        revision = record.draft.revision
        directory = self._draft_dir(draft_id)
        directory.mkdir(parents=True, exist_ok=True)
        latest = self.latest_revision(draft_id)
        expected = 1 if latest is None else latest + 1
        if revision != expected:
            raise DraftConflict(
                "draft_revision_conflict",
                f"draft revision {revision} is not the next immutable revision {expected}",
            )
        if latest is not None:
            previous = self.get(draft_id, latest)
            if (
                previous.draft.plan.plan_id != record.draft.plan.plan_id
                or previous.draft.plan.revision != record.draft.plan.revision
            ):
                raise DraftConflict(
                    "plan_revision_conflict",
                    "draft revisions must retain the same plan revision",
                )
        if record.compile_artifact is not None and (
            record.compile_artifact.source_draft_fingerprint != record.draft.fingerprint()
        ):
            raise DraftConflict(
                "compile_artifact_mismatch",
                "compile artifact does not belong to this draft revision",
            )

        envelope = {
            "record": record.model_dump(mode="json"),
            "fingerprint": record.fingerprint(),
        }
        payload = json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        _write_immutable(self._record_path(draft_id, revision), payload)
        self._write_state(draft_id, revision, record.lifecycle_state, record.fingerprint())
        return record

    def get(self, draft_id: str, revision: int) -> DraftRecord:
        path = self._record_path(draft_id, revision)
        if not path.exists():
            raise DraftNotFound(f"draft {draft_id} revision {revision} was not found")
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            record = DraftRecord.model_validate(envelope["record"])
        except (OSError, KeyError, json.JSONDecodeError, ValueError) as exc:
            raise DraftConflict("draft_corrupt", "draft record is corrupt") from exc
        if record.draft.draft_id != draft_id or record.draft.revision != revision:
            raise DraftConflict("draft_identity_mismatch", "draft path and record identity differ")
        if envelope.get("fingerprint") != record.fingerprint():
            raise DraftConflict("draft_fingerprint_mismatch", "draft record fingerprint differs")
        state = self._read_state(draft_id, revision)
        if state["record_fingerprint"] != record.fingerprint():
            raise DraftConflict("draft_state_mismatch", "draft lifecycle points to other content")
        return record.model_copy(update={"lifecycle_state": DraftLifecycle(state["lifecycle_state"])})

    def latest_revision(self, draft_id: str) -> int | None:
        directory = self._draft_dir(draft_id)
        revisions = [
            int(path.stem)
            for path in directory.glob("*.json")
            if path.stem.isdigit()
        ] if directory.exists() else []
        return max(revisions) if revisions else None

    def latest(self, draft_id: str) -> DraftRecord:
        revision = self.latest_revision(draft_id)
        if revision is None:
            raise DraftNotFound(f"draft {draft_id} was not found")
        return self.get(draft_id, revision)

    def transition(
        self,
        draft_id: str,
        revision: int,
        *,
        expected: DraftLifecycle,
        target: DraftLifecycle,
    ) -> DraftRecord:
        record = self.get(draft_id, revision)
        if record.lifecycle_state != expected:
            raise DraftConflict(
                "draft_lifecycle_conflict",
                f"expected {expected.value}, found {record.lifecycle_state.value}",
            )
        if target not in _TRANSITIONS[expected]:
            raise DraftConflict(
                "draft_lifecycle_transition_invalid",
                f"cannot transition {expected.value} to {target.value}",
            )
        immutable_fingerprint = self._read_state(draft_id, revision)["record_fingerprint"]
        self._write_state(draft_id, revision, target, immutable_fingerprint)
        return record.model_copy(update={"lifecycle_state": target})

    def prepare_transition(
        self,
        draft_id: str,
        revision: int,
        *,
        expected: DraftLifecycle,
        target: DraftLifecycle,
    ) -> tuple[Path, str]:
        """Validate a transition and return its state-file write for a larger transaction."""
        record = self.get(draft_id, revision)
        if record.lifecycle_state != expected:
            raise DraftConflict(
                "draft_lifecycle_conflict",
                f"expected {expected.value}, found {record.lifecycle_state.value}",
            )
        if target not in _TRANSITIONS[expected]:
            raise DraftConflict(
                "draft_lifecycle_transition_invalid",
                f"cannot transition {expected.value} to {target.value}",
            )
        fingerprint = self._read_state(draft_id, revision)["record_fingerprint"]
        return self._state_path(draft_id, revision), json.dumps({
            "lifecycle_state": target.value,
            "record_fingerprint": fingerprint,
        }, sort_keys=True, separators=(",", ":"))

    def _draft_dir(self, draft_id: str) -> Path:
        if not draft_id or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789_" for char in draft_id):
            raise ValueError("invalid draft id")
        return self.root / draft_id

    def _record_path(self, draft_id: str, revision: int) -> Path:
        if isinstance(revision, bool) or revision < 1:
            raise ValueError("revision must be positive")
        return self._draft_dir(draft_id) / f"{revision}.json"

    def _state_path(self, draft_id: str, revision: int) -> Path:
        return self._draft_dir(draft_id) / f"{revision}.state.json"

    def _write_state(
        self,
        draft_id: str,
        revision: int,
        lifecycle: DraftLifecycle,
        fingerprint: str,
    ) -> None:
        _atomic_write_text(
            self._state_path(draft_id, revision),
            json.dumps({
                "lifecycle_state": lifecycle.value,
                "record_fingerprint": fingerprint,
            }, sort_keys=True, separators=(",", ":")),
        )

    def _read_state(self, draft_id: str, revision: int) -> dict[str, str]:
        try:
            data = json.loads(self._state_path(draft_id, revision).read_text(encoding="utf-8"))
            if set(data) != {"lifecycle_state", "record_fingerprint"}:
                raise ValueError
            DraftLifecycle(data["lifecycle_state"])
            return data
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise DraftConflict("draft_state_corrupt", "draft lifecycle state is corrupt") from exc


def _write_immutable(path: Path, payload: str) -> None:
    """Publish complete bytes once; a concurrent/existing revision wins."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise DraftConflict("draft_revision_exists", "draft revision already exists") from exc
    finally:
        try:
            os.unlink(temporary)
        except OSError:
            pass


__all__ = ["DraftConflict", "DraftNotFound", "DraftStore", "DraftStoreError"]
