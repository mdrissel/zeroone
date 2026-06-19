# Regime Analytics — README

CTA-grade performance analytics for any TradingView chart: autocorrelation-corrected
Sharpe, correctly-computed Sortino, a rolling regime label, and Bayesian fractional Kelly
position sizing. Runs as a free-plan-compatible Pine Script v6 indicator in its own pane.

This document covers three things: a definitions table for every metric and symbol in the
script, the reasoning behind the specific approach we settled on (and the alternatives we
rejected), and worked examples showing what the numbers look like in different regimes.

---

## 1. Definitions Table

| Term / Symbol | Definition | Why it's in this script |
|---|---|---|
| **Sharpe ratio (naive)** | `(annualized mean return) / (annualized std. deviation)`, with annualization via the standard `σ × √periods` rule | The industry-default risk-adjusted return metric. Shown for comparison — it's the number this whole indicator argues you shouldn't use alone. |
| **Σρ (rho-sum)** | Sum of serial autocorrelations in returns over `n_lags` (default 5), i.e. `corr(rₜ, rₜ₋₁) + corr(rₜ, rₜ₋₂) + ...` | Negative Σρ is the structural signature of trend-following return series (Burghardt & Liu, 2012). Drives the volatility correction below. |
| **Correction factor** | `max(1 + 2Σρ, ε)` | The multiplier applied to naive variance to get the statistically correct annualized volatility under serial correlation. |
| **Sharpe ratio (corrected)** | `(annualized mean return) / (σ_daily × √(periods × correction))` | The Burghardt-Liu fix. When Σρ < 0 (trend-favorable), corrected volatility is *lower* than naive, so corrected Sharpe is *higher* — the naive Sharpe was overstating risk all along. |
| **MAR** | Minimum Acceptable Return — the return threshold below which a period counts as "underperformance." Default 0% (any loss counts). | Sets the benchmark for Sortino. Configurable to risk-free rate or any hurdle. |
| **TDD** | Target Downside Deviation = `√(mean(min(r − MAR, 0)²))`, averaged over **all** N bars, not just the losing ones | The correct Sortino denominator (Red Rock Capital / CME method). Keeping the zero-underperformance bars in the average is what makes this correct — discarding them is the industry's most common Sortino calculation error. |
| **Sortino ratio** | `(annualized mean return − MAR) / TDD_annualized` | Penalizes only downside deviation, not total volatility — doesn't punish a strategy for its best months the way Sharpe does. |
| **Skew ratio** | `Sortino / Sharpe_corrected` | A live proxy for return-distribution skewness without needing the raw distribution. >1.2 → positive skew (fat right tail). <0.8 → negative skew (hidden left-tail risk). |
| **t-statistic** | `metric × √T`, where T = lookback bars | A measure of how much statistical confidence the live data supports for a given Sharpe or Sortino reading — distinct from the *level* of the ratio itself. |
| **t-stat (Sharpe)** | `Sharpe_corrected × √lookback` | Confidence measure tied to total-variance risk. This is the t-stat that's valid for the GBM drawdown-probability math underlying plain fractional Kelly. |
| **t-stat (Sortino)** | `Sortino × √lookback` | Confidence measure tied to downside-only risk. **This is the t-stat that drives the Bayesian Kelly shrinkage** in this script — see Section 2 for why. |
| **c (prior skepticism)** | The squared t-statistic at which you're equally unsure whether the edge is real or noise — your "50/50 confidence point" | Encodes how much evidence you require before trusting a live edge at face value. Higher c = more skeptical, more shrinkage at a given t-stat. |
| **Shrinkage** | `t_sortino² / (t_sortino² + c)` | The Bayesian-consistent fraction of your raw return estimate that the evidence actually supports trusting. Approaches 1 as t-stat grows, approaches 0 as it shrinks toward zero. |
| **v (variance-risk cap)** | A plain fractional-Kelly ceiling (e.g. 0.5 for the half-Kelly drawdown profile), independent of statistical confidence | Caps variance/drawdown exposure on top of the Bayesian shrinkage — a second, separate dial for a second, separate risk. |
| **k (Bayesian)** | `shrinkage × v` | The final suggested position-sizing fraction. Adapts continuously with live evidence instead of using one fixed number (like conventional half-Kelly) regardless of confidence. |
| **Regime (Bull/Bear/Sideways)** | Z-score of a rolling mean return, normalized over a longer window, thresholded at `zThresh` standard deviations | A simple, transparent regime label used for the background shading. Not a Markov model — see Section 2 for the relationship between this and the more rigorous `regime-performance-analytics` skill. |
| **Periods/yr** | Annualization constant: 252 for stocks/futures/forex, 365 for crypto | Standard convention for converting daily statistics to annualized ones. |

---

