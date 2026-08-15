import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import BackgroundTasks, HTTPException

from harness.generation import (
    ContextPack,
    ChoiceSlot,
    ContinuityProposal,
    GenerationProvenance,
    DraftRecord,
    NarrativeFill,
    NarrativeSlot,
    PassagePlan,
    StateCondition,
    TypedGenerationOutcome,
    assemble_passage_draft,
    compile_passage_draft,
    DraftLifecycle,
    DraftStore,
)
from harness.project import init_project
from harness.server import app as server_app


def _fill(
    plan: PassagePlan,
    text: str,
    *,
    revision: int = 1,
    continuity_proposals: tuple[ContinuityProposal, ...] = (),
) -> NarrativeFill:
    return NarrativeFill.model_validate({
        "plan_id": plan.plan_id,
        "plan_revision": plan.revision,
        "revision": revision,
        "narrative": [{
            "slot_id": "body",
            "kind": "paragraph",
            "speaker": "",
            "parts": [{"kind": "text", "text": text}],
        }],
        "choices": [{"slot_id": "continue", "text": "Continue", "hint": ""}],
        "summary": "A draft scene.",
        "beats": ["Continue."],
        "continuity_proposals": [item.model_dump(mode="json") for item in continuity_proposals],
    })


def test_typed_generate_read_and_edit_are_one_persisted_artifact(tmp_path, monkeypatch):
    init_project(tmp_path)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    context = ContextPack(parent_summary="Before.")
    plan = PassagePlan(
        plan_id="api_plan",
        revision=1,
        passage_mode="normal",
        narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),),
        choice_slots=("continue",),
        context_fingerprint=context.fingerprint(),
    )

    async def fake_generate(cfg, supplied_plan, supplied_context, **kwargs):
        draft = assemble_passage_draft(
            supplied_plan,
            _fill(supplied_plan, "Generated text."),
            draft_id=kwargs["draft_id"],
        )
        artifact = compile_passage_draft(
            draft,
            passage_id=kwargs["passage_id"],
            arc_name=kwargs["arc_name"],
        )
        return TypedGenerationOutcome(
            fill=draft.fill,
            draft=draft,
            compile_artifact=artifact,
            provenance=GenerationProvenance(model_name="fixture"),
        )

    monkeypatch.setattr(server_app, "generate_typed_draft", fake_generate)
    generated = asyncio.run(server_app.generate_typed(server_app.TypedGenerateRequest(
        plan=plan,
        context=context,
        author_task="Write it.",
        passage_id="next_scene",
        arc_name="main",
    )))
    draft_id = generated["draft"]["draft_id"]
    assert generated["lifecycle_state"] == "validated"
    assert generated["draft"]["plan"]["experience_profile_fingerprint"]
    plan = PassagePlan.model_validate(generated["draft"]["plan"])

    loaded = asyncio.run(server_app.get_typed_draft(draft_id, 1))
    assert loaded == generated

    current_draft = assemble_passage_draft(
        plan,
        _fill(plan, "Generated text."),
        draft_id=draft_id,
    )
    edited = asyncio.run(server_app.edit_typed_draft(
        draft_id,
        1,
        server_app.TypedDraftEditRequest(
            expected_draft_fingerprint=current_draft.fingerprint(),
            fill=_fill(plan, "Human-edited text."),
        ),
    ))
    assert edited["draft"]["revision"] == 2
    assert edited["draft"]["fill"]["revision"] == 2
    assert edited["lifecycle_state"] == "edited"
    assert "Human-edited text." in edited["compile_artifact"]["twee_source"]

    edited_record = DraftRecord.model_validate(edited)
    with pytest.raises(HTTPException) as stale_validation:
        asyncio.run(server_app.validate_typed_draft(
            draft_id,
            2,
            server_app.TypedDraftValidateRequest(
                expected_draft_fingerprint="0" * 64,
            ),
        ))
    assert stale_validation.value.detail["code"] == "draft_fingerprint_conflict"
    validated = asyncio.run(server_app.validate_typed_draft(
        draft_id,
        2,
        server_app.TypedDraftValidateRequest(
            expected_draft_fingerprint=edited_record.draft.fingerprint(),
        ),
    ))
    assert validated["lifecycle_state"] == "validated"
    committed = asyncio.run(server_app.commit_typed(
        draft_id,
        2,
        server_app.TypedDraftCommitRequest(
            expected_plan_revision=1,
            expected_draft_fingerprint=edited_record.draft.fingerprint(),
            expected_parent_fingerprint="",
        ),
    ))
    assert committed == {
        "status": "committed",
        "draft_id": draft_id,
        "draft_revision": 2,
        "passage_id": "next_scene",
        "pending_facts": [],
    }
    passage_path = tmp_path / "arcs" / "main" / "next_scene.tw"
    assert passage_path.read_text(encoding="utf-8") == edited["compile_artifact"]["twee_source"]


