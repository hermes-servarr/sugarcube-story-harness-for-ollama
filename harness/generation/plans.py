"""Immutable author-reviewed PassagePlan revisions."""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from pathlib import Path

from ..project import _atomic_write_text
from .contracts import PassagePlan


_PLAN_WRITE_LOCK = threading.RLock()


class PlanStoreError(RuntimeError):
    code = "plan_store_error"


class PlanNotFound(PlanStoreError):
    code = "plan_not_found"


class PlanConflict(PlanStoreError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class PassagePlanStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def latest_revision(self, plan_id: str) -> int | None:
        directory = self._plan_dir(plan_id)
        revisions = [int(path.stem) for path in directory.glob("*.json") if path.stem.isdigit()] \
            if directory.exists() else []
        return max(revisions) if revisions else None

    def put(self, plan: PassagePlan, *, expected_plan_fingerprint: str = "") -> PassagePlan:
        with _PLAN_WRITE_LOCK:
            latest = self.latest_revision(plan.plan_id)
            expected_revision = 1 if latest is None else latest + 1
            if plan.revision != expected_revision:
                raise PlanConflict(
                    "plan_revision_conflict",
                    f"plan revision {plan.revision} is not the next immutable revision {expected_revision}",
                )
            if latest is None:
                if expected_plan_fingerprint:
                    raise PlanConflict("plan_fingerprint_conflict", "new plans cannot expect prior content")
            else:
                current = self.get(plan.plan_id, latest)
                if current.fingerprint() != expected_plan_fingerprint:
                    raise PlanConflict("plan_fingerprint_conflict", "plan changed since it was reviewed")
            envelope = {"plan": plan.model_dump(mode="json"), "fingerprint": plan.fingerprint()}
            _write_immutable(
                self._record_path(plan.plan_id, plan.revision),
                json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            )
            self._write_approval(plan.plan_id, plan.revision, approved=False)
            return plan

    def get(self, plan_id: str, revision: int) -> PassagePlan:
        path = self._record_path(plan_id, revision)
        if not path.exists():
            raise PlanNotFound(f"plan {plan_id} revision {revision} was not found")
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            plan = PassagePlan.model_validate(envelope["plan"])
        except (OSError, KeyError, json.JSONDecodeError, ValueError) as exc:
            raise PlanConflict("plan_corrupt", "immutable plan record is corrupt") from exc
        if plan.plan_id != plan_id or plan.revision != revision:
            raise PlanConflict("plan_identity_mismatch", "plan path and identity differ")
        if envelope.get("fingerprint") != plan.fingerprint():
            raise PlanConflict("plan_fingerprint_mismatch", "stored plan fingerprint differs")
        self._read_approval(plan_id, revision)
        return plan

    def is_approved(self, plan_id: str, revision: int) -> bool:
        self.get(plan_id, revision)
        return self._read_approval(plan_id, revision)["approved"] is True

    def approve(self, plan_id: str, revision: int, *, expected_plan_fingerprint: str) -> PassagePlan:
        with _PLAN_WRITE_LOCK:
            plan = self.get(plan_id, revision)
            if plan.fingerprint() != expected_plan_fingerprint:
                raise PlanConflict("plan_fingerprint_conflict", "plan changed since it was reviewed")
            if self.latest_revision(plan_id) != revision:
                raise PlanConflict("plan_superseded", "a newer immutable plan revision exists")
            self._write_approval(plan_id, revision, approved=True)
            return plan

    def payload(self, plan_id: str, revision: int) -> dict[str, object]:
        plan = self.get(plan_id, revision)
        return {
            "plan": plan.model_dump(mode="json"),
            "fingerprint": plan.fingerprint(),
            "approved": self._read_approval(plan_id, revision)["approved"],
        }

    def _plan_dir(self, plan_id: str) -> Path:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", plan_id):
            raise ValueError("invalid plan id")
        return self.root / plan_id

    def _record_path(self, plan_id: str, revision: int) -> Path:
        if isinstance(revision, bool) or revision < 1:
            raise ValueError("revision must be positive")
        return self._plan_dir(plan_id) / f"{revision}.json"

    def _approval_path(self, plan_id: str, revision: int) -> Path:
        return self._plan_dir(plan_id) / f"{revision}.approval.json"

    def _write_approval(self, plan_id: str, revision: int, *, approved: bool) -> None:
        _atomic_write_text(
            self._approval_path(plan_id, revision),
            json.dumps({"approved": approved}, sort_keys=True, separators=(",", ":")),
        )

    def _read_approval(self, plan_id: str, revision: int) -> dict[str, bool]:
        try:
            value = json.loads(self._approval_path(plan_id, revision).read_text(encoding="utf-8"))
            if set(value) != {"approved"} or not isinstance(value["approved"], bool):
                raise ValueError
            return value
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise PlanConflict("plan_approval_corrupt", "plan approval state is corrupt") from exc


def _write_immutable(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp",
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise PlanConflict("plan_revision_exists", "immutable plan revision already exists") from exc
    finally:
        try:
            os.unlink(temporary)
        except OSError:
            pass


__all__ = ["PassagePlanStore", "PlanConflict", "PlanNotFound", "PlanStoreError"]
