"""Tests for baseline comparison and regression detection.

Covers load_baseline, compare_runs, detect_regressions, threshold constants,
Regression severity, unmatched records, and significance flags.

Enforces P6 invariants INV-CMP1 through INV-CMP9 (comparisons module).
"""
import dataclasses
import json
import os
import tempfile

import pytest

from model_benchmark.comparisons import (
    DEFAULT_OPERATIONAL_THRESHOLD,
    DEFAULT_SCORE_THRESHOLD,
    DEFAULT_STATISTICAL_THRESHOLD,
    ComparisonResult,
    Regression,
    compare_runs,
    detect_regressions,
    load_baseline,
)


# ── Fixtures ────────────────────────────────────────────────────────────────

def _record(test_id, status="PASS", normalized_score=1.0, score=None,
            category="reasoning", runtime_seconds=1.0, total_tokens=100,
            run_id="run-1"):
    """Build a minimal duck-typed record dict for testing."""
    return {
        "test_id": test_id,
        "status": status,
        "normalized_score": normalized_score,
        "score": score if score is not None else normalized_score,
        "category": category,
        "runtime_seconds": runtime_seconds,
        "total_tokens": total_tokens,
        "run_id": run_id,
    }


@pytest.fixture
def baseline_records():
    return [
        _record("t1", status="PASS", normalized_score=0.9),
        _record("t2", status="PASS", normalized_score=0.8),
        _record("t3", status="FAIL", normalized_score=0.3),
        _record("t4", status="PASS", normalized_score=1.0),
    ]


@pytest.fixture
def current_records():
    return [
        _record("t1", status="PASS", normalized_score=0.85),  # slight drop
        _record("t2", status="FAIL", normalized_score=0.2),   # regression
        _record("t3", status="PASS", normalized_score=0.9),   # improvement
        _record("t4", status="PASS", normalized_score=1.0),  # unchanged
    ]


# ── Threshold constants (INV-CMP1) ─────────────────────────────────────────

class TestThresholdConstants:
    def test_default_score_threshold_is_zero(self):
        assert DEFAULT_SCORE_THRESHOLD == 0.0

    def test_statistical_threshold_is_float(self):
        assert isinstance(DEFAULT_STATISTICAL_THRESHOLD, float)
        assert DEFAULT_STATISTICAL_THRESHOLD > 0

    def test_operational_threshold_is_float(self):
        assert isinstance(DEFAULT_OPERATIONAL_THRESHOLD, float)
        assert DEFAULT_OPERATIONAL_THRESHOLD > 0

    def test_operational_gt_statistical(self):
        assert DEFAULT_OPERATIONAL_THRESHOLD >= DEFAULT_STATISTICAL_THRESHOLD


# ── load_baseline (INV-CMP2, INV-CMP3) ─────────────────────────────────────

class TestLoadBaseline:
    def test_load_valid_json(self, tmp_path):
        records = [{"test_id": "t1", "status": "PASS", "normalized_score": 0.9}]
        f = tmp_path / "results_internal.json"
        f.write_text(json.dumps(records))
        result = load_baseline(str(tmp_path))
        assert len(result) == 1
        assert result[0]["test_id"] == "t1"

    def test_load_from_direct_file_path(self, tmp_path):
        records = [{"test_id": "t1"}]
        f = tmp_path / "results_internal.json"
        f.write_text(json.dumps(records))
        result = load_baseline(str(f))
        assert len(result) == 1

    def test_missing_file_returns_empty(self, tmp_path):
        assert load_baseline(str(tmp_path / "nonexistent.json")) == []

    def test_missing_dir_returns_empty(self, tmp_path):
        assert load_baseline(str(tmp_path)) == []

    def test_corrupt_json_returns_empty(self, tmp_path):
        f = tmp_path / "results_internal.json"
        f.write_text("{ this is not valid json }}}")
        assert load_baseline(str(f)) == []

    def test_corrupt_file_returns_empty(self, tmp_path):
        f = tmp_path / "results_internal.json"
        f.write_text("")
        assert load_baseline(str(f)) == []

    def test_dict_with_records_key(self, tmp_path):
        data = {"records": [{"test_id": "t1"}, {"test_id": "t2"}]}
        f = tmp_path / "results_internal.json"
        f.write_text(json.dumps(data))
        result = load_baseline(str(f))
        assert len(result) == 2

    def test_dict_with_results_key(self, tmp_path):
        data = {"results": [{"test_id": "t1"}]}
        f = tmp_path / "results_internal.json"
        f.write_text(json.dumps(data))
        result = load_baseline(str(f))
        assert len(result) == 1

    def test_never_raises(self, tmp_path):
        """load_baseline must never raise on any bad input."""
        assert load_baseline("") == []
        assert load_baseline("/nonexistent/path/to/nowhere") == []

    def test_non_list_payload_returns_empty(self, tmp_path):
        f = tmp_path / "results_internal.json"
        f.write_text(json.dumps({"not_records": 42}))
        assert load_baseline(str(f)) == []

    def test_returns_list(self, tmp_path):
        """INV-CMP3: load_baseline always returns a list."""
        assert isinstance(load_baseline(""), list)
        assert isinstance(load_baseline(str(tmp_path)), list)
        f = tmp_path / "results_internal.json"
        f.write_text(json.dumps([{"test_id": "t1"}]))
        assert isinstance(load_baseline(str(f)), list)