def test_typed_fact_decision_is_bound_to_exact_committed_proposal(tmp_path, monkeypatch):
    paths = init_project(tmp_path)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    plan = PassagePlan(
        plan_id="fact_plan", revision=1, passage_mode="normal",
        narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),),
        choice_slots=("continue",),
    )
    proposal = ContinuityProposal(
        key="moon_is_broken",
        value="The northern moon has a visible fracture.",
        evidence_slot_ids=("body",),
    )
    draft = assemble_passage_draft(
        plan,
        _fill(plan, "The fractured moon hangs overhead.", continuity_proposals=(proposal,)),
        draft_id="draft_fact",
    )
    artifact = compile_passage_draft(draft, passage_id="fact_scene", arc_name="main")
    DraftStore(paths.harness_dir / "drafts").put(DraftRecord(
        generation_id="generation_fact", draft=draft,
        lifecycle_state=DraftLifecycle.VALIDATED,
        provenance=GenerationProvenance(model_name="fixture"),
        compile_artifact=artifact, passage_id="fact_scene", arc_name="main",
    ))

    committed = asyncio.run(server_app.commit_typed(
        "draft_fact", 1,
        server_app.TypedDraftCommitRequest(
            expected_plan_revision=1,
            expected_draft_fingerprint=draft.fingerprint(),
            expected_parent_fingerprint="",
        ),
    ))
    assert committed["pending_facts"] == [proposal.model_dump(mode="json")]
    accepted = asyncio.run(server_app.decide_typed_fact(
        "draft_fact", 1, "moon_is_broken",
        server_app.TypedFactDecisionRequest(action="accept"),
    ))
    assert accepted == {"status": "accepted", "key": "moon_is_broken"}
    assert "northern moon" in paths.lore_file("continuity", "moon_is_broken").read_text(encoding="utf-8")

    # Decisions are idempotent, but cannot be silently reversed.
    assert asyncio.run(server_app.decide_typed_fact(
        "draft_fact", 1, "moon_is_broken",
        server_app.TypedFactDecisionRequest(action="accept"),
    )) == accepted
    with pytest.raises(HTTPException) as reversed_decision:
        asyncio.run(server_app.decide_typed_fact(
            "draft_fact", 1, "moon_is_broken",
            server_app.TypedFactDecisionRequest(action="reject"),
        ))
    assert reversed_decision.value.detail["code"] == "fact_decision_conflict"

    with pytest.raises(HTTPException) as fabricated:
        asyncio.run(server_app.decide_typed_fact(
            "draft_fact", 1, "invented_fact",
            server_app.TypedFactDecisionRequest(action="accept"),
        ))
    assert fabricated.value.detail["code"] == "fact_proposal_not_found"


