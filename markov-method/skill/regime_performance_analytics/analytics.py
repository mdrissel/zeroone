"""Regime performance analytics — autocorrelation-corrected Sharpe and correct Sortino.

Extension 1: Burghardt-Liu (2012) autocorrelation-corrected Sharpe.
  Reference: Burghardt, G. & Liu, B. (2012). "It's the autocorrelation, stupid."
  Newedge Prime Brokerage Research Note.

  CTA return series exhibit negative serial autocorrelation (~-0.20 at monthly
  frequency). Naive Sharpe ignores this structure, misstating vol. The corrected
  formula: σ_corrected = σ_monthly × √(12 × (1 + 2 × Σρᵢ)).

  When Σρ < 0: σ_corrected < σ_naive → corrected Sharpe is HIGHER than naive.
  This is the trend-following signature: momentum causes returns to cluster,
  which the naive annualisation misreads as lower vol than actually exists
  through the full cycle. Burghardt-Liu call this "trend-favorable."

Extension 2: Correct Sortino ratio (Red Rock Capital / CME method).
  Reference: Sortino, F. & Price, L. (1994). "Performance measurement in a
  downside risk framework." Journal of Investing.
  Red Rock Capital / Brian Rom (2008). "Correcting the misuse of the Sortino
  ratio." CME Group whitepaper.

  Industry error: using std(negative returns) in the denominator. This makes
  it impossible to distinguish between a strategy with occasional deep losses
  and one with persistent shallow losses of the same total magnitude.

  Correct TDD: all N observations in denominator, underperformance zeroed
  above MAR. This is the original Sortino definition.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Burghardt-Liu autocorrelation-corrected Sharpe
# ---------------------------------------------------------------------------

def autocorr_sum(returns: np.ndarray, n_lags: int = 5) -> float:
    """Sum of serial autocorrelations at lags 1..n_lags.

    Uses pairwise autocorrelation. Returns nan if fewer than n_lags+5 points.
    """
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < n_lags + 5:
        return float("nan")

    total = 0.0
    for lag in range(1, n_lags + 1):
        c = float(np.corrcoef(r[:-lag], r[lag:])[0, 1])
        total += c if np.isfinite(c) else 0.0
    return total


def corrected_sharpe_monthly(
    monthly_returns: np.ndarray,
    n_lags: int = 5,
) -> dict:
    """Burghardt-Liu (2012) autocorrelation-corrected Sharpe from monthly returns.

    Args:
        monthly_returns: compound monthly return series (decimal).
        n_lags: autocorrelation lags to sum (default 5).

    Returns dict:
        mean_annual, sigma_naive, sigma_corrected,
        sharpe_naive, sharpe_corrected, rho_sum
    """
    r = np.asarray(monthly_returns, dtype=float)
    r = r[np.isfinite(r)]
    nan = float("nan")

    if len(r) < 6:
        return dict(mean_annual=nan, sigma_naive=nan, sigma_corrected=nan,
                    sharpe_naive=nan, sharpe_corrected=nan, rho_sum=nan)

    mean_m = float(r.mean())
    sigma_m = float(r.std(ddof=1))
    mean_annual = mean_m * 12
    sigma_naive = sigma_m * np.sqrt(12)

    rho_sum = autocorr_sum(r, n_lags)
    if np.isfinite(rho_sum):
        factor = 1.0 + 2.0 * rho_sum
        # factor <= 0 means the autocorrelation structure is outside the model's
        # valid range; clamping to a tiny positive would produce astronomically
        # inflated Sharpe values, so return nan instead.
        sigma_corrected = sigma_m * np.sqrt(12.0 * factor) if factor > 0 else nan
    else:
        sigma_corrected = sigma_naive

    sharpe_naive = mean_annual / sigma_naive if sigma_naive > 0 else nan
    sharpe_corrected = (
        mean_annual / sigma_corrected
        if np.isfinite(sigma_corrected) and sigma_corrected > 0
        else nan
    )

    return dict(
        mean_annual=mean_annual,
        sigma_naive=sigma_naive,
        sigma_corrected=sigma_corrected,
        sharpe_naive=sharpe_naive,
        sharpe_corrected=sharpe_corrected,
        rho_sum=rho_sum if np.isfinite(rho_sum) else nan,
    )


def corrected_sharpe_daily(
    daily_returns: np.ndarray,
    n_lags: int = 5,
    periods_per_year: int = 252,
) -> dict:
    """Daily-frequency analog of Burghardt-Liu for per-regime sub-series.

    Per-regime monthly resampling loses too many observations. Instead, apply
    the autocorrelation correction at daily frequency:
      σ_corrected_daily = σ_daily × √(1 + 2Σρ)
      σ_corrected_annual = σ_corrected_daily × √252

    Args:
        daily_returns: daily return sub-series for a single regime.
        n_lags: autocorrelation lags to sum (default 5).
        periods_per_year: trading days per year.

    Returns same keys as corrected_sharpe_monthly.
    """
    r = np.asarray(daily_returns, dtype=float)
    r = r[np.isfinite(r)]
    nan = float("nan")

    if len(r) < 10:
        return dict(mean_annual=nan, sigma_naive=nan, sigma_corrected=nan,
                    sharpe_naive=nan, sharpe_corrected=nan, rho_sum=nan)

    mean_d = float(r.mean())
    sigma_d = float(r.std(ddof=1))
    mean_annual = mean_d * periods_per_year
    sigma_naive = sigma_d * np.sqrt(periods_per_year)

    rho_sum = autocorr_sum(r, n_lags)
    if np.isfinite(rho_sum):
        factor = 1.0 + 2.0 * rho_sum
        sigma_corrected = sigma_d * np.sqrt(periods_per_year * factor) if factor > 0 else nan
    else:
        sigma_corrected = sigma_naive

    sharpe_naive = mean_annual / sigma_naive if sigma_naive > 0 else nan
    sharpe_corrected = (
        mean_annual / sigma_corrected
        if np.isfinite(sigma_corrected) and sigma_corrected > 0
        else nan
    )

    return dict(
        mean_annual=mean_annual,
        sigma_naive=sigma_naive,
        sigma_corrected=sigma_corrected,
        sharpe_naive=sharpe_naive,
        sharpe_corrected=sharpe_corrected,
        rho_sum=rho_sum if np.isfinite(rho_sum) else nan,
    )


def regime_autocorr_flag(rho_sum: float) -> str:
    """Burghardt-Liu (2012) autocorrelation structure classification.

    Thresholds from the paper's finding that the CTA index Σρ ≈ -0.20.
    """
    if not np.isfinite(rho_sum):
        return "insufficient data"
    if rho_sum < -0.15:
        return f"trend-favorable autocorrelation structure (Σρ={rho_sum:+.3f})"
    elif rho_sum > 0.10:
        return f"mean-reversion / momentum-in-price regime (Σρ={rho_sum:+.3f})"
    else:
        return f"neutral autocorrelation structure (Σρ={rho_sum:+.3f})"


# ---------------------------------------------------------------------------
# Correct Sortino ratio (Red Rock / CME method)
# ---------------------------------------------------------------------------

def target_downside_deviation(
    returns: np.ndarray,
    mar: float = 0.0,
) -> float:
    """Correct Target Downside Deviation — all N in the denominator.

    The industry error uses only the N_negative observations:
      TDD_wrong = sqrt(Σ(min(r-MAR, 0)²) / N_negative)

    This is wrong because it cannot distinguish between:
      Series A: [0, 0, 0, -10%] → one bad period out of four
      Series B: [-10%, -10%, -10%, -10%] → persistently bad

    The incorrect method gives TDD=10% for BOTH because the number of
    negative observations changes the denominator. The correct method keeps
    all N in the denominator:
      TDD_correct = sqrt(Σ(min(r-MAR, 0)²) / N_total)
    giving TDD_A=5%, TDD_B=10% — correctly penalising the persistent case.

    Args:
        returns: return series (decimal, any frequency).
        mar: minimum acceptable return per period (same frequency as returns).

    Returns:
        TDD in the same units as returns (not annualised).
    """
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) == 0:
        return float("nan")

    underperformance = np.minimum(r - mar, 0.0)
    return float(np.sqrt(np.mean(underperformance ** 2)))


def _incorrect_tdd(returns: np.ndarray, mar: float = 0.0) -> float:
    """Industry error: TDD using only N_negative in denominator.

    Exposed only for unit testing. Do not use for analysis.
    """
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    below = r[r < mar]
    if len(below) == 0:
        return 0.0
    return float(np.sqrt(np.mean((below - mar) ** 2)))


def sortino_ratio(
    daily_returns: np.ndarray,
    mar_annual: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Correct Sortino ratio using TDD with all N in denominator.

    Args:
        daily_returns: daily return series (decimal).
        mar_annual: minimum acceptable return (annual decimal).
        periods_per_year: trading days per year for annualisation.

    Returns:
        Annualised Sortino ratio.
    """
    r = np.asarray(daily_returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 5:
        return float("nan")

    mar_daily = mar_annual / periods_per_year
    tdd_daily = target_downside_deviation(r, mar=mar_daily)
    tdd_annual = tdd_daily * np.sqrt(periods_per_year)

    mean_annual = float(r.mean()) * periods_per_year

    if tdd_annual == 0 or not np.isfinite(tdd_annual):
        return float("nan")
    return float((mean_annual - mar_annual) / tdd_annual)


# ---------------------------------------------------------------------------
# Skewness classification
# ---------------------------------------------------------------------------

def skew_classification(sortino: float, corrected_sharpe: float) -> str:
    """Classify return distribution skewness via Sortino/Sharpe ratio.

    > 1.2:  positive skew — trend-favorable, fat tail on upside
    0.8–1.2: near-symmetric
    < 0.8:  negative skew — hidden left-tail risk, option-writer profile
    """
    if not np.isfinite(sortino) or not np.isfinite(corrected_sharpe):
        return "insufficient data"
    if corrected_sharpe == 0:
        return "insufficient data"

    ratio = sortino / corrected_sharpe
    if ratio > 1.2:
        return f"positive skew / trend-favorable  (S÷Sr={ratio:.2f} > 1.2)"
    elif ratio >= 0.8:
        return f"near-symmetric                   (S÷Sr={ratio:.2f})"
    else:
        return f"negative skew / left-tail risk   (S÷Sr={ratio:.2f} < 0.8)"


# ---------------------------------------------------------------------------
# Upside Potential Ratio (correct method — all N in denominator)
# ---------------------------------------------------------------------------

def compute_upr(
    returns: np.ndarray,
    mar_annual: float,
    tdd_annual: float,
    periods_per_year: int = 252,
) -> float:
    """Upside Potential Ratio using the correct-method TDD.

    UPR = mean(max(r - MAR_period, 0)) × periods_per_year / TDD_annual

    The TDD_annual must be the value already computed for Sortino (all N in
    denominator). Passing it in ensures TDD is computed exactly once across
    Sortino, UPR, and Omega — not redundantly recalculated.

    With all N in the denominator the UPR correctly penalises strategies
    that capture upside only infrequently — analogous to how correct TDD
    penalises infrequent but large losses.
    """
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) == 0 or not np.isfinite(tdd_annual) or tdd_annual <= 0:
        return float("nan")
    mar_period = mar_annual / periods_per_year
    upside = np.maximum(r - mar_period, 0.0)
    numerator_annual = float(upside.mean()) * periods_per_year
    return float(numerator_annual / tdd_annual)


