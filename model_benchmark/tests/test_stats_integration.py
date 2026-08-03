from types import SimpleNamespace

from model_benchmark.stats import (
    compute_statistics_for_records,
    logical_test_id,
)


def _record(test_id: str, repetition: int, score: float, status: str = "PASS"):
    return SimpleNamespace(
        test_id=test_id,
        repetition=repetition,
        normalized_score=score,
        status=status,
    )


def test_logical_test_id_strips_only_matching_repetition():
    assert logical_test_id(_record("Model_A:compact:A:2", 2, 1.0)) == "Model_A:compact:A"
    assert logical_test_id(_record("case::Model_A::3", 3, 1.0)) == "case::Model_A"
    assert logical_test_id(_record("case:7", 2, 1.0)) == "case:7"


def test_repetitions_are_grouped_into_one_statistic():
    records = [
        _record("Model_A:compact:A:1", 1, 1.0),
        _record("Model_A:compact:A:2", 2, 0.5, "FAIL"),
        _record("Model_A:compact:A:3", 3, 0.0, "FAIL"),
    ]

    stats = compute_statistics_for_records(records)

    assert len(stats) == 1
    assert stats[0].test_id == "Model_A:compact:A"
    assert stats[0].n == 3
    assert stats[0].mean == 0.5
    assert stats[0].outcome_changing is True
