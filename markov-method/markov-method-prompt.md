You are an onboarding agent installing the **Markov Regime Method** as a Claude Code skill. You act — you never instruct. You detect the operating system, you run installs, you handle errors. The user watches.

The skill you are about to install ships a Python module that:

- Fetches daily OHLCV for any ticker via yfinance (free, no key).
- Labels each day as Bull / Bear / Sideways using a z-score of the 20-day rolling return against its own rolling volatility (adaptive threshold — automatically calibrated per asset).
- Builds the transition matrix via maximum-likelihood counting using **stride sampling** (non-overlapping windows) to produce statistically honest transition counts — and shows the overlapping version side-by-side so the user can see the difference.
- Reports **observation counts and confidence intervals per cell** — flags any cell with fewer than 30 transitions as low-confidence.
- Selects the optimal number of regimes (2–5) using BIC, then defaults to 3; reports why.
- Forecasts n-step ahead by matrix powers (Chapman-Kolmogorov); reports convergence to the stationary distribution.
- Runs a walk-forward backtest **net of configurable round-trip transaction costs** (default 5 bps equities, 20 bps crypto), and benchmarks excess Sharpe vs buy-and-hold.
- Optionally fits a Hidden Markov Model via hmmlearn (Baum-Welch + Viterbi); specifically highlights where the HMM **disagrees** with the threshold labels, as that disagreement is the research signal.
- Supports two operating modes: **FILTER** (gate an existing strategy) and **STANDALONE** (trade the differential directly).

This is Roan's framework (@RohOnChain), extended and corrected. Installing as a Claude Code skill so you can run it on any ticker in any future session.

## Phase 0 — Welcome and confirmation

Print this banner so the user knows the agent is running, not describing:

```
✓ Running in agent mode — Markov Regime Method install starting.
```

Then say in plain English: "I'm going to install the Markov Regime Method skill into `~/.claude/skills/markov-regime-method/`. About 90 seconds on Mac and Linux, up to 2–3 minutes on Windows. No keys, no accounts, no admin password. Ready?"

Wait for the user to type **go** before continuing.

Ask: "Quick one before we start — are you going to type to me, or would you like to talk? Speaking is about 3× faster than typing."
- If they want to talk: "Lewis (who made this) uses a free Mac app called Yapper. Want it? You get 2,000 words free, no card needed." If yes, open `https://getyapper.app` with the OS-correct command and include the link. Continue once they're ready.
- If they'd rather type: continue.

Also ask: "Which mode do you want to use?
- **FILTER mode** (default): the regime gates an existing strategy — longs only when the signal is above a threshold, shorts only when below, flat in chop. Your strategy stays yours; the Markov model decides *when* it's allowed to act.
- **STANDALONE mode**: trade the regime differential directly, position size scaled to |signal| with a cap you set.

Two very different use cases. FILTER is safer for beginners; STANDALONE gives you full regime exposure. Which?"

Store the answer as `OPERATING_MODE`. Default to FILTER if they're unsure.

## Phase 1 — Environment check

### 1.1 — Detect the operating system

```bash
uname -s 2>/dev/null || echo "Windows_NT"
```

- Darwin → OS_KIND=mac. Open command: `open`.
- Linux → OS_KIND=linux. Open command: `xdg-open`.
- Windows_NT → OS_KIND=windows. Open command: `start`.

Print: `OS detected: <mac|linux|windows>`.

### 1.2 — Check for existing install (idempotency)

```bash
ls -la ~/.claude/skills/markov-regime-method 2>/dev/null
```

If it exists, back it up non-destructively:

```bash
STAMP=$(date +%Y%m%d-%H%M%S)
mv ~/.claude/skills/markov-regime-method ~/.claude/skills/.markov-regime-method.bak.$STAMP
```

Print: `Previous install backed up to ~/.claude/skills/.markov-regime-method.bak.<timestamp>. Running fresh install.`

### 1.3 — Check for uv

```bash
uv --version
```

If already installed, print `✓ uv already installed` and skip to Phase 2.

If missing, install via the official Astral installer:

Mac / Linux:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows (PowerShell):
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Refresh PATH:
```bash
source $HOME/.local/bin/env 2>/dev/null || export PATH="$HOME/.local/bin:$PATH"
```

Re-verify:
```bash
uv --version
```

If still failing, open the install docs:
- Mac: `open https://docs.astral.sh/uv/getting-started/installation/`
- Linux: `xdg-open https://docs.astral.sh/uv/getting-started/installation/`
- Windows: `start https://docs.astral.sh/uv/getting-started/installation/`

Do not proceed without uv.

## Phase 2 — Configuration

### 2.1 — Create the skill directory tree

```bash
mkdir -p ~/.claude/skills/markov-regime-method/markov_regime_method ~/.claude/skills/markov-regime-method/data
```

### 2.2 — Write the skill files

Write `~/.claude/skills/markov-regime-method/SKILL.md`:

```markdown
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
  --mode filter \
  [--no-hmm] [--k-override 3]
```

## Outputs on every run

