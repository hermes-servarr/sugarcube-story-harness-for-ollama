import json

import pytest

from model_benchmark.config import BenchmarkConfig
from model_benchmark.sandbox_benchmark import (
    SANDBOX_CANARY_IDS,
    SandboxCaseError,
    evaluate_sandbox_case,
    evaluate_sandbox_domain_case,
    execute_sandbox_cases,
    load_sandbox_cases,
    load_sandbox_domain_cases,
    sandbox_corpus_checksums,
    sandbox_corpus_hash,
    select_sandbox_cases,
)


def test_frozen_sandbox_profiles_have_expected_sizes_and_hash():
    cases = load_sandbox_cases()

    assert len(cases) == 4
    assert len(select_sandbox_cases(cases, "sandbox-canary")) == 2
    assert len(select_sandbox_cases(cases, "sandbox-core")) == 4
    assert len(SANDBOX_CANARY_IDS) == len(set(SANDBOX_CANARY_IDS))
    checksums = sandbox_corpus_checksums()
    assert checksums[0] == f"sha256:{sandbox_corpus_hash()}"
    assert len(checksums) == 2


@pytest.mark.parametrize("profile", ["sandbox-canary", "sandbox-core"])
def test_every_sandbox_scenario_clears_all_runtime_gates(profile):
    cases = select_sandbox_cases(load_sandbox_cases(), profile)

    for case in cases:
        categories = evaluate_sandbox_case(case)
        assert [item.name for item in categories] == [
            "choice_eligibility_precision",
            "action_authority",
            "state_delta_correctness",
            "replay_determinism",
            "resource_invariants",
            "sandbox_liveness",
        ]
        assert all(item.passed and item.gating for item in categories), case.id


def test_case_loader_rejects_unknown_fields(tmp_path):
    raw = json.loads((__import__("model_benchmark.sandbox_benchmark", fromlist=["SANDBOX_CASES_PATH"]).SANDBOX_CASES_PATH).read_text(encoding="utf-8"))
    raw[0]["model_may_mutate_state"] = True
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(SandboxCaseError, match="fields"):
        load_sandbox_cases(path)


def test_faction_encounter_and_character_domain_fixtures_pass():
    cases = load_sandbox_domain_cases()

    assert [case["kind"] for case in cases] == ["faction", "encounter", "character"]
    assert all(evaluate_sandbox_domain_case(case)[0].passed for case in cases)


def test_runtime_records_preserve_model_case_seed_and_gate_denominators():
    cfg = BenchmarkConfig(
        models=("fixture-model",), variants=("json",), directions=("A",),
        base_url="http://unused", timeout=1, num_predict=1, temperature=0.0,
        runs=1, benchmark_profile="sandbox-canary",
    )
    cases = select_sandbox_cases(load_sandbox_cases(), "sandbox-canary")

    records = execute_sandbox_cases(cfg, cases)

    assert len(records) == 3
    assert all(record.status == "PASS" for record in records)
    assert all(record.dataset == "sandbox_core" for record in records)
    assert all(len(record.scored_result.category_results) == 6 for record in records[:2])
    assert len(records[-1].scored_result.category_results) == 1
    assert records[0].scored_result.random_seed == str(cases[0].seed)
    assert records[-1].subcategory == "faction"
