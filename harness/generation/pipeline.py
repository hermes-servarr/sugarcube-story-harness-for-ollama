"""Application orchestration for one-call typed passage generation."""
from __future__ import annotations

import hashlib
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from ..models import HarnessConfig
from ..ollama_client import OllamaGenerationResult, call_ollama_detailed
from .compiler import compile_passage_draft
from .context import ContextPack
from .contracts import (
    CompileArtifact,
    GenerationProvenance,
    NarrativeFill,
    PassageDraft,
    PassagePlan,
    assemble_passage_draft,
)
from .strategies import build_strategy_request


TypedTransport = Callable[..., Awaitable[OllamaGenerationResult]]


@dataclass(frozen=True)
class TypedGenerationOutcome:
    fill: NarrativeFill
    draft: PassageDraft
    compile_artifact: CompileArtifact
    provenance: GenerationProvenance


async def generate_typed_draft(
    cfg: HarnessConfig,
    plan: PassagePlan,
    context: ContextPack,
    *,
    author_task: str,
    passage_id: str,
    arc_name: str,
    draft_id: str | None = None,
    strategy: str | None = None,
    timeout: float = 120.0,
    seed: int | None = None,
    transport: TypedTransport = call_ollama_detailed,
) -> TypedGenerationOutcome:
    """Generate, normalize, assemble, and compile without a repair call."""
    selected = strategy or cfg.generation_strategy
    if selected not in {"typed_fill", "flat_fill"}:
        raise ValueError("typed pipeline requires typed_fill or flat_fill")
    if plan.context_fingerprint and plan.context_fingerprint != context.fingerprint():
        raise ValueError("plan context fingerprint does not match the context pack")

    request = build_strategy_request(
        selected,
        plan,
        context=context.render(),
        author_task=author_task,
    )
    started = time.monotonic()
    generated = await transport(
        cfg,
        request.prompt,
        timeout=timeout,
        format_spec=request.schema,
        label=f"passage-shadow-{selected}",
        seed=seed,
    )
    elapsed = time.monotonic() - started
    fill = request.normalize(generated.response)
    draft = assemble_passage_draft(plan, fill, draft_id=draft_id)
    artifact = compile_passage_draft(
        draft,
        passage_id=passage_id,
        arc_name=arc_name,
    )
    profile_id = getattr(cfg, "ingestion_profile", "")
    provenance = GenerationProvenance(
        raw_model_output=generated.response,
        rendered_prompt=request.prompt,
        model_name=cfg.ollama_model,
        ingestion_profile_fingerprint=(
            hashlib.sha256(profile_id.encode("utf-8")).hexdigest() if profile_id else ""
        ),
        effective_configuration={
            "strategy": selected,
            "temperature": cfg.temperature,
            "num_predict": cfg.num_predict,
            "num_ctx": cfg.num_ctx,
            "ingestion_profile": profile_id,
        },
        seed=seed,
        input_tokens=generated.prompt_eval_count,
        output_tokens=generated.eval_count,
        latency_seconds=elapsed,
        finish_reason=generated.done_reason,
    )
    return TypedGenerationOutcome(
        fill=fill,
        draft=draft,
        compile_artifact=artifact,
        provenance=provenance,
    )


__all__ = ["TypedGenerationOutcome", "generate_typed_draft"]
