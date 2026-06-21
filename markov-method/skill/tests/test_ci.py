"""Tests for confidence intervals and estimation uncertainty."""
from __future__ import annotations

import numpy as np
import pytest

from regime_performance_analytics.analytics import target_downside_deviation
from regime_performance_analytics.ci import (
    bootstrap_metrics,
    delta_method_sharpe,
    delta_method_sortino,
    generate_circular_blocks,
    _hac_covariance_2d,
    evaluate_agreement,
)
from regime_performance_analytics.run import _print_confidence_intervals_section


def test_known_distribution_coverage():
    """1. Known-distribution sanity check (coverage test)."""
    np.random.seed(42)
    # Mean 0.05/252, Vol 0.15/sqrt(252) => Annual Sharpe ~ 0.333
    mu_daily = 0.05 / 252
    vol_daily = 0.15 / np.sqrt(252)
    true_sharpe = 0.05 / 0.15
    
    returns = np.random.normal(mu_daily, vol_daily, size=252 * 5)
    
    boot = bootstrap_metrics(returns, n_resamples=500, seed=42)
    sharpe_ci = boot["sharpe"]
    
    assert sharpe_ci["ci_lower"] <= true_sharpe <= sharpe_ci["ci_upper"]
    
    delta = delta_method_sharpe(returns)
    assert delta["ci_lower"] <= true_sharpe <= delta["ci_upper"]


def test_circular_block_bootstrap_wrap():
    """2. Test circular block wrap-around logic."""
    np.random.seed(123)
    # N=10, block length=4
    n = 10
    indices = generate_circular_blocks(n, block_length=4, n_resamples=10, seed=123)
    
    assert indices.shape == (10, n)
    # All indices must be valid
    assert np.all((indices >= 0) & (indices < n))
    
    # Within each block of 4, the difference between adjacent indices should be 1,
    # except when it wraps around (diff will be -(n-1))
    for resample in indices:
        # First block is first 4 elements
        block = resample[:4]
        diffs = np.diff(block)
        # diff is either 1 or -9
        assert np.all(np.isin(diffs, [1, -(n-1)]))


def test_hac_vs_naive_variance():
    """3. Test HAC covariance produces higher variance under positive AC."""
    np.random.seed(123)
    n = 1000
    rho = 0.5
    returns = np.zeros(n)
    eps = np.random.normal(0, 0.01, n)
    for i in range(1, n):
        returns[i] = rho * returns[i-1] + eps[i]
        
    x = returns
    y = np.minimum(returns, 0)**2
    
    cov_hac = _hac_covariance_2d(x, y, max_lag=5)
    
    # Naive i.i.d covariance of means
    var_x_naive = np.var(x, ddof=0) / n
    var_y_naive = np.var(y, ddof=0) / n
    
    # Under strong positive AC, HAC variance should be substantially larger
    assert cov_hac[0, 0] > var_x_naive * 1.5
    assert cov_hac[1, 1] > var_y_naive * 1.5


def test_omega_inf_handling():
    """4. Test Omega handles zero downside (inf) correctly without poisoning."""
    # Returns always strictly positive -> no downside -> Omega = inf
    returns = np.random.uniform(0.01, 0.05, 50)
    
    boot = bootstrap_metrics(returns, n_resamples=100, seed=42)
    omega = boot["omega"]
    
    assert omega["point"] == np.inf
    assert np.isnan(omega["se"])
    assert np.isnan(omega["bias"])
    # Percentiles should safely report inf
    assert omega["ci_upper"] == np.inf


def test_kink_proximity_warning():
    """5. Kink-proximity warning fires correctly."""
    np.random.seed(42)
    clustered = np.random.normal(0.0, 1e-5, 100)
    delta = delta_method_sortino(clustered, mar_annual=0.0)
    assert delta["kink_warning"] is True
    
    far = np.random.normal(0.05, 0.01, 100)
    delta2 = delta_method_sortino(far, mar_annual=0.0)
    assert delta2["kink_warning"] is False


def test_agreement_classification():
    """6. Agreement classification logic."""
    boot_ok = {"ci_lower": 1.0, "ci_upper": 2.0}
    delta_ok = {"ci_lower": 1.05, "ci_upper": 1.95}
    assert evaluate_agreement(boot_ok, delta_ok) == "OK"
    
    boot_shift = {"ci_lower": 1.0, "ci_upper": 2.0}
    delta_shift = {"ci_lower": 1.5, "ci_upper": 2.5}
    assert evaluate_agreement(boot_shift, delta_shift) == "WIDE — caution"
    
    boot_wide = {"ci_lower": 1.0, "ci_upper": 3.0}
    delta_narrow = {"ci_lower": 1.5, "ci_upper": 2.0}
    assert evaluate_agreement(boot_wide, delta_narrow) == "WIDE — caution"
    
    # Inf upper bound handling
    boot_inf = {"ci_lower": 1.0, "ci_upper": np.inf}
    delta_inf = {"ci_lower": 1.0, "ci_upper": np.inf}
    # Should be OK or WIDE depending on logic (if both are inf it's N/A or WIDE)
    # The code currently says if boot_width is inf and delta_width is NOT inf -> WIDE
    assert evaluate_agreement(boot_inf, delta_ok) == "WIDE — caution"


def test_n_based_confidence_flags(capsys):
    """7. N-based confidence flag thresholds."""
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
