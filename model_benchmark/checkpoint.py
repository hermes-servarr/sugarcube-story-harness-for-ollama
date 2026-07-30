"""Checkpoint state, persistence, and signal handlers for the model benchmark.

This module is the **home** of the :class:`CheckpointState` data structure
per ``p2_data_structures.md`` §3.6 (module-home table §1) and now also provides
the Phase-7 **behaviour**: atomic save/load, resume support, and
SIGINT/SIGTERM signal handlers that trigger a graceful checkpoint before
exit.

Re-export of the frozen dataclass
---------------------------------
The :class:`CheckpointState` frozen dataclass itself is defined centrally in
:mod:`model_benchmark.schema` (alongside the other new types) to avoid
circular imports.  This module re-exports it so callers can import it from
its logical home::

    from model_benchmark.checkpoint import CheckpointState

The re-export preserves class identity (``checkpoint.CheckpointState is
schema.CheckpointState``), so any code that constructs or pattern-matches on
the dataclass keeps working regardless of which module it imported from.

Public API (Phase 7 behaviour)
-------------------------------
- :class:`CheckpointManager` — mutable manager that tracks iteration/step
  progress, model config, and partial results, and provides ``save()`` /
  ``load()`` / ``resume()`` plus SIGINT/SIGTERM signal handlers registered
  via a context manager (``with CheckpointManager(...) as ck:``) or explicit
  ``start()`` / ``stop()``.
- :func:`save_checkpoint` — atomic persistence of a :class:`CheckpointState`
  to ``checkpoint.json`` (reuses :func:`model_benchmark.persistence.write_json`).
- :func:`load_checkpoint` — load a :class:`CheckpointState` from disk; return
  ``None`` if absent.

Design constraints (from P1 §4.4 / P6 INV-A3 / INV-A4)
------------------------------------------------------
- **Atomic writes.**  ``save()`` / ``save_checkpoint()`` delegate to
  :func:`model_benchmark.persistence.write_json`, which writes a temp file
  in the *same directory* as the target and swaps it into place with
  :func:`os.replace` (POSIX-atomic).  On crash the destination is either the
  previous complete file or the new complete file — never a partial write
  (INV-A3).  A leftover ``.tmp`` file is the only debris.
- **Resume.**  ``resume()`` / ``load_checkpoint()`` read an existing
  ``checkpoint.json`` and restore the ``completed_ids`` set so already-
  finalised cases are skipped on the next run (INV-A4) unless ``force_rerun``
  is set.
- **Signal handlers.**  SIGINT (Ctrl-C) and SIGTERM both trigger a final
  ``save()`` before the process exits with the same exit code the default
  handler would have produced (``128 + signum``).  Handlers are installed
  only while the manager is *active* (inside the ``with`` block or between
  ``start()`` / ``stop()``) and the previous handlers are restored on
  ``stop()``, so the manager is safe to nest and to use from code that has
  its own signal handling.
- **stdlib only.**  No new dependencies (``signal``, ``json``, ``os``,
  ``sys``, ``dataclasses``, ``datetime``, ``pathlib``).
- **No harness imports.**  This module does not import from ``harness`` or
  modify it (INV-5).

Serialization format
--------------------
The on-disk ``checkpoint.json`` is a JSON object with the five
:class:`CheckpointState` fields::

    {
      "run_id": "...",
      "completed_ids": ["test_id_a", "test_id_b"],
      "total_cases": 12,
      "last_saved_at": "2026-07-30T01:00:00+00:00",
      "provenance": [["test_id_a", "new"], ["test_id_b", "resumed"]]
    }

``completed_ids`` and ``provenance`` are tuples on the dataclass but lists
of strings / 2-element lists in JSON (tuples have no JSON representation).
``load_checkpoint`` converts them back to tuples.  Extra top-level keys are
tolerated (forward-compatible) but unknown values in ``provenance`` fall
back to ``"new"``.
"""
from __future__ import annotations

