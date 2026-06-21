"""Tests for confidence intervals and estimation uncertainty."""
from __future__ import annotations

import numpy as np
import pytest

from regime_performance_analytics.analytics import target_downside_deviation
from regime_performance_analytics.ci import (
    bootstrap_metrics,
    delta_method_sharpe,
    delta_method_sortino,
    moving_block_bootstrap,
    evaluate_agreement,
)
from regime_performance_analytics.run import _print_confidence_intervals_section


def test_known_distribution_coverage():
    """1. Known-distribution sanity check (coverage test).
    
    Generate synthetic returns from a known normal distribution.
    True annual Sharpe should be roughly within the 95% CI 95% of the time.
    We just test that a single large sample's CI contains the true value.
    """
    np.random.seed(42)
    # Mean 0.05/252, Vol 0.15/sqrt(252) => Annual Sharpe ~ 0.333
    mu_daily = 0.05 / 252
    vol_daily = 0.15 / np.sqrt(252)
    true_sharpe = 0.05 / 0.15
    
    # Generate 5 years of daily returns
    returns = np.random.normal(mu_daily, vol_daily, size=252 * 5)
    
    boot = bootstrap_metrics(returns, n_resamples=500, seed=42)
    sharpe_ci = boot["sharpe"]
    
    assert sharpe_ci["ci_lower"] <= true_sharpe <= sharpe_ci["ci_upper"], (
        f"True Sharpe {true_sharpe} outside CI [{sharpe_ci['ci_lower']}, {sharpe_ci['ci_upper']}]"
    )
    
    delta = delta_method_sharpe(returns)
    assert delta["ci_lower"] <= true_sharpe <= delta["ci_upper"]


def test_block_bootstrap_preserves_autocorrelation():
    """2. Block bootstrap preserves autocorrelation vs naive i.i.d."""
    np.random.seed(123)
    # Generate AR(1) process with negative autocorrelation
    n = 1000
    rho = -0.4
    returns = np.zeros(n)
    eps = np.random.normal(0, 0.01, n)
    for i in range(1, n):
        returns[i] = rho * returns[i-1] + eps[i]
        
    def autocorr_sum_1(arr):
        return np.corrcoef(arr[:-1], arr[1:])[0, 1]
        
    orig_ac = autocorr_sum_1(returns)
    
    # Block bootstrap (block size > 1)
    res_block = moving_block_bootstrap(returns, block_length=10, n_resamples=50, seed=123)
    ac_block = np.mean([autocorr_sum_1(r) for r in res_block])
    
    # Naive bootstrap (block size = 1)
    res_naive = moving_block_bootstrap(returns, block_length=1, n_resamples=50, seed=123)
    ac_naive = np.mean([autocorr_sum_1(r) for r in res_naive])
    
    # Block should preserve the negative AC better than naive (which should be ~0)
    assert ac_block < -0.1, f"Block bootstrap lost AC: {ac_block}"
    assert abs(ac_naive) < 0.1, f"Naive bootstrap AC not zero: {ac_naive}"
    assert abs(ac_block - orig_ac) < abs(ac_naive - orig_ac)


def test_kink_proximity_warning():
    """3. Kink-proximity warning fires correctly."""
    np.random.seed(42)
    
    # Data tightly clustered around MAR (0.0)
    clustered = np.random.normal(0.0, 1e-5, 100)
    delta = delta_method_sortino(clustered, mar_annual=0.0)
    assert delta["kink_warning"] is True
    
    # Data far from MAR
    far = np.random.normal(0.05, 0.01, 100)
    delta2 = delta_method_sortino(far, mar_annual=0.0)
    assert delta2["kink_warning"] is False


def test_agreement_classification():
    """4. Agreement classification logic."""
    # Case 1: OK
    boot_ok = {"ci_lower": 1.0, "ci_upper": 2.0}
    delta_ok = {"ci_lower": 1.05, "ci_upper": 1.95}
    assert evaluate_agreement(boot_ok, delta_ok) == "OK"
    
    # Case 2: WIDE (midpoints differ by > 25% of boot width)
    # boot width = 1.0. 25% is 0.25.
    boot_shift = {"ci_lower": 1.0, "ci_upper": 2.0}  # mid=1.5
    delta_shift = {"ci_lower": 1.5, "ci_upper": 2.5} # mid=2.0
    assert evaluate_agreement(boot_shift, delta_shift) == "WIDE — caution"
    
    # Case 3: WIDE (widths differ by > 1.5x)
    boot_wide = {"ci_lower": 1.0, "ci_upper": 3.0}  # width 2.0
    delta_narrow = {"ci_lower": 1.5, "ci_upper": 2.0} # width 0.5
    assert evaluate_agreement(boot_wide, delta_narrow) == "WIDE — caution"


def test_n_based_confidence_flags(capsys):
    """5. N-based confidence flag thresholds."""
    mar_annual = 0.0
    
    def run_with_n(n):
        returns = np.random.normal(0.001, 0.01, n)
        result = {
            "daily_returns_net": returns,
            "state_series": np.zeros(n)
        }
        _print_confidence_intervals_section(
            result, ["State0"], mar_annual, 
            ci_method="none", n_bootstrap=10, 
            block_length=2, ci_level=0.95
        )
        return capsys.readouterr().out
        
    out_low = run_with_n(20)
    assert "LOW CONFIDENCE" in out_low
    assert "MODERATE CONFIDENCE" not in out_low
    
    out_mod = run_with_n(50)
    assert "LOW CONFIDENCE" not in out_mod
    assert "MODERATE CONFIDENCE" in out_mod
    
    out_high = run_with_n(120)
    assert "HIGHER CONFIDENCE" in out_high
