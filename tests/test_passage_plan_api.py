import asyncio
import threading

import pytest
from fastapi import HTTPException

from harness.generation import (
    ContextPack,
    GenerationProvenance,
    NarrativeFill,
    NarrativeSlot,
    PassagePlan,
    TypedGenerationOutcome,
    assemble_passage_draft,
    compile_passage_draft,
)
from harness.project import init_project
from harness.server import app as server_app


def _plan(revision: int = 1) -> PassagePlan:
    return PassagePlan(
        plan_id="reviewed_plan",
        revision=revision,
        passage_mode="normal",
        narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),),
        choice_slots=("continue",),
    )


def test_plan_revisions_require_exact_fingerprint_and_explicit_approval(tmp_path, monkeypatch):
    init_project(tmp_path)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    first = asyncio.run(server_app.create_passage_plan(
        server_app.PassagePlanCreateRequest(plan=_plan()),
    ))
    assert first["approved"] is False
    assert asyncio.run(server_app.get_passage_plan("reviewed_plan", 1)) == first

    approved = asyncio.run(server_app.approve_passage_plan(
        "reviewed_plan", 1,
        server_app.PassagePlanApprovalRequest(expected_plan_fingerprint=first["fingerprint"]),
    ))
    assert approved["approved"] is True

    second_plan = _plan(2).model_copy(update={"required_components": ("author_reviewed",)})
    second = asyncio.run(server_app.revise_passage_plan(
        "reviewed_plan",
        server_app.PassagePlanRevisionRequest(
            plan=second_plan, expected_plan_fingerprint=first["fingerprint"],
        ),
    ))
    assert second["approved"] is False
    with pytest.raises(HTTPException) as superseded:
        asyncio.run(server_app.approve_passage_plan(
            "reviewed_plan", 1,
            server_app.PassagePlanApprovalRequest(expected_plan_fingerprint=first["fingerprint"]),
        ))
    assert superseded.value.detail["code"] == "plan_superseded"


def test_plan_revision_compare_and_swap_allows_only_one_writer(tmp_path, monkeypatch):
    init_project(tmp_path)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    first = asyncio.run(server_app.create_passage_plan(
        server_app.PassagePlanCreateRequest(plan=_plan()),
    ))
    barrier = threading.Barrier(2)
    results = []

    def writer(component: str) -> None:
        barrier.wait()
        try:
            results.append(asyncio.run(server_app.revise_passage_plan(
                "reviewed_plan",
                server_app.PassagePlanRevisionRequest(
                    plan=_plan(2).model_copy(update={"required_components": (component,)}),
                    expected_plan_fingerprint=first["fingerprint"],
                ),
            )))
        except HTTPException as exc:
            results.append(exc)

    threads = [threading.Thread(target=writer, args=(name,)) for name in ("alpha", "beta")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(not isinstance(item, HTTPException) for item in results) == 1
    conflict = next(item for item in results if isinstance(item, HTTPException))
    assert conflict.detail["code"] in {"plan_revision_conflict", "plan_fingerprint_conflict"}


def test_typed_generation_accepts_only_an_approved_exact_plan_reference(tmp_path, monkeypatch):
    init_project(tmp_path)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    created = asyncio.run(server_app.create_passage_plan(
        server_app.PassagePlanCreateRequest(plan=_plan()),
    ))
    request = server_app.TypedGenerateRequest(
        plan_id="reviewed_plan", plan_revision=1,
        expected_plan_fingerprint=created["fingerprint"],
        context=ContextPack(), author_task="Write it.",
        passage_id="reviewed_scene", arc_name="main",
    )
    with pytest.raises(HTTPException) as unapproved:
        asyncio.run(server_app.generate_typed(request))
    assert unapproved.value.detail["code"] == "plan_not_approved"

    asyncio.run(server_app.approve_passage_plan(
        "reviewed_plan", 1,
        server_app.PassagePlanApprovalRequest(expected_plan_fingerprint=created["fingerprint"]),
    ))

    async def fake_generate(cfg, supplied_plan, supplied_context, **kwargs):
        fill = NarrativeFill.model_validate({
            "plan_id": supplied_plan.plan_id, "plan_revision": supplied_plan.revision,
            "revision": 1,
            "narrative": [{"slot_id": "body", "kind": "paragraph", "speaker": "", "parts": [{"kind": "text", "text": "Reviewed prose."}]}],
            "choices": [{"slot_id": "continue", "text": "Continue", "hint": ""}],
            "summary": "Reviewed.", "beats": ["Continue."],
        })
        draft = assemble_passage_draft(supplied_plan, fill, draft_id=kwargs["draft_id"])
        artifact = compile_passage_draft(draft, passage_id=kwargs["passage_id"], arc_name=kwargs["arc_name"])
        return TypedGenerationOutcome(
            fill=fill, draft=draft, compile_artifact=artifact,
            provenance=GenerationProvenance(model_name="fixture"),
        )

    monkeypatch.setattr(server_app, "generate_typed_draft", fake_generate)
    generated = asyncio.run(server_app.generate_typed(request))
    assert generated["draft"]["plan"]["plan_id"] == "reviewed_plan"