## 2. The Approach We Settled On

### 2.1 Why correct Sharpe and Sortino instead of the textbook versions

The textbook Sharpe ratio assumes returns are serially independent. Trend-following
return series systematically violate this — Burghardt and Liu (2012) documented negative
serial autocorrelation as a structural property of CTA returns, which means the standard
`σ × √T` annualization *overstates* true volatility and therefore *understates* the true
Sharpe ratio. We correct for this directly rather than ignoring it, because the correction
can move the reported Sharpe by a large margin in either direction depending on the sign
and magnitude of Σρ.

The textbook Sortino ratio is also frequently miscalculated industry-wide: many
implementations compute downside deviation using only the negative-return periods,
discarding the zero-underperformance periods from the average. This inflates Sortino for
any strategy that's usually profitable, and the inflation is worst for exactly the
strategies that look best. We use the Red Rock Capital / CME-documented correct method —
all N periods in the denominator, with above-MAR periods contributing zero rather than
being dropped — because it's the only version of Sortino that correctly reflects
*frequency* of underperformance, not just magnitude.

### 2.2 Why the Kelly shrinkage uses Sortino's t-statistic, not Sharpe's

This is the one place in the script where we deliberately split a single concept into two
separate calculations, and it's worth explaining why.

Kelly position sizing is mathematically derived from `μ/σ²` under geometric Brownian
motion — true variance, not downside deviation, is the correct denominator for the
*growth-rate and drawdown-probability* math (the formulas behind `P(50% drawdown) = b^(2/k-1)`
require total variance to hold). So the variance-risk cap, `v`, stays anchored to the
Sharpe-corrected volatility. Swapping Sortino's downside deviation into that part of the
formula would mean we're no longer computing the quantity Kelly was actually derived to
optimize.

But the *separate* question — "how much do I trust this edge estimate, statistically?" —
doesn't require GBM at all. A t-statistic is a general-purpose signal-to-noise measure,
and Sortino's TDD is just as legitimate a noise measure for that purpose as Sharpe's
total volatility. Using Sharpe's t-statistic here would re-import the same skew-blindness
problem Sharpe has everywhere else: a positively-skewed trend-following strategy would be
shrunk *more* than the evidence warrants, purely because its big winning months count
against it the same way a big losing month would.

**The resolution:** Sortino's t-statistic drives the Bayesian shrinkage (estimation-risk
side). Sharpe's volatility stays in the variance-risk cap (drawdown-probability side).
Both t-statistics are displayed side by side in the table specifically so the *gap*
between them is visible — a wide gap is itself a live skew signal, consistent with the
Sortino ÷ Sharpe skew-ratio row already in the table.

### 2.3 Why a fixed multiplier (conventional half-Kelly) isn't used

The standard industry practice of betting a fixed fraction — most commonly k=0.5 — of
full Kelly is only the mathematically correct, Bayesian-consistent choice at one specific
level of statistical confidence (a t-statistic of roughly 2.0, under a moderate
skepticism setting of c=4). Below that confidence level, fixed half-Kelly is *too
aggressive* relative to the actual evidence. Above it, fixed half-Kelly is *too
conservative*, leaving achievable growth on the table for well-established edges.

Rather than pick one fixed number, the script computes the Bayesian-consistent multiplier
continuously from the live data: shrinkage rises automatically as the live t-statistic
strengthens (more bars, more consistent Sortino) and falls automatically as it weakens —
without requiring you to manually decide "is this edge proven yet?"

### 2.4 Why the regime label is a simple z-score, not the full Markov model

This script's regime label (Bull/Bear/Sideways via rolling z-score) is intentionally
simple — it has to run as a self-contained Pine indicator with no external dependencies
and no persistent storage of historical state beyond what Pine's bar-by-bar execution
naturally provides. It is **not** a replacement for the more rigorous Markov-chain regime
detection in the separate `regime-performance-analytics` Python skill, which computes a
full transition matrix, BIC-driven state-count selection, and HMM disagreement analysis.

Think of this Pine indicator's regime label as a fast, always-visible proxy you can glance
at on any chart, and the Python skill as the deeper, more statistically rigorous tool you'd
run when actually validating a strategy or deciding on regime-conditional position sizing
at the portfolio level.

### 2.5 What this script deliberately does not do

- **No order execution.** Pine indicators have no broker connection. The `k` value is a
  sizing *suggestion* to inform a manual decision, not an automated trade.
- **No multi-instrument portfolio logic.** Each chart this indicator runs on is analyzed
  independently. It doesn't know about correlation with your other positions.
- **No drawdown-conditional rule reversal.** The Burghardt-Liu finding that
  negatively-autocorrelated strategies should *increase* size after a loss (rather than
  the conventional decrease) is not implemented here — it's a portfolio-level risk
  management decision, not something this analytics readout makes for you.

