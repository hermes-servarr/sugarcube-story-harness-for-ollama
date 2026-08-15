import dataclasses
import json

import pytest

from model_benchmark.browser_rescore import (
    BROWSER_CATEGORY_NAMES,
    BROWSER_RESCORE_VERSION,
    BrowserRescoreError,
    _evaluator_source_hashes,
    rescore_browser_records,
)
from model_benchmark.refactor_benchmark import (
    _model_output_from_fill,
    _production_pipeline_categories,
    load_refactor_cases,
    parse_refactor_fill,
    score_refactor_fill,
)
from model_benchmark.runner import result_record_from_model_run
from model_benchmark.scoring import CategoryResult, ModelRunResult


def _source_record():
    case = next(item for item in load_refactor_cases() if item.id == "R0-ORDINARY-FANTASY")
    raw = json.dumps({
        "plan_id": case.plan.plan_id,
        "plan_revision": case.plan.revision,
        "narrative": [{
            "slot_id": "opening", "kind": "paragraph", "speaker": "",
            "parts": [{"kind": "text", "text": "A lamp glows beside the book."}],
        }],
        "choices": [
            {"slot_id": "choice_read", "text": "Open it", "hint": "Read."},
            {"slot_id": "choice_return", "text": "Leave it", "hint": "Go."},
        ],
        "summary": "A book waits.",
        "beats": ["The apprentice decides."],
    })
    fill = parse_refactor_fill(raw)
    categories = (
        *score_refactor_fill(case, raw, fill),
        *_production_pipeline_categories(case, fill),
    )
    run = ModelRunResult(
        model_name="fixture:model", variant="json", direction="A", run_index=0,
        raw_response=raw, parsed_output=_model_output_from_fill(fill),
        category_results=tuple(categories), overall_pass=True, random_seed="42",
    )
    record = result_record_from_model_run(run)
    record = dataclasses.replace(
        record,
        test_id=f"fixture:model:{case.id}:typed_fill:1",
        test_version="refactor-plan-v1",
        category="harness_structure_typed_fill",
        subcategory="typed_fill",
        input_summary=f"{case.id}:{case.plan.plan_id}@{case.plan.revision}",
    )
    return dataclasses.asdict(record)


def _passing_browser(*_args):
    return tuple(
        CategoryResult(name, True, 1.0, "fixture browser pass")
        for name in BROWSER_CATEGORY_NAMES
    )


def test_browser_rescore_reuses_raw_response_and_links_parent():
    source = _source_record()
    [child] = rescore_browser_records([source], _passing_browser)

    assert child["actual_output_raw"] == source["actual_output_raw"]
    assert child["parent_result_id"] == source["test_id"]
    assert child["provenance"] == "recovered"
    assert child["evaluator_version"] == BROWSER_RESCORE_VERSION
    categories = {
        item["name"]: item for item in child["scored_result"]["category_results"]
    }
    assert all(categories[name]["passed"] for name in BROWSER_CATEGORY_NAMES)
    expected_pass = all(
        item["passed"] for item in categories.values()
        if item.get("applicable", True) and item.get("gating", True)
    )
    assert child["status"] == ("PASS" if expected_pass else "FAIL")


def test_browser_rescore_rejects_non_browser_evaluator_drift():
    source = _source_record()
    source["scored_result"]["category_results"][0]["details"] = "tampered"

    with pytest.raises(BrowserRescoreError, match="evaluator drift"):
        rescore_browser_records([source], _passing_browser)


def test_browser_rescore_provenance_hashes_all_semantic_sources():
    hashes = _evaluator_source_hashes()
    assert {
        "model_benchmark/refactor_cases.json",
        "model_benchmark/refactor_benchmark.py",
        "harness/generation/contracts.py",
        "harness/generation/compiler.py",
        "harness/generation/browser_evaluator.py",
    }.issubset(hashes)
    assert all(len(value) == 64 for value in hashes.values())
