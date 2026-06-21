---
name: regime-performance-analytics
description: >
  Statistically rigorous Markov regime model with CTA-grade performance analytics.
  Adaptive z-score labeling, stride-sampled transition matrix with per-cell
  confidence intervals, BIC-driven state-count selection, walk-forward backtest
  net of transaction costs, Burghardt-Liu (2012) autocorrelation-corrected Sharpe,
  correct Sortino ratio (Red Rock/CME method, all N in denominator), Upside
  Potential Ratio, Omega ratio, regime signal synthesis block, and HMM
  disagreement analysis. Supports FILTER and STANDALONE operating modes.
  Formerly: markov-regime-method (backward-compatible, same CLI flags).
---

# regime-performance-analytics

**Skill name:** regime-performance-analytics
**Formerly:** markov-regime-method (symlink preserved, same CLI flags)
**Framework authors:** Roan (@RohOnChain). Extended by Lewis Jackson. Distributional metrics (UPR, Omega, regime signal synthesis) added in v3.1.

Install location: `~/.claude/skills/markov-regime-method/` (symlink to repo at `markov-method/skill/`)

## What this skill does

Given any ticker symbol, this skill fetches daily price history, labels each trading day into Bear / Sideways / Bull regimes using an adaptive z-score threshold (self-calibrating per asset), and builds a statistically honest Markov transition matrix using stride-sampled (non-overlapping) windows to avoid the diagonal-inflation flaw endemic to retail regime models. It selects the optimal number of regime states via BIC, runs a walk-forward backtest net of transaction costs, and then applies five layers of CTA-grade performance analytics: (1) Burghardt-Liu (2012) autocorrelation-corrected Sharpe — correcting for the negative serial correlation signature of trend-following strategies; (2) correct Sortino ratio using Target Downside Deviation computed with all N observations in the denominator, not just the negative ones; (3) Upside Potential Ratio, computed once using the same TDD to avoid redundant calculation; (4) Omega ratio, which unifies the full return distribution above and below the MAR threshold; and (5) a Regime Signal Synthesis block that combines all metrics into a human-readable FULL SIZE / REDUCE / DEFENSIVE signal for the current regime. An optional Hidden Markov Model overlay identifies ambiguous / choppy environments where the Markov signal should be suppressed.

## Invocation

- "run the regime performance analytics on SPY"
- "run the markov regime method on BTC-USD in standalone mode"
- "analyse QQQ with a 7% MAR for the Sortino"

```bash
cd ~/.claude/skills/markov-regime-method
uv run python -m regime_performance_analytics.run \
  --ticker SPY \
  --years 10 \
  --window 20 \
  --cost-bps 5 \
  --mode standalone \
  --mar zero \
  [--no-hmm] [--k-override 3]
```

Backward-compatible entry point (identical output):
```bash
uv run python -m markov_regime_method.run --ticker SPY
```

## CLI reference

| Flag | Default | Description |
|---|---|---|
| `--ticker` | `SPY` | Ticker symbol |
| `--years` | `10` | Years of daily history |
| `--window` | `20` | Rolling-return window (trading days) |
| `--z-thresh` | `0.5` | Z-score threshold for Bull/Bear labels |
| `--cost-bps` | `5.0` | One-way transaction cost in basis points |
| `--mode` | `standalone` | `standalone` (trade signal directly) or `filter` (gate a strategy) |
| `--signal-threshold` | `0.0` | Min \|signal\| for filter mode |
| `--k-override` | _(BIC)_ | Force number of regime states |
| `--no-hmm` | — | Skip HMM fit |
| `--mar` | `zero` | MAR for Sortino/UPR/Omega: `rfr` (3m T-bill from ^IRX), `zero` (absolute return mandate), or a decimal float e.g. `0.07` for 7% |

## Outputs on every run

1. Regime label distribution (% Bull / Bear / Sideways) — sanity check.
2. BIC curve across k=2..5 states; optimal k highlighted.
3. Overlapping vs stride-sampled transition matrix with 95% CI per cell.
4. Stationary distribution (long-run regime mix).
5. Multi-step forecast table (1–5 steps + convergence to stationary).
6. Walk-forward backtest net of round-trip costs: gross Sharpe, net Sharpe, buy-and-hold Sharpe, excess Sharpe, max drawdown, win rate, profit factor.

**Extension 1 — Burghardt-Liu (2012) autocorrelation-corrected Sharpe:**

7. Five-lag serial autocorrelation sum (Σρ lags 1–5) on monthly return series.
8. Naive annualised volatility vs autocorrelation-corrected volatility side by side.
9. Naive Sharpe vs corrected Sharpe side by side.
10. Per-regime Σρ (daily sub-series). Flag: Σρ < -0.15 → trend-favorable; Σρ > +0.10 → mean-reversion / momentum-in-price.