def test_latest_and_reject_endpoints_preserve_exact_revision(tmp_path, monkeypatch):
    paths = init_project(tmp_path)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    plan = PassagePlan(
        plan_id="reject_plan", revision=1, passage_mode="normal",
        narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),),
        choice_slots=("continue",),
    )
    draft = assemble_passage_draft(plan, _fill(plan, "Reject this."), draft_id="draft_reject")
    artifact = compile_passage_draft(draft, passage_id="rejected_scene", arc_name="main")
    record = DraftRecord(
        generation_id="generation_reject", draft=draft,
        lifecycle_state=DraftLifecycle.VALIDATED,
        provenance=GenerationProvenance(model_name="fixture"),
        compile_artifact=artifact, passage_id="rejected_scene", arc_name="main",
    )
    DraftStore(paths.harness_dir / "drafts").put(record)

    latest = asyncio.run(server_app.get_latest_typed_draft("draft_reject"))
    rejected = asyncio.run(server_app.reject_typed_draft(
        "draft_reject", 1,
        server_app.TypedDraftRejectRequest(expected_draft_fingerprint=draft.fingerprint()),
    ))

    assert latest["draft"]["revision"] == 1
    assert rejected["lifecycle_state"] == "rejected"
    with pytest.raises(HTTPException) as closed:
        asyncio.run(server_app.reject_typed_draft(
            "draft_reject", 1,
            server_app.TypedDraftRejectRequest(expected_draft_fingerprint=draft.fingerprint()),
        ))
    assert closed.value.detail["code"] == "draft_closed"


