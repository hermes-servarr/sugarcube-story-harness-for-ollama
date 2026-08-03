from model_benchmark.profiles import (
    ALL_DIRECTIONS,
    ALL_VARIANTS,
    CANARY_CAPABILITY_IDS,
    CANARY_MATRIX_CASES,
    CORE_MATRIX_CASES,
    resolve_matrix_cases,
)


def test_canary_matrix_is_eight_case_covering_array():
    cases = resolve_matrix_cases("canary", (), ())

    assert cases == CANARY_MATRIX_CASES
    assert len(cases) == 8
    assert {variant for variant, _ in cases} == set(ALL_VARIANTS)
    assert {direction for _, direction in cases} == set(ALL_DIRECTIONS)
    assert all(
        sum(variant == candidate for candidate, _ in cases) == 2
        for variant in ALL_VARIANTS
    )


def test_core_uses_covering_array_and_full_uses_complete_matrix():
    assert resolve_matrix_cases("core", ("compact",), ("A",)) == (
        CORE_MATRIX_CASES
    )
    assert len(CORE_MATRIX_CASES) == 16
    assert {variant for variant, _ in CORE_MATRIX_CASES} == set(ALL_VARIANTS)
    assert {direction for _, direction in CORE_MATRIX_CASES} == set(ALL_DIRECTIONS)
    assert len(resolve_matrix_cases("full", ("compact",), ("A",))) == 32


def test_custom_workload_preserves_requested_cartesian_product():
    assert resolve_matrix_cases("", ("compact", "json"), ("A", "G")) == (
        ("compact", "A"),
        ("compact", "G"),
        ("json", "A"),
        ("json", "G"),
    )


def test_canary_capability_set_has_eight_unique_harness_cases():
    assert len(CANARY_CAPABILITY_IDS) == 8
    assert len(set(CANARY_CAPABILITY_IDS)) == 8
    assert all("HARNESS" in case_id for case_id in CANARY_CAPABILITY_IDS)
