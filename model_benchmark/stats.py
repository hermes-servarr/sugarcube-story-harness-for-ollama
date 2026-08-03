"""Repeated-run statistics for the model benchmark (§15).

Implements mean / median / standard deviation (sample and population),
confidence intervals, variance flags, and sample-size flags using ONLY the
Python standard library (``statistics`` + ``math``). No third-party
dependencies (OQ-6 resolution in ``p1_research.md`` §5: stdlib statistics is
sufficient for this benchmark's small sample sizes).

Design notes
------------
- The canonical summary container is ``RunStatistics`` defined in
  ``model_benchmark/schema.py`` (§3.14 of ``p2_data_structures.md``).
  This module populates it via :func:`compute_run_statistics`.
- Every function here is **pure**: it takes plain numbers and returns plain
  numbers/bools/enums. No I/O, no global state, no side effects.
- Thresholds for the variance/sample-size flags are module-level constants
  (documented below) so callers and tests can inspect or override them.
- For small samples (n < 30) the 95% confidence interval uses the Student's
  t-distribution critical value via a small inline t-table (``_T_CRIT_95``).
  For n >= 30 it falls back to the normal-approximation z-score (1.96), per
  the task spec ("t-distribution approximation or z-score for large samples").
  For n == 1 the CI collapses to the single observation (stddev is undefined;
  we treat it as 0.0 and the CI as [value, value]).
- All numeric results are plain ``float``; ``float('nan')`` is never produced
  for well-formed non-empty input. Empty input raises ``ValueError``.

References
----------
- ``model_benchmark/p1_research.md`` §4.8 (Statistics), §5 OQ-6.
- ``model_benchmark/p2_data_structures.md`` §3.14 (RunStatistics).
"""
from __future__ import annotations

import math
import statistics
from enum import Enum
from typing import Any, Sequence

from model_benchmark.schema import RunStatistics

# ═══════════════════════════════════════════════════════════════════════════
# Flag enum
# ═══════════════════════════════════════════════════════════════════════════


class VarianceFlag(str, Enum):
    """Human-readable variance/instability flags (§15).

    Returned by the flag functions as a set/list and also surfaced as the
    ``variance_flags`` tuple on ``RunStatistics``. Subclassing ``str`` makes
    the enum values directly comparable to plain strings and serializable as
    text without an explicit conversion step.
    """

    HIGH_VARIANCE = "high_variance"
    """Coefficient of variation exceeds the acceptable threshold — results
    are unstable across repetitions."""

    UNSTABLE = "unstable"
    """The spread between min and max (relative to the mean) is large enough
    that the per-repetition outcomes are considered unstable."""

    OUTCOME_CHANGING = "outcome_changing"
    """Pass/fail outcomes flip across repetitions — the same test passes for
    some repetitions and fails for others."""

    INSUFFICIENT_SAMPLE = "insufficient_sample"
    """Sample size is below the minimum threshold for statistical
    significance; the CI and variance flags should be treated with caution."""


# ═══════════════════════════════════════════════════════════════════════════
# Configurable thresholds (module-level constants)
# ═══════════════════════════════════════════════════════════════════════════

#: Coefficient of variation (stddev / |mean|) above which results are flagged
#: as high-variance. A CV of 0.30 means the spread is 30% of the mean — a
#: common heuristic for "unstable" benchmark measurements.
DEFAULT_HIGH_VARIANCE_CV: float = 0.30

#: Relative spread (max - min) / |mean| above which results are flagged as
#: unstable. Distinct from CV because it is sensitive to outliers / extreme
#: repetitions rather than average dispersion.
DEFAULT_UNSTABLE_SPREAD: float = 0.50

#: Minimum number of repetitions required for a statistically meaningful
#: mean/CI. Below this, :func:`flag_insufficient_sample` returns True.
DEFAULT_MIN_SAMPLE_SIZE: int = 5

#: Minimum number of repetitions required before the normal-approximation
#: (z-score) CI is used instead of the t-distribution table. Below this,
#: the t critical value from ``_T_CRIT_95`` is used.
LARGE_SAMPLE_THRESHOLD: int = 30

#: z critical value for a 95% confidence interval under the normal
#: approximation (used when n >= LARGE_SAMPLE_THRESHOLD).
Z_CRIT_95: float = 1.959963984540054

#: Student's t critical values for a 95% two-sided confidence interval,
#: keyed by degrees of freedom (df = n - 1). Covers n = 2..30 (df 1..29).
#: Values are the standard two-tailed t-values at alpha = 0.05. For df > 29
#: the normal approximation (Z_CRIT_95) is used instead.
_T_CRIT_95: dict[int, float] = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.160,
    14: 2.145,
    15: 2.131,
    16: 2.120,
    17: 2.110,
    18: 2.101,
    19: 2.093,
    20: 2.086,
    21: 2.080,
    22: 2.074,
    23: 2.069,
    24: 2.064,
    25: 2.060,
    26: 2.056,
    27: 2.052,
    28: 2.048,
    29: 2.045,
}