def test_exact_compile_and_background_playtest_job_lifecycle(tmp_path, monkeypatch):
    paths = init_project(tmp_path)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    plan = PassagePlan(
        plan_id="playtest_plan", revision=1, passage_mode="normal",
        narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),),
        choice_slots=(
            ChoiceSlot(
                id="continue", destination="next_scene",
                conditions=(StateCondition(target="weather_safe", operation="truthy"),),
            ),
        ),
        allowed_state_refs=("weather_safe",),
    )
    draft = assemble_passage_draft(
        plan, _fill(plan, "Test this exact draft."), draft_id="draft_playtest",
    )
    artifact = compile_passage_draft(draft, passage_id="playtest_scene", arc_name="main")
    record = DraftRecord(
        generation_id="generation_playtest", draft=draft,
        lifecycle_state=DraftLifecycle.VALIDATED,
        provenance=GenerationProvenance(model_name="fixture"),
        compile_artifact=artifact, passage_id="playtest_scene", arc_name="main",
    )
    DraftStore(paths.harness_dir / "drafts").put(record)

    compiled = asyncio.run(server_app.compile_typed_draft(
        "draft_playtest", 1,
        server_app.TypedDraftCompileRequest(
            expected_draft_fingerprint=draft.fingerprint(),
        ),
    ))
    assert compiled.persisted_artifact_match is True
    assert compiled.artifact.fingerprint() == artifact.fingerprint()

    captured = {}

    def fake_execute(project_root, supplied_record, scenario):
        captured.update({
            "project_root": project_root,
            "record": supplied_record,
            "scenario": scenario,
        })
        return server_app.TypedDraftPlaytestResult(
            passed=True,
            tweego_compile=True,
            browser_load=True,
            choice_reachability=True,
        )

    monkeypatch.setattr(server_app, "_execute_draft_playtest", fake_execute)
    tasks = BackgroundTasks()
    queued = asyncio.run(server_app.playtest_typed_draft(
        "draft_playtest", 1,
        server_app.TypedDraftPlaytestRequest(
            expected_draft_fingerprint=draft.fingerprint(),
            initial_state={"weather_safe": True},
            choice_slot_ids=("continue",),
        ),
        tasks,
    ))
    assert queued.status == "queued"
    assert queued.result is None
    asyncio.run(tasks())
    completed = asyncio.run(server_app.get_typed_draft_playtest(queued.job_id))
    assert completed.status == "completed"
    assert completed.result and completed.result.passed is True
    assert captured["project_root"] == tmp_path
    assert captured["record"].draft.fingerprint() == draft.fingerprint()
    assert captured["scenario"].verify_state is False
    assert captured["scenario"].choices[0].target == "next_scene"
    assert len(captured["scenario"].choices) == 1

    hidden = server_app._draft_browser_scenario(record, {"weather_safe": False})
    assert hidden.choices == ()
    with pytest.raises(ValueError, match="at least one slot"):
        server_app._draft_browser_scenario(record, {}, ())
    with pytest.raises(ValueError, match="duplicate slots"):
        server_app._draft_browser_scenario(record, {}, ("continue", "continue"))

    monkeypatch.setattr(
        server_app,
        "_execute_draft_playtest",
        lambda *args: (_ for _ in ()).throw(server_app.PlaytestRuntimeUnavailable(
            "playtest runtime unavailable: configure tweego and TWEEGO_FORMATS"
        )),
    )
    failed_tasks = BackgroundTasks()
    failed_queued = asyncio.run(server_app.playtest_typed_draft(
        "draft_playtest", 1,
        server_app.TypedDraftPlaytestRequest(
            expected_draft_fingerprint=draft.fingerprint(),
        ),
        failed_tasks,
    ))
    asyncio.run(failed_tasks())
    failed = asyncio.run(server_app.get_typed_draft_playtest(failed_queued.job_id))
    assert failed.status == "failed"
    assert failed.error_code == "playtest_runtime_unavailable"

    stale_time = datetime.now(timezone.utc) - timedelta(minutes=6)
    stale_job = server_app.TypedDraftPlaytestJobResponse(
        job_id="playtest_" + "1" * 32,
        status="running",
        draft_id="draft_playtest",
        draft_revision=1,
        draft_fingerprint=draft.fingerprint(),
        created_at=stale_time,
        updated_at=stale_time,
    )
    server_app._write_playtest_job(server_app._p(), stale_job)
    recovered = server_app._read_playtest_job(server_app._p(), stale_job.job_id)
    assert recovered.status == "failed"
    assert recovered.error_code == "playtest_job_stale"

    with pytest.raises(HTTPException) as stale:
        asyncio.run(server_app.compile_typed_draft(
            "draft_playtest", 1,
            server_app.TypedDraftCompileRequest(expected_draft_fingerprint="0" * 64),
        ))
    assert stale.value.detail["code"] == "draft_fingerprint_conflict"

    with pytest.raises(HTTPException) as unauthorized_fixture:
        asyncio.run(server_app.playtest_typed_draft(
            "draft_playtest", 1,
            server_app.TypedDraftPlaytestRequest(
                expected_draft_fingerprint=draft.fingerprint(),
                initial_state={"model_invented": True},
            ),
            BackgroundTasks(),
        ))
    assert unauthorized_fixture.value.detail["code"] == "playtest_fixture_invalid"

    with pytest.raises(HTTPException) as unknown_choice:
        asyncio.run(server_app.playtest_typed_draft(
            "draft_playtest", 1,
            server_app.TypedDraftPlaytestRequest(
                expected_draft_fingerprint=draft.fingerprint(),
                choice_slot_ids=("model_invented",),
            ),
            BackgroundTasks(),
        ))
    assert unknown_choice.value.detail == {
        "code": "playtest_fixture_invalid",
        "message": "playtest choice selection contains an unknown slot",
    }

    tampered = record.model_copy(update={
        "compile_artifact": record.compile_artifact.model_copy(update={
            "twee_source": record.compile_artifact.twee_source + "\nTampered",
        }),
    })
    monkeypatch.setattr(server_app, "_exact_draft_record", lambda *args: tampered)
    with pytest.raises(HTTPException) as artifact_conflict:
        asyncio.run(server_app.playtest_typed_draft(
            "draft_playtest", 1,
            server_app.TypedDraftPlaytestRequest(
                expected_draft_fingerprint=draft.fingerprint(),
            ),
            BackgroundTasks(),
        ))
    assert artifact_conflict.value.detail == {
        "code": "compile_artifact_conflict",
        "message": "persisted compile artifact does not reproduce from the exact draft",
    }


def test_typed_generate_rejects_plan_from_stale_experience_profile(tmp_path, monkeypatch):
    init_project(tmp_path)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    context = ContextPack()
    plan = PassagePlan(
        plan_id="stale_profile_plan",
        revision=1,
        passage_mode="normal",
        narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),),
        choice_slots=("continue",),
        context_fingerprint=context.fingerprint(),
        experience_profile_fingerprint="0" * 64,
    )

    with pytest.raises(HTTPException) as rejected:
        asyncio.run(server_app.generate_typed(server_app.TypedGenerateRequest(
            plan=plan,
            context=context,
            author_task="Write it.",
            passage_id="next_scene",
            arc_name="main",
        )))

    assert rejected.value.status_code == 409
    assert rejected.value.detail["code"] == "experience_profile_fingerprint_conflict"
