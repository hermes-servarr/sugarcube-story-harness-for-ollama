import json

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT = (
    Path(__file__).parents[2]
    / "skills"
    / "optimize-sugarcube-prompts"
    / "scripts"
    / "summarize_results.py"
)
SPEC = spec_from_file_location("summarize_results", SCRIPT)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_summary_uses_aliases_and_failure_details(tmp_path):
    path = tmp_path / "results.json"
    path.write_text(
        json.dumps(
            [
                {
                    "test_id": "Model_A:json:D:1",
                    "model_alias": "Model_A",
                    "subcategory": "json",
                    "difficulty": "D",
                    "normalized_score": 0.5,
                    "status": "FAIL",
                    "failure_category": "instruction_following",
                    "evaluator_reasoning": "Missing required output.",
                    "scored_result": {
                        "category_results": [
                            {
                                "name": "markup_compliance",
                                "passed": False,
                                "details": "Used Markdown.",
                            }
                        ]
                    },
                },
                {
                    "test_id": "Model_B:json:D:1",
                    "model_alias": "Model_B",
                    "subcategory": "json",
                    "difficulty": "D",
                    "normalized_score": 1.0,
                    "status": "PASS",
                },
                {
                    "test_id": "Model_A:thinking:H:1",
                    "model_alias": "Model_A",
                    "subcategory": "thinking",
                    "difficulty": "H",
                    "normalized_score": 0.25,
                    "status": "FAIL",
                    "failure_category": "instruction_following",
                    "scored_result": {
                        "category_results": [
                            {
                                "name": "thinking_quality",
                                "passed": False,
                                "details": "Category-level planning metrics.",
                            },
                            {
                                "name": "passage_structure",
                                "passed": False,
                                "details": "Final passage was incomplete.",
                            },
                        ]
                    },
                },
            ]
        ),
        encoding="utf-8",
    )

    summary = MODULE.summarize(path)

    assert summary["total_cases"] == 3
    assert summary["pass_rate"] == 0.3333
    assert summary["by_model_alias"]["Model_A"]["passed"] == 0
    assert summary["representative_failures"][0]["failed_categories"][0] == {
        "name": "thinking_quality",
        "details": "Category-level planning metrics.",
    }
    assert summary["thinking_variant"] == {
        "cases": 1,
        "passed": 0,
        "pass_rate": 0.0,
        "mean_score": 0.25,
        "failed_evaluator_categories": {
            "thinking_quality": 1,
            "passage_structure": 1,
        },
        "thinking_quality_failures": 1,
        "final_passage_structure_failures": 1,
    }
    assert summary["candidate_tests"]["cases"] == 0


def test_candidate_results_are_excluded_from_objective(tmp_path):
    path = tmp_path / "results.json"
    path.write_text(
        json.dumps(
            [
                {
                    "test_id": "Model_A:compact:A:1",
                    "model_alias": "Model_A",
                    "dataset": "sugarcube_fixtures",
                    "subcategory": "compact",
                    "difficulty": "A",
                    "normalized_score": 0.0,
                    "status": "FAIL",
                },
                {
                    "test_id": "Model_A:CAND-T0-EASY:compact:1",
                    "model_alias": "Model_A",
                    "dataset": "capability_candidate",
                    "subcategory": "compact",
                    "difficulty": "T0",
                    "normalized_score": 1.0,
                    "status": "PASS",
                },
            ]
        ),
        encoding="utf-8",
    )

    summary = MODULE.summarize(path)

    assert summary["total_cases"] == 1
    assert summary["pass_rate"] == 0.0
    assert summary["candidate_tests"]["cases"] == 1
    assert summary["candidate_tests"]["pass_rate"] == 1.0


def test_context_window_results_are_diagnostic_and_summarized(tmp_path):
    result_path = tmp_path / "results.json"
    result_path.write_text(
        json.dumps(
            [
                {
                    "test_id": "Model_A:base:compact:1",
                    "model_alias": "Model_A",
                    "status": "PASS",
                    "normalized_score": 1.0,
                    "dataset": "capability_core",
                },
                {
                    "test_id": "Model_A:CTX-4096:plain_text:1",
                    "model_alias": "Model_A",
                    "status": "PASS",
                    "normalized_score": 1.0,
                    "dataset": "capability_context_window",
                    "split": "num_ctx_4096",
                    "input_tokens": 3900,
                    "runtime_seconds": 1.5,
                },
                {
                    "test_id": "Model_A:CTX-8192:plain_text:1",
                    "model_alias": "Model_A",
                    "status": "FAIL",
                    "normalized_score": 0.5,
                    "dataset": "capability_context_window",
                    "split": "num_ctx_8192",
                    "input_tokens": 8150,
                    "runtime_seconds": 2.5,
                },
            ]
        ),
        encoding="utf-8",
    )

    summary = MODULE.summarize(result_path)

    assert summary["total_cases"] == 1
    context = summary["context_window"]
    assert context["diagnostic_only"] is True
    assert context["cases"] == 2
    assert context["configured_num_ctx_levels"] == [4096, 8192]
    model = context["by_model_alias"]["Model_A"]
    assert model["max_accepted_num_ctx"] == 8192
    assert model["max_full_retrieval_num_ctx"] == 4096
    assert model["accepted_at_least_configured_max"] is True
    assert model["retrieved_at_least_configured_max"] is False


