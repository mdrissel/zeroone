---
name: markov-regime-method
description: >
  Statistically rigorous Markov regime model for any ticker. Adaptive z-score
  labeling, stride-sampled transition matrix with per-cell confidence intervals,
  BIC-driven state-count selection, walk-forward backtest net of transaction
  costs, excess-Sharpe benchmark vs buy-and-hold, HMM disagreement analysis.
  Supports FILTER and STANDALONE operating modes.
---

# markov-regime-method

Install location: `~/.claude/skills/markov-regime-method/`
Framework author: Roan (@RohOnChain). Extended by Lewis Jackson.

## Invocation

- "run the markov regime method on SPY"
- "run the markov regime method on BTC-USD in standalone mode"
- "fit the HMM on QQQ and show where it disagrees with the threshold labels"

```bash
cd ~/.claude/skills/markov-regime-method
uv run python -m markov_regime_method.run \
  --ticker SPY \
  --years 10 \
  --window 20 \
  --cost-bps 5 \
  --mode standalone \
  [--no-hmm] [--k-override 3]
```

## Outputs on every run

1. Regime label distribution (% Bull / Bear / Sideways) — sanity check.
2. BIC curve across k=2..5 states; optimal k highlighted.
3. Overlapping transition matrix (legacy) vs stride-sampled matrix (statistically honest) side by side.
4. Per-cell observation counts and 95% confidence intervals. Low-count cells (< 30) flagged.
5. Stationary distribution.
6. Multi-step forecast table (1–5 steps + convergence to stationary).
7. Walk-forward backtest net of round-trip costs: Sharpe, max drawdown, win rate, profit factor.
8. Buy-and-hold benchmark; excess Sharpe reported.
9. HMM regime mean returns (if available) with disagreement map vs threshold labels.