# ---------------------------------------------------------------------------
# Omega ratio
# ---------------------------------------------------------------------------

def compute_omega(
    returns: np.ndarray,
    mar_annual: float,
    periods_per_year: int = 252,
) -> float:
    """Omega ratio: mean upside excess / mean downside shortfall.

    Omega = mean(max(r - MAR, 0)) / mean(max(MAR - r, 0))

    Annualisation factors cancel in numerator and denominator so the
    result is scale-invariant. Omega > 1 means the right tail outweighs
    the left tail relative to MAR. Omega < 0.8 flags left-tail dominance.
    """
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) == 0:
        return float("nan")
    mar_period = mar_annual / periods_per_year
    upside = np.maximum(r - mar_period, 0.0)
    downside = np.maximum(mar_period - r, 0.0)
    den = float(downside.mean())
    if den == 0:
        return float("inf") if float(upside.mean()) > 0 else float("nan")
    return float(upside.mean() / den)


# ---------------------------------------------------------------------------
# Classification helpers for the skewness diagnostic table
# ---------------------------------------------------------------------------

def classify_omega(omega: float) -> str:
    """Classify Omega ratio signal."""
    if not np.isfinite(omega):
        return "insufficient data" if np.isnan(omega) else "Strong positive skew"
    if omega > 1.5:
        return "Strong positive skew"
    if omega >= 1.0:
        return "Mild positive skew"
    if omega >= 0.8:
        return "Near neutral"
    return "Negative skew — left tail dominant"


def classify_upr_sortino(ratio: float) -> str:
    """Classify UPR/Sortino ratio signal."""
    if not np.isfinite(ratio):
        return "insufficient data"
    if ratio > 1.0:
        return "Capturing upside cleanly"
    if ratio >= 0.6:
        return "Partial upside capture"
    return "Missing upside moves — possible chop or signal timing issue"


def classify_sortino_sharpe(ratio: float) -> str:
    """Classify Sortino/Sharpe divergence (short form for table)."""
    if not np.isfinite(ratio):
        return "insufficient data"
    if ratio > 1.2:
        return "Positive skew / trend-favorable"
    if ratio >= 0.8:
        return "Near-symmetric distribution"
    return "Negative skew — hidden left-tail risk"


def classify_autocorr_sum(rho_sum: float) -> str:
    """Classify autocorrelation sum (short form for table and synthesis)."""
    if not np.isfinite(rho_sum):
        return "insufficient data"
    if rho_sum < -0.15:
        return "Trend-favorable"
    if rho_sum <= 0.10:
        return "Neutral — monitor"
    return "Mean-reverting / momentum-in-price"
