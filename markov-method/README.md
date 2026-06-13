## What this does

This one-shot prompt installs a working Markov-regime trading skill into your Claude Code at `~/.claude/skills/markov-regime/`. The skill ships the framework hedge fund quants use to model markets as a probability map of regimes — Bull, Bear, Sideways — and to convert state-transition probabilities into a signed trading signal. After install you can ask Claude, in any session, on any ticker, to run the skill — and it will.

About 90 seconds on Mac and Linux, up to 2 to 3 minutes on Windows. The install touches only your home directory — no sudo, no admin password, no API keys, no sign-ups, no accounts. The first run fetches SPY 10y daily data and prints the transition matrix, the stationary distribution, and a walk-forward Sharpe + max drawdown on screen before the agent says it's done.

## Why this matters

A regime is not a vibe drawn on a chart. It is a state in a probability space — and the transition matrix is a literal map of how markets move between states. Most traders look at a chart and see price. Quant research desks at Citadel and Two Sigma look at the same chart and see this matrix. The persistence diagonal of that matrix is how often each state stays where it is. The off-diagonals are how often it flips. That is the structural input every regime-aware systematic strategy is built on.

This is the framework Roan (@RohOnChain) wrote up — backend dev shipping quant research at HFT-firm quality on his own. I read the article, my mind went somewhere, and the most honest thing I could do was install it on camera so you can install it tonight. He's the genius; I'm the guy installing it.

## What you get

- An observable Markov model that fits the 3x3 transition matrix on any ticker via MLE counting.
- A stationary-distribution solver (the long-run regime mix — the tail-risk sanity check you run before you size anything).
- An n-step forecaster via matrix power (Chapman-Kolmogorov — the same math under Google's original PageRank).
- A walk-forward backtest that re-estimates the matrix at every timestep using only data that existed before that day, then reports Sharpe and max drawdown. No lookahead. This is the production-readiness detail that separates real edge from a YouTube backtest scam.
- An optional Hidden Markov Model layer (Baum-Welch + Viterbi via hmmlearn) that infers regimes from raw returns without you labelling anything by hand. Graceful-degrade on Windows machines without Microsoft's C++ Build Tools — the observable model still ships even if hmmlearn won't compile.

## Prerequisites

- Claude Code already installed and running in agent view (the mode where Claude executes commands, not the mode where it describes them).
- A working internet connection for the first install (uv, Python 3.12, and the Python libraries are downloaded once).
- Mac, Windows, or Linux. The agent detects your OS and picks the right install path.
- No Python pre-installed required — uv manages the Python interpreter inside the skill folder. No system Python pollution.

## The one-shot prompt

Paste the markov-prompt.md into Claude Code in agent view and hit Enter. The agent does the rest.

## What the onboarding agent does

- **Environment check** — detects your OS (Mac / Windows / Linux), checks whether uv is installed, installs Astral's uv toolchain via the official installer if it's missing, and detects any previous install of the skill (backed up non-destructively so you can re-run safely).
- **Configuration** — scaffolds `~/.claude/skills/markov-regime/` with the skill module, SKILL.md, and pyproject.toml, then pins Python 3.12 via uv inside a venv local to the skill folder. No system Python touched.
- **Installation** — installs yfinance, numpy, pandas, and scikit-learn into the pinned venv. Then attempts the optional hmmlearn install, wrapped in error handling. If it fails on Windows without MSVC build tools, the agent prints "HMM extension skipped (optional); observable Markov model installed successfully" and continues.
- **First run** — fetches SPY 10y daily OHLCV via yfinance, fits the transition matrix, prints the matrix and the persistence diagonal, solves the stationary distribution, runs the walk-forward backtest, and prints Sharpe + max drawdown. If hmmlearn was installed, fits the HMM and prints the regime mean returns alongside.
- **Confirmation** — prints a summary of what's installed (including the HMM state), names Roan as the framework author, and tells you what you can say to Claude next to run the skill on any other ticker.

## How to use it after setup

Once the install is done, the skill is registered at `~/.claude/skills/markov-regime/`. From any new Claude Code session — in agent view — you can say things like:

- "run the markov regime skill on AAPL"
- "run the markov regime skill on BTC-USD with a 60-day lookback"
- "fit the HMM on QQQ"

Claude invokes the skill via the pinned environment and prints the matrix, stationary distribution, and walk-forward backtest for whatever ticker you named. You can also call the module directly from a terminal:

```bash
cd ~/.claude/skills/markov-regime
uv run python -m markov_regime.run --ticker SPY --years 10 --window 20
```

**Flags:** `--ticker SYMBOL` (default SPY), `--years N` (default 10), `--window N` (rolling-return window in trading days, default 20), `--threshold X` (rolling-return threshold for Bull / Bear labels, default 0.02), `--no-hmm` (skip the HMM fit even if hmmlearn is installed).

## Why a probability map of regimes beats a chart pattern

Most retail technical analysis treats the market like a dice roll — fresh throw every time, no memory. That is the lie. The next state depends on the state you're in. A loan that is "current" cannot jump to "90+ days late" in one month — it has to walk through 30, then 60, then 90. Markets behave the same way. Regimes persist. They don't flip without warning. The transition matrix is the bookkeeping of exactly this — and once you have it, you can ask the only question that matters: given where the market is right now, what is the probability distribution over where it will be next? That is the actual edge hedge fund quants compound on. Not "win every trade" — quantify every future market state from where you are now, and size into the high-probability ones.

The framework is free, the libraries are free, the install is free. The matrix is the measurement. Point it at whatever you trade.

## Stuck?

Comment below with: 1) the phase you got to (1, 2, 3, 4, or 5), 2) the exact error message, 3) your operating system. Lewis or another member will reply within 24 hours.

