"""Confidence intervals for distributional metrics using block bootstrap and delta method.

This module implements:
1. Block Bootstrap (primary): Moving block bootstrap to preserve autocorrelation structure.
2. Delta Method (secondary): Asymptotic standard errors for fast approximations.
"""
from __future__ import annotations

import numpy as np

from .analytics import (
    autocorr_sum,
    corrected_sharpe_daily,
    corrected_sharpe_monthly,
    target_downside_deviation,
    sortino_ratio,
    compute_upr,
    compute_omega,
)


# ---------------------------------------------------------------------------
# Delta Method (Asymptotic Standard Errors)
# ---------------------------------------------------------------------------

def delta_method_sharpe(
    daily_returns: np.ndarray,
    n_lags: int = 5,
    periods_per_year: int = 252,
) -> dict:
    """Asymptotic standard error for the Burghardt-Liu corrected Sharpe ratio.
    
    Uses Lo (2002) asymptotic variance formula adjusted for serial correlation.
    SE = sqrt( (1 + 0.5 * SR^2) * factor * 252 / N )
    where factor = 1 + 2 * sum(rho).
    """
    r = np.asarray(daily_returns, dtype=float)
    r = r[np.isfinite(r)]
    n = len(r)
    nan = float("nan")

    if n < 10:
        return {"point": nan, "se": nan, "ci_lower": nan, "ci_upper": nan, "kink_warning": False}

    bl = corrected_sharpe_daily(r, n_lags, periods_per_year)
    sr = bl["sharpe_corrected"]
    rho_sum = bl["rho_sum"]

    if not np.isfinite(sr) or not np.isfinite(rho_sum):
        return {"point": nan, "se": nan, "ci_lower": nan, "ci_upper": nan, "kink_warning": False}

    factor = 1.0 + 2.0 * rho_sum
    if factor <= 0:
        return {"point": sr, "se": nan, "ci_lower": nan, "ci_upper": nan, "kink_warning": False}

    var_sr = (1.0 + 0.5 * sr**2) * factor * periods_per_year / n
    se = float(np.sqrt(var_sr)) if var_sr > 0 else nan

    return {
        "point": sr,
        "se": se,
        "ci_lower": sr - 1.96 * se,
        "ci_upper": sr + 1.96 * se,
        "kink_warning": False,
    }


def _check_kink_proximity(returns: np.ndarray, mar_period: float, epsilon: float = 1e-4) -> bool:
    """Check if >5% of returns are within epsilon of the MAR kink point."""
    if len(returns) == 0:
        return False
    kink_count = np.sum(np.abs(returns - mar_period) < epsilon)
    return bool((kink_count / len(returns)) > 0.05)


def delta_method_sortino(
    daily_returns: np.ndarray,
    mar_annual: float = 0.0,
    periods_per_year: int = 252,
) -> dict:
    """Asymptotic standard error for the Sortino ratio using the delta method."""
    r = np.asarray(daily_returns, dtype=float)
    r = r[np.isfinite(r)]
    n = len(r)
    nan = float("nan")

    if n < 5:
        return {"point": nan, "se": nan, "ci_lower": nan, "ci_upper": nan, "kink_warning": False}

    mar_daily = mar_annual / periods_per_year
    kink_warning = _check_kink_proximity(r, mar_daily)

    # Moments
    x_val = r - mar_daily
    y_val = np.minimum(x_val, 0.0)**2

    mu_x = np.mean(x_val)
    mu_y = np.mean(y_val)

    if mu_y <= 0:
        return {"point": nan, "se": nan, "ci_lower": nan, "ci_upper": nan, "kink_warning": kink_warning}

    var_x = np.var(x_val, ddof=0)
    var_y = np.var(y_val, ddof=0)
    cov_xy = np.mean(x_val * y_val) - mu_x * mu_y

    # Delta method for g(X, Y) = X / sqrt(Y)
    # dg/dX = 1 / sqrt(Y)
    # dg/dY = -0.5 * X / Y^(3/2)
    dg_dx = 1.0 / np.sqrt(mu_y)
    dg_dy = -0.5 * mu_x / (mu_y**1.5)

    var_g = dg_dx**2 * var_x + dg_dy**2 * var_y + 2 * dg_dx * dg_dy * cov_xy
    se_daily = np.sqrt(max(var_g, 0.0) / n)
    se_annual = se_daily * np.sqrt(periods_per_year)

    point = sortino_ratio(r, mar_annual, periods_per_year)

    return {
        "point": point,
        "se": se_annual,
        "ci_lower": point - 1.96 * se_annual,
        "ci_upper": point + 1.96 * se_annual,
        "kink_warning": kink_warning,
    }