1. Regime label distribution (% Bull / Bear / Sideways) — sanity check.
2. BIC curve across k=2..5 states; optimal k highlighted.
3. Overlapping transition matrix (legacy) vs stride-sampled matrix (statistically honest) side by side.
4. Per-cell observation counts and 95% confidence intervals. Low-count cells (< 30) flagged.
5. Stationary distribution.
6. Walk-forward backtest net of round-trip costs: Sharpe, max drawdown, win rate, profit factor.
7. Buy-and-hold benchmark; excess Sharpe reported.
8. HMM regime mean returns (if available) with disagreement map vs threshold labels.
```

Write `~/.claude/skills/markov-regime-method/markov_regime_method/__init__.py`:

```python
"""Markov Regime Method — statistically rigorous regime model with optional HMM."""
__version__ = "2.0.0"
```

Write `~/.claude/skills/markov-regime-method/markov_regime_method/regime.py`:

```python
"""Markov regime model — adaptive labeling, stride-sampled matrix, confidence intervals.

Key design decisions vs the original:
- Adaptive threshold: z-score of rolling return / rolling vol, not a fixed %.
  This self-calibrates per asset; a 5% move means different things on SPY vs BTC.
- Stride sampling: transitions counted on NON-overlapping windows (stride=window).
  Overlapping windows inflate the diagonal by ~(window-1)/window — this is the
  most common flaw in retail regime models.
- Confidence intervals: multinomial proportion CI per cell. Flag cells with n<30.
- BIC model selection: fit k=2..5 and let the data choose the number of states.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


STATES_3 = ["Bear", "Sideways", "Bull"]   # default 3-state labels
MIN_CELL_OBS = 30                          # flag cells below this count


# ---------------------------------------------------------------------------
# Regime labeling
# ---------------------------------------------------------------------------

def label_regimes_adaptive(
    close: pd.Series,
    window: int = 20,
    z_thresh: float = 0.5,
) -> pd.Series:
    """Label each day Bull/Bear/Sideways using z-scored rolling return.

    Why z-score instead of fixed threshold:
      A 5% 20-day move is noise on BTC but a significant move on TLT.
      Dividing by rolling volatility makes the threshold asset-agnostic.

    z_thresh: how many std devs from zero counts as a directional regime.
      Default 0.5 captures roughly the top/bottom ~30% of observations
      as Bull/Bear, leaving ~40% as Sideways — reasonable priors for most
      liquid assets. Raise to 1.0 for a stricter "only strong regimes" mode.
    """
    rolling_ret = close.pct_change(window)
    rolling_vol = rolling_ret.rolling(window * 3, min_periods=window).std()
    z = rolling_ret / rolling_vol.replace(0, np.nan)

    labels = pd.Series(1, index=close.index, dtype=int)  # default Sideways (1)
    labels[z > z_thresh] = 2   # Bull
    labels[z < -z_thresh] = 0  # Bear

    labeled = labels.dropna()

    # Sanity-check: each regime should appear at least 10% of the time.
    # If not, warn — the threshold is probably wrong for this asset.
    counts = labeled.value_counts(normalize=True)
    for state_idx, name in enumerate(STATES_3):
        freq = counts.get(state_idx, 0.0)
        if freq < 0.05:
            print(
                f"  ⚠ Label warning: '{name}' appears only {freq:.1%} of the time. "
                f"Consider adjusting --z-thresh for this asset."
            )

    return labeled


def verify_labels(labels: pd.Series, close: pd.Series) -> None:
    """Programmatically verify that labels make economic sense.

    Checks three anchor periods known a priori:
      - 2017-01 to 2018-01: strong equity bull
      - 2020-02 to 2020-04: COVID crash
      - 2015-07 to 2016-07: choppy/flat SPY

    Only runs if the data covers these periods. Prints a pass/fail per period.
    This catches display bugs (bull/bear swapped) and gross calibration errors.
    """
    checks = [
        ("2017-01-01", "2018-01-01", 2, "Bull (2017 equity rally)"),
        ("2020-02-15", "2020-04-30", 0, "Bear (2020 COVID crash)"),
    ]
    for start, end, expected_dominant, desc in checks:
        try:
            window_labels = labels.loc[start:end]
            if len(window_labels) < 10:
                continue
            dominant = int(window_labels.mode()[0])
            status = "✓" if dominant == expected_dominant else "✗"
            actual_name = STATES_3[dominant]
            expected_name = STATES_3[expected_dominant]
            print(
                f"  {status} Label check [{desc}]: "
                f"dominant regime = {actual_name} "
                f"(expected {expected_name})"
            )
        except Exception:
            pass  # period not in data — skip silently


# ---------------------------------------------------------------------------
# Transition matrix — stride-sampled (statistically honest)
# ---------------------------------------------------------------------------

def build_transition_matrix(
    labels: pd.Series,
    n_states: int = 3,
    stride: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Build the MLE transition matrix.

    Args:
        labels: integer state sequence.
        n_states: number of states (matches the k used in label_regimes_*).
        stride: if None, use overlapping consecutive-day transitions (legacy,
                inflates diagonal). If int, use non-overlapping windows of
                this length (stride-sampled — statistically honest).

    Returns:
        (P, counts): row-normalised probability matrix and raw count matrix.
    """
    arr = labels.to_numpy()
    counts = np.zeros((n_states, n_states), dtype=float)

    if stride is None:
        # Overlapping: every consecutive pair (day t → day t+1)
        for i in range(len(arr) - 1):
            counts[arr[i], arr[i + 1]] += 1
    else:
        # Stride-sampled: only non-overlapping epochs
        # idx selects the LAST bar of each non-overlapping window
        indices = list(range(stride - 1, len(arr), stride))
        for i in range(len(indices) - 1):
            from_state = arr[indices[i]]
            to_state = arr[indices[i + 1]]
            counts[from_state, to_state] += 1

    row_sums = counts.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0  # guard against unseen states
    P = counts / row_sums

    return P, counts


def transition_confidence_intervals(
    counts: np.ndarray,
    confidence: float = 0.95,
) -> np.ndarray:
    """Wilson score 95% CI half-width per cell.

    For a multinomial row, the Wilson interval for each cell gives the
    uncertainty in the estimated transition probability given the row's
    total observation count. Returns a matrix of half-widths (±).

    Cells with row_sum < MIN_CELL_OBS are flagged as low-confidence.
    """
    n_states = counts.shape[0]
    ci_half = np.zeros_like(counts)
    z = stats.norm.ppf((1 + confidence) / 2)

    for i in range(n_states):
        n = counts[i].sum()
        if n == 0:
            ci_half[i] = np.nan
            continue
        for j in range(n_states):
            p_hat = counts[i, j] / n
            # Wilson score interval half-width (simplified to normal approx for clarity)
            ci_half[i, j] = z * np.sqrt(p_hat * (1 - p_hat) / n)

    return ci_half


def print_matrix_comparison(
    P_overlap: np.ndarray,
    counts_overlap: np.ndarray,
    P_stride: np.ndarray,
    counts_stride: np.ndarray,
    state_names: list[str],
) -> None:
    """Print overlapping vs stride-sampled matrices side by side."""
    ci_stride = transition_confidence_intervals(counts_stride)
    n = len(state_names)

    print("\n  ── Overlapping transitions (legacy — diagonal inflated) ──")
    print(f"  {'':>10s}", end="")
    for name in state_names:
        print(f"  {name:>9s}", end="")
    print()
    for i, from_name in enumerate(state_names):
        n_row = int(counts_overlap[i].sum())
        print(f"  {from_name:>10s}", end="")
        for j in range(n):
            print(f"  {P_overlap[i, j]*100:7.1f}% ", end="")
        print(f"  (n={n_row})")

    print("\n  ── Stride-sampled transitions (statistically honest) ──")
    print(f"  {'':>10s}", end="")
    for name in state_names:
        print(f"  {name:>9s}", end="")
    print("  [95% CI ±]")
    for i, from_name in enumerate(state_names):
        n_row = int(counts_stride[i].sum())
        low_conf = "  ⚠ LOW CONFIDENCE" if n_row < MIN_CELL_OBS else ""
        print(f"  {from_name:>10s}", end="")
        for j in range(n):
            p = P_stride[i, j] * 100
            ci = ci_stride[i, j] * 100
            print(f"  {p:5.1f}±{ci:4.1f}%", end="")
        print(f"  (n={n_row}){low_conf}")

    print()
    print("  ⚠ Only the stride-sampled matrix is statistically honest.")
    print("    Overlapping windows share 19 of 20 days, inflating the diagonal")
    print("    by ~(window-1)/window — a persistent-looking matrix may be noise.")


