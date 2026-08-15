import json

import pytest

from harness.generation import ProjectTransaction


@pytest.mark.parametrize("phase,index", [
    ("before_replace", 0),
    ("after_replace", 0),
    ("before_replace", 1),
    ("after_replace", 1),
    ("before_replace", 2),
    ("after_replace", 2),
])
def test_failure_at_each_write_restores_all_prior_files(tmp_path, phase, index):
    project = tmp_path / "project"
    project.mkdir()
    journal = project / ".harness" / "transactions"
    existing_a = project / "a.txt"
    existing_b = project / "nested" / "b.txt"
    new_file = project / "new.txt"
    existing_a.write_text("old-a", encoding="utf-8")
    existing_b.parent.mkdir()
    existing_b.write_text("old-b", encoding="utf-8")

    transaction = ProjectTransaction(project, journal, f"txn_{phase}_{index}")
    transaction.add_text(existing_a, "new-a")
    transaction.add_text(existing_b, "new-b")
    transaction.add_text(new_file, "created")

    def fail(actual_phase, actual_index, target):
        if (actual_phase, actual_index) == (phase, index):
            raise RuntimeError("injected")

    with pytest.raises(RuntimeError, match="injected"):
        transaction.commit(fail)
    assert existing_a.read_text(encoding="utf-8") == "old-a"
    assert existing_b.read_text(encoding="utf-8") == "old-b"
    assert not new_file.exists()
    assert not list(journal.glob("*/journal.json"))


def test_success_replaces_all_files_and_cleans_journal(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    journal = project / ".harness" / "transactions"
    first = project / "first.txt"
    first.write_text("old", encoding="utf-8")
    second = project / "second.txt"
    transaction = ProjectTransaction(project, journal, "txn_success")
    transaction.add_text(first, "new")
    transaction.add_text(second, "created")
    transaction.commit()
    assert first.read_text(encoding="utf-8") == "new"
    assert second.read_text(encoding="utf-8") == "created"
    assert not (journal / "txn_success").exists()


def test_restart_recovers_replacement_after_process_crash(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    journal = project / ".harness" / "transactions"
    target = project / "story.json"
    target.write_text(json.dumps({"old": True}), encoding="utf-8")
    transaction = ProjectTransaction(project, journal, "txn_crash")
    transaction.add_text(target, json.dumps({"new": True}))

    class SimulatedCrash(BaseException):
        pass

    def crash(phase, index, path):
        if phase == "after_replace":
            raise SimulatedCrash

    with pytest.raises(SimulatedCrash):
        transaction.commit(crash)
    assert json.loads(target.read_text(encoding="utf-8")) == {"new": True}
    assert ProjectTransaction.recover_pending(project, journal) == ["txn_crash"]
    assert json.loads(target.read_text(encoding="utf-8")) == {"old": True}
    assert not (journal / "txn_crash").exists()


def test_targets_outside_project_are_rejected(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    transaction = ProjectTransaction(project, project / ".transactions")
    with pytest.raises(ValueError, match="outside"):
        transaction.add_text(tmp_path / "escape.txt", "no")
