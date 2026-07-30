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
            ]
        ),
        encoding="utf-8",
    )

    summary = MODULE.summarize(path)

    assert summary["total_cases"] == 2
    assert summary["pass_rate"] == 0.5
    assert summary["by_model_alias"]["Model_A"]["passed"] == 0
    assert summary["representative_failures"][0]["failed_categories"][0] == {
        "name": "markup_compliance",
        "details": "Used Markdown.",
    }
