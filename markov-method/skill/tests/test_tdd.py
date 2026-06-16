"""Unit tests for the correct vs incorrect Sortino / TDD calculation.

Red Rock Capital thought experiment (Brian Rom, 2008):
  Two series with identical total loss magnitude but different distribution:

  Series A: [0, 0, 0, -10%]  — one bad period out of four
  Series B: [-10%, -10%, -10%, -10%]  — persistently bad

  Series B has higher downside risk. A correct TDD must distinguish them.
  The industry error (std of negative-only observations) gives the same
  TDD for both, making it impossible to compare strategies on this axis.
"""
import numpy as np
import pytest

from regime_performance_analytics.analytics import (
    target_downside_deviation,
    _incorrect_tdd,
    sortino_ratio,
    skew_classification,
)


# ---------------------------------------------------------------------------
# Red Rock thought experiment
# ---------------------------------------------------------------------------

SERIES_A = np.array([0.0, 0.0, 0.0, -0.10])   # one bad period
SERIES_B = np.array([-0.10, -0.10, -0.10, -0.10])  # persistently bad


def test_correct_tdd_distinguishes_series():
    """Correct TDD: Series A has lower downside risk than Series B."""
    tdd_a = target_downside_deviation(SERIES_A, mar=0.0)
    tdd_b = target_downside_deviation(SERIES_B, mar=0.0)
    assert tdd_a < tdd_b, (
        f"Correct TDD must rank Series A ({tdd_a:.4f}) < Series B ({tdd_b:.4f})"
    )


def test_correct_tdd_series_a_value():
    """Series A: TDD = sqrt(0.01/4) = 0.05 exactly."""
    tdd_a = target_downside_deviation(SERIES_A, mar=0.0)
    assert abs(tdd_a - 0.05) < 1e-10, f"Expected 0.05, got {tdd_a}"


def test_correct_tdd_series_b_value():
    """Series B: TDD = sqrt(0.04/4) = 0.10 exactly."""
    tdd_b = target_downside_deviation(SERIES_B, mar=0.0)
    assert abs(tdd_b - 0.10) < 1e-10, f"Expected 0.10, got {tdd_b}"


def test_incorrect_tdd_cannot_distinguish():
    """Industry error: same TDD for both series — this is the flaw."""
    tdd_a = _incorrect_tdd(SERIES_A, mar=0.0)
    tdd_b = _incorrect_tdd(SERIES_B, mar=0.0)
    # Both equal 0.10 because the incorrect method uses N_negative in denominator
    assert abs(tdd_a - tdd_b) < 1e-10, (
        f"Incorrect TDD should give same value for both series "
        f"(A={tdd_a:.4f}, B={tdd_b:.4f}) to demonstrate the flaw"
    )


def test_correct_vs_incorrect_differ_for_series_a():
    """Correct and incorrect methods disagree on Series A — the whole point."""
    correct = target_downside_deviation(SERIES_A, mar=0.0)
    incorrect = _incorrect_tdd(SERIES_A, mar=0.0)
    assert correct < incorrect, (
        f"Correct TDD ({correct:.4f}) should be lower than incorrect ({incorrect:.4f}) "
        f"for a series with many neutral periods"
    )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_tdd_all_positive_returns():
    """All returns above MAR → TDD = 0."""
    r = np.array([0.01, 0.02, 0.03, 0.05])
    tdd = target_downside_deviation(r, mar=0.0)
    assert tdd == 0.0


def test_tdd_empty_series():
    tdd = target_downside_deviation(np.array([]), mar=0.0)
    assert np.isnan(tdd)


def test_tdd_with_nonzero_mar():
    """MAR shifts what counts as underperformance."""
    r = np.array([0.01, 0.02, 0.03])
    # With MAR=0.025: only 0.01 and 0.02 underperform
    tdd_high_mar = target_downside_deviation(r, mar=0.025)
    tdd_zero_mar = target_downside_deviation(r, mar=0.0)
    assert tdd_high_mar > tdd_zero_mar


def test_tdd_nan_ignored():
    """NaN values in the series are dropped."""
    r = np.array([0.0, np.nan, -0.10, 0.0])
    tdd = target_downside_deviation(r, mar=0.0)
    # After dropping NaN: [0, -0.10, 0] → underperformances²: [0, 0.01, 0] → mean=0.01/3
    expected = np.sqrt(0.01 / 3)
    assert abs(tdd - expected) < 1e-10


# ---------------------------------------------------------------------------
# Sortino ratio
# ---------------------------------------------------------------------------

def test_sortino_positive_for_positive_mean():
    """Strategy with positive mean above MAR should have positive Sortino."""
    rng = np.random.default_rng(42)
    r = rng.normal(loc=0.001, scale=0.01, size=500)
    s = sortino_ratio(r, mar_annual=0.0)
    assert s > 0


def test_sortino_negative_for_negative_mean():
    rng = np.random.default_rng(42)
    r = rng.normal(loc=-0.001, scale=0.01, size=500)
    s = sortino_ratio(r, mar_annual=0.0)
    assert s < 0


def test_sortino_nan_for_short_series():
    s = sortino_ratio(np.array([0.01, -0.01, 0.005]), mar_annual=0.0)
    assert np.isnan(s)


# ---------------------------------------------------------------------------
# Skewness classification
# ---------------------------------------------------------------------------

def test_skew_positive():
    # Sortino > 1.2 × Sharpe → positive skew
    result = skew_classification(sortino=1.5, corrected_sharpe=1.0)
    assert "positive skew" in result


def test_skew_symmetric():
    result = skew_classification(sortino=1.0, corrected_sharpe=1.0)
    assert "near-symmetric" in result


def test_skew_negative():
    result = skew_classification(sortino=0.5, corrected_sharpe=1.0)
    assert "negative skew" in result


def test_skew_nan_inputs():
    result = skew_classification(float("nan"), 1.0)
    assert "insufficient" in result
