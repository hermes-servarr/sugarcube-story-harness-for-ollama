import json
import os
from pathlib import Path

import pytest

from harness.ollama_client import OllamaGenerationResult
from model_benchmark.config import BenchmarkConfig
from model_benchmark.refactor_benchmark import (
    execute_refactor_cases,
    load_refactor_cases,
    make_refactor_browser_evaluator,
)


def _runtime_paths() -> tuple[Path, Path]:
    tweego = Path(os.environ.get("TWEEGO_BIN", ""))
    formats = Path(os.environ.get("TWEEGO_FORMATS", ""))
    if not tweego.is_file() or not formats.is_dir():
        pytest.skip("set TWEEGO_BIN and TWEEGO_FORMATS to run browser gates")
    return tweego, formats


@pytest.mark.e2e
def test_refactor_benchmark_runs_production_browser_categories(monkeypatch):
    tweego, formats = _runtime_paths()
    case = next(
        item for item in load_refactor_cases()
        if item.id == "R1-STATE-REFERENCE"
    )
    response = json.dumps({
        "plan_id": case.plan.plan_id,
        "plan_revision": case.plan.revision,
        "narrative": [{
            "slot_id": "merchant_scene",
            "kind": "paragraph",
            "speaker": "",
            "parts": [
                {"kind": "text", "text": "The merchant counts "},
                {"kind": "state_ref", "target": "gold"},
                {"kind": "text", "text": " coins beside the medicine."},
            ],
        }],
        "choices": [
            {"slot_id": "choice_buy", "text": "Buy medicine", "hint": "Buy."},
            {"slot_id": "choice_leave", "text": "Leave", "hint": "Leave."},
        ],
        "summary": "The merchant offers medicine.",
        "beats": ["The player considers the offer."],
    })
    monkeypatch.setattr(
        "model_benchmark.refactor_benchmark.call_ollama_sync_detailed",
        lambda *args, **kwargs: OllamaGenerationResult(response=response),
    )
    cfg = BenchmarkConfig(
        models=("fixture-model",), variants=("json",), directions=("A",),
        base_url="http://127.0.0.1:11434", timeout=30, num_predict=640,
        temperature=0.2, runs=1,
    )

    record = execute_refactor_cases(
        cfg,
        [case],
        browser_evaluator=make_refactor_browser_evaluator(tweego, formats),
    )[0]
    categories = {
        result.name: result for result in record.scored_result.category_results
    }

    for name in (
        "tweego_compile",
        "browser_load",
        "choice_reachability",
        "choice_effect_execution",
        "runtime_state_transaction",
        "continuity_after_navigation",
    ):
        assert categories[name].passed, categories[name]
