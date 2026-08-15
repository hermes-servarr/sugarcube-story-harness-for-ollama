import asyncio
import json

import pytest

from harness.generation import (
    ContextPack,
    NarrativeSlot,
    PassagePlan,
    generate_typed_draft,
)
from harness.models import HarnessConfig
from harness.ollama_client import OllamaGenerationResult


def _plan(context: ContextPack) -> PassagePlan:
    return PassagePlan(
        plan_id="shadow_plan",
        revision=1,
        passage_mode="normal",
        narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),),
        choice_slots=("continue",),
        context_fingerprint=context.fingerprint(),
    )


def test_typed_pipeline_uses_one_detailed_call_and_compiles():
    context = ContextPack(parent_summary="The door opened.")
    plan = _plan(context)
    calls = []

    async def transport(*args, **kwargs):
        calls.append((args, kwargs))
        return OllamaGenerationResult(
            response=json.dumps({
                "plan_id": plan.plan_id,
                "plan_revision": plan.revision,
                "revision": 1,
                "narrative": [{
                    "slot_id": "body",
                    "kind": "paragraph",
                    "speaker": "",
                    "parts": [{"kind": "text", "text": "Beyond it waits dawn."}],
                }],
                "choices": [{"slot_id": "continue", "text": "Step through", "hint": ""}],
                "summary": "The threshold is crossed.",
                "beats": ["The player advances."],
                "continuity_proposals": [],
                "media_proposals": [],
            }),
            prompt_eval_count=120,
            eval_count=42,
            done_reason="stop",
        )

    result = asyncio.run(
        generate_typed_draft(
            HarnessConfig(generation_strategy="typed_fill"),
            plan,
            context,
            author_task="Continue the story.",
            passage_id="threshold",
            arc_name="opening",
            seed=42,
            transport=transport,
        )
    )

    assert len(calls) == 1
    assert calls[0][1]["format_spec"]["additionalProperties"] is False
    assert "Beyond it waits dawn." in result.compile_artifact.twee_source
    assert result.provenance.input_tokens == 120
    assert result.provenance.output_tokens == 42
    assert result.provenance.seed == 42


def test_typed_pipeline_rejects_stale_context_before_calling_model():
    context = ContextPack(parent_summary="Current")
    plan = _plan(ContextPack(parent_summary="Old"))
    called = False

    async def transport(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("transport must not run")

    with pytest.raises(ValueError, match="context fingerprint"):
        asyncio.run(
            generate_typed_draft(
                HarnessConfig(generation_strategy="typed_fill"),
                plan,
                context,
                author_task="Continue.",
                passage_id="next",
                arc_name="main",
                transport=transport,
            )
        )
    assert called is False
