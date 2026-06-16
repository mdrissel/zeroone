---
name: regime-performance-analytics
description: >
  Statistically rigorous Markov regime model with CTA-grade performance analytics.
  Adaptive z-score labeling, stride-sampled transition matrix with per-cell
  confidence intervals, BIC-driven state-count selection, walk-forward backtest
  net of transaction costs, Burghardt-Liu (2012) autocorrelation-corrected Sharpe,
  correct Sortino ratio (Red Rock/CME method, all N in denominator),
  regime-conditional interpretation block, and HMM disagreement analysis.
  Supports FILTER and STANDALONE operating modes.
  Previous name: markov-regime-method (backward-compatible, same CLI flags).
---

# regime-performance-analytics

Install location: `~/.claude/skills/markov-regime-method/` (symlink to repo)
Framework author: Roan (@RohOnChain). Extended by Lewis Jackson.

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

Backward-compatible entry point (same output):
```bash
uv run python -m markov_regime_method.run --ticker SPY
```

## CLI flags

| Flag | Default | Description |
|---|---|---|
| `--ticker` | `SPY` | Ticker symbol |
| `--years` | `10` | Years of daily history |
| `--window` | `20` | Rolling-return window (trading days) |
| `--z-thresh` | `0.5` | Z-score threshold for Bull/Bear labels |
| `--cost-bps` | `5.0` | One-way transaction cost in basis points |
| `--mode` | `standalone` | `standalone` or `filter` |
| `--signal-threshold` | `0.0` | Min \|signal\| for filter mode |
| `--k-override` | _(BIC)_ | Force number of regime states |
| `--no-hmm` | — | Skip HMM fit |
| `--mar` | `zero` | MAR for Sortino: `rfr`, `zero`, or decimal float (e.g. `0.07`) |

## Outputs on every run

1. Regime label distribution (% Bull / Bear / Sideways) — sanity check.
2. BIC curve across k=2..5 states; optimal k highlighted.
3. Overlapping vs stride-sampled transition matrix with 95% CI per cell.
4. Stationary distribution (long-run regime mix).
5. Multi-step forecast table (1–5 steps + convergence to stationary).
6. Walk-forward backtest net of round-trip costs: gross Sharpe, net Sharpe,
   buy-and-hold Sharpe, excess Sharpe, max drawdown, win rate, profit factor.

**Extension 1 — Burghardt-Liu (2012) autocorrelation-corrected Sharpe:**

7. Five-lag serial autocorrelation sum (Σρ lags 1–5) on monthly return series.
8. Naive annualised volatility vs autocorrelation-corrected volatility side by side.
   Formula: σ_corrected = σ_monthly × √(12 × (1 + 2 × Σρ)).
9. Naive Sharpe vs corrected Sharpe side by side.
10. Per-regime Σρ (daily sub-series). Flag: Σρ < -0.15 → trend-favorable;
    Σρ > +0.10 → mean-reversion / momentum-in-price.

**Extension 2 — Correct Sortino ratio (Red Rock / CME method):**

11. Target Downside Deviation (TDD) using all N observations in the denominator —
    not std of negative-only returns. Correct method distinguishes:
    [0, 0, 0, -10%] (TDD=5%) from [-10%, -10%, -10%, -10%] (TDD=10%).
    The industry error gives TDD=10% for both.
12. Sortino ratio = (annualised return − MAR) / TDD_annual. Reported overall
    and per regime.
13. Sortino/Sharpe ratio with skewness classification:
    >1.2 = positive skew / trend-favorable; 0.8–1.2 = near-symmetric;
    <0.8 = negative skew / left-tail risk (option-writer profile).

**Extension 3 — Regime-conditional interpretation block:**

14. Per-regime summary table: corrected Sharpe, Sortino, S÷Sr, autocorr sum,
    skewness class.
15. Flag: high transition persistence (diagonal > 70%) AND Σρ < -0.15 →
    high-confidence trend-following environment.
16. Flag: HMM/threshold disagreement periods with near-zero autocorrelation (Σρ ≈ 0) →
    ambiguous / choppy — suppress trend signals from Markov matrix.

17. HMM disagreement map (if hmmlearn available): where HMM and threshold labels
    disagree is the research signal, not the agreement.

## Theoretical basis

**Burghardt-Liu (2012):**
CTA index monthly returns exhibit Σρ ≈ -0.20 at lags 1–5. Naive Sharpe assumes
i.i.d. returns. When autocorrelation is negative, the effective vol is lower than
naive suggests, so corrected Sharpe > naive Sharpe for trend-following strategies.
The correction factor is (1 + 2Σρ). When Σρ < 0, σ_corrected < σ_naive.

**Red Rock / CME Sortino (2008):**
The original Sortino (1994) definition uses all N observations in the TDD
denominator. The industry adopted a shortcut (N_negative only) that conflates
frequency of loss with magnitude of loss. The correct method penalises both.
