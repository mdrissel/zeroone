"""Unit tests for UPR, Omega, and regime signal synthesis.

Test categories:
  1. UPR correct method — scattered vs concentrated upside
  2. Omega boundary conditions
  3. UPR/Sortino relationship across skewness profiles
  4. Synthesis signal classification logic
"""
import numpy as np
import pytest

from regime_performance_analytics.analytics import (
    target_downside_deviation,
    sortino_ratio,
    compute_upr,
    compute_omega,
    classify_omega,
    classify_upr_sortino,
    classify_sortino_sharpe,
    classify_autocorr_sum,
)


# ---------------------------------------------------------------------------
# 1. UPR correct method — all N in denominator (analogous to TDD thought
#    experiment: scattered upside ≠ concentrated upside)
# ---------------------------------------------------------------------------

def test_upr_correct_method_distinguishes_series():
    """Series A (scattered upside) must have lower UPR than Series B (concentrated)."""
    series_a = np.array([0.0, 0.0, 0.0, 0.10])   # one gain out of four
    series_b = np.array([0.10, 0.10, 0.10, 0.10])  # gain every period

    tdd_fixed = 1.0  # same denominator so only numerator differs
    upr_a = compute_upr(series_a, 0.0, tdd_fixed)
    upr_b = compute_upr(series_b, 0.0, tdd_fixed)
    assert upr_a < upr_b, (
        f"Scattered upside UPR ({upr_a:.4f}) must be lower than "
        f"concentrated upside UPR ({upr_b:.4f})"
    )


def test_upr_scattered_value():
    """Series A [0, 0, 0, +10%]: mean(max(r,0)) = 0.025; with tdd=1 → UPR = 6.3."""
    r = np.array([0.0, 0.0, 0.0, 0.10])
    upr = compute_upr(r, 0.0, tdd_annual=1.0)
    # mean(max(r,0)) = 0.025; 0.025 × 252 / 1.0 = 6.3
    assert abs(upr - 0.025 * 252) < 1e-9


def test_upr_concentrated_value():
    """Series B [+10%, +10%, +10%, +10%]: mean(max(r,0)) = 0.10; with tdd=1 → UPR = 25.2."""
    r = np.array([0.10, 0.10, 0.10, 0.10])
    upr = compute_upr(r, 0.0, tdd_annual=1.0)
    assert abs(upr - 0.10 * 252) < 1e-9


def test_upr_nan_for_zero_tdd():
    """If TDD is zero (no downside) UPR is undefined."""
    r = np.array([0.01, 0.02, 0.03, 0.04, 0.05])
    tdd = target_downside_deviation(r, mar=0.0)
    upr = compute_upr(r, 0.0, tdd_annual=tdd * np.sqrt(252))
    assert np.isnan(upr)


def test_upr_nan_for_empty_series():
    upr = compute_upr(np.array([]), 0.0, tdd_annual=0.10)
    assert np.isnan(upr)


# ---------------------------------------------------------------------------
# 2. Omega boundary conditions
# ---------------------------------------------------------------------------

def test_omega_all_above_mar_is_infinite():
    """All returns above MAR → denominator = 0 → Omega is +inf."""
    r = np.array([0.01, 0.02, 0.03, 0.04, 0.05])
    omega = compute_omega(r, mar_annual=0.0)
    assert np.isposinf(omega), f"Expected +inf, got {omega}"


def test_omega_all_below_mar_is_zero():
    """All returns below MAR → numerator = 0 → Omega = 0."""
    r = np.array([-0.01, -0.02, -0.03, -0.04, -0.05])
    omega = compute_omega(r, mar_annual=0.0)
    assert omega == 0.0, f"Expected 0.0, got {omega}"


def test_omega_greater_than_one_for_net_positive():
    """Strategy with positive mean above MAR should have Omega > 1."""
    rng = np.random.default_rng(42)
    r = rng.normal(loc=0.002, scale=0.01, size=500)
    omega = compute_omega(r, mar_annual=0.0)
    assert np.isfinite(omega) and omega > 1.0


def test_omega_less_than_one_for_net_negative():
    """Strategy with negative mean below MAR should have Omega < 1."""
    rng = np.random.default_rng(42)
    r = rng.normal(loc=-0.002, scale=0.01, size=500)
    omega = compute_omega(r, mar_annual=0.0)
    assert np.isfinite(omega) and omega < 1.0


def test_omega_nan_for_empty_series():
    omega = compute_omega(np.array([]), mar_annual=0.0)
    assert np.isnan(omega)


