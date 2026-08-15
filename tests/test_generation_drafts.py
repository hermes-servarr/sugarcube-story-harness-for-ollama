import json

import pytest

from harness.generation import (
    DraftConflict,
    DraftLifecycle,
    DraftNotFound,
    DraftRecord,
    DraftStore,
    GenerationProvenance,
    NarrativeSlot,
    PassagePlan,
    assemble_passage_draft,
)
from harness.generation.contracts import NarrativeFill


def _record(revision: int = 1) -> DraftRecord:
    plan = PassagePlan(
        plan_id="persisted_plan",
        revision=1,
        passage_mode="normal",
        narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),),
        choice_slots=("continue",),
    )
    fill = NarrativeFill.model_validate({
        "plan_id": plan.plan_id,
        "plan_revision": plan.revision,
        "revision": revision,
        "narrative": [{
            "slot_id": "body",
            "kind": "paragraph",
            "speaker": "",
            "parts": [{"kind": "text", "text": f"Draft {revision}."}],
        }],
        "choices": [{"slot_id": "continue", "text": "Continue", "hint": ""}],
        "summary": "A persisted draft.",
        "beats": ["Continue."],
    })
    draft = assemble_passage_draft(
        plan,
        fill,
        draft_id="draft_persisted",
        revision=revision,
    )
    return DraftRecord(
        generation_id=f"generation_{revision}",
        draft=draft,
        lifecycle_state=(DraftLifecycle.GENERATED if revision == 1 else DraftLifecycle.EDITED),
        provenance=GenerationProvenance(model_name="fixture"),
    )


def test_draft_store_survives_restart_and_records_immutable_revisions(tmp_path):
    store = DraftStore(tmp_path / "drafts")
    first = _record(1)
    store.put(first)
    store.put(_record(2))

    restarted = DraftStore(tmp_path / "drafts")
    assert restarted.get("draft_persisted", 1).draft.fill.narrative[0].parts[0].text == "Draft 1."
    assert restarted.latest("draft_persisted").draft.revision == 2
    with pytest.raises(DraftConflict) as error:
        restarted.put(first)
    assert error.value.code == "draft_revision_conflict"


def test_lifecycle_transition_is_atomic_and_conflict_checked(tmp_path):
    store = DraftStore(tmp_path / "drafts")
    store.put(_record())
    validated = store.transition(
        "draft_persisted",
        1,
        expected=DraftLifecycle.GENERATED,
        target=DraftLifecycle.VALIDATED,
    )
    assert validated.lifecycle_state == DraftLifecycle.VALIDATED
    committed = store.transition(
        "draft_persisted",
        1,
        expected=DraftLifecycle.VALIDATED,
        target=DraftLifecycle.COMMITTED,
    )
    assert committed.lifecycle_state == DraftLifecycle.COMMITTED
    assert store.get("draft_persisted", 1).lifecycle_state == DraftLifecycle.COMMITTED
    with pytest.raises(DraftConflict) as error:
        store.transition(
            "draft_persisted",
            1,
            expected=DraftLifecycle.VALIDATED,
            target=DraftLifecycle.COMMITTED,
        )
    assert error.value.code == "draft_lifecycle_conflict"


def test_corruption_and_missing_revisions_fail_closed(tmp_path):
    store = DraftStore(tmp_path / "drafts")
    with pytest.raises(DraftNotFound):
        store.get("draft_missing", 1)
    store.put(_record())
    path = tmp_path / "drafts" / "draft_persisted" / "1.json"
    envelope = json.loads(path.read_text(encoding="utf-8"))
    envelope["record"]["draft"]["fill"]["summary"] = "Tampered"
    path.write_text(json.dumps(envelope), encoding="utf-8")
    with pytest.raises(DraftConflict) as error:
        store.get("draft_persisted", 1)
    assert error.value.code == "draft_fingerprint_mismatch"