def test_plain_text_results_are_reported_by_context_profile(tmp_path):
    path = tmp_path / "results.json"
    path.write_text(
        json.dumps(
            [
                {
                    "test_id": "Model_A:T6-PLAIN-TINY-XL:compact:1",
                    "model_alias": "Model_A",
                    "dataset": "capability_core",
                    "subcategory": "plain_text",
                    "difficulty": "T6",
                    "split": "XL-K1-D0",
                    "normalized_score": 1.0,
                    "status": "PASS",
                }
            ]
        ),
        encoding="utf-8",
    )

    summary = MODULE.summarize(path)

    assert summary["plain_text"]["cases"] == 1
    assert summary["plain_text"]["pass_rate"] == 1.0
    assert summary["plain_text"]["by_context_profile"]["XL-K1-D0"]["passed"] == 1


def test_conversation_layout_reports_failed_signed_checks(tmp_path):
    path = tmp_path / "results.json"
    path.write_text(
        json.dumps(
            [
                {
                    "test_id": "Model_A:T8-CONVERSATION-XL:full:1",
                    "model_alias": "Model_A",
                    "dataset": "capability_core",
                    "subcategory": "full",
                    "difficulty": "T8",
                    "split": "XL-K3-D1",
                    "normalized_score": 0.5,
                    "status": "FAIL",
                    "scored_result": {
                        "category_results": [
                            {
                                "name": "capability_observables",
                                "passed": False,
                                "evidence": [
                                    "conversation_layout=pass",
                                    "min_dialogue_turns=fail",
                                    "mc_inner_monologue=fail",
                                ],
                            }
                        ]
                    },
                }
            ]
        ),
        encoding="utf-8",
    )

    summary = MODULE.summarize(path)

    assert summary["conversation_layout"]["cases"] == 1
    assert summary["conversation_layout"]["failed_checks"] == {
        "min_dialogue_turns": 1,
        "mc_inner_monologue": 1,
    }
    assert summary["conversation_layout"]["by_variant"]["full"]["passed"] == 0


def test_writing_style_cases_are_summarized_separately(tmp_path):
    path = tmp_path / "results.json"
    path.write_text(
        json.dumps(
            [
                {
                    "test_id": "Model_A:T2-STYLE-CANT-COMPACT:compact:1",
                    "model_alias": "Model_A",
                    "dataset": "capability_core",
                    "subcategory": "compact",
                    "difficulty": "T2",
                    "split": "S-K2-D0",
                    "normalized_score": 0.66,
                    "status": "FAIL",
                    "scored_result": {
                        "category_results": [
                            {
                                "name": "capability_observables",
                                "passed": False,
                                "evidence": [
                                    "dialogue_slang=pass",
                                    "slang_confined_to_dialogue=fail",
                                    "banned_register=fail",
                                ],
                            }
                        ]
                    },
                },
                {
                    "test_id": "Model_A:T8-CONVERSATION-XL:full:1",
                    "model_alias": "Model_A",
                    "dataset": "capability_core",
                    "subcategory": "full",
                    "difficulty": "T8",
                    "split": "XL-K3-D1",
                    "normalized_score": 1.0,
                    "status": "PASS",
                },
            ]
        ),
        encoding="utf-8",
    )

    summary = MODULE.summarize(path)

    assert summary["writing_style"]["cases"] == 1
    assert summary["writing_style"]["pass_rate"] == 0.0
    assert summary["writing_style"]["failed_checks"] == {
        "slang_confined_to_dialogue": 1,
        "banned_register": 1,
    }
    assert summary["writing_style"]["by_context_profile"]["S-K2-D0"]["cases"] == 1
    assert summary["conversation_layout"]["cases"] == 1