**Extension 2 — Sortino, UPR, and Omega (Red Rock / CME correct method):**

11. Target Downside Deviation (TDD) computed once using all N observations in the denominator.
12. Sortino ratio = (annualised return − MAR) / TDD_annual. Per regime and overall.
13. Upside Potential Ratio = mean(max(r − MAR, 0)) × 252 / TDD_annual. Per regime and overall. Reuses TDD from Sortino — not recomputed.
14. Omega ratio = mean(max(r − MAR, 0)) / mean(max(MAR − r, 0)). Per regime and overall with classification.

**Extension 3 — Regime-conditional interpretation block:**

15. Per-regime summary table: corrected Sharpe, Sortino, S÷Sr, autocorr sum, skewness class.
16. Flag: high transition persistence (diagonal > 70%) AND Σρ < -0.15 → high-confidence trend-following environment.
17. HMM disagreement map (if hmmlearn available): disagreement periods with near-zero autocorrelation → suppress trend signals.

**Extension 4 — Skewness diagnostic table:**

18. Per-regime and overall table: Corrected Sharpe, Sortino, UPR, Omega, Sortino/Sharpe, UPR/Sortino, Autocorrelation sum — each with signal classification and color-flagged warnings for adverse thresholds.

**Extension 5 — Regime signal synthesis:**

19. For the current regime: FULL SIZE / REDUCE / DEFENSIVE signal derived from all five metric dimensions, with individual readings displayed inline.

## Theoretical basis

**Burghardt-Liu (2012) autocorrelation correction:**
CTA monthly return series exhibit Σρ ≈ −0.20 at lags 1–5. Naive Sharpe assumes i.i.d. returns; when autocorrelation is negative, effective vol is lower than naive annualisation implies, so corrected Sharpe > naive Sharpe for trend-following strategies. The correction factor is (1 + 2Σρ). This is the "trend-favorable" signature that Burghardt and Liu identify as endemic to CTA indices. Ignoring it understates the true risk-adjusted return of momentum strategies.

**Why correct TDD matters:**
The original Sortino (1994) definition uses all N observations in the TDD denominator. The industry shortcut (std of negative-only observations) conflates frequency of loss with magnitude: it gives the same TDD for [0, 0, 0, −10%] and [−10%, −10%, −10%, −10%] because both have one value of −10% when you look only at the negatives. The correct method gives TDD = 5% for the first series and 10% for the second, correctly penalising persistent drawdowns. Red Rock Capital (Brian Rom, 2008 CME whitepaper) documented this error and its consequences for strategy ranking.

**What UPR adds beyond Sortino:**
Sortino uses mean return in the numerator — it measures average performance relative to downside risk. UPR replaces the mean with mean(max(r − MAR, 0)), capturing only the upside exceedances. The correct-method UPR uses all N observations in the denominator (including zero-contribution periods), so a strategy that wins infrequently but wins large registers differently from one that wins frequently but modestly. The UPR/Sortino ratio then separates strategies that earn their return through upside capture (high UPR/Sortino) from those that earn it via low volatility with rare gains (low UPR/Sortino). Reusing TDD eliminates any inconsistency between Sortino and UPR denominators.

**What Omega unifies:**
Omega integrates the full return distribution above and below the MAR threshold in a single ratio. It equals the probability-weighted sum of all upside exceedances over the probability-weighted sum of all downside shortfalls. Omega > 1 means the right tail outweighs the left tail relative to MAR — an unambiguous signal that the MAR is achievable under this regime's return distribution. Unlike Sortino and UPR, Omega does not require an assumption about the shape of the distribution and is not sensitive to annualisation convention. Omega < 0.8 is a clear warning that the left tail dominates regardless of the mean return.

**How the regime signal synthesis works:**
FULL SIZE requires all five dimensions to align simultaneously: high regime persistence (diagonal > 0.70), trend-favorable autocorrelation (Σρ < −0.15), strong right-tail dominance (Omega > 1.5), clean upside capture (UPR/Sortino > 1.0), and confirmed positive skew (Sortino/Sharpe > 1.2). DEFENSIVE triggers on any single adverse reading that implies structural left-tail risk or mean-reverting dynamics. REDUCE fires when conditions are mixed but not yet alarming. Defensive overrides full-size — a single red flag cannot be offset by other green flags.

## Confidence Intervals and Estimation Uncertainty

Point estimates of distributional metrics (Sharpe, Sortino, UPR, Omega) carry inherent sampling variance — Fisher Information sets a Cramér-Rao lower bound on how precisely any parameter can be known from finite data. This uncertainty is largest right after regime transitions when the sample size for the new regime is small. To avoid false confidence in early numbers, this skill reports uncertainty via two methods:

1. **Moving Block Bootstrap (Primary):** We use a block bootstrap rather than a naive i.i.d. bootstrap. Naive resampling destroys the serial correlation structure (the momentum/mean-reversion signature) that is critical to trend-following analysis. The block bootstrap preserves this structure by drawing overlapping blocks of consecutive returns.
2. **Delta Method (Secondary, Fast Check):** We compute asymptotic standard errors using closed-form approximations. For Sharpe, this uses the Lo (2002) formula adjusted for autocorrelation. For Sortino, UPR, and Omega, we use standard Taylor-expanded approximations of partial moments.

> [!WARNING]
> **Kink-Point Limitation**: The delta method for Sortino, UPR, and Omega treats the indicator function around the Minimum Acceptable Return (MAR) as fixed. This is asymptotically valid, but if a large cluster of returns (e.g. >5%) sits exactly at or near the MAR kink point, the local derivative becomes unreliable. A "KINK-PROXIMITY WARNING" flag will appear if this is detected.

### Interpreting the Agreement Flag

The tool displays an **Agreement** column to compare the two methods:
- **OK**: The methods roughly agree, supporting the point estimate's stability.
- **WIDE — caution**: The methods diverge in midpoint or width. This signals the asymptotic assumptions are breaking down (often due to small sample size or fat tails).

**Example Interpretation:**

| Metric          | Point Est. | Bootstrap CI          | Delta-Method CI       | Agreement      |
|-----------------|------------|-----------------------|-----------------------|----------------|
| Sharpe (corr)   | 1.42       | [0.88, 2.01]          | [0.95, 1.89]          | OK             |
| UPR             | 1.20       | [0.40, 2.95]          | [0.50, 1.90]          | WIDE — caution |

In this example, the UPR shows "WIDE — caution". This often happens in short regimes where a few extreme days skew the bootstrap. You should treat the point estimate of 1.20 with significant skepticism, prefer the wider bootstrap CI as the true range of uncertainty, and factor this uncertainty into position sizing by being more conservative.

## Signal interpretation guide

### Omega ratio
| Range | Classification |
|---|---|
| > 1.5 | Strong positive skew |
| 1.0 – 1.5 | Mild positive skew |
| 0.8 – 1.0 | Near neutral |
| < 0.8 | **Negative skew — left tail dominant** ⚠ |

### Sortino/Sharpe divergence
| Range | Classification |
|---|---|
| > 1.2 | Positive skew — trend-favorable, fat right tail |
| 0.8 – 1.2 | Near-symmetric distribution |
| < 0.8 | **Negative skew — hidden left-tail risk** ⚠ |

### UPR/Sortino
| Range | Classification |
|---|---|
| > 1.0 | Capturing upside cleanly |
| 0.6 – 1.0 | Partial upside capture |
| < 0.6 | **Missing upside moves — possible chop or signal timing issue** ⚠ |

### Autocorrelation sum (Σρ lags 1–5)
| Range | Classification |
|---|---|
| < −0.15 | Trend-favorable autocorrelation structure |
| −0.15 to 0.10 | Neutral — monitor |
| > 0.10 | Mean-reverting / momentum-in-price regime |

### Regime signal synthesis thresholds
| Signal | Conditions |
|---|---|
| **FULL SIZE** | All of: diagonal > 0.70, Σρ < −0.15, Omega > 1.5, UPR/Sortino > 1.0, Sortino/Sharpe > 1.2 |
| **REDUCE** | Any of: diagonal < 0.65, Σρ in [−0.15, 0.10], Omega in [0.8, 1.0], UPR/Sortino < 0.6 |
| **DEFENSIVE** | Any of: Omega < 0.8, Σρ > 0.10, Bear transition probability > 0.35, Sortino/Sharpe < 0.8 |

Defensive overrides Full Size. NEUTRAL is returned when no category's conditions are triggered.

## Known limitations

- UPR and Omega estimates become unreliable with fewer than ~30 above-MAR or below-MAR observations respectively. The per-regime output shows observation counts (n=) so users can assess reliability; cells with n < 30 should be treated as directional indicators only, not precise estimates.
- Regime signal synthesis thresholds are calibrated for trend-following / CTA-style strategies. For option-writing or pure mean-reversion strategies, the interpretation of UPR/Sortino and Sortino/Sharpe is inverted: high UPR/Sortino in an option-writing context may indicate the strategy is taking on uncompensated tail risk, not capturing upside cleanly.
- The Burghardt-Liu autocorrelation correction assumes stationarity of the return series within each regime window. For very short regime episodes (< 20 observations), the autocorrelation estimate is unreliable and the correction may amplify rather than remove noise. The corrected Sharpe should be interpreted cautiously for low-count regime cells.