# ── compare_runs (INV-CMP4, INV-CMP5) ───────────────────────────────────────

class TestCompareRuns:
    def test_returns_comparison_result(self, current_records, baseline_records):
        result = compare_runs(current_records, baseline_records)
        assert isinstance(result, ComparisonResult)

    def test_absolute_score_diff(self, current_records, baseline_records):
        result = compare_runs(current_records, baseline_records)
        # t1: 0.85-0.9=-0.05, t2: 0.2-0.8=-0.6, t3: 0.9-0.3=+0.6, t4: 1.0-1.0=0
        # mean = (-0.05 - 0.6 + 0.6 + 0) / 4 = -0.0125
        assert result.absolute_score_diff == pytest.approx(-0.0125, abs=1e-6)

    def test_newly_failing(self, current_records, baseline_records):
        result = compare_runs(current_records, baseline_records)
        # t2 went PASS -> FAIL
        assert "t2" in result.newly_failing
        # t1 stays PASS
        assert "t1" not in result.newly_failing

    def test_newly_passing(self, current_records, baseline_records):
        result = compare_runs(current_records, baseline_records)
        # t3 went FAIL -> PASS
        assert "t3" in result.newly_passing
        # t2 went PASS -> FAIL (not newly passing)
        assert "t2" not in result.newly_passing

    def test_newly_failing_newly_passing_disjoint(self, current_records,
                                                   baseline_records):
        """INV-CMP5: newly_failing and newly_passing are disjoint."""
        result = compare_runs(current_records, baseline_records)
        assert set(result.newly_failing).isdisjoint(result.newly_passing)

    def test_category_regressions(self, current_records, baseline_records):
        result = compare_runs(current_records, baseline_records)
        # t2 is newly failing, category "reasoning"
        assert "reasoning" in result.category_regressions

    def test_runtime_diff(self, current_records, baseline_records):
        result = compare_runs(current_records, baseline_records)
        # all runtimes are 1.0, so diff = 0.0
        assert result.runtime_diff == 0.0

    def test_token_diff(self, current_records, baseline_records):
        result = compare_runs(current_records, baseline_records)
        # all tokens are 100, so diff = 0
        assert result.token_diff == 0

    def test_empty_runs(self):
        """compare_runs([], []) returns valid ComparisonResult."""
        result = compare_runs([], [])
        assert isinstance(result, ComparisonResult)
        assert result.absolute_score_diff == 0.0
        assert result.newly_failing == ()
        assert result.newly_passing == ()

    def test_unmatched_records_excluded_from_score_diff(self):
        """INV-CMP4: unmatched records excluded from score diffs."""
        current = [_record("t1", normalized_score=0.5)]
        baseline = [_record("t2", normalized_score=0.9)]
        result = compare_runs(current, baseline)
        # No matched IDs -> score diff is 0
        assert result.absolute_score_diff == 0.0
        assert result.runtime_diff == 0.0
        assert result.token_diff == 0

    def test_significance_flags(self):
        current = [_record("t1", normalized_score=0.5)]
        baseline = [_record("t1", normalized_score=0.9)]
        result = compare_runs(current, baseline)
        # diff = -0.4, which exceeds both thresholds
        assert result.is_statistically_significant is True
        assert result.is_operationally_significant is True

    def test_significance_flags_below_threshold(self):
        current = [_record("t1", normalized_score=0.98)]
        baseline = [_record("t1", normalized_score=1.0)]
        result = compare_runs(current, baseline)
        # diff = -0.02, below statistical threshold (0.05)
        assert result.is_statistically_significant is False
        assert result.is_operationally_significant is False

    def test_run_ids(self, current_records, baseline_records):
        result = compare_runs(current_records, baseline_records)
        assert result.current_run_id == "run-1"
        assert result.baseline_run_id == "run-1"

    def test_relative_score_diff(self):
        """relative = absolute / baseline_mean."""
        current = [_record("t1", normalized_score=0.45)]
        baseline = [_record("t1", normalized_score=0.5)]
        result = compare_runs(current, baseline)
        # absolute = -0.05, baseline_mean = 0.5, relative = -0.05/0.5 = -0.1
        assert result.relative_score_diff == pytest.approx(-0.1, abs=1e-6)

    def test_relative_score_diff_zero_baseline_mean(self):
        """relative is 0.0 when baseline mean is 0 (div-zero guard)."""
        current = [_record("t1", normalized_score=0.5)]
        baseline = [_record("t1", normalized_score=0.0)]
        result = compare_runs(current, baseline)
        assert result.relative_score_diff == 0.0


