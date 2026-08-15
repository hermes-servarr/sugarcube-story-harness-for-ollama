from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from model_benchmark.narrative_review import NarrativeReviewError
from model_benchmark.promotion_confirmation import analyze_confirmation


def _categories(*, accepted: bool, playable: bool) -> list[dict[str, object]]:
    results = []
    for name in (
        "raw_contract",
        "plan_adherence",
        "fill_completeness",
        "semantic_observables",
        "draft_assembly",
        "required_component_resolution",
        "state_transaction",
        "compile_success",
        "tweego_compile",
        "browser_load",
        "choice_reachability",
        "choice_effect_execution",
        "runtime_state_transaction",
        "continuity_after_navigation",
    ):
        browser = name in {
            "tweego_compile",
            "browser_load",
            "choice_reachability",
            "choice_effect_execution",
            "runtime_state_transaction",
            "continuity_after_navigation",
        }
        results.append({
            "name": name,
            "applicable": accepted or not browser,
            "passed": accepted and (playable or not browser),
            "gating": True,
        })
    return results


def _record(architecture: str, repetition: int, *, accepted: bool, playable: bool) -> dict[str, object]:
    test_id = f"model:case:{architecture}:{repetition}"
    return {
        "test_id": test_id,
        "parent_result_id": "",
        "input_summary": "case:plan@1",
        "category": f"harness_structure_{architecture}",
        "subcategory": architecture,
        "status": "PASS" if accepted and playable else "FAIL",
        "actual_output_raw": f"raw-{architecture}-{repetition}",
        "finish_reason": "stop",
        "input_tokens": 10,
        "model_alias": "model",
        "output_tokens": 20,
        "random_seed": str(41 + repetition),
        "repetition": repetition,
        "runtime_seconds": 2.0 if architecture == "legacy_json" else 2.2,
        "total_tokens": 30,
        "scored_result": {"category_results": _categories(accepted=accepted, playable=playable)},
    }


def _write_runs(tmp_path: Path) -> tuple[Path, Path]:
    parent = tmp_path / "parent"
    child = tmp_path / "child"
    parent.mkdir()
    child.mkdir()
    parent_records = []
    for repetition in (1, 2):
        parent_records.append(_record("legacy_json", repetition, accepted=False, playable=False))
        parent_records.append(_record("typed_fill", repetition, accepted=True, playable=True))
    parent_text = "".join(json.dumps(record) + "\n" for record in parent_records)
    (parent / "results_internal.jsonl").write_text(parent_text, encoding="utf-8")
    parent_manifest = {"repeated_runs_count": 2, "random_seed": "42"}
    (parent / "run_manifest.json").write_text(json.dumps(parent_manifest), encoding="utf-8")
    child_records = deepcopy(parent_records)
    for record in child_records:
        record["parent_result_id"] = record["test_id"]
    (child / "results_internal.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in child_records), encoding="utf-8"
    )
    child_manifest = deepcopy(parent_manifest)
    child_manifest["browser_rescore"] = {
        "model_calls": 0,
        "source_results_sha256": hashlib.sha256(parent_text.encode()).hexdigest(),
    }
    (child / "run_manifest.json").write_text(json.dumps(child_manifest), encoding="utf-8")
    return parent, child


def test_analyzes_matched_confirmation_and_gates(tmp_path: Path) -> None:
    parent, child = _write_runs(tmp_path)
    result = analyze_confirmation(parent, child, required_margin_percentage_points=5)

    assert result["record_count"] == 4
    assert result["generation_fields_preserved"] is True
    assert result["architectures"]["typed_fill"]["request_playable"] == {"passed": 2, "rate": 1.0}
    assert result["architectures"]["typed_fill"]["semantic_observable_without_draft"] == 0
    assert result["comparisons"]["typed_fill"]["request_playable"]["wins"] == 2
    assert result["comparisons"]["typed_fill"]["request_playable_delta_percentage_points"] == 100
    assert result["automated_promotion_gates"]["typed_fill"]["mechanical_and_latency_gates_pass"] is True
    assert result["human_narrative_gate"] == "not_assessed"


def test_rejects_child_that_changes_generation_output(tmp_path: Path) -> None:
    parent, child = _write_runs(tmp_path)
    records = [json.loads(line) for line in (child / "results_internal.jsonl").read_text().splitlines()]
    records[0]["actual_output_raw"] = "changed"
    (child / "results_internal.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )

    with pytest.raises(NarrativeReviewError, match="changed generation field"):
        analyze_confirmation(parent, child)


def test_rejects_wrong_parent_hash(tmp_path: Path) -> None:
    parent, child = _write_runs(tmp_path)
    manifest = json.loads((child / "run_manifest.json").read_text())
    manifest["browser_rescore"]["source_results_sha256"] = "0" * 64
    (child / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(NarrativeReviewError, match="source-results hash"):
        analyze_confirmation(parent, child)
