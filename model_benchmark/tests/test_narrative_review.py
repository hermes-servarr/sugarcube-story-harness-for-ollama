from __future__ import annotations

import json
import os

import pytest

from model_benchmark.narrative_review import NarrativeReviewError, build_review_bundle, main
from model_benchmark.narrative_review_results import decode_review_scores


def _record(architecture: str, repetition: int, prose: str = "Specific scene prose.") -> dict:
    return {
        "test_id": f"model:R0-ORDINARY-FANTASY:{architecture}:{repetition}",
        "subcategory": architecture,
        "model_alias": "secret-model",
        "repetition": repetition,
        "input_summary": "R0-ORDINARY-FANTASY:plan_ordinary_fantasy@1",
        "scored_result": {
            "overall_pass": True,
            "parsed_output": {
                "prose": prose,
                "choices": [{"text": "Read it", "hint": "Risk knowledge"}],
            },
            "category_results": [{"name": "compile_success", "passed": True}],
        },
    }


def _run(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    rows = []
    for repetition in (1, 2, 3):
        rows.extend((_record("typed_fill", repetition), _record("legacy_json", repetition, "Control prose.")))
    (run / "results_internal.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return run


def test_bundle_is_deterministic_blinded_and_separates_scores(tmp_path):
    run = _run(tmp_path)
    first = build_review_bundle(run, architecture_a="typed_fill", architecture_b="legacy_json", sample_size=2, seed="fixed")
    second = build_review_bundle(run, architecture_a="typed_fill", architecture_b="legacy_json", sample_size=2, seed="fixed")
    assert first == second
    bundle, private_key, template = first
    public = json.dumps(bundle)
    assert "typed_fill" not in public
    assert "legacy_json" not in public
    assert "secret-model" not in public
    assert "compile_success" not in public
    assert private_key["private"] is True
    assert private_key["output_a_counts"] == {"typed_fill": 1, "legacy_json": 1}
    assert len(bundle["items"]) == 2
    assert bundle["sampled_case_count"] == 1
    assert all(value is None for value in template["items"][0]["ratings"]["A"].values())


def test_cli_writes_private_key_with_restrictive_mode(tmp_path):
    run = _run(tmp_path)
    output = tmp_path / "review"
    assert main([str(run), str(output), "--sample-size", "1", "--seed", "fixed"]) == 0
    assert (output / "review_bundle.json").is_file()
    assert (output / "review_scores.template.json").is_file()
    key = output / "review_key.private.json"
    assert key.is_file()
    if os.name != "nt":
        assert key.stat().st_mode & 0o777 == 0o600


def test_requires_distinct_architectures_and_reviewable_pairs(tmp_path):
    run = _run(tmp_path)
    with pytest.raises(NarrativeReviewError, match="distinct"):
        build_review_bundle(run, architecture_a="typed_fill", architecture_b="typed_fill", sample_size=1, seed="fixed")
    rows = [_record("typed_fill", 1, ""), _record("legacy_json", 1, "")]
    (run / "results_internal.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    with pytest.raises(NarrativeReviewError, match="no matched"):
        build_review_bundle(run, architecture_a="typed_fill", architecture_b="legacy_json", sample_size=1, seed="fixed")


def test_completed_scores_decode_per_dimension_without_combined_score(tmp_path):
    run = _run(tmp_path)
    _, key, scores = build_review_bundle(run, architecture_a="typed_fill", architecture_b="legacy_json", sample_size=2, seed="fixed")
    for item in scores["items"]:
        for value in item["ratings"]["A"]:
            item["ratings"]["A"][value] = 5
            item["ratings"]["B"][value] = 3
        item["preference"] = "A"
    score_path = tmp_path / "scores.json"
    key_path = tmp_path / "key.json"
    score_path.write_text(json.dumps(scores), encoding="utf-8")
    key_path.write_text(json.dumps(key), encoding="utf-8")
    result = decode_review_scores(score_path, key_path)
    assert result["completed_items"] == 2
    assert "combined_score" not in result
    assert sum(result["preference_counts"].values()) == 2
    assert all(len(value) == 3 for value in result["dimension_results"].values())


def test_completed_scores_reject_blanks(tmp_path):
    run = _run(tmp_path)
    _, key, scores = build_review_bundle(run, architecture_a="typed_fill", architecture_b="legacy_json", sample_size=1, seed="fixed")
    score_path = tmp_path / "scores.json"
    key_path = tmp_path / "key.json"
    score_path.write_text(json.dumps(scores), encoding="utf-8")
    key_path.write_text(json.dumps(key), encoding="utf-8")
    with pytest.raises(NarrativeReviewError, match="integer 1..5"):
        decode_review_scores(score_path, key_path)


def test_extra_required_architecture_controls_pair_eligibility(tmp_path):
    run = _run(tmp_path)
    rows = [json.loads(line) for line in (run / "results_internal.jsonl").read_text(encoding="utf-8").splitlines()]
    rows.extend((_record("flat_fill", 1), _record("flat_fill", 2)))
    (run / "results_internal.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    bundle, key, _ = build_review_bundle(
        run,
        architecture_a="typed_fill",
        architecture_b="legacy_json",
        sample_size=3,
        seed="fixed",
        required_architectures=("flat_fill",),
    )
    assert bundle["eligible_pairs"] == 2
    assert key["eligibility_architectures"] == ["flat_fill", "legacy_json", "typed_fill"]