# ── detect_regressions (INV-CMP6, INV-CMP7) ─────────────────────────────────

class TestDetectRegressions:
    def test_returns_list_of_regressions(self, current_records, baseline_records):
        comparison = compare_runs(current_records, baseline_records)
        regressions = detect_regressions(comparison, current_records, baseline_records)
        assert isinstance(regressions, list)
        for r in regressions:
            assert isinstance(r, Regression)

    def test_detects_score_regression(self, current_records, baseline_records):
        comparison = compare_runs(current_records, baseline_records)
        regressions = detect_regressions(comparison, current_records, baseline_records)
        # t1: 0.85 vs 0.9 (score dropped by 0.05)
        t1_regs = [r for r in regressions if r.test_id == "t1"]
        assert len(t1_regs) == 1
        assert t1_regs[0].score_diff < 0  # negative = regression

    def test_detects_status_regression(self, current_records, baseline_records):
        comparison = compare_runs(current_records, baseline_records)
        regressions = detect_regressions(comparison, current_records, baseline_records)
        # t2: PASS -> FAIL
        t2_regs = [r for r in regressions if r.test_id == "t2"]
        assert len(t2_regs) == 1
        assert t2_regs[0].baseline_status == "PASS"
        assert t2_regs[0].current_status == "FAIL"

    def test_no_improvement_regression(self, current_records, baseline_records):
        """INV-CMP6: improvements are not regressions."""
        comparison = compare_runs(current_records, baseline_records)
        regressions = detect_regressions(comparison, current_records, baseline_records)
        # t3: FAIL -> PASS (improvement, not regression)
        t3_regs = [r for r in regressions if r.test_id == "t3"]
        assert len(t3_regs) == 0

    def test_score_threshold_filter(self):
        current = [_record("t1", normalized_score=0.99)]
        baseline = [_record("t1", normalized_score=1.0)]
        comparison = compare_runs(current, baseline)
        # With threshold 0.05, a 0.01 drop is NOT a regression
        regressions = detect_regressions(comparison, current, baseline,
                                         score_threshold=0.05)
        assert len(regressions) == 0

    def test_score_threshold_zero_flags_all(self):
        current = [_record("t1", normalized_score=0.99)]
        baseline = [_record("t1", normalized_score=1.0)]
        comparison = compare_runs(current, baseline)
        # With threshold 0.0, a 0.01 drop IS a regression
        regressions = detect_regressions(comparison, current, baseline,
                                         score_threshold=0.0)
        assert len(regressions) == 1

    def test_regression_fields(self, current_records, baseline_records):
        comparison = compare_runs(current_records, baseline_records)
        regressions = detect_regressions(comparison, current_records, baseline_records)
        r = regressions[0]
        assert hasattr(r, "test_id")
        assert hasattr(r, "category")
        assert hasattr(r, "baseline_score")
        assert hasattr(r, "current_score")
        assert hasattr(r, "score_diff")
        assert hasattr(r, "baseline_status")
        assert hasattr(r, "current_status")
        assert hasattr(r, "severity")
        assert hasattr(r, "threshold")

    def test_severity_values(self, current_records, baseline_records):
        """severity in {statistical, operational, minor, version}."""
        comparison = compare_runs(current_records, baseline_records)
        regressions = detect_regressions(comparison, current_records, baseline_records)
        valid_severities = {"statistical", "operational", "minor", "version"}
        for r in regressions:
            assert r.severity in valid_severities

    def test_score_diff_is_current_minus_baseline(self):
        """score_diff = current - baseline (negative = regression)."""
        current = [_record("t1", normalized_score=0.3)]
        baseline = [_record("t1", normalized_score=0.9)]
        comparison = compare_runs(current, baseline)
        regressions = detect_regressions(comparison, current, baseline)
        assert regressions[0].score_diff == pytest.approx(0.3 - 0.9)
        assert regressions[0].score_diff < 0

    def test_empty_inputs(self):
        """detect_regressions(empty) returns []."""
        comparison = compare_runs([], [])
        regressions = detect_regressions(comparison, [], [])
        assert regressions == []

    def test_threshold_recorded_in_regression(self):
        """Regression.threshold = passed score_threshold."""
        current = [_record("t1", normalized_score=0.8)]
        baseline = [_record("t1", normalized_score=0.9)]
        comparison = compare_runs(current, baseline)
        regressions = detect_regressions(comparison, current, baseline,
                                         score_threshold=0.02)
        assert regressions[0].threshold == 0.02

    def test_default_threshold_is_zero(self):
        """default score_threshold is 0.0 (DEFAULT_SCORE_THRESHOLD)."""
        current = [_record("t1", normalized_score=0.99)]
        baseline = [_record("t1", normalized_score=1.0)]
        comparison = compare_runs(current, baseline)
        regressions = detect_regressions(comparison, current, baseline)
        assert regressions[0].threshold == 0.0

    def test_score_threshold_keyword_only(self):
        """INV-CMP7: score_threshold is keyword-only (after *)."""
        current = [_record("t1", normalized_score=0.8)]
        baseline = [_record("t1", normalized_score=0.9)]
        comparison = compare_runs(current, baseline)
        # Positional after * should raise TypeError
        with pytest.raises(TypeError):
            detect_regressions(comparison, current, baseline, 0.05)


