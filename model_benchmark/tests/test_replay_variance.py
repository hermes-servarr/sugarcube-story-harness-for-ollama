from __future__ import annotations

import json

import pytest

from model_benchmark.narrative_review import NarrativeReviewError
from model_benchmark.replay_variance import analyze_replay_variance


def _run(tmp_path, name: str, passes: int, *, seed: str = "42"):
    path = tmp_path / name
    path.mkdir()
    manifest = {
        "run_id": name,
        "parent_run_id": f"parent-{name}",
        "random_seed": seed,
        "repeated_runs_count": 1,
        "model_configs": [{"digest": "digest"}],
        "dataset_checksums": ["cases"],
        "generation_params": {"temperature": "0.2"},
        "python_version": "same",
        "source_commit_hash": "commit",
        "benchmark_version": "1",
        "evaluator_version": "browser-rescore-v1",
        "prompt_template": "compact",
        "prompt_version": 1,
        "runtime_settings": {"benchmark_profile": "sandbox-core", "num_predict": "640", "temperature": "0.2", "timeout": "180", "refactor_architectures": "typed_fill", "ollama_version": "1"},
        "browser_rescore": {"model_calls": 0, "evaluator_source_sha256": {"compiler": "same"}},
    }
    (path / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    rows = []
    for index in range(10):
        passed = index < passes
        categories = [
            {"name": "compile_success", "passed": passed, "applicable": True},
            {"name": "browser_load", "passed": passed, "applicable": passed},
            {"name": "choice_reachability", "passed": passed, "applicable": passed},
        ]
        rows.append({"test_id": str(index), "category": "harness_structure_typed_fill", "subcategory": "typed_fill", "status": "PASS" if passed else "FAIL", "scored_result": {"category_results": categories}})
    (path / "results_internal.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def test_reports_original_request_playable_range_and_margin(tmp_path):
    result = analyze_replay_variance([_run(tmp_path, "one", 8), _run(tmp_path, "two", 9), _run(tmp_path, "three", 8)])
    assert result["request_playable_noise_floor_percentage_points"] == pytest.approx(10.0)
    assert result["required_promotion_margin_percentage_points"] == 11
    assert result["ranges"]["typed_fill"]["compiled_playable"]["range_percentage_points"] == 0


def test_rejects_seed_mismatch(tmp_path):
    with pytest.raises(NarrativeReviewError, match="not compatible"):
        analyze_replay_variance([_run(tmp_path, "one", 8), _run(tmp_path, "two", 8, seed="43")])