---

## 3. Worked Examples

These are illustrative, not live data — they show how the metrics move together so you can
sanity-check what you see on your own chart.

### Example A: Clean trend-following regime (Bull, strong evidence)

| Metric | Value |
|---|---|
| Regime | Bull |
| Σρ (5 lags) | −0.24 → **trend-favorable** |
| Correction × | 0.52 |
| Sharpe (naive) | 0.61 |
| Sharpe (corrected) | 0.85 |
| Sortino | 1.42 |
| Skew classification | **pos / trend** (1.42 / 0.85 = 1.67) |
| t-stat (Sharpe) | 1.35 |
| t-stat (Sortino) | 2.25 |
| k (Bayesian), c=4, v=0.5 | 0.40 |
| k vs conventional | near ceiling |

**Reading it:** Negative Σρ confirms the trend-favorable return structure. Corrected
Sharpe is meaningfully higher than naive Sharpe — the naive number was overstating risk.
The wide gap between the two t-statistics (2.25 vs 1.35) shows the Sortino-based
confidence is substantially stronger than the Sharpe-based confidence, which is exactly
what positive skew looks like numerically. k of 0.40 against a 0.5 ceiling means the
Bayesian shrinkage has released most of the way — the live evidence strongly supports
sizing close to the variance cap.

### Example B: Choppy, low-confidence regime (Sideways, early data)

| Metric | Value |
|---|---|
| Regime | Sideways |
| Σρ (5 lags) | −0.03 → **neutral** |
| Correction × | 0.94 |
| Sharpe (naive) | 0.18 |
| Sharpe (corrected) | 0.19 |
| Sortino | 0.21 |
| Skew classification | **near-symm** (0.21 / 0.19 = 1.11) |
| t-stat (Sharpe) | 0.30 |
| t-stat (Sortino) | 0.33 |
| k (Bayesian), c=4, v=0.5 | 0.005 |
| k vs conventional | well below |

**Reading it:** Σρ near zero means the autocorrelation correction barely moves anything —
naive and corrected Sharpe are nearly identical, which is itself informative: this is not
a regime with the structural property that makes the correction matter. Both t-statistics
are low and close together — no skew signal, just weak evidence overall. k collapses to
roughly 1% of full Kelly: the Bayesian shrinkage is doing exactly what it's supposed to
here, refusing to size up on a thin, unconvincing sample regardless of how the point
estimate looks.

### Example C: Negative-skew warning sign (still "Bull" by label, hidden risk)

| Metric | Value |
|---|---|
| Regime | Bull |
| Σρ (5 lags) | +0.08 → **neutral** (leaning mom/MR) |
| Correction × | 1.16 |
| Sharpe (naive) | 0.95 |
| Sharpe (corrected) | 0.88 |
| Sortino | 0.61 |
| Skew classification | **neg / left-tail** (0.61 / 0.88 = 0.69) |
| t-stat (Sharpe) | 1.40 |
| t-stat (Sortino) | 0.97 |
| k (Bayesian), c=4, v=0.5 | 0.16 |
| k vs conventional | well below |

**Reading it:** The regime label alone says "Bull" — naive inspection of the price chart
would look fine. But Sortino sitting well below corrected Sharpe is the classic
option-writer / negative-skew fingerprint: steady-looking returns concealing a fatter left
tail. The Sortino t-statistic is meaningfully weaker than the Sharpe t-statistic here — the
reverse of Example A — and k is shrunk down to 0.16 specifically *because* the
skew-sensitive t-stat is telling a more cautious story than the headline Sharpe number
would suggest on its own. This is the scenario the dual-t-stat design exists to catch.

---

## 4. Quick Reference: Reading the Live Table

| Row | Good sign | Caution sign |
|---|---|---|
| Σρ flag | "trend-favorable" (< −0.15) | "mom/MR" (> +0.10) — different return structure than naive Sharpe assumes |
| Sharpe corrected vs naive | Corrected meaningfully higher (aqua) | Corrected lower (red) — naive Sharpe was *understating* risk here |
| Skew classification | "pos / trend" | "neg / left-tail" — hidden downside risk |
| t-stat gap (Sortino vs Sharpe) | Sortino notably higher | Sortino notably lower — confirms negative skew numerically |
| k vs conventional | "near ceiling" — evidence strongly supports current sizing | "well below" — thin evidence, don't override the shrinkage manually |

---

*Built on Burghardt & Liu (2012), Red Rock Capital / CME (Sortino methodology), and
Rising & Wyner (2012) / MacLean, Thorp & Ziemba (2010) for the Bayesian Kelly framework.
This is an analytics tool, not investment advice — position sizing decisions remain yours
to make.*