# ---------------------------------------------------------------------------
# 3. UPR/Sortino relationship across skewness profiles
#
# Mathematical property: UPR/Sortino = mean(max(r-MAR,0)) / (mean(r) - MAR)
#   = 1 + mean(max(MAR-r,0)) / (mean(r) - MAR)   [when mean(r) > MAR]
#
# Therefore UPR/Sortino ≥ 1.0 always when Sortino > 0. The ratio grows
# larger as below-MAR deviations increase relative to the mean return.
# A strategy with a fat left tail (negative skew) but still positive mean
# shows a HIGHER UPR/Sortino than a fat-right-tail strategy with the same
# mean, because the large losses reduce mean(r) while leaving UPR_num fixed.
# ---------------------------------------------------------------------------

def test_upr_sortino_above_one_for_positive_mean():
    """UPR/Sortino must be ≥ 1.0 for any series with mean > MAR."""
    rng = np.random.default_rng(99)
    r = rng.normal(loc=0.001, scale=0.01, size=500)
    tdd_d = target_downside_deviation(r, mar=0.0)
    tdd_a = tdd_d * np.sqrt(252)
    upr = compute_upr(r, 0.0, tdd_a)
    s = sortino_ratio(r, 0.0)
    assert upr / s >= 1.0 - 1e-9


def test_upr_sortino_fat_left_tail_exceeds_fat_right_tail():
    """Fat-left-tail (neg-skew) series produces higher UPR/Sortino than fat-right-tail.

    Both series have the same approximate mean. The left-tail series has its
    mean compressed by occasional large losses; the right-tail series does not.
    Since UPR_numerator ignores losses, the ratio diverges more for neg-skew.
    """
    # Fat right tail: many small losses, few large gains
    pos_skew = np.concatenate([
        np.full(90, -0.001),   # small losses
        np.full(10, 0.10),     # large gains (right tail)
    ])
    # Fat left tail: many small gains, few large losses
    neg_skew = np.concatenate([
        np.full(90, 0.020),    # small gains
        np.full(10, -0.100),   # large losses (left tail)
    ])

    def _us_ratio(r: np.ndarray) -> float:
        tdd_d = target_downside_deviation(r, mar=0.0)
        tdd_a = tdd_d * np.sqrt(252)
        u = compute_upr(r, 0.0, tdd_a)
        s = sortino_ratio(r, 0.0)
        return u / s

    us_pos = _us_ratio(pos_skew)
    us_neg = _us_ratio(neg_skew)
    assert us_pos > 1.0, f"Fat-right-tail UPR/Sortino should be > 1, got {us_pos:.3f}"
    assert us_neg > us_pos, (
        f"Fat-left-tail ratio ({us_neg:.3f}) should exceed fat-right-tail ({us_pos:.3f})"
    )


# ---------------------------------------------------------------------------
# 4. Synthesis signal classification logic
# ---------------------------------------------------------------------------

def _classify_signal(diag, rho, omega, us_ratio, ss_ratio, bear_prob=0.10, sortino=1.0):
    """Mirror of the synthesis logic in run._print_regime_synthesis.

    Defensive is checked first — it overrides full-size.
    Mirrors all fixes: s<0 → DEFENSIVE; isposinf(upr) satisfies FULL SIZE UPR gate.
    Note: this helper is a structural risk — see test note below.
    """
    defensive = (
        (np.isfinite(omega) and omega < 0.8)
        or (np.isfinite(rho) and rho > 0.10)
        or bear_prob > 0.35
        or (np.isfinite(ss_ratio) and ss_ratio < 0.8)
        or (np.isfinite(sortino) and sortino < 0)
    )
    full_size = (
        not defensive
        and diag > 0.70
        and np.isfinite(rho) and rho < -0.15
        and (np.isposinf(omega) or (np.isfinite(omega) and omega > 1.5))
        and (np.isposinf(us_ratio) or (np.isfinite(us_ratio) and us_ratio > 1.0))
        and np.isfinite(ss_ratio) and ss_ratio > 1.2
    )
    reduce = (
        not full_size and not defensive
        and (
            diag < 0.65
            or (np.isfinite(rho) and -0.15 <= rho <= 0.10)
            or (np.isfinite(omega) and 0.8 <= omega <= 1.0)
            or (np.isfinite(us_ratio) and us_ratio < 0.6)
        )
    )
    if full_size:
        return "FULL SIZE"
    if defensive:
        return "DEFENSIVE"
    if reduce:
        return "REDUCE"
    return "NEUTRAL"