# ═══════════════════════════════════════════════════════════════════════════
# Core statistics primitives
# ═══════════════════════════════════════════════════════════════════════════


def mean(values: Sequence[float]) -> float:
    """Arithmetic mean of ``values``.

    Args:
        values: Non-empty sequence of numbers.

    Returns:
        The arithmetic mean.

    Raises:
        ValueError: If ``values`` is empty.
    """
    if not values:
        raise ValueError("mean requires at least one value")
    return statistics.fmean(values)


def median(values: Sequence[float]) -> float:
    """Median (middle value) of ``values``.

    Uses :func:`statistics.median`, which returns the mean of the two middle
    values for an even-length sequence.

    Args:
        values: Non-empty sequence of numbers.

    Returns:
        The median.

    Raises:
        ValueError: If ``values`` is empty.
    """
    if not values:
        raise ValueError("median requires at least one value")
    return statistics.median(values)


def stdev_sample(values: Sequence[float]) -> float:
    """Sample standard deviation (Bessel-corrected, n-1 denominator).

    For a single value the sample standard deviation is undefined; this
    function returns ``0.0`` in that case so callers building a
    ``RunStatistics`` for n=1 do not have to special-case it.

    Args:
        values: Sequence of numbers (n >= 1).

    Returns:
        The sample standard deviation, or ``0.0`` when ``len(values) < 2``.

    Raises:
        ValueError: If ``values`` is empty.
    """
    if not values:
        raise ValueError("stdev_sample requires at least one value")
    if len(values) < 2:
        return 0.0
    return statistics.stdev(values)


def stdev_population(values: Sequence[float]) -> float:
    """Population standard deviation (n denominator).

    Args:
        values: Non-empty sequence of numbers.

    Returns:
        The population standard deviation.

    Raises:
        ValueError: If ``values`` is empty.
    """
    if not values:
        raise ValueError("stdev_population requires at least one value")
    if len(values) < 2:
        return 0.0
    return statistics.pstdev(values)


def confidence_interval_95(
    values: Sequence[float],
) -> tuple[float, float]:
    """95% confidence interval for the mean of ``values``.

    Uses the Student's t-distribution critical value for small samples
    (n < 30) and the normal-approximation z-score (1.96) for large samples,
    per the task spec. For n == 1 the interval collapses to the single
    observation since the standard error is undefined.

    The interval is ``mean ± critical_value * standard_error`` where the
    standard error is ``sample_stddev / sqrt(n)``.

    Args:
        values: Non-empty sequence of numbers.

    Returns:
        A ``(lower, upper)`` tuple of floats. For n == 1 both bounds equal
        the single value.

    Raises:
        ValueError: If ``values`` is empty.
    """
    if not values:
        raise ValueError("confidence_interval_95 requires at least one value")

    n = len(values)
    m = statistics.fmean(values)
    if n == 1:
        return (m, m)

    s = stdev_sample(values)  # 0.0 for n < 2, but n >= 2 here
    se = s / math.sqrt(n)

    if n >= LARGE_SAMPLE_THRESHOLD:
        crit = Z_CRIT_95
    else:
        df = n - 1
        crit = _T_CRIT_95.get(df, Z_CRIT_95)

    margin = crit * se
    return (m - margin, m + margin)


def coefficient_of_variation(values: Sequence[float]) -> float:
    """Coefficient of variation (sample stddev / |mean|).

    A dimensionless measure of relative dispersion. Returns ``0.0`` when the
    mean is exactly zero (to avoid division-by-zero) — in that case the
    spread is considered not meaningfully large relative to the mean.

    Args:
        values: Non-empty sequence of numbers.

    Returns:
        The CV as a non-negative float, or ``0.0`` if the mean is zero.

    Raises:
        ValueError: If ``values`` is empty.
    """
    if not values:
        raise ValueError("coefficient_of_variation requires at least one value")
    m = statistics.fmean(values)
    if m == 0:
        return 0.0
    return abs(stdev_sample(values) / m)


def relative_spread(values: Sequence[float]) -> float:
    """Relative spread: ``(max - min) / |mean|``.

    An outlier-sensitive dispersion measure complementary to the CV. Returns
    ``0.0`` when the mean is zero.

    Args:
        values: Non-empty sequence of numbers.

    Returns:
        The relative spread as a non-negative float.

    Raises:
        ValueError: If ``values`` is empty.
    """
    if not values:
        raise ValueError("relative_spread requires at least one value")
    m = statistics.fmean(values)
    if m == 0:
        return 0.0
    return (max(values) - min(values)) / abs(m)


