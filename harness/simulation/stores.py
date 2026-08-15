"""Immutable persistence for authored topologies and runtime session revisions."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from .contracts import RuntimeSession, SimulationRecord, WorldTopology


_STORE_WRITE_LOCK = threading.RLock()


class SimulationStoreError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class TopologyStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def latest_revision(self) -> int | None:
        return _latest_revision(self.root)

    def get(self, revision: int | None = None) -> WorldTopology:
        target = self.latest_revision() if revision is None else revision
        if target is None:
            raise SimulationStoreError("topology_not_found", "no topology has been authored")
        topology = _read_envelope(self.root / f"{target}.json", "topology", WorldTopology)
        if topology.revision != target:
            raise SimulationStoreError("topology_identity_mismatch", "topology path and revision differ")
        return topology

    def by_fingerprint(self, fingerprint: str) -> WorldTopology:
        for revision in sorted(_revisions(self.root), reverse=True):
            topology = self.get(revision)
            if topology.fingerprint() == fingerprint:
                return topology
        raise SimulationStoreError(
            "topology_revision_not_found", "the session topology revision is unavailable"
        )

    def put(self, topology: WorldTopology, *, expected_revision: int) -> WorldTopology:
        with _STORE_WRITE_LOCK:
            latest = self.latest_revision() or 0
            if latest != expected_revision:
                raise SimulationStoreError(
                    "topology_revision_conflict",
                    f"expected topology revision {expected_revision}, found {latest}",
                )
            if topology.revision != expected_revision + 1:
                raise SimulationStoreError(
                    "topology_revision_invalid",
                    f"candidate topology revision must be {expected_revision + 1}",
                )
            _write_envelope(self.root / f"{topology.revision}.json", "topology", topology)
            return topology


class RuntimeSessionStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def latest_revision(self, session_id: str) -> int | None:
        return _latest_revision(self._session_dir(session_id))

    def get(self, session_id: str, revision: int | None = None) -> SimulationRecord:
        target = self.latest_revision(session_id) if revision is None else revision
        if target is None:
            raise SimulationStoreError("simulation_not_found", "simulation was not found")
        record = _read_envelope(
            self._session_dir(session_id) / f"{target}.json", "record", SimulationRecord
        )
        if record.session.session_id != session_id or record.session.revision != target:
            raise SimulationStoreError(
                "simulation_identity_mismatch", "simulation path and session identity differ"
            )
        return record

    def put(self, record: SimulationRecord, *, expected_revision: int) -> SimulationRecord:
        with _STORE_WRITE_LOCK:
            session = record.session
            latest = self.latest_revision(session.session_id) or 0
            if latest != expected_revision:
                raise SimulationStoreError(
                    "simulation_revision_conflict",
                    f"expected simulation revision {expected_revision}, found {latest}",
                )
            if session.revision != expected_revision + 1:
                raise SimulationStoreError(
                    "simulation_revision_invalid",
                    f"candidate simulation revision must be {expected_revision + 1}",
                )
            _write_envelope(
                self._session_dir(session.session_id) / f"{session.revision}.json",
                "record",
                record,
            )
            return record

    def _session_dir(self, session_id: str) -> Path:
        import re
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", session_id):
            raise ValueError("invalid simulation session id")
        return self.root / session_id


ModelT = TypeVar("ModelT", bound=BaseModel)


def _read_envelope(path: Path, key: str, model: type[ModelT]) -> ModelT:
    if not path.exists():
        raise SimulationStoreError("revision_not_found", "immutable revision was not found")
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        raw_value = envelope[key]
        value = model.model_validate(raw_value)
    except (OSError, KeyError, json.JSONDecodeError, ValueError) as exc:
        raise SimulationStoreError("revision_corrupt", "immutable revision is corrupt") from exc
    stored_fingerprint = envelope.get("fingerprint")
    raw_fingerprint = hashlib.sha256(json.dumps(
        raw_value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    if stored_fingerprint not in {value.fingerprint(), raw_fingerprint}:
        raise SimulationStoreError("revision_fingerprint_mismatch", "revision fingerprint differs")
    return value


def _write_envelope(path: Path, key: str, value: BaseModel) -> None:
    envelope = {
        key: value.model_dump(mode="json"),
        "fingerprint": value.fingerprint(),
    }
    payload = json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise SimulationStoreError("revision_exists", "immutable revision already exists") from exc
    finally:
        try:
            os.unlink(temporary)
        except OSError:
            pass


def _revisions(root: Path) -> list[int]:
    return [int(path.stem) for path in root.glob("*.json") if path.stem.isdigit()] if root.exists() else []


def _latest_revision(root: Path) -> int | None:
    revisions = _revisions(root)
    return max(revisions) if revisions else None


__all__ = ["RuntimeSessionStore", "SimulationStoreError", "TopologyStore"]
