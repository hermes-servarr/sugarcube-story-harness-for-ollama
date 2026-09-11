#!/usr/bin/env python3
"""Restricted SSH trigger for the Windows benchmark Scheduled Task."""

from __future__ import annotations

import contextlib
import json
import os
import secrets
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATE_DIR = Path("C:/ProgramData/HermesBenchmark/state")
STATUS_PATH = STATE_DIR / "task-status.json"
PROGRESS_PATH = STATE_DIR / "public-progress.json"
TRIGGER_LOCK_PATH = STATE_DIR / "trigger.lock"
RUN_LOCK_PATH = STATE_DIR / "run.lock"
TASK_NAME = "HermesBenchmarkPublisher"
POLL_SECONDS = 3
STARTUP_TIMEOUT_SECONDS = 60

PUSHED_MESSAGE = "Benchmark completed and anonymized results were pushed."
UNCHANGED_MESSAGE = "Benchmark completed; anonymized results were unchanged."
RUNNING_MESSAGE = "A benchmark is already running."
FAILURE_MESSAGE = "Benchmark request failed; ask the PC administrator to check the private log."
TERMINAL_STATES = {"succeeded", "unchanged", "already_running", "failed"}
ACTIVE_STATES = {"queued", "running"}


@contextlib.contextmanager
def _exclusive_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise BlockingIOError from exc
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise BlockingIOError from exc
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)


def _read_status(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_status(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    value = dict(payload)
    value["updated_at"] = datetime.now(timezone.utc).isoformat()
    fd, temporary_name = tempfile.mkstemp(
        prefix=".task-status-",
        suffix=".json",
        dir=path.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        for attempt in range(10):
            try:
                os.replace(temporary_name, path)
                break
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.05)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _lock_is_held(path: Path) -> bool:
    """Return whether another process owns an advisory benchmark lock."""
    try:
        with _exclusive_lock(path):
            return False
    except BlockingIOError:
        return True


def _valid_request_id(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 32
        and all(character in "0123456789abcdef" for character in value)
    )


def _active_status_age_seconds(status: dict[str, Any]) -> float | None:
    raw = status.get("updated_at")
    if not isinstance(raw, str):
        return None
    try:
        updated_at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - updated_at).total_seconds())


