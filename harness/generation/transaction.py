"""Journaled multi-file replacement for typed passage commits."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path

from ..project import _atomic_write_text


FailureInjector = Callable[[str, int, Path], None]


class ProjectTransaction:
    """Stage exact file bytes and recover the previous project on failure."""

    def __init__(self, project_root: Path, journal_root: Path, transaction_id: str | None = None):
        self.project_root = Path(project_root).resolve()
        self.journal_root = Path(journal_root).resolve()
        self.transaction_id = transaction_id or f"txn_{uuid.uuid4().hex}"
        self._writes: dict[Path, bytes] = {}

    def add_text(self, path: Path, value: str) -> None:
        self.add_bytes(path, value.encode("utf-8"))

    def add_bytes(self, path: Path, value: bytes) -> None:
        target = Path(path).resolve()
        try:
            target.relative_to(self.project_root)
        except ValueError as exc:
            raise ValueError("transaction target is outside the project") from exc
        if target in self._writes:
            raise ValueError("duplicate transaction target")
        self._writes[target] = bytes(value)

    def commit(self, failure_injector: FailureInjector | None = None) -> None:
        if not self._writes:
            raise ValueError("transaction contains no writes")
        directory = self.journal_root / self.transaction_id
        directory.mkdir(parents=True, exist_ok=False)
        entries = []
        for index, (target, value) in enumerate(self._writes.items()):
            target.parent.mkdir(parents=True, exist_ok=True)
            staged = directory / f"{index}.staged"
            _write_bytes(staged, value)
            backup_name = ""
            if target.exists():
                backup_name = f"{index}.backup"
                shutil.copyfile(target, directory / backup_name)
            entries.append({
                "target": target.relative_to(self.project_root).as_posix(),
                "staged": staged.name,
                "backup": backup_name,
            })
        journal = {
            "schema_version": 1,
            "transaction_id": self.transaction_id,
            "status": "prepared",
            "entries": entries,
        }
        journal_path = directory / "journal.json"
        _write_journal(journal_path, journal)
        try:
            journal["status"] = "applying"
            _write_journal(journal_path, journal)
            for index, entry in enumerate(entries):
                target = self.project_root / entry["target"]
                if failure_injector:
                    failure_injector("before_replace", index, target)
                os.replace(directory / entry["staged"], target)
                if failure_injector:
                    failure_injector("after_replace", index, target)
            journal["status"] = "committed"
            _write_journal(journal_path, journal)
        except Exception:
            _rollback(self.project_root, directory, journal)
            raise
        shutil.rmtree(directory)

    @staticmethod
    def recover_pending(project_root: Path, journal_root: Path) -> list[str]:
        root = Path(project_root).resolve()
        recovered: list[str] = []
        directory = Path(journal_root)
        if not directory.exists():
            return recovered
        for journal_path in sorted(directory.glob("*/journal.json")):
            transaction_dir = journal_path.parent
            try:
                journal = json.loads(journal_path.read_text(encoding="utf-8"))
                if journal.get("status") == "committed":
                    shutil.rmtree(transaction_dir)
                    continue
                _rollback(root, transaction_dir, journal)
                recovered.append(str(journal.get("transaction_id", transaction_dir.name)))
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                # Preserve an unreadable journal for manual inspection.
                continue
        return recovered


def _rollback(project_root: Path, directory: Path, journal: dict) -> None:
    journal["status"] = "rolling_back"
    _write_journal(directory / "journal.json", journal)
    for entry in reversed(journal["entries"]):
        target = project_root / entry["target"]
        staged_exists = (directory / entry["staged"]).exists()
        if staged_exists:
            continue
        backup = entry.get("backup", "")
        if backup:
            _copy_atomic(directory / backup, target)
        else:
            try:
                target.unlink()
            except FileNotFoundError:
                pass
    journal["status"] = "rolled_back"
    _write_journal(directory / "journal.json", journal)
    shutil.rmtree(directory)


def _write_journal(path: Path, value: dict) -> None:
    _atomic_write_text(path, json.dumps(value, sort_keys=True, separators=(",", ":")))


def _write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except OSError:
            pass


def _copy_atomic(source: Path, target: Path) -> None:
    _write_bytes(target, source.read_bytes())


__all__ = ["ProjectTransaction"]