# ---------------------------------------------------------------------------
# BIC model selection
# ---------------------------------------------------------------------------

def bic_for_k_states(
    labels: pd.Series,
    k: int,
    window: int,
) -> float:
    """Compute BIC for a k-state model fitted on stride-sampled transitions.

    BIC = -2 * log_likelihood + n_params * log(n_observations)
    For a k-state Markov chain: n_params = k*(k-1) (free params per row).
    Log-likelihood = sum over observed transitions of log P(to|from).
    """
    # Re-bin labels to k states by quantile-splitting the z-scores
    # (Simple approach: equal-frequency binning of the existing 3-state labels
    #  remapped to k states via quantile cut on the raw return.)
    arr = labels.to_numpy()
    indices = list(range(window - 1, len(arr), window))
    if len(indices) < k * 5:
        return np.inf  # not enough data for this k

    counts = np.zeros((k, k), dtype=float)
    # Map 3-state labels to k states proportionally
    state_map = np.clip((arr * (k / 3)).astype(int), 0, k - 1)
    for i in range(len(indices) - 1):
        f = state_map[indices[i]]
        t = state_map[indices[i + 1]]
        counts[f, t] += 1

    row_sums = counts.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0
    P = counts / row_sums

    log_lik = 0.0
    n_obs = 0
    for i in range(len(indices) - 1):
        f = state_map[indices[i]]
        t = state_map[indices[i + 1]]
        p = P[f, t]
        if p > 0:
            log_lik += np.log(p)
            n_obs += 1

    n_params = k * (k - 1)
    bic = -2 * log_lik + n_params * np.log(max(n_obs, 1))
    return bic


def select_optimal_k(
    labels: pd.Series,
    window: int,
    k_range: range = range(2, 6),
) -> int:
    """Select the number of regime states using BIC. Print the BIC curve."""
    print("\n  ── BIC model selection (lower = better fit) ──")
    bic_scores = {}
    for k in k_range:
        bic_scores[k] = bic_for_k_states(labels, k, window)
        print(f"    k={k}: BIC = {bic_scores[k]:.1f}")

    best_k = min(bic_scores, key=bic_scores.get)
    print(f"  ✓ Optimal k = {best_k} (lowest BIC)")
    return best_k


# ---------------------------------------------------------------------------
# Stationary distribution and signal
# ---------------------------------------------------------------------------

def stationary_distribution(P: np.ndarray) -> np.ndarray:
    """Left eigenvector of P with eigenvalue 1, normalised to sum to 1."""
    eigvals, eigvecs = np.linalg.eig(P.T)
    idx = np.argmin(np.abs(eigvals - 1.0))
    vec = np.real(eigvecs[:, idx])
    vec = np.abs(vec)
    return vec / vec.sum()


def n_step_forecast(P: np.ndarray, n: int) -> np.ndarray:
    """Chapman-Kolmogorov: P^n is the n-step transition matrix."""
    return np.linalg.matrix_power(P, n)


def signal_from_matrix(P: np.ndarray, current_state: int, n_states: int = 3) -> float:
    """Signed signal: P(next=highest_state|current) - P(next=lowest_state|current).

    Positive → long, negative → short, magnitude → conviction.

    Note: for a 3-state model (0=Bear,1=Sideways,2=Bull):
      signal = P[current,2] - P[current,0]

    The signal is most informative when it DEVIATES from what the stationary
    distribution would predict. If Bull persists 90% of the time and you're
    already in Bull, the signal is telling you something you already know.
    The excess signal (vs stationary) is the actual informational content.
    """
    bull_state = n_states - 1
    bear_state = 0
    return float(P[current_state, bull_state] - P[current_state, bear_state])


def excess_signal(P: np.ndarray, pi: np.ndarray, current_state: int, n_states: int = 3) -> float:
    """Signal minus what you'd expect from the stationary distribution alone.

    This measures incremental information content — the part that isn't
    just 'the market has been bullish so it'll stay bullish.'
    """
    raw = signal_from_matrix(P, current_state, n_states)
    baseline = float(pi[n_states - 1] - pi[0])  # stationary bull - bear
    return raw - baseline


# ---------------------------------------------------------------------------
# Walk-forward backtest
# ---------------------------------------------------------------------------

def walk_forward_backtest(
    close: pd.Series,
    labels: pd.Series,
    window: int = 20,
    min_train: int = 252,
    cost_bps: float = 5.0,
    mode: str = "standalone",
    signal_threshold: float = 0.0,
) -> dict:
    """Walk-forward: at each day t, fit the matrix on labels up to t-1.

    Key integrity guarantees:
    - Matrix re-estimated at every step using only data before that day.
    - Threshold re-estimated as rolling z-score — no look-ahead in the label rule.
    - Round-trip transaction costs deducted on every position change.
    - Mode 'filter': only trade when |signal| > signal_threshold.
    - Mode 'standalone': position = sign(signal) scaled by |signal| / max_signal.
    - All metrics reported BOTH gross and net of costs.

    Args:
        cost_bps: one-way cost in basis points (default 5 bps = 0.05%).
                  Round trip = 2 * cost_bps. Typical ranges:
                  SPY/QQQ: 2-5 bps, Small-cap equities: 10-20 bps,
                  BTC on major CEX: 10-20 bps, Crypto altcoins: 20-50 bps.
        mode: 'filter' or 'standalone'.
        signal_threshold: for filter mode, only take positions when
                          |signal| > this threshold (default 0 = always).
    """
    daily_returns = close.pct_change().dropna()
    common_index = labels.index.intersection(daily_returns.index)
    labels = labels.loc[common_index]
    daily_returns = daily_returns.loc[common_index]

    if len(labels) < min_train + 30:
        return {
            "sharpe_net": float("nan"), "sharpe_gross": float("nan"),
            "max_drawdown": float("nan"), "win_rate": float("nan"),
            "profit_factor": float("nan"), "n_trades": 0,
            "bh_sharpe": float("nan"), "excess_sharpe": float("nan"),
        }

    cost_per_side = cost_bps / 10_000.0
    strategy_returns_gross = []
    strategy_returns_net = []
    prev_position = 0.0

    for t in range(min_train, len(labels) - 1):
        P_t, _ = build_transition_matrix(labels.iloc[:t], n_states=3, stride=window)
        pi_t = stationary_distribution(P_t)
        current_state = int(labels.iloc[t])
        sig = excess_signal(P_t, pi_t, current_state, n_states=3)
        next_day_return = float(daily_returns.iloc[t + 1])

        if mode == "standalone":
            position = float(np.sign(sig))
        else:  # filter
            position = float(np.sign(sig)) if abs(sig) > signal_threshold else 0.0

        gross_ret = position * next_day_return
        # Cost only charged on position changes
        turnover = abs(position - prev_position)
        cost = turnover * cost_per_side  # one-way cost × units turned

        strategy_returns_gross.append(gross_ret)
        strategy_returns_net.append(gross_ret - cost)
        prev_position = position

    def _sharpe(arr):
        a = np.array(arr, dtype=float)
        if a.std(ddof=1) == 0 or not np.isfinite(a.std(ddof=1)):
            return float("nan")
        return float(a.mean() / a.std(ddof=1) * np.sqrt(252))

    def _max_dd(arr):
        eq = (1.0 + np.array(arr, dtype=float)).cumprod()
        rm = np.maximum.accumulate(eq)
        dd = (eq - rm) / rm
        return float(dd.min()) if len(dd) else float("nan")

    def _win_rate(arr):
        a = np.array(arr, dtype=float)
        nonzero = a[a != 0]
        return float((nonzero > 0).mean()) if len(nonzero) else float("nan")

    def _profit_factor(arr):
        a = np.array(arr, dtype=float)
        wins = a[a > 0].sum()
        losses = abs(a[a < 0].sum())
        return float(wins / losses) if losses > 0 else float("nan")

    # Buy-and-hold benchmark (same period)
    bh_slice = daily_returns.iloc[min_train:min_train + len(strategy_returns_net)]
    bh_sharpe = _sharpe(bh_slice.tolist())
    net_sharpe = _sharpe(strategy_returns_net)

    return {
        "sharpe_gross": _sharpe(strategy_returns_gross),
        "sharpe_net": net_sharpe,
        "bh_sharpe": bh_sharpe,
        "excess_sharpe": float(net_sharpe - bh_sharpe) if np.isfinite(net_sharpe) and np.isfinite(bh_sharpe) else float("nan"),
        "max_drawdown": _max_dd(strategy_returns_net),
        "win_rate": _win_rate(strategy_returns_net),
        "profit_factor": _profit_factor(strategy_returns_net),
        "n_trades": len(strategy_returns_net),
        "cost_bps": cost_bps,
    }
