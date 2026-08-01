"""Diagnostic context-window sweep with identity-safe result records."""
from __future__ import annotations

import dataclasses
import re
import time
from typing import Any, Callable, Iterable

from harness.models import HarnessConfig
from harness.ollama_client import call_ollama_sync_detailed
from harness.parsers import parse_model_output
from model_benchmark.ingestion_routing import profile_for_model
from model_benchmark.runner import result_record_from_model_run
from model_benchmark.scoring import (
    BenchmarkConfig,
    CategoryResult,
    ModelRunResult,
)


ALLOWED_CONTEXT_SIZES = (2048, 4096, 8192, 16384, 32768, 65536)
DEFAULT_CONTEXT_SIZES = (2048, 4096, 8192, 16384, 32768)
_MARKERS = (
    "EMBER-271",
    "GLASS-593",
    "HARBOR-847",
)
_FILLER = " ledger"


def validate_context_sizes(values: Iterable[int]) -> tuple[int, ...]:
    """Accept a sorted unique subset of the signed, GPU-bounded ladder."""
    sizes = tuple(int(value) for value in values)
    if not sizes or len(sizes) > len(ALLOWED_CONTEXT_SIZES):
        raise ValueError("context window sizes must be a non-empty bounded list")
    if sizes != tuple(sorted(set(sizes))):
        raise ValueError("context window sizes must be sorted and unique")
    if any(size not in ALLOWED_CONTEXT_SIZES for size in sizes):
        raise ValueError("context window size is outside the signed ladder")
    return sizes


def build_context_probe_prompt(num_ctx: int) -> str:
    """Build a deterministic prompt with markers near start, middle, and end."""
    if num_ctx not in ALLOWED_CONTEXT_SIZES:
        raise ValueError("unsupported context window size")
    # Common ASCII words are intentionally used as tokenizer-neutral probe
    # units. Ollama's prompt_eval_count records the model's actual token count.
    units = max(256, num_ctx - 192)
    left = _FILLER * (units // 2)
    right = _FILLER * (units - units // 2)
    return (
        "CONTEXT WINDOW DIAGNOSTIC\n"
        f"Beginning marker: {_MARKERS[0]}.\n"
        f"{left}\n"
        f"Middle marker: {_MARKERS[1]}.\n"
        f"{right}\n"
        f"Ending marker: {_MARKERS[2]}.\n\n"
        "TASK\nReturn only the three markers in beginning, middle, ending order, "
        "separated by single spaces."
    )


def _marker_categories(response: str) -> tuple[CategoryResult, ...]:
    folded = response.casefold()
    categories = []
    for position, marker in zip(("beginning", "middle", "ending"), _MARKERS):
        present = marker.casefold() in folded
        categories.append(
            CategoryResult(
                name=f"context_{position}_retrieval",
                passed=present,
                score=1.0 if present else 0.0,
                details=f"{position} marker {'retained' if present else 'missing'}",
                evidence=(f"{position}_marker={'pass' if present else 'fail'}",),
            )
        )
    ordered = re.search(
        rf"{re.escape(_MARKERS[0])}.*{re.escape(_MARKERS[1])}.*"
        rf"{re.escape(_MARKERS[2])}",
        response,
        re.IGNORECASE | re.DOTALL,
    ) is not None
    categories.append(
        CategoryResult(
            name="context_marker_order",
            passed=ordered,
            score=1.0 if ordered else 0.0,
            details=f"marker order {'preserved' if ordered else 'not preserved'}",
            evidence=(f"marker_order={'pass' if ordered else 'fail'}",),
        )
    )
    return tuple(categories)


def execute_context_window_tests(
    cfg: BenchmarkConfig,
    sizes: Iterable[int] = DEFAULT_CONTEXT_SIZES,
    *,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> list[Any]:
    """Run the context ladder sequentially for every configured model."""
    selected_sizes = validate_context_sizes(sizes)
    total = len(cfg.models) * len(selected_sizes)
    completed = 0
    records = []
    sampling_seed = int(cfg.random_seed) if cfg.random_seed else None

    for model in cfg.models:
        ingestion_profile = profile_for_model(
            model,
            getattr(cfg, "ingestion_routing_path", ""),
        )
        for num_ctx in selected_sizes:
            prompt = build_context_probe_prompt(num_ctx)
            harness_cfg = HarnessConfig(
                ollama_model=model,
                ollama_base_url=cfg.base_url,
                model_mode="full",
                num_ctx=num_ctx,
                temperature=0.0,
                num_predict=32,
            )
            started = time.monotonic()
            error = ""
            prompt_tokens = 0
            output_tokens = 0
            raw = ""
            try:
                generated = call_ollama_sync_detailed(
                    harness_cfg,
                    prompt,
                    timeout=cfg.timeout,
                    temperature=0.0,
                    num_predict=32,
                    label=f"context-window-{num_ctx}",
                    ingestion_profile=ingestion_profile,
                    seed=sampling_seed,
                )
                raw = generated.response
                prompt_tokens = generated.prompt_eval_count
                output_tokens = generated.eval_count
                categories = _marker_categories(raw)
            except Exception as exc:
                error = str(exc)
                categories = tuple(
                    CategoryResult(
                        name=f"context_{position}_retrieval",
                        passed=False,
                        score=0.0,
                        details="context request failed",
                    )
                    for position in ("beginning", "middle", "ending")
                )

            run = ModelRunResult(
                model_name=model,
                variant="plain_text",
                direction="CTX",
                run_index=0,
                raw_response=raw,
                parsed_output=parse_model_output(raw),
                category_results=categories,
                overall_pass=not error and all(item.passed for item in categories),
                elapsed_seconds=time.monotonic() - started,
                error=error,
            )
            base_record = result_record_from_model_run(run)
            records.append(
                dataclasses.replace(
                    base_record,
                    test_id=f"{model}:CTX-{num_ctx}:plain_text:1",
                    test_version="context-window-v1",
                    capability="context_window_probe",
                    category="context_window",
                    subcategory="context_window",
                    difficulty=f"CTX-{num_ctx}",
                    dataset="capability_context_window",
                    split=f"num_ctx_{num_ctx}",
                    input_summary=(
                        f"requested_num_ctx={num_ctx};prompt_chars={len(prompt)}"
                    ),
                    expected_behavior=(
                        "request accepted and beginning/middle/ending markers retained"
                    ),
                    reference_rubric="signed context-window marker probe v1",
                    input_tokens=prompt_tokens,
                    output_tokens=output_tokens,
                    total_tokens=prompt_tokens + output_tokens,
                )
            )
            completed += 1
            if progress_callback is not None:
                try:
                    progress_callback(completed, total, model)
                except Exception:
                    pass
    return records
