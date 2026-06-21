"""Confidence intervals for distributional metrics using block bootstrap and delta method.

This module implements:
1. Block Bootstrap (primary): Circular moving block bootstrap with vectorized logic.
2. Delta Method (secondary): Asymptotic standard errors with HAC adjustments.
"""
from __future__ import annotations

import numpy as np

from .analytics import (
    autocorr_sum,
    corrected_sharpe_daily,
    target_downside_deviation,
    sortino_ratio,
    compute_upr,
    compute_omega,
)


# ---------------------------------------------------------------------------
# Helpers for HAC Variance-Covariance
# ---------------------------------------------------------------------------

def _hac_covariance_2d(x: np.ndarray, y: np.ndarray, max_lag: int = 5) -> np.ndarray:
    """Compute Newey-West (HAC) covariance matrix for sample means of X and Y.
    
    Args:
        x: 1D array of observations for variable 1
        y: 1D array of observations for variable 2
        max_lag: maximum number of lags for the Bartlett kernel
        
    Returns:
        2x2 covariance matrix of the sample means of X and Y.
    """
    n = len(x)
    mu_x = np.mean(x)
    mu_y = np.mean(y)
    
    dev_x = x - mu_x
    dev_y = y - mu_y
    
    # 0-th lag (contemporaneous covariance)
    omega_00 = np.mean(dev_x * dev_x)
    omega_11 = np.mean(dev_y * dev_y)
    omega_01 = np.mean(dev_x * dev_y)
    
    # Cross-autocovariances
    sum_00 = 0.0
    sum_11 = 0.0
    sum_01 = 0.0
    
    for lag in range(1, max_lag + 1):
        weight = 1.0 - lag / (max_lag + 1.0)  # Bartlett kernel
        # cov(X_t, X_{t-lag})
        c_00 = np.mean(dev_x[lag:] * dev_x[:-lag])
        c_11 = np.mean(dev_y[lag:] * dev_y[:-lag])
        # cov(X_t, Y_{t-lag}) + cov(Y_t, X_{t-lag})
        c_01 = np.mean(dev_x[lag:] * dev_y[:-lag]) + np.mean(dev_y[lag:] * dev_x[:-lag])
        
        sum_00 += weight * c_00
        sum_11 += weight * c_11
        sum_01 += weight * c_01
        
    lr_var_x = omega_00 + 2.0 * sum_00
    lr_var_y = omega_11 + 2.0 * sum_11
    lr_cov_xy = omega_01 + sum_01
    
    # Return covariance matrix of the sample *means* (divide by N)
    return np.array([
        [lr_var_x / n, lr_cov_xy / n],
        [lr_cov_xy / n, lr_var_y / n]
    ])


# ---------------------------------------------------------------------------
# Delta Method (Asymptotic Standard Errors)
# ---------------------------------------------------------------------------