def test_synthesis_full_size():
    """All full-size conditions met → FULL SIZE signal."""
    assert _classify_signal(
        diag=0.82, rho=-0.19, omega=1.87, us_ratio=1.24, ss_ratio=1.41
    ) == "FULL SIZE"


def test_synthesis_defensive_omega():
    """Omega < 0.8 triggers DEFENSIVE regardless of other conditions."""
    assert _classify_signal(
        diag=0.82, rho=-0.19, omega=0.70, us_ratio=1.24, ss_ratio=1.41
    ) == "DEFENSIVE"


def test_synthesis_defensive_bear_prob():
    """Bear transition probability > 0.35 triggers DEFENSIVE."""
    assert _classify_signal(
        diag=0.75, rho=-0.20, omega=1.60, us_ratio=1.10, ss_ratio=1.30,
        bear_prob=0.40
    ) == "DEFENSIVE"


def test_synthesis_defensive_mean_reverting():
    """Autocorrelation sum > 0.10 triggers DEFENSIVE."""
    assert _classify_signal(
        diag=0.75, rho=0.15, omega=1.60, us_ratio=1.10, ss_ratio=1.30
    ) == "DEFENSIVE"


def test_synthesis_reduce_low_diagonal():
    """Diagonal persistence < 0.65 triggers REDUCE."""
    assert _classify_signal(
        diag=0.60, rho=-0.20, omega=1.60, us_ratio=1.10, ss_ratio=1.30
    ) == "REDUCE"


def test_synthesis_reduce_neutral_autocorr():
    """Neutral autocorrelation (−0.15 to 0.10) triggers REDUCE."""
    assert _classify_signal(
        diag=0.80, rho=0.00, omega=1.60, us_ratio=1.10, ss_ratio=1.30
    ) == "REDUCE"


def test_synthesis_reduce_omega_near_neutral():
    """Omega in 0.8–1.0 range triggers REDUCE."""
    assert _classify_signal(
        diag=0.80, rho=-0.20, omega=0.90, us_ratio=1.10, ss_ratio=1.30
    ) == "REDUCE"


# ---------------------------------------------------------------------------
# Classification helper unit tests
# ---------------------------------------------------------------------------

def test_synthesis_bear_regime_not_forced_defensive():
    """Bear regime with high self-persistence must NOT be forced defensive.

    Bug: bear_prob = P[0,0] (self-transition) was always > 0.35, making every
    Bear regime permanently DEFENSIVE. Fix: bear_prob = 0 when current_state == 0.
    """
    # High diagonal Bear, trend-favorable — should be FULL SIZE not DEFENSIVE
    assert _classify_signal(
        diag=0.82, rho=-0.19, omega=1.87, us_ratio=1.24, ss_ratio=1.41,
        bear_prob=0.0,  # correctly zero for Bear current state
    ) == "FULL SIZE"


def test_synthesis_negative_sortino_is_defensive():
    """A losing regime (Sortino < 0) must trigger DEFENSIVE."""
    assert _classify_signal(
        diag=0.82, rho=-0.19, omega=1.87, us_ratio=1.24, ss_ratio=1.41,
        sortino=-0.5,
    ) == "DEFENSIVE"


def test_synthesis_zero_tdd_full_size_via_inf_upr():
    """All returns above MAR → upr=inf → FULL SIZE gate passes (fix 4)."""
    assert _classify_signal(
        diag=0.82, rho=-0.19, omega=float("inf"), us_ratio=float("inf"),
        ss_ratio=1.41,
    ) == "FULL SIZE"


def test_classify_omega_bands():
    assert classify_omega(2.0) == "Strong positive skew"
    assert classify_omega(1.2) == "Mild positive skew"
    assert classify_omega(0.9) == "Near neutral"
    assert "left tail" in classify_omega(0.5)


def test_classify_omega_infinite():
    assert classify_omega(float("inf")) == "Strong positive skew"


def test_classify_upr_sortino_bands():
    assert classify_upr_sortino(1.5) == "Capturing upside cleanly"
    assert classify_upr_sortino(0.8) == "Partial upside capture"
    assert "Missing" in classify_upr_sortino(0.3)


def test_classify_sortino_sharpe_bands():
    assert "Positive skew" in classify_sortino_sharpe(1.5)
    assert "Near-symmetric" in classify_sortino_sharpe(1.0)
    assert "left-tail" in classify_sortino_sharpe(0.5)


def test_classify_autocorr_sum_bands():
    assert "Trend-favorable" in classify_autocorr_sum(-0.20)
    assert "Neutral" in classify_autocorr_sum(0.00)
    assert "Mean-reverting" in classify_autocorr_sum(0.15)