def _start_task(task_name: str) -> None:
    completed = subprocess.run(
        [
            "C:/Windows/System32/schtasks.exe",
            "/Run",
            "/TN",
            task_name,
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError("could not start scheduled task")


def _emit_terminal(status: dict[str, Any]) -> int:
    state = status.get("state")
    message = status.get("message")
    allowed = {
        "succeeded": (PUSHED_MESSAGE, 0),
        "unchanged": (UNCHANGED_MESSAGE, 0),
        "already_running": (RUNNING_MESSAGE, 75),
        "failed": (FAILURE_MESSAGE, 1),
    }
    expected_message, returncode = FAILURE_MESSAGE, 1
    if state in allowed:
        candidate_message, candidate_code = allowed[state]
        if message == candidate_message:
            expected_message, returncode = candidate_message, candidate_code
    print(expected_message)
    return returncode


def _duration_label(seconds: float) -> str:
    value = max(0, min(int(round(seconds)), 7 * 24 * 60 * 60))
    hours, remainder = divmod(value, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _progress_message(progress: dict[str, Any]) -> str | None:
    if progress.get("phase") not in {
        "starting",
        "matrix",
        "capability",
        "refactor",
        "context_window",
        "finalizing",
    }:
        return None
    try:
        completed = max(0, int(progress["overall_completed"]))
        total = max(1, int(progress["overall_total"]))
        phase_completed = max(0, int(progress.get("completed", 0)))
        phase_total = max(0, int(progress.get("total", 0)))
        elapsed = max(0.0, float(progress.get("overall_elapsed_seconds", 0.0)))
    except (KeyError, TypeError, ValueError):
        return None
    completed = min(completed, total)
    percent = completed / total * 100.0
    message = (
        f"Benchmark progress: {completed}/{total} ({percent:.1f}%); "
        f"phase={progress['phase']} {phase_completed}/{phase_total}; "
        f"elapsed={_duration_label(elapsed)}"
    )
    try:
        eta = float(progress["overall_eta_seconds"])
    except (KeyError, TypeError, ValueError):
        eta = -1.0
    if 0 <= eta <= 7 * 24 * 60 * 60:
        basis = (
            "previous run"
            if progress.get("estimate_basis") == "previous_successful_run"
            else "current rate"
        )
        message += f"; ETA={_duration_label(eta)} ({basis})"
    return message + "."


def _wait_for_request(
    request_id: str,
    *,
    status_path: Path,
    progress_path: Path,
    run_lock_path: Path,
    startup_timeout_seconds: float = STARTUP_TIMEOUT_SECONDS,
) -> int:
    """Relay one queued/running request until it publishes a terminal state."""
    startup_deadline = time.monotonic() + startup_timeout_seconds
    last_progress_key: tuple[str, int] | None = None

    while True:
        status = _read_status(status_path)
        if status.get("request_id") != request_id:
            print(FAILURE_MESSAGE)
            return 1
        if status.get("state") in TERMINAL_STATES:
            return _emit_terminal(status)

        # The publisher's process-owned lock is the liveness authority.  A
        # status file can survive a killed task or a reboot, while this lock
        # cannot.  Once observed, a long benchmark may safely run without a
        # synthetic wall-clock deadline.
        if _lock_is_held(run_lock_path):
            startup_deadline = float("inf")

        progress = _read_status(progress_path)
        progress_message = _progress_message(progress)
        if progress_message is not None:
            try:
                overall_completed = int(progress["overall_completed"])
                overall_total = max(1, int(progress["overall_total"]))
                progress_key = (
                    str(progress["phase"]),
                    int(overall_completed / overall_total * 100),
                )
            except (KeyError, TypeError, ValueError):
                progress_key = None
            if progress_key is not None and progress_key != last_progress_key:
                print(progress_message, flush=True)
                last_progress_key = progress_key

        if time.monotonic() >= startup_deadline:
            # Do not overwrite a terminal state that landed between reads.
            latest = _read_status(status_path)
            if (
                latest.get("request_id") == request_id
                and latest.get("state") in ACTIVE_STATES
                and not _lock_is_held(run_lock_path)
            ):
                _write_status(
                    status_path,
                    {
                        "request_id": request_id,
                        "state": "failed",
                        "message": FAILURE_MESSAGE,
                        "exit_code": 1,
                    },
                )
            print(FAILURE_MESSAGE)
            return 1
        time.sleep(POLL_SECONDS)


def trigger(
    *,
    status_path: Path = STATUS_PATH,
    lock_path: Path = TRIGGER_LOCK_PATH,
    progress_path: Path = PROGRESS_PATH,
    run_lock_path: Path = RUN_LOCK_PATH,
    task_name: str = TASK_NAME,
) -> int:
    if os.environ.get("SSH_ORIGINAL_COMMAND", "") != "run":
        print(FAILURE_MESSAGE)
        return 1

    try:
        with _exclusive_lock(lock_path):
            existing = _read_status(status_path)
            if existing.get("state") in ACTIVE_STATES:
                existing_request_id = existing.get("request_id")
                if _lock_is_held(run_lock_path):
                    if not _valid_request_id(existing_request_id):
                        print(RUNNING_MESSAGE)
                        return 75
                    # The original SSH connection may have disappeared while
                    # the Scheduled Task kept running.  Reattach instead of
                    # rejecting the caller and relay its eventual result.
                    return _wait_for_request(
                        existing_request_id,
                        status_path=status_path,
                        progress_path=progress_path,
                        run_lock_path=run_lock_path,
                    )
                age = _active_status_age_seconds(existing)
                if (
                    _valid_request_id(existing_request_id)
                    and age is not None
                    and age < STARTUP_TIMEOUT_SECONDS
                ):
                    # A Scheduled Task can set running just before its child
                    # publisher acquires run.lock.  Preserve that startup
                    # window rather than replacing a live request in flight.
                    return _wait_for_request(
                        existing_request_id,
                        status_path=status_path,
                        progress_path=progress_path,
                        run_lock_path=run_lock_path,
                        startup_timeout_seconds=(
                            STARTUP_TIMEOUT_SECONDS - age
                        ),
                    )
                # No process owns the authoritative publisher lock.  The
                # queued/running JSON is stale (for example after a reboot),
                # so replace it with a fresh request below.

            request_id = secrets.token_hex(16)
            try:
                progress_path.unlink(missing_ok=True)
            except OSError:
                print(FAILURE_MESSAGE)
                return 1
            _write_status(
                status_path,
                {"request_id": request_id, "state": "queued"},
            )
            try:
                _start_task(task_name)
            except Exception:
                _write_status(
                    status_path,
                    {
                        "request_id": request_id,
                        "state": "failed",
                        "message": FAILURE_MESSAGE,
                        "exit_code": 1,
                    },
                )
                raise
            return _wait_for_request(
                request_id,
                status_path=status_path,
                progress_path=progress_path,
                run_lock_path=run_lock_path,
            )
    except BlockingIOError:
        print(RUNNING_MESSAGE)
        return 75
    except Exception:
        print(FAILURE_MESSAGE)
        return 1


if __name__ == "__main__":
    raise SystemExit(trigger())