# ── P6 invariant checks: dataclass structure (INV-CMP9) ────────────────────

class TestComparisonResultStructure:
    """INV-CMP9: ComparisonResult frozen with exactly 11 fields."""

    EXPECTED_FIELDS = {
        "baseline_run_id", "current_run_id", "absolute_score_diff",
        "relative_score_diff", "newly_failing", "newly_passing",
        "category_regressions", "runtime_diff", "token_diff",
        "is_statistically_significant", "is_operationally_significant",
    }

    def test_is_frozen(self):
        assert dataclasses.is_dataclass(ComparisonResult)
        assert ComparisonResult.__dataclass_params__.frozen

    def test_has_exactly_11_fields(self):
        fields = {f.name for f in dataclasses.fields(ComparisonResult)}
        assert len(fields) == 11
        assert fields == self.EXPECTED_FIELDS


class TestRegressionStructure:
    """INV-CMP9: Regression frozen with exactly 9 fields."""

    EXPECTED_FIELDS = {
        "test_id", "category", "baseline_score", "current_score",
        "score_diff", "baseline_status", "current_status",
        "severity", "threshold",
    }

    def test_is_frozen(self):
        assert dataclasses.is_dataclass(Regression)
        assert Regression.__dataclass_params__.frozen

    def test_has_exactly_9_fields(self):
        fields = {f.name for f in dataclasses.fields(Regression)}
        assert len(fields) == 9
        assert fields == self.EXPECTED_FIELDS


# ── P6 invariant checks: tuple fields immutability (INV-CMP9) ──────────────

class TestTupleFieldsImmutable:
    """INV-CMP9: tuple fields are immutable (frozen dataclass enforcement)."""

    def test_newly_failing_is_tuple(self, current_records, baseline_records):
        result = compare_runs(current_records, baseline_records)
        assert isinstance(result.newly_failing, tuple)

    def test_newly_passing_is_tuple(self, current_records, baseline_records):
        result = compare_runs(current_records, baseline_records)
        assert isinstance(result.newly_passing, tuple)

    def test_category_regressions_is_tuple(self, current_records,
                                            baseline_records):
        result = compare_runs(current_records, baseline_records)
        assert isinstance(result.category_regressions, tuple)

    def test_frozen_instance_raises_on_assignment(self, current_records,
                                                    baseline_records):
        result = compare_runs(current_records, baseline_records)
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.absolute_score_diff = 999.0


# ── P6 invariant checks: score field resolution (INV-CMP8) ────────────────

class TestScoreFieldResolution:
    """INV-CMP8: score field resolution prefers normalized_score then score."""

    def test_prefers_normalized_score(self):
        """A record with both fields uses normalized_score."""
        current = [{
            "test_id": "t1", "status": "PASS",
            "normalized_score": 0.5, "score": 0.9,
        }]
        baseline = [{
            "test_id": "t1", "status": "PASS",
            "normalized_score": 0.9, "score": 0.5,
        }]
        result = compare_runs(current, baseline)
        # Uses normalized_score: 0.5 - 0.9 = -0.4
        assert result.absolute_score_diff == pytest.approx(-0.4, abs=1e-6)

    def test_falls_back_to_score(self):
        """A record with only score (no normalized_score) uses score."""
        current = [{"test_id": "t1", "status": "PASS", "score": 0.5}]
        baseline = [{"test_id": "t1", "status": "PASS", "score": 0.9}]
        result = compare_runs(current, baseline)
        # Uses score: 0.5 - 0.9 = -0.4
        assert result.absolute_score_diff == pytest.approx(-0.4, abs=1e-6)
