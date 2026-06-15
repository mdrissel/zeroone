## What this does

This one-shot prompt installs the **Markov Regime Method** as a Claude Code skill at `~/.claude/skills/markov-regime-method/`. The skill models any ticker as a probability map of regimes — Bull, Bear, Sideways — and converts state-transition probabilities into a signed trading signal. After install you can ask Claude, in any session, on any ticker, to run the skill.

About 90 seconds on Mac and Linux, up to 2–3 minutes on Windows. The install touches only your home directory — no sudo, no admin password, no API keys, no sign-ups. The first run fetches SPY 10y daily data and prints the transition matrix, confidence intervals, stationary distribution, and a walk-forward Sharpe on screen before the agent says it's done.

## Why this matters

A regime is not a vibe drawn on a chart. It is a state in a probability space — and the transition matrix is a literal map of how markets move between states. Most traders look at a chart and see price. Quant research desks at Citadel and Two Sigma look at the same chart and see this matrix. The persistence diagonal is how often each state stays where it is. The off-diagonals are how often it flips. That is the structural input every regime-aware systematic strategy is built on.

This framework is based on Roan's work (@RohOnChain) — a backend dev shipping quant research at HFT-firm quality. Version 3 fixes the statistical flaws in the original and adds the infrastructure needed to trust the output.

## What you get

- **Adaptive z-score labeling** — regime labels calibrate automatically per asset. A 5% move means different things on SPY vs BTC; dividing by rolling volatility makes the threshold asset-agnostic.
- **Stride-sampled transition matrix** — transitions counted on non-overlapping windows only. Overlapping windows inflate the persistence diagonal by ~(window−1)/window; this fix eliminates that bias. The overlapping matrix is shown alongside for comparison.
- **Per-cell confidence intervals** — Wilson score 95% CI on every cell. Cells with fewer than 30 observations are flagged ⚠ LOW CONFIDENCE so you know when the matrix is underpowered.
- **BIC model selection** — fits k=2..5 states and lets the data choose the number of regimes. Reported for information; the model defaults to k=3 (Bull/Bear/Sideways) unless you override.
- **Walk-forward backtest net of transaction costs** — re-estimates the matrix at every timestep using only data that existed before that day. Round-trip costs deducted on every position change. Reports gross Sharpe, net Sharpe, buy-and-hold Sharpe, and excess Sharpe. No lookahead.
- **Excess Sharpe vs buy-and-hold** — the honest benchmark. A positive gross Sharpe that still underperforms buy-and-hold is not edge.
- **HMM disagreement map** — optionally fits a Hidden Markov Model (Baum-Welch + Viterbi via hmmlearn) and shows where it disagrees with the threshold labels. Agreement is the null result; disagreement is the research signal.
- **FILTER and STANDALONE modes** — STANDALONE trades the regime signal directly; FILTER gates an existing strategy, only allowing it to act when the signal clears a threshold.

## Prerequisites

- Claude Code installed and running in agent view (the mode where Claude executes commands, not describes them).
- A working internet connection for the first install (uv, Python 3.12, and the Python libraries are downloaded once).
- Mac, Windows, or Linux. The agent detects your OS and picks the right install path.
- No Python pre-installed required — uv manages the Python interpreter inside the skill folder.

## The one-shot prompt

Paste `markov-method-prompt.md` into Claude Code in agent view and hit Enter. The agent does the rest.

## Setup after cloning this repo

The skill implementation lives at `markov-method/skill/` in this repo. Claude Code expects skills at `~/.claude/skills/`. Wire them up with a single symlink:

```bash
ln -s $(pwd)/markov-method/skill ~/.claude/skills/markov-regime-method
```

Run this once from the repo root after cloning. After that, the skill is live and any changes you make to `markov-method/skill/` are reflected immediately — no reinstall needed.

## What the onboarding agent does

- **Environment check** — detects your OS, checks whether uv is installed, installs Astral's uv toolchain via the official installer if missing, backs up any previous install non-destructively.
- **Configuration** — scaffolds the skill module, SKILL.md, and pyproject.toml, then pins Python 3.12 via uv in a venv local to the skill folder.
- **Installation** — installs yfinance, numpy, pandas, scikit-learn, and scipy. Then attempts the optional hmmlearn install. If it fails (e.g. Windows without MSVC build tools), prints a skip message and continues — the observable model is fully functional without it.
- **First run** — fetches SPY 10y daily OHLCV, labels regimes, runs BIC selection, prints both transition matrices with confidence intervals, runs the walk-forward backtest net of costs, and prints the HMM disagreement map if available.
- **Confirmation** — summarises what's installed, names Roan as the framework author, and tells you what to say next.

## How to use it after setup

From any Claude Code session in agent view:

- "run the markov regime method on AAPL"
- "run the markov regime method on BTC-USD in standalone mode"
- "fit the HMM on QQQ and show where it disagrees with the threshold labels"

Or directly from a terminal:

```bash
cd ~/.claude/skills/markov-regime-method
uv run python -m markov_regime_method.run --ticker SPY --years 10
```

**Flags:**

| Flag | Default | Description |
|---|---|---|
| `--ticker` | `SPY` | Ticker symbol |
| `--years` | `10` | Years of daily history to fetch |
| `--window` | `20` | Rolling-return window in trading days |
| `--z-thresh` | `0.5` | Z-score threshold for Bull/Bear labels |
| `--cost-bps` | `5.0` | One-way transaction cost in basis points |
| `--mode` | `standalone` | `standalone` or `filter` |
| `--signal-threshold` | `0.0` | Minimum \|signal\| to take a position (filter mode) |
| `--k-override` | _(BIC)_ | Force a specific number of regime states |
| `--no-hmm` | — | Skip HMM fit even if hmmlearn is installed |

## Interpreting the output

**Stride-sampled matrix vs overlapping** — the overlapping matrix will always look more persistent than reality. Only the stride-sampled matrix is statistically honest. If confidence intervals are wide or cells are flagged LOW CONFIDENCE, you don't have enough data to trust that row — collect more history or widen the window.

**BIC preferring k=2** — common on large-cap indices like SPY. The data is saying there isn't a statistically distinct "Sideways" regime separate from the others. You can use `--k-override 2` to force it, or keep k=3 for named states.

**Negative excess Sharpe** — means buy-and-hold beat the model on this ticker and period. This is not a bug; it is the honest result. SPY in a bull market is one of the hardest benchmarks. Use the model as a FILTER on another strategy, or point it at a more regime-driven asset (sector ETFs, small-cap, crypto).

**HMM disagreement > 50%** — common and expected. The HMM fits return distributions; the threshold fits levels. They will disagree on transitions and on periods where the market was moving but not trending. Pull those periods and ask which model was right — that is the research.

## Why a probability map of regimes beats a chart pattern

Most retail technical analysis treats the market like a dice roll — fresh throw every time, no memory. That is the lie. The next state depends on the state you're in. Regimes persist. They don't flip without warning. The transition matrix is the bookkeeping of exactly this — and once you have it, you can ask the only question that matters: given where the market is right now, what is the probability distribution over where it will be next? That is the edge quant desks compound on. Not "win every trade" — quantify every future market state from where you are now, and size into the high-probability ones.

The framework is free, the libraries are free, the install is free. The matrix is the measurement. Point it at whatever you trade.

## Stuck?

Comment below with: 1) the phase you got to (1, 2, 3, 4, or 5), 2) the exact error message, 3) your operating system. Lewis or another member will reply within 24 hours.