def delta_method_upr(
    daily_returns: np.ndarray,
    mar_annual: float = 0.0,
    periods_per_year: int = 252,
) -> dict:
    """Asymptotic standard error for the Upside Potential Ratio."""
    r = np.asarray(daily_returns, dtype=float)
    r = r[np.isfinite(r)]
    n = len(r)
    nan = float("nan")

    if n < 5:
        return {"point": nan, "se": nan, "ci_lower": nan, "ci_upper": nan, "kink_warning": False}

    mar_daily = mar_annual / periods_per_year
    kink_warning = _check_kink_proximity(r, mar_daily)

    x_val = np.maximum(r - mar_daily, 0.0)
    y_val = np.minimum(r - mar_daily, 0.0)**2

    mu_x = np.mean(x_val)
    mu_y = np.mean(y_val)

    if mu_y <= 0:
        return {"point": nan, "se": nan, "ci_lower": nan, "ci_upper": nan, "kink_warning": kink_warning}

    var_x = np.var(x_val, ddof=0)
    var_y = np.var(y_val, ddof=0)
    # Covariance is exact since max(r-MAR,0) * min(r-MAR,0)^2 = 0
    cov_xy = -mu_x * mu_y

    dg_dx = 1.0 / np.sqrt(mu_y)
    dg_dy = -0.5 * mu_x / (mu_y**1.5)

    var_g = dg_dx**2 * var_x + dg_dy**2 * var_y + 2 * dg_dx * dg_dy * cov_xy
    se_daily = np.sqrt(max(var_g, 0.0) / n)
    se_annual = se_daily * np.sqrt(periods_per_year)

    tdd_annual = target_downside_deviation(r, mar_daily) * np.sqrt(periods_per_year)
    point = compute_upr(r, mar_annual, tdd_annual, periods_per_year)

    return {
        "point": point,
        "se": se_annual,
        "ci_lower": point - 1.96 * se_annual,
        "ci_upper": point + 1.96 * se_annual,
        "kink_warning": kink_warning,
    }


def delta_method_omega(
    daily_returns: np.ndarray,
    mar_annual: float = 0.0,
    periods_per_year: int = 252,
) -> dict:
    """Asymptotic standard error for the Omega ratio."""
    r = np.asarray(daily_returns, dtype=float)
    r = r[np.isfinite(r)]
    n = len(r)
    nan = float("nan")

    if n < 5:
        return {"point": nan, "se": nan, "ci_lower": nan, "ci_upper": nan, "kink_warning": False}

    mar_daily = mar_annual / periods_per_year
    kink_warning = _check_kink_proximity(r, mar_daily)

    x_val = np.maximum(r - mar_daily, 0.0)
    y_val = np.maximum(mar_daily - r, 0.0)

    mu_x = np.mean(x_val)
    mu_y = np.mean(y_val)

    if mu_y <= 0:
        point = float("inf") if mu_x > 0 else nan
        return {"point": point, "se": nan, "ci_lower": nan, "ci_upper": nan, "kink_warning": kink_warning}

    var_x = np.var(x_val, ddof=0)
    var_y = np.var(y_val, ddof=0)
    cov_xy = -mu_x * mu_y

    dg_dx = 1.0 / mu_y
    dg_dy = -mu_x / (mu_y**2)

    var_g = dg_dx**2 * var_x + dg_dy**2 * var_y + 2 * dg_dx * dg_dy * cov_xy
    se = np.sqrt(max(var_g, 0.0) / n)

    point = compute_omega(r, mar_annual, periods_per_year)

    return {
        "point": point,
        "se": se,
        "ci_lower": point - 1.96 * se,
        "ci_upper": point + 1.96 * se,
        "kink_warning": kink_warning,
    }


# ---------------------------------------------------------------------------
# Block Bootstrap
# ---------------------------------------------------------------------------

def compute_block_length(n: int) -> int:
    """Politis & Romano style heuristic for moving block bootstrap.
    block_length = max(5, round(n^(1/3)))
    """
    if n <= 0:
        return 1
    return max(5, int(round(n ** (1 / 3))))


def moving_block_bootstrap(
    returns: np.ndarray,
    block_length: int,
    n_resamples: int,
    seed: int | None = None,
) -> np.ndarray:
    """Generate bootstrap samples using a moving block bootstrap.
    
    Returns a 2D array of shape (n_resamples, len(returns)).
    """
    r = np.asarray(returns, dtype=float)
    n = len(r)
    if n == 0:
        return np.empty((n_resamples, 0))

    rng = np.random.default_rng(seed)
    
    if block_length >= n:
        block_length = n

    n_blocks = int(np.ceil(n / block_length))
    # Possible start indices for blocks
    start_indices = rng.integers(0, n - block_length + 1, size=(n_resamples, n_blocks))
    
    resamples = np.empty((n_resamples, n_blocks * block_length), dtype=float)
    for i in range(n_blocks):
        idx = start_indices[:, i]
        for j in range(block_length):
            resamples[:, i * block_length + j] = r[idx + j]

    # Truncate to exact length n
    return resamples[:, :n]


