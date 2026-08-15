import json

import pytest

from harness.generation import (
    DraftLifecycle,
    DraftRecord,
    DraftStore,
    GenerationProvenance,
    NarrativeFill,
    NarrativeSlot,
    PassagePlan,
    assemble_passage_draft,
    commit_typed_draft,
    compile_passage_draft,
    parent_fingerprint,
)
from harness.models import ModelOutput, ParsedChoice
from harness.passage import create_passage
from harness.project import init_project, load_story


def _setup(tmp_path):
    p = init_project(tmp_path)
    parent_id, _ = create_passage(
        p,
        "main",
        "parent",
        ModelOutput(
            prose="The path divides.",
            choices=[ParsedChoice(text="Take the path")],
            summary="A path divides.",
            beats=["Choose a path."],
        ),
        None,
    )
    context_fingerprint = "a" * 64
    plan = PassagePlan(
        plan_id="commit_plan",
        revision=1,
        passage_mode="normal",
        narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),),
        choice_slots=("continue",),
        context_fingerprint=context_fingerprint,
    )
    fill = NarrativeFill.model_validate({
        "plan_id": plan.plan_id,
        "plan_revision": 1,
        "narrative": [{
            "slot_id": "body",
            "kind": "paragraph",
            "speaker": "",
            "parts": [{"kind": "text", "text": "The exact child passage."}],
        }],
        "choices": [{"slot_id": "continue", "text": "Continue", "hint": ""}],
        "summary": "The child passage.",
        "beats": ["Arrive."],
    })
    draft = assemble_passage_draft(plan, fill, draft_id="draft_commit")
    artifact = compile_passage_draft(
        draft,
        passage_id="main_child",
        arc_name="main",
    )
    record = DraftRecord(
        generation_id="generation_commit",
        draft=draft,
        lifecycle_state=DraftLifecycle.VALIDATED,
        provenance=GenerationProvenance(model_name="fixture"),
        compile_artifact=artifact,
        parent_passage_id=parent_id,
        parent_choice_index=0,
        parent_revision=1,
        parent_fingerprint=parent_fingerprint(p, parent_id),
        passage_id="main_child",
        arc_name="main",
    )
    store = DraftStore(p.harness_dir / "drafts")
    store.put(record)
    return p, store, record


def test_typed_commit_writes_exact_artifact_and_marks_same_revision(tmp_path):
    p, store, record = _setup(tmp_path)
    committed = commit_typed_draft(
        p,
        store,
        draft_id="draft_commit",
        revision=1,
        expected_plan_revision=1,
        expected_draft_fingerprint=record.draft.fingerprint(),
        expected_parent_fingerprint=record.parent_fingerprint,
    )
    graph = load_story(p)
    child_path = p.root / graph.passages["main_child"].file
    parent_path = p.root / graph.passages[record.parent_passage_id].file
    assert child_path.read_text(encoding="utf-8") == record.compile_artifact.twee_source
    assert "main_child" in parent_path.read_text(encoding="utf-8")
    assert graph.passages[record.parent_passage_id].children == ["main_child"]
    assert committed.lifecycle_state == DraftLifecycle.COMMITTED
    assert store.get("draft_commit", 1).lifecycle_state == DraftLifecycle.COMMITTED


@pytest.mark.parametrize("index", range(5))
def test_typed_commit_failure_at_each_write_restores_project(tmp_path, index):
    p, store, record = _setup(tmp_path)
    before_story = p.story_json.read_bytes()
    parent_path = p.root / load_story(p).passages[record.parent_passage_id].file
    before_parent = parent_path.read_bytes()

    def fail(phase, actual_index, target):
        if phase == "after_replace" and actual_index == index:
            raise RuntimeError(f"failure {index}")

    with pytest.raises(RuntimeError, match="failure"):
        commit_typed_draft(
            p,
            store,
            draft_id="draft_commit",
            revision=1,
            expected_plan_revision=1,
            expected_draft_fingerprint=record.draft.fingerprint(),
            expected_parent_fingerprint=record.parent_fingerprint,
            failure_injector=fail,
        )
    assert p.story_json.read_bytes() == before_story
    assert parent_path.read_bytes() == before_parent
    assert not p.passage_file("main", "main_child.tw").exists()
    assert store.get("draft_commit", 1).lifecycle_state == DraftLifecycle.VALIDATED
    assert not list((p.harness_dir / "transactions").glob("*/journal.json"))


def test_parent_change_after_generation_conflicts_without_writes(tmp_path):
    p, store, record = _setup(tmp_path)
    graph = load_story(p)
    parent_path = p.root / graph.passages[record.parent_passage_id].file
    parent_path.write_text(parent_path.read_text(encoding="utf-8") + "\nChanged.\n", encoding="utf-8")
    from harness.generation import DraftConflict

    with pytest.raises(DraftConflict) as error:
        commit_typed_draft(
            p,
            store,
            draft_id="draft_commit",
            revision=1,
            expected_plan_revision=1,
            expected_draft_fingerprint=record.draft.fingerprint(),
            expected_parent_fingerprint=record.parent_fingerprint,
        )
    assert error.value.code == "parent_fingerprint_conflict"
    assert "main_child" not in json.loads(p.story_json.read_text(encoding="utf-8"))["passages"]


def test_commit_rejects_artifact_that_does_not_reproduce_from_exact_draft(tmp_path):
    from harness.generation import DraftConflict

    p, store, record = _setup(tmp_path)
    tampered = record.model_copy(update={
        "compile_artifact": record.compile_artifact.model_copy(update={
            "twee_source": record.compile_artifact.twee_source + "\nTampered",
        }),
    })

    class TamperedStore:
        def get(self, draft_id, revision):
            return tampered

        def latest_revision(self, draft_id):
            return store.latest_revision(draft_id)

    with pytest.raises(DraftConflict) as error:
        commit_typed_draft(
            p,
            TamperedStore(),
            draft_id="draft_commit",
            revision=1,
            expected_plan_revision=1,
            expected_draft_fingerprint=record.draft.fingerprint(),
            expected_parent_fingerprint=record.parent_fingerprint,
        )
    assert error.value.code == "compile_artifact_conflict"
    assert "main_child" not in load_story(p).passages


def test_plan_revision_and_duplicate_commit_return_stable_conflicts(tmp_path):
    from harness.generation import DraftConflict

    p, store, record = _setup(tmp_path)
    with pytest.raises(DraftConflict) as stale:
        commit_typed_draft(
            p,
            store,
            draft_id="draft_commit",
            revision=1,
            expected_plan_revision=2,
            expected_draft_fingerprint=record.draft.fingerprint(),
            expected_parent_fingerprint=record.parent_fingerprint,
        )
    assert stale.value.code == "plan_revision_conflict"

    commit_typed_draft(
        p,
        store,
        draft_id="draft_commit",
        revision=1,
        expected_plan_revision=1,
        expected_draft_fingerprint=record.draft.fingerprint(),
        expected_parent_fingerprint=record.parent_fingerprint,
    )
    with pytest.raises(DraftConflict) as duplicate:
        commit_typed_draft(
            p,
            store,
            draft_id="draft_commit",
            revision=1,
            expected_plan_revision=1,
            expected_draft_fingerprint=record.draft.fingerprint(),
            expected_parent_fingerprint=record.parent_fingerprint,
        )
    assert duplicate.value.code == "draft_already_committed"