def delta_method_sharpe(
    daily_returns: np.ndarray,
    n_lags: int = 5,
    periods_per_year: int = 252,
) -> dict:
    """Asymptotic standard error for the Burghardt-Liu corrected Sharpe ratio.
    
    Corrected SE formula where the autocorrelation factor cancels out of the leading 
    term, preventing massive over/under-statement of variance.
    SE = sqrt( (252 / N) * (1 + 0.5 * (factor / 252) * sr**2) )
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

    # Asymptotic variance for the *annualised corrected* Sharpe
    var_sr = (periods_per_year / n) * (1.0 + 0.5 * (factor / periods_per_year) * sr**2)
    se = float(np.sqrt(max(var_sr, 0.0)))

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
    """Asymptotic standard error for the Sortino ratio using the HAC delta method."""
    r = np.asarray(daily_returns, dtype=float)
    r = r[np.isfinite(r)]
    n = len(r)
    nan = float("nan")

    if n < 5:
        return {"point": nan, "se": nan, "ci_lower": nan, "ci_upper": nan, "kink_warning": False}

    mar_daily = mar_annual / periods_per_year
    kink_warning = _check_kink_proximity(r, mar_daily)

    x_val = r - mar_daily
    y_val = np.minimum(x_val, 0.0)**2

    mu_x = np.mean(x_val)
    mu_y = np.mean(y_val)

    if mu_y <= 0:
        return {"point": nan, "se": nan, "ci_lower": nan, "ci_upper": nan, "kink_warning": kink_warning}

    # HAC covariance matrix for sample means
    cov_mat = _hac_covariance_2d(x_val, y_val, max_lag=5)
    var_x_mean, cov_xy_mean = cov_mat[0, 0], cov_mat[0, 1]
    var_y_mean = cov_mat[1, 1]

    # Delta method for g(X, Y) = X / sqrt(Y)
    dg_dx = 1.0 / np.sqrt(mu_y)
    dg_dy = -0.5 * mu_x / (mu_y**1.5)

    var_g = dg_dx**2 * var_x_mean + dg_dy**2 * var_y_mean + 2 * dg_dx * dg_dy * cov_xy_mean
    se_daily = np.sqrt(max(var_g, 0.0))
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
    """Asymptotic standard error for the Upside Potential Ratio (HAC adjusted)."""
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

    cov_mat = _hac_covariance_2d(x_val, y_val, max_lag=5)
    var_x_mean, cov_xy_mean = cov_mat[0, 0], cov_mat[0, 1]
    var_y_mean = cov_mat[1, 1]

    dg_dx = 1.0 / np.sqrt(mu_y)
    dg_dy = -0.5 * mu_x / (mu_y**1.5)

    var_g = dg_dx**2 * var_x_mean + dg_dy**2 * var_y_mean + 2 * dg_dx * dg_dy * cov_xy_mean
    se_daily = np.sqrt(max(var_g, 0.0))
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
    """Asymptotic standard error for the Omega ratio (HAC adjusted)."""
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

    cov_mat = _hac_covariance_2d(x_val, y_val, max_lag=5)
    var_x_mean, cov_xy_mean = cov_mat[0, 0], cov_mat[0, 1]
    var_y_mean = cov_mat[1, 1]

    dg_dx = 1.0 / mu_y
    dg_dy = -mu_x / (mu_y**2)

    var_g = dg_dx**2 * var_x_mean + dg_dy**2 * var_y_mean + 2 * dg_dx * dg_dy * cov_xy_mean
    se = np.sqrt(max(var_g, 0.0))

    point = compute_omega(r, mar_annual, periods_per_year)

    return {
        "point": point,
        "se": se,
        "ci_lower": point - 1.96 * se,
        "ci_upper": point + 1.96 * se,
        "kink_warning": kink_warning,
    }


# ---------------------------------------------------------------------------
# Vectorized Circular Block Bootstrap
# ---------------------------------------------------------------------------

def compute_block_length(n: int) -> int:
    """Politis & Romano style heuristic for moving block bootstrap."""
    if n <= 0:
        return 1
    return max(5, int(round(n ** (1 / 3))))


def generate_circular_blocks(
    n: int,
    block_length: int,
    n_resamples: int,
    seed: int | None = None,
) -> np.ndarray:
    """Generate index matrix for circular block bootstrap."""
    rng = np.random.default_rng(seed)
    
    if block_length >= n:
        block_length = n

    n_blocks = int(np.ceil(n / block_length))
    # Start indices allowed anywhere [0, n-1] for circular wrap
    start_indices = rng.integers(0, n, size=(n_resamples, n_blocks))
    
    # Broadcast to form full blocks and wrap around modulo n
    offsets = np.arange(block_length)
    idx_matrix = (start_indices[:, :, None] + offsets) % n
    
    # Reshape and truncate to exact length n
    return idx_matrix.reshape(n_resamples, -1)[:, :n]


def bootstrap_metrics(
    daily_returns: np.ndarray,
    mar_annual: float = 0.0,
    periods_per_year: int = 252,
    n_resamples: int = 2000,
    block_length: int | None = None,
    ci_level: float = 0.95,
    seed: int | None = None,
) -> dict:
    """Vectorized circular block bootstrap for all metrics."""
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

    # 1. Generate resamples matrix (shape: n_resamples x n)
    indices = generate_circular_blocks(n, block_length, n_resamples, seed=seed)
    res_r = r[indices]

    mar_daily = mar_annual / periods_per_year
    
    # 2. Vectorized Metric Calculations
    # Means and standard deviations across rows
    means_d = np.mean(res_r, axis=1)
    stds_d = np.std(res_r, axis=1, ddof=1)
    
    # Autocorrelation (lags 1..5) vectorized over rows
    rho_sums = np.zeros(n_resamples)
    for lag in range(1, 6):
        if n > lag + 1:
            x = res_r[:, :-lag]
            y = res_r[:, lag:]
            x_mean = np.mean(x, axis=1, keepdims=True)
            y_mean = np.mean(y, axis=1, keepdims=True)
            cov = np.sum((x - x_mean) * (y - y_mean), axis=1) / (x.shape[1] - 1)
            std_x = np.std(x, axis=1, ddof=1)
            std_y = np.std(y, axis=1, ddof=1)
            # handle division by zero
            denom = std_x * std_y
            valid = denom > 0
            rho_sums[valid] += cov[valid] / denom[valid]

    # Corrected Sharpe
    sharpe_vals = np.full(n_resamples, nan)
    valid_rho = np.isfinite(rho_sums)
    factor = 1.0 + 2.0 * rho_sums
    valid_factor = factor > 0
    valid_all = valid_rho & valid_factor & (stds_d > 0)
    
    if np.any(valid_all):
        sharpe_vals[valid_all] = (means_d[valid_all] * periods_per_year) / (
            stds_d[valid_all] * np.sqrt(periods_per_year * factor[valid_all])
        )

    # Partial Moments
    under = np.minimum(res_r - mar_daily, 0.0)
    upside = np.maximum(res_r - mar_daily, 0.0)
    downside = np.maximum(mar_daily - res_r, 0.0)
    
    tdd_d = np.sqrt(np.mean(under**2, axis=1))
    tdd_a = tdd_d * np.sqrt(periods_per_year)
    
    mean_a = means_d * periods_per_year
    
    # Sortino
    sortino_vals = np.full(n_resamples, nan)
    valid_tdd = tdd_a > 0
    sortino_vals[valid_tdd] = (mean_a[valid_tdd] - mar_annual) / tdd_a[valid_tdd]
    
    # UPR
    upr_vals = np.full(n_resamples, nan)
    upr_vals[valid_tdd] = (np.mean(upside, axis=1)[valid_tdd] * periods_per_year) / tdd_a[valid_tdd]
    
    # Omega
    den_mean = np.mean(downside, axis=1)
    num_mean = np.mean(upside, axis=1)
    
    # Where den_mean is 0, Omega is inf (if num_mean > 0)
    omega_vals = np.divide(num_mean, den_mean, out=np.full(n_resamples, np.inf), where=(den_mean > 0))
    omega_vals[(den_mean == 0) & (num_mean == 0)] = nan

    # 3. Compute point estimates on original data
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
        # For CIs, we include 'inf' but exclude 'nan'
        v_ci = vals[~np.isnan(vals)]
        if len(v_ci) < n_resamples * 0.5:
            return {"point": point, "se": nan, "ci_lower": nan, "ci_upper": nan, "bias": nan}
            
        ci_lower = float(np.percentile(v_ci, lower_q, method='nearest'))
        ci_upper = float(np.percentile(v_ci, upper_q, method='nearest'))
        
        # For SE and Bias, we MUST exclude 'inf' to prevent NaN propagation
        v_se = v_ci[np.isfinite(v_ci)]
        if len(v_se) < n_resamples * 0.5:
            se = nan
            bias = nan
        else:
            se = float(np.std(v_se, ddof=1))
            bias = float(np.mean(v_se) - point)
            
        return {
            "point": point,
            "se": se,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "bias": bias,
        }

    return {
        "sharpe": _stats(sharpe_vals, point_sharpe),
        "sortino": _stats(sortino_vals, point_sortino),
        "upr": _stats(upr_vals, point_upr),
        "omega": _stats(omega_vals, point_omega),
    }


def evaluate_agreement(boot: dict, delta: dict) -> str:
    """Determine if Bootstrap and Delta methods agree."""
    if not np.isfinite(boot["ci_lower"]) or not np.isfinite(delta["ci_lower"]):
        return "N/A"
        
    # boot_width can be inf if ci_upper is inf
    boot_width = boot["ci_upper"] - boot["ci_lower"]
    delta_width = delta["ci_upper"] - delta["ci_lower"]
    
    if np.isnan(boot_width) or np.isnan(delta_width) or boot_width <= 0 or delta_width <= 0:
        return "N/A"
        
    if np.isposinf(boot_width) and not np.isposinf(delta_width):
        return "WIDE — caution"
        
    boot_mid = (boot["ci_upper"] + boot["ci_lower"]) / 2.0
    delta_mid = (delta["ci_upper"] + delta["ci_lower"]) / 2.0
    
    if abs(boot_mid - delta_mid) > 0.25 * boot_width:
        return "WIDE — caution"
        
    if boot_width > 1.5 * delta_width or delta_width > 1.5 * boot_width:
        return "WIDE — caution"
        
    return "OK"