def bootstrap_metrics(
    daily_returns: np.ndarray,
    mar_annual: float = 0.0,
    periods_per_year: int = 252,
    n_resamples: int = 2000,
    block_length: int | None = None,
    ci_level: float = 0.95,
    seed: int | None = None,
) -> dict:
    """Compute block bootstrap distributions and CIs for all 4 metrics."""
    r = np.asarray(daily_returns, dtype=float)
    r = r[np.isfinite(r)]
    n = len(r)
    nan = float("nan")

    if n < 10:
        return {
            "sharpe": {"point": nan, "se": nan, "ci_lower": nan, "ci_upper": nan, "bias": nan},
            "sortino": {"point": nan, "se": nan, "ci_lower": nan, "ci_upper": nan, "bias": nan},
            "upr": {"point": nan, "se": nan, "ci_lower": nan, "ci_upper": nan, "bias": nan},
            "omega": {"point": nan, "se": nan, "ci_lower": nan, "ci_upper": nan, "bias": nan},
        }

    if block_length is None:
        block_length = compute_block_length(n)

    resamples = moving_block_bootstrap(r, block_length, n_resamples, seed=seed)

    sharpe_vals = np.empty(n_resamples, dtype=float)
    sortino_vals = np.empty(n_resamples, dtype=float)
    upr_vals = np.empty(n_resamples, dtype=float)
    omega_vals = np.empty(n_resamples, dtype=float)

    mar_daily = mar_annual / periods_per_year

    for i in range(n_resamples):
        res_r = resamples[i]
        
        # Sharpe
        bl = corrected_sharpe_daily(res_r, periods_per_year=periods_per_year)
        sharpe_vals[i] = bl["sharpe_corrected"]
        
        # TDD (compute once)
        tdd_d = target_downside_deviation(res_r, mar_daily)
        tdd_a = tdd_d * np.sqrt(periods_per_year)
        
        # Sortino
        mean_a = float(res_r.mean()) * periods_per_year
        if np.isfinite(tdd_a) and tdd_a > 0:
            sortino_vals[i] = (mean_a - mar_annual) / tdd_a
        else:
            sortino_vals[i] = nan
            
        # UPR
        upr_vals[i] = compute_upr(res_r, mar_annual, tdd_a, periods_per_year)
        
        # Omega
        omega_vals[i] = compute_omega(res_r, mar_annual, periods_per_year)

    # Compute point estimates on original data
    bl_orig = corrected_sharpe_daily(r, periods_per_year=periods_per_year)
    point_sharpe = bl_orig["sharpe_corrected"]
    point_sortino = sortino_ratio(r, mar_annual, periods_per_year)
    
    tdd_d_orig = target_downside_deviation(r, mar_daily)
    tdd_a_orig = tdd_d_orig * np.sqrt(periods_per_year)
    point_upr = compute_upr(r, mar_annual, tdd_a_orig, periods_per_year)
    point_omega = compute_omega(r, mar_annual, periods_per_year)

    alpha = 1.0 - ci_level
    lower_q = 100 * (alpha / 2)
    upper_q = 100 * (1 - alpha / 2)

    def _stats(vals: np.ndarray, point: float) -> dict:
        v = vals[np.isfinite(vals)]
        if len(v) < n_resamples * 0.5:  # if more than 50% failed
            return {"point": point, "se": nan, "ci_lower": nan, "ci_upper": nan, "bias": nan}
        return {
            "point": point,
            "se": float(np.std(v, ddof=1)),
            "ci_lower": float(np.percentile(v, lower_q)),
            "ci_upper": float(np.percentile(v, upper_q)),
            "bias": float(np.mean(v) - point),
        }

    return {
        "sharpe": _stats(sharpe_vals, point_sharpe),
        "sortino": _stats(sortino_vals, point_sortino),
        "upr": _stats(upr_vals, point_upr),
        "omega": _stats(omega_vals, point_omega),
    }

def evaluate_agreement(boot: dict, delta: dict) -> str:
    """Determine if Bootstrap and Delta methods agree.
    
    Returns "WIDE — caution" if:
    1. The two CIs' midpoints differ by more than 25% of the bootstrap CI width.
    2. OR if one CI's width is more than 1.5x the other's.
    Otherwise "OK".
    """
    if not np.isfinite(boot["ci_lower"]) or not np.isfinite(delta["ci_lower"]):
        return "N/A"
        
    boot_width = boot["ci_upper"] - boot["ci_lower"]
    delta_width = delta["ci_upper"] - delta["ci_lower"]
    
    if boot_width <= 0 or delta_width <= 0:
        return "N/A"
        
    boot_mid = (boot["ci_upper"] + boot["ci_lower"]) / 2.0
    delta_mid = (delta["ci_upper"] + delta["ci_lower"]) / 2.0
    
    if abs(boot_mid - delta_mid) > 0.25 * boot_width:
        return "WIDE — caution"
        
    if boot_width > 1.5 * delta_width or delta_width > 1.5 * boot_width:
        return "WIDE — caution"
        
    return "OK"