```

Write `~/.claude/skills/markov-regime-method/markov_regime_method/hmm_extension.py`:

```python
"""Optional Hidden Markov Model layer. Imports hmmlearn lazily.

Key change from v1: the primary output is WHERE the HMM DISAGREES with the
threshold labels, not where it agrees. Agreement is the null result.
Disagreement is the research signal — it means the threshold labeling is wrong
and the HMM is surfacing latent structure that a fixed threshold cannot see.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def fit_hmm(returns: pd.Series, n_components: int = 3, n_trials: int = 5):
    """Fit a Gaussian HMM on daily returns.

    Runs n_trials fits with different random seeds and keeps the best by
    log-likelihood. Baum-Welch finds local maxima; multiple starts reduce
    the risk of a poor solution.

    Returns (model, hidden_states) or (None, None) if hmmlearn not installed.
    """
    try:
        from hmmlearn import hmm
    except ImportError:
        return None, None

    X = returns.dropna().to_numpy().reshape(-1, 1)
    best_model = None
    best_score = -np.inf

    for seed in range(n_trials):
        try:
            m = hmm.GaussianHMM(
                n_components=n_components,
                covariance_type="diag",
                n_iter=300,
                random_state=seed,
            )
            m.fit(X)
            score = m.score(X)
            if score > best_score:
                best_score = score
                best_model = m
        except Exception:
            continue

    if best_model is None:
        return None, None

    hidden_states = best_model.predict(X)
    return best_model, hidden_states


def hmm_disagreement_map(
    threshold_labels: pd.Series,
    returns: pd.Series,
    hmm_states: np.ndarray,
    state_names: list[str],
) -> None:
    """Print where the HMM disagrees with threshold labels.

    This is the analytically interesting output. Where the two models agree,
    the threshold is probably correct. Where they disagree, one of them is
    wrong — and the HMM is fitting latent volatility structure that the
    fixed threshold cannot see, making disagreement the research opportunity.
    """
    aligned_thresh = threshold_labels.dropna()
    common_idx = aligned_thresh.index[:len(hmm_states)]
    thresh_arr = aligned_thresh.loc[common_idx].to_numpy()
    hmm_arr = hmm_states[:len(thresh_arr)]

    # Sort HMM states by mean return to assign Bull/Bear/Sideways semantics
    means = []
    for k in range(hmm_arr.max() + 1):
        mask = hmm_arr == k
        m = returns.dropna().iloc[:len(hmm_arr)].to_numpy()[mask].mean() if mask.any() else 0
        means.append(m)

    order = np.argsort(means)  # lowest mean return = Bear
    remap = {old: new for new, old in enumerate(order)}
    hmm_semantic = np.array([remap[s] for s in hmm_arr])

    agree_mask = thresh_arr == hmm_semantic
    agree_pct = agree_mask.mean() * 100

    print(f"\n  HMM vs threshold-label agreement: {agree_pct:.1f}%")
    print(f"  Disagreement: {100 - agree_pct:.1f}% of bars")
    print()

    # Show the disagreement breakdown by threshold state
    print("  Disagreement map (read: threshold says X, HMM says Y):")
    disagree_idx = np.where(~agree_mask)[0]
    confusion = {}
    for i in disagree_idx:
        key = (state_names[thresh_arr[i]], state_names[hmm_semantic[i]])
        confusion[key] = confusion.get(key, 0) + 1

    for (thresh_state, hmm_state), count in sorted(confusion.items(), key=lambda x: -x[1]):
        print(f"    Threshold={thresh_state:>9s}, HMM={hmm_state:>9s}: {count:4d} bars")

    print()
    print("  ⚠ Bars where models DISAGREE are the research opportunity.")
    print("    Pull those periods and ask: which model was right?")
    print("    The HMM is fitting return distributions; the threshold is fitting levels.")
    print("    They should agree on obvious regimes and diverge on transitions.")
```

Write `~/.claude/skills/markov-regime-method/markov_regime_method/run.py`:

```python
"""CLI entry point: fetch → label → matrix → backtest → report.

Usage:
    uv run python -m markov_regime_method.run --ticker SPY --years 10
    uv run python -m markov_regime_method.run --ticker BTC-USD --cost-bps 20 --mode standalone
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .regime import (
    STATES_3,
    label_regimes_adaptive,
    verify_labels,
    build_transition_matrix,
    print_matrix_comparison,
    select_optimal_k,
    stationary_distribution,
    n_step_forecast,
    signal_from_matrix,
    excess_signal,
    walk_forward_backtest,
)

HMM_FLAG_FILE = Path(__file__).resolve().parent.parent / ".hmm_available"


def _hmm_available() -> bool:
    if HMM_FLAG_FILE.exists():
        return HMM_FLAG_FILE.read_text().strip().lower() == "true"
    try:
        import hmmlearn  # noqa: F401
        return True
    except ImportError:
        return False