# ═══════════════════════════════════════════════════════════════════════════
# Pass/fail consistency
# ═══════════════════════════════════════════════════════════════════════════


def pass_rate_consistency(passed: Sequence[bool]) -> float:
    """Fraction of repetitions sharing the majority pass/fail outcome.

    A value of 1.0 means every repetition agrees (all pass or all fail);
    0.5 means the outcomes are split evenly. This is the per-test consistency
    metric from §15.

    Args:
        passed: Sequence of boolean pass/fail outcomes per repetition.

    Returns:
        A float in [0.5, 1.0] — the fraction of repetitions matching the
        majority outcome. Returns 1.0 for an empty sequence (vacuously
        consistent) so that ``RunStatistics`` construction never fails.
    """
    if not passed:
        return 1.0
    n = len(passed)
    pass_count = sum(1 for p in passed if p)
    majority = max(pass_count, n - pass_count)
    return majority / n


# ═══════════════════════════════════════════════════════════════════════════
# Flag functions
# ═══════════════════════════════════════════════════════════════════════════


# TODO(benchmark-upgrade): stats.py — flag_high_variance needs a P3 §3.12
# wrapper.  P3 signature:
#   def flag_high_variance(stats: list[RunStatistics]) -> list[str]:
# The current flag_high_variance(values, threshold) -> bool is a low-level
# helper.  Add a new function `flag_high_variance_from_stats(stats) -> list[str]`
# or rename the P3 interface to avoid collision.  The P3 version inspects
# RunStatistics entries and returns human-readable strings for high-variance
# tests.  Keep the low-level helper as `_flag_high_variance_cv`.
def flag_high_variance(
    values: Sequence[float],
    threshold: float = DEFAULT_HIGH_VARIANCE_CV,
) -> bool:
    """Return True if the coefficient of variation exceeds ``threshold``.

    High CV indicates unstable results across repetitions (§15). The default
    threshold (0.30) flags results whose spread is 30% or more of their mean.

    Args:
        values: Sequence of per-repetition scores.
        threshold: Maximum acceptable coefficient of variation.

    Returns:
        True if ``coefficient_of_variation(values) > threshold``, False
        otherwise. An empty sequence never flags (returns False).
    """
    if not values:
        return False
    return coefficient_of_variation(values) > threshold


def flag_unstable(
    values: Sequence[float],
    threshold: float = DEFAULT_UNSTABLE_SPREAD,
) -> bool:
    """Return True if the relative spread exceeds ``threshold``.

    Unstable means the per-repetition outcomes swing widely (max - min is
    large relative to the mean), indicating outlier-dominated behavior (§15).

    Args:
        values: Sequence of per-repetition scores.
        threshold: Maximum acceptable relative spread.

    Returns:
        True if ``relative_spread(values) > threshold``, False otherwise.
        An empty sequence never flags.
    """
    if not values:
        return False
    return relative_spread(values) > threshold


def flag_outcome_changing(passed: Sequence[bool]) -> bool:
    """Return True if pass/fail outcomes flip across repetitions.

    An "outcome-changing" test (§15) is one that passes for some repetitions
    and fails for others — the binary verdict is not stable.

    Args:
        passed: Sequence of boolean pass/fail outcomes per repetition.

    Returns:
        True if both True and False appear in ``passed`` (i.e. the outcome
        is not unanimous). An empty or single-element sequence never flags.
    """
    if len(passed) < 2:
        return False
    has_pass = any(passed)
    has_fail = any(not p for p in passed)
    return has_pass and has_fail


def flag_insufficient_sample(
    n: int,
    min_samples: int = DEFAULT_MIN_SAMPLE_SIZE,
) -> bool:
    """Return True if the sample size is below ``min_samples``.

    Below the minimum, mean/CI/variance estimates are statistically weak
    and should be treated with caution (§15: "flag insufficient sample
    sizes").

    Args:
        n: The number of repetitions actually collected.
        min_samples: The minimum sample size for statistical significance.

    Returns:
        True if ``n < min_samples``, False otherwise. A non-positive
        ``min_samples`` disables the flag (returns False).
    """
    if min_samples <= 0:
        return False
    return n < min_samples


# ═══════════════════════════════════════════════════════════════════════════
# Aggregate: build a RunStatistics record
# ═══════════════════════════════════════════════════════════════════════════