import json
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Re-exported types (home module) ──────────────────────────────────────
# The frozen dataclass is defined in schema.py to keep a single type registry
# and avoid circular imports.  Re-export eagerly — it is a cheap, dependency-
# free frozen dataclass + Literal alias.  ``is`` identity is preserved.
from model_benchmark.schema import CheckpointState, ResultProvenance

# ── Atomic write utility (reused per task brief) ────────────────────────
# persistence.write_json serialises dataclasses via dataclasses.asdict
# (tuples -> lists) and writes via tmpfile + os.replace (INV-A3).
from model_benchmark.persistence import write_json

__all__ = [
    "CheckpointState",
    "ResultProvenance",
    "CheckpointManager",
    "save_checkpoint",
    "load_checkpoint",
]

# ═══════════════════════════════════════════════════════════════════════════
# §3.6  CheckpointState  — field reference (definition lives in schema.py)
# ═══════════════════════════════════════════════════════════════════════════
#
# The authoritative definition is in ``model_benchmark/schema.py``.  It is
# reproduced here as a field reference so this home module documents the
# structure without duplicating the ``@dataclass`` definition (which would
# create a second, incompatible class identity).
#
#   @dataclass(frozen=True)
#   class CheckpointState:
#       run_id: str
#       completed_ids: tuple[str, ...]
#       total_cases: int
#       last_saved_at: str
#       provenance: tuple[tuple[str, ResultProvenance], ...]
#
# Field-by-field spec compliance (p2_data_structures.md §3.6):
#   run_id        : str           — unique run identifier (§3)
#   completed_ids : tuple[str,...] — finalized result IDs to skip on resume (§3)
#   total_cases   : int           — total cases in the full run (§3)
#   last_saved_at : str           — ISO 8601 timestamp of last checkpoint write (§3)
#   provenance    : tuple[tuple[str, ResultProvenance], ...]
#                                 — per-result (test_id, provenance) pairs (§3)
#
# Design notes:
#   - Frozen dataclass -> immutable; updates via dataclasses.replace or via
#     the mutable CheckpointManager wrapper provided below.
#   - provenance is tuple-of-pairs (not dict) because frozen dataclasses
#     cannot hold a mutable dict default; JSON serializes as a list of
#     2-element lists; load converts back.
#   - ResultProvenance = Literal["new", "resumed", "retried", "recovered"]
#     (§3.4, defined in schema.py).


# ═══════════════════════════════════════════════════════════════════════════
# Serialization helpers
# ═══════════════════════════════════════════════════════════════════════════

#: The set of valid provenance strings (mirrors ``ResultProvenance`` Literal).
_VALID_PROVENANCE: frozenset[str] = frozenset(
    {"new", "resumed", "retried", "recovered"}
)