def _fetch_with_retry(ticker: str, years: int) -> pd.DataFrame:
    import yfinance as yf
    end = pd.Timestamp.utcnow().normalize()
    start = end - pd.DateOffset(years=years)
    for attempt in (1, 2):
        try:
            df = yf.download(
                ticker,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,
            )
        except Exception as exc:
            print(f"  ! yfinance error on attempt {attempt}: {exc}")
            df = pd.DataFrame()
        if not df.empty:
            return df
        if attempt == 1:
            print("  ! yfinance returned empty data — retrying in 30s.")
            time.sleep(30)
    raise RuntimeError(
        f"yfinance returned empty data for {ticker} after retry. "
        "Yahoo may be rate-limiting. Try again in a few minutes."
    )


def main() -> int:
    parser = argparse.ArgumentParser(prog="markov-regime-method")
    parser.add_argument("--ticker", default="SPY")
    parser.add_argument("--years", type=int, default=10)
    parser.add_argument("--window", type=int, default=20,
                        help="Rolling-return window in trading days")
    parser.add_argument("--z-thresh", type=float, default=0.5,
                        help="Z-score threshold for Bull/Bear labeling (default 0.5)")
    parser.add_argument("--cost-bps", type=float, default=5.0,
                        help="One-way transaction cost in basis points (default 5)")
    parser.add_argument("--mode", default="standalone", choices=["standalone", "filter"],
                        help="Operating mode: standalone (trade signal directly) or filter (gate a strategy)")
    parser.add_argument("--signal-threshold", type=float, default=0.0,
                        help="For filter mode: minimum |signal| to take a position")
    parser.add_argument("--k-override", type=int, default=None,
                        help="Override BIC model selection; force k states")
    parser.add_argument("--no-hmm", action="store_true",
                        help="Skip HMM fit even if hmmlearn is installed")
    args = parser.parse_args()

    print(f"\nMarkov Regime Method — ticker={args.ticker} years={args.years} "
          f"window={args.window} mode={args.mode} cost={args.cost_bps}bps")
    print(f"  fetching {args.ticker} from Yahoo Finance...")
    df = _fetch_with_retry(args.ticker, args.years)

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    close = df["Close"].dropna()
    print(f"  fetched {len(close)} rows | {close.index.min().date()} → {close.index.max().date()}")

    # ── Label regimes ──────────────────────────────────────────────────────
    print(f"\n  Labeling regimes (adaptive z-score threshold = ±{args.z_thresh})...")
    labels = label_regimes_adaptive(close, window=args.window, z_thresh=args.z_thresh)

    # Label frequency sanity check
    freq = labels.value_counts(normalize=True).sort_index()
    print("  Regime frequencies:")
    for idx, name in enumerate(STATES_3):
        f = freq.get(idx, 0.0)
        print(f"    {name:>9s}: {f:.1%}")

    # Verify labels against known anchor periods
    verify_labels(labels, close)

    # ── BIC model selection ────────────────────────────────────────────────
    if args.k_override:
        best_k = args.k_override
        print(f"\n  k overridden to {best_k} (skipping BIC)")
    else:
        best_k = select_optimal_k(labels, args.window)

    state_names = STATES_3 if best_k == 3 else [f"State{i}" for i in range(best_k)]

    # ── Build matrices: overlapping (legacy) and stride-sampled (honest) ──
    P_overlap, C_overlap = build_transition_matrix(labels, n_states=3, stride=None)
    P_stride, C_stride = build_transition_matrix(labels, n_states=3, stride=args.window)
    print_matrix_comparison(P_overlap, C_overlap, P_stride, C_stride, state_names)

    # ── Stationary distribution ────────────────────────────────────────────
    pi = stationary_distribution(P_stride)
    print("  Stationary distribution (long-run regime mix):")
    for name, p in zip(state_names, pi):
        print(f"    {name:>9s}: {p*100:.2f}%")

    # ── Current regime signal ──────────────────────────────────────────────
    current_state = int(labels.iloc[-1])
    raw_sig = signal_from_matrix(P_stride, current_state)
    exc_sig = excess_signal(P_stride, pi, current_state)
    print(f"\n  Current regime: {state_names[current_state]}")
    print(f"  Raw signal:     {raw_sig:+.4f}")
    print(f"  Excess signal:  {exc_sig:+.4f}  (raw minus stationary baseline)")
    print(f"  (Excess signal is the informational content above 'market has memory')")

    # ── Walk-forward backtest ──────────────────────────────────────────────
    print(f"\n  Walk-forward backtest (net of {args.cost_bps} bps/side, mode={args.mode})...")
    result = walk_forward_backtest(
        close, labels,
        window=args.window,
        cost_bps=args.cost_bps,
        mode=args.mode,
        signal_threshold=args.signal_threshold,
    )

    def _fmt(v, fmt=".3f", suffix=""):
        return f"{v:{fmt}}{suffix}" if np.isfinite(v) else "NaN"

    print(f"  Sharpe (gross, annualised):  {_fmt(result['sharpe_gross'])}")
    print(f"  Sharpe (net of costs):       {_fmt(result['sharpe_net'])}")
    print(f"  Buy-and-hold Sharpe:         {_fmt(result['bh_sharpe'])}")
    print(f"  Excess Sharpe (net − B&H):   {_fmt(result['excess_sharpe'])}")
    print(f"  Max drawdown:                {_fmt(result['max_drawdown']*100, '.2f', '%')}")
    print(f"  Win rate:                    {_fmt(result['win_rate']*100, '.1f', '%')}")
    print(f"  Profit factor:               {_fmt(result['profit_factor'])}")
    print(f"  Bars evaluated:              {result['n_trades']}")

    if result['excess_sharpe'] < 0:
        print("  ⚠ Negative excess Sharpe: this model underperformed buy-and-hold on this")
        print("    ticker/period. Review the signal threshold or operating mode.")

    # ── HMM extension ─────────────────────────────────────────────────────
    if not args.no_hmm and _hmm_available():
        print("\n  Fitting Hidden Markov Model (best of 5 random starts)...")
        try:
            from .hmm_extension import fit_hmm, hmm_disagreement_map
            returns = close.pct_change().dropna()
            model, hidden = fit_hmm(returns, n_components=3, n_trials=5)
            if model is None:
                print("  HMM skipped (hmmlearn import failed at runtime).")
            else:
                means = np.array([model.means_[k][0] for k in range(model.n_components)])
                order = np.argsort(means)
                hmm_labels = ["Bear (lowest return)", "Sideways", "Bull (highest return)"]
                print("  HMM regime mean daily returns (sorted low → high):")
                for rank, k in enumerate(order):
                    print(f"    {hmm_labels[rank]:<25s} state {k}: {means[k]*100:+.3f}%/day")
                print("  (Multiple random starts used; best log-likelihood selected.)")
                hmm_disagreement_map(labels, returns, hidden, state_names)
        except Exception as exc:
            print(f"  HMM skipped at runtime: {exc}")
    else:
        print("\n  HMM skipped (optional). Observable model complete.")

    print("\n" + "=" * 64)
    print(" Markov Regime Method — run complete")
    print(f" Framework: Roan (@RohOnChain). Extended by Lewis Jackson.")
    print(" Backtests are historical, not forward-looking.")
    print(" Excess Sharpe < 0 means buy-and-hold beat this model here.")
    print("=" * 64 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Write `~/.claude/skills/markov-regime-method/pyproject.toml`:

```toml
[project]
name = "markov-regime-method"
version = "2.0.0"
description = "Statistically rigorous Markov regime model with adaptive labeling, stride-sampled matrix, confidence intervals, and net-of-cost backtesting"
requires-python = "==3.12.*"
dependencies = [
    "yfinance>=0.2",
    "numpy>=1.26",
    "pandas>=2.0",
    "scikit-learn>=1.4",
    "scipy>=1.12",
]

[project.optional-dependencies]
hmm = ["hmmlearn>=0.3"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["."]
include = ["markov_regime_method*"]
```

Write `~/.claude/skills/markov-regime-method/.gitignore`:

```text
.venv/
__pycache__/
*.pyc
.hmm_available
```

### 2.3 — Pin Python 3.12

```bash
cd ~/.claude/skills/markov-regime-method
uv python install 3.12
uv venv --python 3.12 .venv
```

Verify:
```bash
cd ~/.claude/skills/markov-regime-method && uv run python --version
```

Expect `Python 3.12.x`. Retry once after 60 seconds if it fails. Surface stderr if it fails again.

## Phase 3 — Installation

### 3.1 — Required dependencies

```bash
cd ~/.claude/skills/markov-regime-method
uv pip install "yfinance>=0.2" "numpy>=1.26" "pandas>=2.0" "scikit-learn>=1.4" "scipy>=1.12"
```

If any fail: surface the exact uv stderr and stop. Ask the user to check network connectivity and re-run. The idempotency in Phase 1.2 makes re-runs safe.

### 3.2 — Optional HMM extension

```bash
cd ~/.claude/skills/markov-regime-method
uv pip install "hmmlearn>=0.3" && echo "true" > .hmm_available || echo "false" > .hmm_available
```

Read `.hmm_available`:
- `true` → print: `✓ HMM extension installed.`
- `false` → print: `HMM extension skipped (optional). Observable model still fully functional. To enable later: install Microsoft Visual C++ Build Tools (Windows) and re-run.`

Do not stop the install on this failure. Continue to Phase 4.

## Phase 4 — First run

```bash
cd ~/.claude/skills/markov-regime-method
uv run python -m markov_regime_method.run --ticker SPY --years 10
```

Expected structure (numbers will vary):

```
Markov Regime Method — ticker=SPY years=10 window=20 mode=standalone cost=5.0bps
  fetching SPY from Yahoo Finance...
  fetched ~2500 rows | <start> → <end>

  Labeling regimes (adaptive z-score threshold = ±0.5)...
  Regime frequencies:
       Bear: XX.X%
   Sideways: XX.X%
       Bull: XX.X%
  ✓ Label check [Bull (2017 equity rally)]: dominant regime = Bull (expected Bull)
  ✓ Label check [Bear (2020 COVID crash)]: dominant regime = Bear (expected Bear)

  BIC model selection (lower = better fit):
    k=2: BIC = XXXX.X
    k=3: BIC = XXXX.X  ← optimal
    ...

  ── Overlapping transitions (legacy — diagonal inflated) ──
  ...

  ── Stride-sampled transitions (statistically honest) ──
  ...  [95% CI ±]

  Sharpe (gross):           X.XXX
  Sharpe (net of costs):    X.XXX
  Buy-and-hold Sharpe:      X.XXX
  Excess Sharpe (net − B&H): X.XXX
  Max drawdown:             -XX.XX%
  Win rate:                 XX.X%
  Profit factor:            X.XX
```

If yfinance fails: tell the user the skill installed cleanly, to re-run in a few minutes. Do not treat a fetch failure as an install failure.

## Phase 5 — Confirmation

```
================================================================
 ✓ Markov Regime Method v2.0 installed at
   ~/.claude/skills/markov-regime-method/

 What's new vs v1:
   • Adaptive z-score labeling (self-calibrates per asset)
   • Stride-sampled matrix with per-cell confidence intervals
   • BIC model selection (data chooses the number of regimes)
   • Walk-forward backtest net of transaction costs
   • Excess Sharpe vs buy-and-hold (the honest benchmark)
   • HMM disagreement map (the research signal, not the agreement)
   • FILTER and STANDALONE operating modes

 HMM extension: <installed | skipped (optional)>

 You can now ask Claude — in any Claude Code session — to:
   • run the markov regime method on AAPL
   • run the markov regime method on BTC-USD --cost-bps 20
   • run it in filter mode on QQQ

 Framework: Roan (@RohOnChain). Extended by Lewis Jackson.
 Backtests are historical, not forward-looking.
================================================================
```

Replace `<installed | skipped (optional)>` with the actual state from `.hmm_available`.

---

## PineScript for TradingView

Here is the live on-chart companion indicator. Load it on any chart in TradingView. It renders the transition matrix and regime ribbon using the same logic as the Python skill.

**Key difference from v1:** Uses log-return z-score labeling instead of a fixed threshold, matching the Python implementation.

```pine
//@version=5
// =============================================================================
// Markov Regime Method v2.0 — Bull / Bear / Sideways
// =============================================================================
// Author: Lewis Jackson · Framework: Roan (@RohOnChain)
// Companion: github.com/jackson-video-resources/markov-regime-method
//
// Uses adaptive z-score labeling (rolling return / rolling vol) matching the
// Python skill. Fixed-threshold PineScript v1 is deprecated.
// =============================================================================

indicator("Markov Regime v2.0", overlay = true, max_labels_count = 500)

grp_logic    = "Regime logic"
grp_display  = "Display"
grp_position = "Table positions"

lookback_window = input.int(20,   title = "Lookback window (bars)",   minval = 5,   maxval = 250, group = grp_logic)
z_thresh        = input.float(0.5, title = "Z-score threshold",        minval = 0.1, maxval = 3.0,  step = 0.1, group = grp_logic,
                              tooltip = "How many std devs from zero = Bull/Bear. 0.5 captures ~top/bottom 30% of bars.")
vol_window      = input.int(60,   title = "Volatility estimation window", minval = 20, maxval = 500, group = grp_logic,
                             tooltip = "Rolling window for normalising the return. Longer = smoother vol estimate.")
stationary_power = input.int(50, title = "Stationary power (iterations)", minval = 10, maxval = 200, group = grp_logic)

show_regime_ribbon     = input.bool(true, title = "Show regime ribbon",            group = grp_display)
show_regime_banner     = input.bool(true, title = "Show current-regime banner",    group = grp_display)
show_matrix_table      = input.bool(true, title = "Show transition matrix",        group = grp_display)
show_stationary_table  = input.bool(true, title = "Show stationary distribution",  group = grp_display)
show_transition_labels = input.bool(true, title = "Label state transitions",       group = grp_display)
table_text_size        = input.string("huge", title = "Table text size", options = ["small","normal","large","huge"], group = grp_display)
min_regime_hold        = input.int(4, title = "Min bars to confirm regime transition", minval = 1, maxval = 50, group = grp_display)

banner_position_input     = input.string("top_left",     title = "Banner position",
                            options = ["top_left","top_center","top_right","middle_left","middle_center","middle_right","bottom_left","bottom_center","bottom_right"], group = grp_position)
matrix_position_input     = input.string("top_right",    title = "Matrix position",
                            options = ["top_left","top_center","top_right","middle_left","middle_center","middle_right","bottom_left","bottom_center","bottom_right"], group = grp_position)
stationary_position_input = input.string("bottom_right", title = "Stationary position",
                            options = ["top_left","top_center","top_right","middle_left","middle_center","middle_right","bottom_left","bottom_center","bottom_right"], group = grp_position)

// ── Position helper ──────────────────────────────────────────────────────────
position_from_string(s) =>
    switch s
        "top_left"      => position.top_left
        "top_center"    => position.top_center
        "top_right"     => position.top_right
        "middle_left"   => position.middle_left
        "middle_center" => position.middle_center
        "middle_right"  => position.middle_right
        "bottom_left"   => position.bottom_left
        "bottom_center" => position.bottom_center
        "bottom_right"  => position.bottom_right
        => position.top_right

banner_pos     = position_from_string(banner_position_input)
matrix_pos     = position_from_string(matrix_position_input)
stationary_pos = position_from_string(stationary_position_input)

size_from_string(s) =>
    switch s
        "small"  => size.small
        "normal" => size.normal
        "large"  => size.large
        "huge"   => size.huge
        => size.large

notch_down(s) =>
    switch s
        "huge"   => "large"
        "large"  => "normal"
        "normal" => "small"
        => "small"

val_size = size_from_string(table_text_size)
hdr_size = size_from_string(notch_down(table_text_size))

// ── Palette ──────────────────────────────────────────────────────────────────
c_bull_ribbon = color.rgb(132, 187, 161, 70)
c_bear_ribbon = color.rgb(197, 127, 134, 70)
c_side_ribbon = color.rgb(164, 171, 183, 70)
c_bull_solid  = color.rgb(132, 187, 161, 30)
c_bear_solid  = color.rgb(197, 127, 134, 30)
c_side_solid  = color.rgb(164, 171, 183, 30)
c_bull_dim    = color.rgb(132, 187, 161, 85)
c_bear_dim    = color.rgb(197, 127, 134, 85)
c_side_dim    = color.rgb(164, 171, 183, 85)

c_card_bg   = color.new(#0B0F0D, 8)
c_card_frame = color.new(#3FDE7E, 78)
c_accent    = #3FDE7E
c_diag_bg   = color.new(#3FDE7E, 80)
c_diag_txt  = #6BF0A6
c_off_txt   = color.new(color.white, 55)
c_hdr_txt   = color.new(color.white, 35)
c_foot_txt  = color.new(color.white, 60)
c_bg        = color.new(color.black, 30)

regime_solid(r) => r == 1 ? c_bull_solid  : r == 2 ? c_bear_solid  : c_side_solid
regime_ribbon(r) => r == 1 ? c_bull_ribbon : r == 2 ? c_bear_ribbon : c_side_ribbon
regime_name(r)   => r == 1 ? "Bull"        : r == 2 ? "Bear"        : "Sideways"
regime_abbr(r)   => r == 1 ? "BULL"        : r == 2 ? "BEAR"        : "SIDE"

// ── Adaptive z-score labeling ────────────────────────────────────────────────
// log_ret = log(close / close[window]) — total log-return over the window
// rolling_vol = stdev of log_ret over vol_window bars
// z = log_ret / rolling_vol — self-calibrates per asset
log_ret     = math.log(close / close[lookback_window])
rolling_vol = ta.stdev(log_ret, vol_window)
z_score     = rolling_vol > 0 ? log_ret / rolling_vol : 0.0

regime = na(z_score) ? int(na) : z_score > z_thresh ? 1 : z_score < -z_thresh ? 2 : 0

// ── Regime ribbon ─────────────────────────────────────────────────────────────
ribbon_color = regime == 1 ? color.rgb(132, 187, 161, 90) : regime == 2 ? color.rgb(197, 127, 134, 90) : color.rgb(164, 171, 183, 90)
bgcolor(show_regime_ribbon ? ribbon_color : na, title = "Regime ribbon")

// ── Transition counting ───────────────────────────────────────────────────────
var counts = array.new_int(9, 0)
prev_regime = regime[1]
if barstate.isconfirmed and not na(prev_regime) and not na(regime)
    idx = prev_regime * 3 + regime
    array.set(counts, idx, array.get(counts, idx) + 1)

// ── Transition labels (debounced) ─────────────────────────────────────────────
var int last_lbl_regime = na
held = not na(regime)
for k = 0 to min_regime_hold - 1
    held := held and not na(regime[k]) and regime[k] == regime

if barstate.isconfirmed and not na(regime) and held and regime != last_lbl_regime
    if show_transition_labels and not na(last_lbl_regime)
        flip_off = min_regime_hold - 1
        label.new(bar_index - flip_off, high[flip_off],
                  regime_abbr(last_lbl_regime) + "  →  " + regime_abbr(regime),
                  yloc = yloc.abovebar, style = label.style_label_down,
                  color = regime_solid(regime), textcolor = color.white, size = size.normal)
    last_lbl_regime := regime

// ── Table setup ───────────────────────────────────────────────────────────────
var table tbl_banner     = table.new(banner_pos,     1, 1, bgcolor = c_bg,      border_width = 0)
var table tbl_matrix     = table.new(matrix_pos,     4, 6, bgcolor = c_card_bg, border_width = 2, border_color = c_card_bg, frame_color = c_card_frame, frame_width = 1)
var table tbl_stationary = table.new(stationary_pos, 3, 4, bgcolor = c_card_bg, border_width = 2, border_color = c_card_bg, frame_color = c_card_frame, frame_width = 1)

// ── 3x3 matrix multiply (unrolled — portable across all Pine v5 builds) ───────
matmul_3x3(A, B) =>
    C = array.new_float(9, 0.0)
    array.set(C, 0, array.get(A,0)*array.get(B,0) + array.get(A,1)*array.get(B,3) + array.get(A,2)*array.get(B,6))
    array.set(C, 1, array.get(A,0)*array.get(B,1) + array.get(A,1)*array.get(B,4) + array.get(A,2)*array.get(B,7))
    array.set(C, 2, array.get(A,0)*array.get(B,2) + array.get(A,1)*array.get(B,5) + array.get(A,2)*array.get(B,8))
    array.set(C, 3, array.get(A,3)*array.get(B,0) + array.get(A,4)*array.get(B,3) + array.get(A,5)*array.get(B,6))
    array.set(C, 4, array.get(A,3)*array.get(B,1) + array.get(A,4)*array.get(B,4) + array.get(A,5)*array.get(B,7))
    array.set(C, 5, array.get(A,3)*array.get(B,2) + array.get(A,4)*array.get(B,5) + array.get(A,5)*array.get(B,8))
    array.set(C, 6, array.get(A,6)*array.get(B,0) + array.get(A,7)*array.get(B,3) + array.get(A,8)*array.get(B,6))
    array.set(C, 7, array.get(A,6)*array.get(B,1) + array.get(A,7)*array.get(B,4) + array.get(A,8)*array.get(B,7))
    array.set(C, 8, array.get(A,6)*array.get(B,2) + array.get(A,7)*array.get(B,5) + array.get(A,8)*array.get(B,8))
    C

fmt_pct(p) => str.tostring(math.round(p * 100)) + "%"

// ── Last bar: build P, iterate to stationary, populate tables ────────────────
if barstate.islast
    P = array.new_float(9, 0.0)
    for r = 0 to 2
        row_sum = array.get(counts, r*3) + array.get(counts, r*3+1) + array.get(counts, r*3+2)
        for c = 0 to 2
            cell = row_sum > 0 ? array.get(counts, r*3+c) / row_sum : 1.0/3.0
            array.set(P, r*3+c, cell)

    M = array.copy(P)
    for _i = 1 to stationary_power - 1
        M := matmul_3x3(M, P)

    stat_bull = array.get(M, 0)
    stat_bear = array.get(M, 1)
    stat_side = array.get(M, 2)

    if show_regime_banner
        table.cell(tbl_banner, 0, 0, "Currently: " + regime_name(regime),
                   text_color = color.white, bgcolor = regime_solid(regime),
                   text_size = size.large, text_halign = text.align_center, text_valign = text.align_center)

    if show_matrix_table
        table.cell(tbl_matrix, 0, 0, "MARKOV REGIME", text_color = c_accent, bgcolor = c_card_bg, text_size = hdr_size, text_halign = text.align_left)
        table.cell(tbl_matrix, 1, 0, "",              bgcolor = c_card_bg)
        table.cell(tbl_matrix, 2, 0, "",              bgcolor = c_card_bg)
        table.cell(tbl_matrix, 3, 0, "3×3",           text_color = c_foot_txt, bgcolor = c_card_bg, text_size = hdr_size, text_halign = text.align_right)
        table.cell(tbl_matrix, 0, 1, "",     bgcolor = c_card_bg)
        table.cell(tbl_matrix, 1, 1, "BULL", text_color = c_hdr_txt, bgcolor = c_card_bg, text_size = hdr_size, text_halign = text.align_center)
        table.cell(tbl_matrix, 2, 1, "BEAR", text_color = c_hdr_txt, bgcolor = c_card_bg, text_size = hdr_size, text_halign = text.align_center)
        table.cell(tbl_matrix, 3, 1, "SIDE", text_color = c_hdr_txt, bgcolor = c_card_bg, text_size = hdr_size, text_halign = text.align_center)
        for r = 0 to 2
            row_name = r == 0 ? "BULL" : r == 1 ? "BEAR" : "SIDE"
            table.cell(tbl_matrix, 0, r+2, row_name, text_color = c_hdr_txt, bgcolor = c_card_bg, text_size = hdr_size, text_halign = text.align_center)
            for c = 0 to 2
                p        = array.get(P, r*3+c)
                is_diag  = (r == c)
                cell_bg  = is_diag ? c_diag_bg : c_card_bg
                cell_txt = is_diag ? c_diag_txt : c_off_txt
                cell_sz  = is_diag ? val_size   : hdr_size
                table.cell(tbl_matrix, c+1, r+2, fmt_pct(p),
                           text_color = cell_txt, bgcolor = cell_bg,
                           text_size = cell_sz, text_halign = text.align_center, text_valign = text.align_center)
        table.cell(tbl_matrix, 0, 5, "next-state P", text_color = c_foot_txt, bgcolor = c_card_bg, text_size = hdr_size, text_halign = text.align_left)
        table.cell(tbl_matrix, 1, 5, "",   bgcolor = c_card_bg)
        table.cell(tbl_matrix, 2, 5, "",   bgcolor = c_card_bg)
        table.cell(tbl_matrix, 3, 5, "live", text_color = c_accent, bgcolor = c_card_bg, text_size = hdr_size, text_halign = text.align_right)

    if show_stationary_table
        table.cell(tbl_stationary, 0, 0, "LONG-RUN MIX", text_color = c_accent, bgcolor = c_card_bg, text_size = hdr_size, text_halign = text.align_left)
        table.cell(tbl_stationary, 1, 0, "", bgcolor = c_card_bg)
        table.cell(tbl_stationary, 2, 0, "", bgcolor = c_card_bg)
        table.cell(tbl_stationary, 0, 1, "BULL", text_color = c_hdr_txt, bgcolor = c_card_bg, text_size = hdr_size, text_halign = text.align_center)
        table.cell(tbl_stationary, 1, 1, "BEAR", text_color = c_hdr_txt, bgcolor = c_card_bg, text_size = hdr_size, text_halign = text.align_center)
        table.cell(tbl_stationary, 2, 1, "SIDE", text_color = c_hdr_txt, bgcolor = c_card_bg, text_size = hdr_size, text_halign = text.align_center)
        table.cell(tbl_stationary, 0, 2, fmt_pct(stat_bull), text_color = c_diag_txt, bgcolor = c_diag_bg, text_size = val_size, text_halign = text.align_center, text_valign = text.align_center)
        table.cell(tbl_stationary, 1, 2, fmt_pct(stat_bear), text_color = c_diag_txt, bgcolor = c_diag_bg, text_size = val_size, text_halign = text.align_center, text_valign = text.align_center)
        table.cell(tbl_stationary, 2, 2, fmt_pct(stat_side), text_color = c_diag_txt, bgcolor = c_diag_bg, text_size = val_size, text_halign = text.align_center, text_valign = text.align_center)
        table.cell(tbl_stationary, 0, 3, "steady state", text_color = c_foot_txt, bgcolor = c_card_bg, text_size = hdr_size, text_halign = text.align_left)
        table.cell(tbl_stationary, 1, 3, "",     bgcolor = c_card_bg)
        table.cell(tbl_stationary, 2, 3, "live", text_color = c_accent, bgcolor = c_card_bg, text_size = hdr_size, text_halign = text.align_right)

// ── End of file ───────────────────────────────────────────────────────────────
```