# TODO(benchmark-upgrade): stats.py — compute_run_statistics is the P3 §3.12
# interface.  P3 signature:
#   def compute_run_statistics(records: list[ResultRecord]) -> list[RunStatistics]:
# Current signature takes (test_id, scores, passed, *) and returns ONE
# RunStatistics.  Add a wrapper that groups records by test_id and calls
# this for each group, returning list[RunStatistics].  Keep this as the
# per-test helper `_compute_single_test_stats`.
def compute_run_statistics(
    test_id: str,
    scores: Sequence[float],
    passed: Sequence[bool],
    *,
    high_variance_cv: float = DEFAULT_HIGH_VARIANCE_CV,
    unstable_spread: float = DEFAULT_UNSTABLE_SPREAD,
    min_sample_size: int = DEFAULT_MIN_SAMPLE_SIZE,
) -> RunStatistics:
    """Compute the full repeated-run statistics for one test (§15).

    Combines the central-tendency, dispersion, CI, consistency, and flag
    computations into a single :class:`RunStatistics` record (defined in
    ``model_benchmark/schema.py`` §3.14).

    Args:
        test_id: Identifier of the test/category/model these stats describe.
        scores: Per-repetition numeric scores (e.g. normalized scores in
            [0.0, 1.0]). Must be non-empty.
        passed: Per-repetition boolean pass/fail outcomes. Must have the
            same length as ``scores``.
        high_variance_cv: Coefficient-of-variation threshold for the
            high-variance flag.
        unstable_spread: Relative-spread threshold for the unstable flag.
        min_sample_size: Minimum sample size for statistical significance.

    Returns:
        A populated :class:`RunStatistics`.

    Raises:
        ValueError: If ``scores`` is empty, or if ``len(scores) !=
            len(passed)``.
    """
    if not scores:
        raise ValueError("compute_run_statistics requires at least one score")
    if len(scores) != len(passed):
        raise ValueError(
            f"scores and passed must have the same length: "
            f"{len(scores)} != {len(passed)}"
        )

    n = len(scores)
    m = mean(scores)
    med = median(scores)
    sd = stdev_sample(scores)
    lo = min(scores)
    hi = max(scores)
    ci_lo, ci_hi = confidence_interval_95(scores)
    consistency = pass_rate_consistency(passed)

    high_var = flag_high_variance(scores, threshold=high_variance_cv)
    unstable = flag_unstable(scores, threshold=unstable_spread)
    changing = flag_outcome_changing(passed)
    insufficient = flag_insufficient_sample(n, min_samples=min_sample_size)

    flag_strs: list[str] = []
    if high_var:
        flag_strs.append(VarianceFlag.HIGH_VARIANCE.value)
    if unstable:
        flag_strs.append(VarianceFlag.UNSTABLE.value)
    if changing:
        flag_strs.append(VarianceFlag.OUTCOME_CHANGING.value)
    if insufficient:
        flag_strs.append(VarianceFlag.INSUFFICIENT_SAMPLE.value)

    return RunStatistics(
        test_id=test_id,
        n=n,
        mean=m,
        median=med,
        stddev=sd,
        min=lo,
        max=hi,
        ci_lower=ci_lo,
        ci_upper=ci_hi,
        pass_rate_consistency=consistency,
        high_variance=high_var,
        unstable=unstable,
        outcome_changing=changing,
        insufficient_sample=insufficient,
        variance_flags=tuple(flag_strs),
    )


def logical_test_id(record: Any) -> str:
    """Return a repetition-independent identity for a result record.

    Current result IDs end in either ``:<repetition>`` (legacy/capability)
    or ``::<repetition>`` (declarative).  Strip that suffix only when it
    agrees with the record's explicit repetition field.
    """
    test_id = str(getattr(record, "test_id", "") or "")
    repetition = getattr(record, "repetition", None)
    if repetition is None:
        return test_id
    suffix = str(repetition)
    for separator in ("::", ":"):
        marker = separator + suffix
        if test_id.endswith(marker):
            return test_id[: -len(marker)]
    return test_id


def compute_statistics_for_records(records: Sequence[Any]) -> list[RunStatistics]:
    """Group repeated records by logical case and compute every statistic."""
    grouped_scores: dict[str, list[float]] = {}
    grouped_passed: dict[str, list[bool]] = {}
    for record in records:
        key = logical_test_id(record)
        if not key:
            continue
        grouped_scores.setdefault(key, []).append(
            float(getattr(record, "normalized_score", getattr(record, "score", 0.0)))
        )
        grouped_passed.setdefault(key, []).append(
            getattr(record, "status", "FAIL") == "PASS"
        )
    return [
        compute_run_statistics(key, scores, grouped_passed[key])
        for key, scores in grouped_scores.items()
    ]
