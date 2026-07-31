import json
from pathlib import Path

import scripts.hermes_benchmark_task as task_runner
import scripts.hermes_benchmark_trigger as trigger


def test_task_runner_publishes_only_allowlisted_success(monkeypatch, tmp_path):
    status_path = tmp_path / "status.json"
    status_path.write_text(
        json.dumps({"request_id": "a" * 32, "state": "queued"}),
        encoding="utf-8",
    )

    class Completed:
        returncode = 0
        stdout = task_runner.PUSHED_MESSAGE + "\n"
        stderr = ""

    monkeypatch.setattr(task_runner.subprocess, "run", lambda *args, **kwargs: Completed())

    assert task_runner.run_task(
        status_path=status_path,
        publisher_path=tmp_path / "publisher.py",
    ) == 0
    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert status["state"] == "succeeded"
    assert status["message"] == task_runner.PUSHED_MESSAGE


def test_task_runner_replaces_unexpected_output_with_generic_failure(
    monkeypatch, tmp_path
):
    status_path = tmp_path / "status.json"
    status_path.write_text(
        json.dumps({"request_id": "b" * 32, "state": "queued"}),
        encoding="utf-8",
    )

    class Completed:
        returncode = 1
        stdout = "sensitive unexpected output\n"
        stderr = "sensitive error\n"

    monkeypatch.setattr(task_runner.subprocess, "run", lambda *args, **kwargs: Completed())

    assert task_runner.run_task(
        status_path=status_path,
        publisher_path=tmp_path / "publisher.py",
    ) == 1
    rendered = status_path.read_text(encoding="utf-8")
    assert "sensitive" not in rendered
    assert task_runner.FAILURE_MESSAGE in rendered


def test_trigger_refuses_when_status_is_active(monkeypatch, tmp_path, capsys):
    status_path = tmp_path / "status.json"
    status_path.write_text(json.dumps({"state": "running"}), encoding="utf-8")
    monkeypatch.setenv("SSH_ORIGINAL_COMMAND", "run")
    monkeypatch.setattr(
        trigger,
        "_start_task",
        lambda task_name: (_ for _ in ()).throw(AssertionError("must not start")),
    )

    assert trigger.trigger(
        status_path=status_path,
        lock_path=tmp_path / "trigger.lock",
    ) == 75
    assert capsys.readouterr().out.strip() == trigger.RUNNING_MESSAGE


def test_trigger_starts_once_and_relays_allowlisted_result(
    monkeypatch, tmp_path, capsys
):
    status_path = tmp_path / "status.json"
    starts = []
    monkeypatch.setenv("SSH_ORIGINAL_COMMAND", "run")
    monkeypatch.setattr(trigger, "_task_state", lambda task_name: 3)

    def start(task_name):
        starts.append(task_name)
        status = json.loads(status_path.read_text(encoding="utf-8"))
        trigger._write_status(
            status_path,
            {
                "request_id": status["request_id"],
                "state": "unchanged",
                "message": trigger.UNCHANGED_MESSAGE,
                "exit_code": 0,
            },
        )

    monkeypatch.setattr(trigger, "_start_task", start)

    assert trigger.trigger(
        status_path=status_path,
        lock_path=tmp_path / "trigger.lock",
    ) == 0
    assert starts == [trigger.TASK_NAME]
    assert capsys.readouterr().out.strip() == trigger.UNCHANGED_MESSAGE


def test_trigger_rejects_any_other_remote_command(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("SSH_ORIGINAL_COMMAND", "shell")

    assert trigger.trigger(
        status_path=tmp_path / "status.json",
        lock_path=tmp_path / "trigger.lock",
    ) == 1
    assert capsys.readouterr().out.strip() == trigger.FAILURE_MESSAGE