def _now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string (timezone-aware)."""
    return datetime.now(timezone.utc).isoformat()


def _checkpoint_to_dict(state: CheckpointState) -> dict[str, Any]:
    """Serialize a :class:`CheckpointState` to a plain JSON-able dict.

    Tuples are converted to lists (JSON has no tuple type) so the result is
    directly serialisable by :func:`json.dumps`.  The five keys match the
    dataclass fields exactly.
    """
    return {
        "run_id": state.run_id,
        "completed_ids": list(state.completed_ids),
        "total_cases": state.total_cases,
        "last_saved_at": state.last_saved_at,
        "provenance": [
            [test_id, prov] for test_id, prov in state.provenance
        ],
    }


def _checkpoint_from_dict(d: dict[str, Any]) -> CheckpointState:
    """Deserialize a :class:`CheckpointState` from a plain dict.

    Tolerates: missing keys (defaults applied), extra keys (ignored for
    forward-compat), and ``provenance`` entries that are not 2-element lists
    or whose second element is not a valid provenance string (fall back to
    ``"new"``).  ``completed_ids``/``provenance`` are returned as tuples to
    satisfy the frozen-dataclass field types.
    """
    completed_ids = tuple(d.get("completed_ids", ()))
    raw_provenance = d.get("provenance", ())
    provenance: list[tuple[str, str]] = []
    for entry in raw_provenance:
        # Each entry should be [test_id, provenance_string].
        if isinstance(entry, (list, tuple)) and len(entry) >= 2:
            test_id = str(entry[0])
            prov = str(entry[1])
            if prov not in _VALID_PROVENANCE:
                prov = "new"
            provenance.append((test_id, prov))
        elif isinstance(entry, (list, tuple)) and len(entry) == 1:
            provenance.append((str(entry[0]), "new"))
        # Malformed entries are silently skipped (defensive).
    return CheckpointState(
        run_id=str(d.get("run_id", "")),
        completed_ids=completed_ids,
        total_cases=int(d.get("total_cases", 0)),
        last_saved_at=str(d.get("last_saved_at", "")),
        provenance=tuple(provenance),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Module-level save / load (operate on the frozen CheckpointState)
# ═══════════════════════════════════════════════════════════════════════════
#
# ── P4 DEVIATION NOTE (checkpoint.py) ──────────────────────────────────
# Phase 4's contract is "TODO markers at modification sites; no
# implementation."  This module violates that contract: it contains live
# P7-level implementations of save_checkpoint and load_checkpoint (the
# CheckpointManager class and its signal handlers) alongside the TODO
# markers.  The implementations predate this P4 pass — they were written
# in an earlier run that did full implementation during P4.
#
# Two P3 signature divergences exist in the live code:
#
#   DEV-C1  save_checkpoint
#     P3 §3.4 signature:  save_checkpoint(state: CheckpointState, path: str) -> None
#     Current signature:   save_checkpoint(state: CheckpointState, path: str | os.PathLike[str]) -> Path
#     Divergence: returns the resolved Path on success; P3 says -> None.
#     Resolution: P7 must change the return to None (or P3 must be amended
#     to accept -> Path).  The path-accepting os.PathLike[str] widening is
#     backward-compatible and need not change.
#
#   DEV-C2  load_checkpoint
#     P3 §3.4 signature:  load_checkpoint(path: str) -> CheckpointState
#     Current signature:   load_checkpoint(path: str | os.PathLike[str]) -> CheckpointState | None
#     Divergence: returns None for absent/corrupt files; P3 §3.4 returns an
#     empty CheckpointState (run_id="", completed_ids=(), total_cases=0,
#     last_saved_at="", provenance=()) instead — never None.
#     Resolution: P7 must return an empty CheckpointState instead of None
#     (or P3 must be amended to allow Optional).  Callers in runner.py
#     currently handle the None case; that must be updated in P7 too.
#
# These deviations are flagged here for the P5 deviation report and P7
# implementation.  They do NOT affect the P4 TODO markers — the markers
# correctly identify the modification sites and reference the P3 signatures.
# ── End P4 DEVIATION NOTE ──────────────────────────────────────────────


# TODO(benchmark-upgrade): checkpoint.py — implement save_checkpoint per
# P3 §3.4. Signature: save_checkpoint(state: CheckpointState, path: str) -> None.
# Atomically persist a CheckpointState to a JSON file (tmpfile + os.replace);
# never leaves a partial file. Current impl delegates to
# persistence.write_json (tmpfile + os.replace, INV-A3).
# DEVIATION DEV-C1: current impl returns Path, P3 says -> None. See P4
# deviation note above; reconcile in P7.
def save_checkpoint(state: CheckpointState, path: str | os.PathLike[str]) -> Path:
    """Atomically write ``state`` as JSON to ``path``.

    Delegates to :func:`model_benchmark.persistence.write_json` (tmpfile +
    :func:`os.replace`, INV-A3).  Parent directories are created if missing.

    Parameters
    ----------
    state
        The :class:`CheckpointState` to persist.
    path
        Destination file path (convention: ``checkpoint.json`` in the run dir).

    Returns
    -------
    pathlib.Path
        The resolved destination path on success.
    """
    target = Path(path)
    return write_json(target, _checkpoint_to_dict(state), indent=2)


# TODO(benchmark-upgrade): checkpoint.py — implement load_checkpoint per
# P3 §3.4. Signature: load_checkpoint(path: str) -> CheckpointState. Load a
# CheckpointState from a JSON file, returning an empty state if the file is
# absent or corrupt (never raises).
# DEVIATION DEV-C2: current impl returns CheckpointState | None (None for
# absent); P3 §3.4 returns an empty CheckpointState instead. See P4
# deviation note above; reconcile in P7.
def load_checkpoint(path: str | os.PathLike[str]) -> CheckpointState | None:
    """Load a :class:`CheckpointState` from ``path``; return ``None`` if absent.

    If the file exists but is empty or contains invalid JSON, returns
    ``None`` (a corrupt/empty checkpoint is treated as "no checkpoint" so
    the run starts fresh rather than crashing — consistent with the
    fault-tolerance goal of §3).

    Parameters
    ----------
    path
        Checkpoint file path to read.

    Returns
    -------
    CheckpointState or None
        The restored state, or ``None`` if the file does not exist or is
        unreadable/empty.
    """
    target = Path(path)
    if not target.exists():
        return None
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.strip():
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return _checkpoint_from_dict(data)


# ═══════════════════════════════════════════════════════════════════════════
# should_checkpoint — pure decision function (P3 §3.4 NEW interface, missing)
# ═══════════════════════════════════════════════════════════════════════════

# TODO(benchmark-upgrade): checkpoint.py — implement should_checkpoint per
# P3 §3.4. Signature:
#   should_checkpoint(
#       completed_since_last: int,
#       seconds_since_last: float,
#       config: BenchmarkConfig,
#   ) -> bool
# Return True if a checkpoint should be persisted now based on count/interval
# thresholds from config (config.checkpoint_every,
# config.checkpoint_interval_seconds). Pure decision function — no I/O.


# ═══════════════════════════════════════════════════════════════════════════
# atomic_write_json — generic atomic JSON writer (P3 §3.4 NEW interface, missing)
# ═══════════════════════════════════════════════════════════════════════════

# TODO(benchmark-upgrade): checkpoint.py — implement atomic_write_json per
# P3 §3.4. Signature: atomic_write_json(path: str, data: dict) -> None.
# Atomically write a JSON-serializable dict to a file (tmpfile + os.replace).
# Generic helper used by save_checkpoint, write_manifest, write_results, etc.
# Writes to path + ".tmp" then os.replace(path + ".tmp", path). INV-A3 (P6)
# enforces atomicity across all persisted files. Note: persistence.write_json
# already implements tmpfile + os.replace; this stub marks the P3 interface
# site that may delegate to it or supersede it in P7.


# ═══════════════════════════════════════════════════════════════════════════
# CheckpointManager — mutable wrapper with save/load + signal handlers
# ═══════════════════════════════════════════════════════════════════════════


class CheckpointManager:
    """Mutable checkpoint manager with atomic save/load and signal handlers.

    Wraps the immutable :class:`CheckpointState` with a mutable working
    state that tracks iteration/step progress, model configuration, and any
    partial results, and persists snapshots atomically to disk.

    The manager can be used two ways:

    **1. Context manager (recommended)** — installs SIGINT/SIGTERM handlers
    for the duration of the ``with`` block, then restores the previous
    handlers on exit::

        with CheckpointManager(run_id="r1", path=run_dir / "checkpoint.json") as ck:
            ck.total_cases = len(plan)
            for item in plan:
                result = run_case(item)
                ck.mark_completed(item.test_id)
                if ck.should_save():
                    ck.save()

    **2. Explicit start/stop** — for non-``with`` control flows::

        ck = CheckpointManager(run_id="r1", path=...)
        ck.start()
        try:
            ...
            ck.save()
        finally:
            ck.stop()

    On SIGINT or SIGTERM while active, the handler triggers a final
    :meth:`save` and then re-raises the default behaviour (exit with
    ``128 + signum``) so the process terminates promptly without losing
    progress.

    Parameters
    ----------
    run_id
        Unique identifier for this benchmark run.  Stored on every snapshot.
    path
        Filesystem path to the ``checkpoint.json`` file.  ``save()`` writes
        here; ``resume()`` / ``load()`` read from here.
    total_cases
        Total number of cases in the full run (for progress tracking).
        Defaults to ``0``; set later via attribute assignment or
        :meth:`update_progress`.
    model_config
        Optional model/configuration dict to track alongside the checkpoint
        (e.g. temperature, num_predict, base_url).  Stored in
        ``partial_results["__model_config__"]``.  May be ``None``.
    force_rerun
        If ``True``, :meth:`resume` ignores any existing checkpoint and the
        run starts fresh (INV-A4 override).  Defaults to ``False``.

    Attributes
    ----------
    run_id : str
    path : pathlib.Path
    completed_ids : set[str]
        Mutable set of finalised result/test IDs.
    total_cases : int
    current_iteration : int
        0-based index of the current outer iteration (model loop).
    current_step : int
        0-based index of the current step within the iteration (case loop).
    partial_results : dict[str, Any]
        Free-form dict of partial/in-progress results keyed by ``test_id``.
        Populated by :meth:`mark_completed` and by direct assignment.
    provenance : dict[str, ResultProvenance]
        Per-test-id provenance map (``new``/``resumed``/``retried``/
        ``recovered``).  Mirrors :attr:`CheckpointState.provenance`.
    last_saved_at : str
        ISO 8601 timestamp of the most recent successful :meth:`save`.
    """

    #: Signals that trigger a graceful checkpoint save on interruption.
    _HANDLED_SIGNALS: tuple[int, ...] = (
        signal.SIGINT,
        signal.SIGTERM,
    )

    def __init__(
        self,
        *,
        run_id: str,
        path: str | os.PathLike[str],
        total_cases: int = 0,
        model_config: dict[str, Any] | None = None,
        force_rerun: bool = False,
    ) -> None:
        self.run_id: str = run_id
        self.path: Path = Path(path)
        self.total_cases: int = total_cases
        self.force_rerun: bool = force_rerun

        # Mutable working state.
        self.completed_ids: set[str] = set()
        self.current_iteration: int = 0
        self.current_step: int = 0
        self.partial_results: dict[str, Any] = {}
        self.provenance: dict[str, str] = {}
        self.last_saved_at: str = ""

        if model_config is not None:
            # Stored under a reserved key so it round-trips with the snapshot
            # but doesn't collide with test_id keys.
            self.partial_results["__model_config__"] = dict(model_config)

        # Signal-handler bookkeeping (populated by start()).
        self._active: bool = False
        self._previous_handlers: dict[int, Any] = {}

    # ── Snapshot <-> frozen state ───────────────────────────────────────

    def _to_state(self) -> CheckpointState:
        """Build an immutable :class:`CheckpointState` from current state."""
        # Sync the model_config back out of partial_results for the snapshot
        # (it is stored alongside partial results so a single dict captures
        # both the model config and any partial per-case results).
        return CheckpointState(
            run_id=self.run_id,
            completed_ids=tuple(sorted(self.completed_ids)),
            total_cases=self.total_cases,
            last_saved_at=self.last_saved_at,
            provenance=tuple(
                (tid, self.provenance.get(tid, "new"))
                for tid in sorted(self.completed_ids)
            ),
        )

    def _restore_from_state(self, state: CheckpointState) -> None:
        """Restore mutable working state from an immutable snapshot."""
        self.run_id = state.run_id
        self.completed_ids = set(state.completed_ids)
        self.total_cases = state.total_cases
        self.last_saved_at = state.last_saved_at
        self.provenance = dict(state.provenance)

    # ── Public save / load / resume ──────────────────────────────────────

    def save(self, path: str | os.PathLike[str] | None = None) -> Path:
        """Atomically persist the current state to ``checkpoint.json``.

        Updates :attr:`last_saved_at` to the current UTC time, builds a
        :class:`CheckpointState` snapshot, and writes it via
        :func:`model_benchmark.persistence.write_json` (tmpfile +
        :func:`os.replace`, INV-A3).  Parent directories are created if
        missing.

        Parameters
        ----------
        path
            Optional override for the destination path.  Defaults to
            :attr:`self.path`.

        Returns
        -------
        pathlib.Path
            The resolved destination path on success.
        """
        target = Path(path) if path is not None else self.path
        self.last_saved_at = _now_iso()
        state = self._to_state()
        return save_checkpoint(state, target)

    def load(self, path: str | os.PathLike[str] | None = None) -> CheckpointState | None:
        """Load a checkpoint from ``path`` into this manager's working state.

        Reads the file (returning ``None`` if absent/empty/invalid), restores
        the mutable working state (:meth:`_restore_from_state`), and returns
        the loaded :class:`CheckpointState`.

        Does **not** install signal handlers — use :meth:`resume` or the
        context manager for that.  ``load()`` is the read half; ``resume()``
        is ``load()`` + ``start()``.

        Parameters
        ----------
        path
            Optional override for the source path.  Defaults to
            :attr:`self.path`.

        Returns
        -------
        CheckpointState or None
            The restored state, or ``None`` if no checkpoint was found.
        """
        src = Path(path) if path is not None else self.path
        state = load_checkpoint(src)
        if state is not None:
            self._restore_from_state(state)
        return state

    def resume(
        self,
        path: str | os.PathLike[str] | None = None,
    ) -> CheckpointState | None:
        """Resume from an existing checkpoint, installing signal handlers.

        Convenience method combining :meth:`load` + :meth:`start`:

        1. Loads the checkpoint from ``path`` (or :attr:`self.path`).
        2. If ``force_rerun`` is set, ignores any loaded state (the run
           starts fresh) but still installs handlers.
        3. Installs SIGINT/SIGTERM handlers (:meth:`start`).

        On a successful resume, already-completed IDs remain in
        :attr:`completed_ids` so the caller can skip them (INV-A4).

        Parameters
        ----------
        path
            Optional override for the source path.

        Returns
        -------
        CheckpointState or None
            The restored state (``None`` if no checkpoint existed or
            ``force_rerun`` discarded it).
        """
        state: CheckpointState | None = None
        if not self.force_rerun:
            state = self.load(path)
        # Always install handlers for the upcoming run.
        self.start()
        return state

    # ── Progress / result tracking ──────────────────────────────────────

    def update_progress(
        self,
        *,
        iteration: int | None = None,
        step: int | None = None,
        total_cases: int | None = None,
    ) -> None:
        """Update iteration/step/total progress counters.

        Each argument is optional; only the supplied ones are updated.
        """
        if iteration is not None:
            self.current_iteration = int(iteration)
        if step is not None:
            self.current_step = int(step)
        if total_cases is not None:
            self.total_cases = int(total_cases)

    def mark_completed(
        self,
        test_id: str,
        *,
        result: Any = None,
        provenance: str = "new",
    ) -> None:
        """Record a completed case.

        Adds ``test_id`` to :attr:`completed_ids`, optionally stores a
        partial result, and records provenance (``new``/``resumed``/
        ``retried``/``recovered``).

        Parameters
        ----------
        test_id
            The case's deterministic identifier.
        result
            Optional partial result object to store under
            ``partial_results[test_id]``.
        provenance
            How this result was obtained.  Defaults to ``"new"``.
        """
        self.completed_ids.add(test_id)
        if result is not None:
            self.partial_results[test_id] = result
        if provenance not in _VALID_PROVENANCE:
            provenance = "new"
        self.provenance[test_id] = provenance

    def is_completed(self, test_id: str) -> bool:
        """Return ``True`` if ``test_id`` is already in the checkpoint."""
        return test_id in self.completed_ids

    def remaining(self) -> int:
        """Number of cases still to do (``total_cases - len(completed_ids)``).

        Clamped at ``0`` (never negative if more IDs were recorded than the
        declared total).
        """
        return max(0, self.total_cases - len(self.completed_ids))

    def should_save(self, *, every: int = 1) -> bool:
        """Heuristic: return ``True`` every ``every`` completed cases.

        A simple cadence gate for callers that want to checkpoint
        periodically without tracking counts themselves.  ``every=1``
        (default) means "save after every completed case".
        """
        if every <= 1:
            return True
        return len(self.completed_ids) > 0 and len(self.completed_ids) % every == 0

    # ── Signal handlers ─────────────────────────────────────────────────

    def start(self) -> None:
        """Install SIGINT/SIGTERM handlers (idempotent).

        Stores the previous handlers so :meth:`stop` can restore them.  If
        called while already active, this is a no-op.
        """
        if self._active:
            return
        self._previous_handlers = {}
        for sig in self._HANDLED_SIGNALS:
            # signal.getsignal may return a callable or an int (SIG_DFL/SIG_IGN).
            prev = signal.getsignal(sig)
            self._previous_handlers[sig] = prev
            try:
                signal.signal(sig, self._handle_signal)
            except (OSError, ValueError):
                # SIGTERM can occasionally fail to install in restricted
                # environments (e.g. inside some threads).  Skip silently —
                # the manager still works without that one signal.
                self._previous_handlers.pop(sig, None)
        self._active = True

    def stop(self) -> None:
        """Restore the previous SIGINT/SIGTERM handlers (idempotent).

        Restores handlers in the reverse order they were installed.  Safe
        to call even if :meth:`start` was not called or failed.
        """
        if not self._active:
            return
        for sig in self._HANDLED_SIGNALS:
            prev = self._previous_handlers.pop(sig, None)
            if prev is not None:
                try:
                    signal.signal(sig, prev)
                except (OSError, ValueError):
                    pass
        self._previous_handlers = {}
        self._active = False

    def _handle_signal(self, signum: int, frame: Any) -> None:
        """Signal handler: save a checkpoint, then exit with ``128 + signum``.

        Best-effort: if the save itself raises, we still exit (so a stuck
        save can't trap the user in an uninterruptible process).  Writes a
        short notice to stderr before exiting.
        """
        try:
            self.save()
        except BaseException as exc:  # noqa: BLE001 — log and proceed
            try:
                sys.stderr.write(
                    f"[checkpoint] signal {signum}: save failed ({exc!r}); "
                    f"exiting without checkpoint\n"
                )
                sys.stderr.flush()
            except Exception:
                pass
        else:
            try:
                sys.stderr.write(
                    f"[checkpoint] signal {signum}: checkpoint saved to "
                    f"{self.path}\n"
                )
                sys.stderr.flush()
            except Exception:
                pass
        # Re-raise default behaviour: exit with the conventional 128+signum.
        sys.exit(128 + signum)

    # ── Context manager protocol ────────────────────────────────────────

    def __enter__(self) -> "CheckpointManager":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        # Save a final checkpoint on normal exit (no exception), then
        # restore signal handlers regardless of outcome.
        if exc_type is None:
            try:
                self.save()
            except BaseException:
                # A failing final save must not mask the caller's logic.
                pass
        self.stop()
        # Do not suppress exceptions — returning None/False propagates them.
