import json

import pytest

from model_benchmark.capability_tests import (
    CapabilityCaseError,
    _build_prompt,
    execute_capability_cases,
    load_cases,
    validate_case,
)
from model_benchmark.config import BenchmarkConfig


def _candidate(**overrides):
    data = {
        "schema_version": 1,
        "id": "CAND-T6-RETRIEVE-XL-02",
        "tier": 6,
        "context_ref": "scifi",
        "context_size": "XL",
        "task_complexity": "K1",
        "distractor_density": "D0",
        "variant": "compact",
        "direction_key": "C",
        "task": "Write a complete passage that states the archive code.",
        "checks": [
            {"check": "sections"},
            {"check": "context_needle", "name": "archive_code"},
            {"check": "min_choices", "count": 2},
        ],
    }
    data.update(overrides)
    return data


def test_core_ladder_has_paired_context_sizes_and_large_harness_case():
    cases = load_cases(candidate_dir=None)
    retrieval = {
        case.context_size
        for case in cases
        if case.id.startswith("T6-RETRIEVE-")
    }

    assert retrieval == {"S", "M", "L", "XL"}
    assert any(
        case.tier == 9
        and case.context_size == "XL"
        and case.task_complexity == "K4"
        for case in cases
    )
    prompts = {
        case.context_size: len(_build_prompt(case))
        for case in cases
        if case.id.startswith("T6-RETRIEVE-")
    }
    assert prompts["S"] < prompts["M"] < prompts["L"] < prompts["XL"]


def test_candidate_schema_rejects_code_fields_and_weak_checks():
    with pytest.raises(CapabilityCaseError, match="unknown fields"):
        validate_case(
            _candidate(command="ollama list"),
            candidate=True,
            source="candidate",
        )

    with pytest.raises(CapabilityCaseError, match="non-trivial"):
        validate_case(
            _candidate(
                checks=[
                    {"check": "sections"},
                    {"check": "contains", "value": "PROSE:"},
                    {"check": "no_markdown"},
                ]
            ),
            candidate=True,
            source="candidate",
        )


def test_loads_valid_candidate_as_separate_source(tmp_path):
    path = tmp_path / "CAND-T6-RETRIEVE-XL-02.json"
    path.write_text(json.dumps(_candidate()), encoding="utf-8")

    cases = load_cases(candidate_dir=tmp_path)

    candidate = cases[-1]
    assert candidate.id == "CAND-T6-RETRIEVE-XL-02"
    assert candidate.source == "candidate"


def test_executes_candidate_with_private_model_only_in_internal_record(monkeypatch):
    case = validate_case(
        _candidate(
            id="CAND-T0-SET-01",
            tier=0,
            context_size="S",
            task_complexity="K1",
            task="Write a complete passage that sets $hasKey and gives two choices.",
            checks=[
                {"check": "sections"},
                {"check": "macro", "name": "set"},
                {"check": "variable", "name": "$hasKey"},
            ],
        ),
        candidate=True,
        source="candidate",
    )
    response = """PROSE:
The key turns. ''Ready.'' <<set $hasKey to true>>

CHOICES:
- Continue | Move onward
- Wait | Stay here

SUMMARY:
The player used the key.
"""
    monkeypatch.setattr(
        "model_benchmark.capability_tests.call_ollama_sync",
        lambda *args, **kwargs: response,
    )
    cfg = BenchmarkConfig(
        models=("private-model",),
        variants=("compact",),
        directions=("A",),
        base_url="http://127.0.0.1:11434",
        timeout=30,
        num_predict=640,
        temperature=0.2,
        runs=1,
    )

    records = execute_capability_cases(cfg, [case])

    assert len(records) == 1
    assert records[0].dataset == "capability_candidate"
    assert records[0].test_id == "private-model:CAND-T0-SET-01:compact:1"
    assert records[0].scored_result.category_results[-1].name == (
        "capability_observables"
    )
