#!/usr/bin/env python3
"""Run the protected publisher from a Windows Scheduled Task."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATE_DIR = Path("C:/ProgramData/HermesBenchmark/state")
STATUS_PATH = STATE_DIR / "task-status.json"
PUBLISHER_PATH = Path("C:/ProgramData/HermesBenchmark/hermes_benchmark_publish.py")

PUSHED_MESSAGE = "Benchmark completed and anonymized results were pushed."
UNCHANGED_MESSAGE = "Benchmark completed; anonymized results were unchanged."
RUNNING_MESSAGE = "A benchmark is already running."
FAILURE_MESSAGE = "Benchmark request failed; ask the PC administrator to check the private log."


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


def _public_result(returncode: int, stdout: str) -> tuple[str, str, int]:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    message = lines[-1] if lines else ""
    if returncode == 0 and message == PUSHED_MESSAGE:
        return "succeeded", PUSHED_MESSAGE, 0
    if returncode == 0 and message == UNCHANGED_MESSAGE:
        return "unchanged", UNCHANGED_MESSAGE, 0
    if returncode == 75 and message == RUNNING_MESSAGE:
        return "already_running", RUNNING_MESSAGE, 75
    return "failed", FAILURE_MESSAGE, 1


def run_task(
    *,
    status_path: Path = STATUS_PATH,
    publisher_path: Path = PUBLISHER_PATH,
) -> int:
    status = _read_status(status_path)
    request_id = status.get("request_id")
    if (
        status.get("state") != "queued"
        or not isinstance(request_id, str)
        or len(request_id) != 32
    ):
        return 1

    _write_status(status_path, {"request_id": request_id, "state": "running"})
    try:
        completed = subprocess.run(
            [sys.executable, str(publisher_path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        state, message, returncode = _public_result(
            completed.returncode,
            completed.stdout,
        )
    except Exception:
        state, message, returncode = "failed", FAILURE_MESSAGE, 1

    _write_status(
        status_path,
        {
            "request_id": request_id,
            "state": state,
            "message": message,
            "exit_code": returncode,
        },
    )
    return returncode


if __name__ == "__main__":
    raise SystemExit(run_task())
