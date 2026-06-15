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
    end = pd.Timestamp.now("UTC").normalize()
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
                        help="standalone: trade signal directly. filter: gate a strategy.")
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

    freq = labels.value_counts(normalize=True).sort_index()
    print("  Regime frequencies:")
    for idx, name in enumerate(STATES_3):
        f = freq.get(idx, 0.0)
        print(f"    {name:>9s}: {f:.1%}")

    verify_labels(labels, close)

    # ── BIC model selection (informational; default stays 3) ──────────────
    if args.k_override:
        best_k = args.k_override
        print(f"\n  k overridden to {best_k} (skipping BIC)")
    else:
        bic_best = select_optimal_k(labels, args.window)
        best_k = 3  # labeling is always 3-state; BIC shown for information only
        if bic_best != 3:
            print(f"  (BIC prefers k={bic_best}, but defaulting to k=3 to match the 3-state labels.)")
            print(f"  Use --k-override {bic_best} to force BIC's choice.")

    state_names = STATES_3  # always Bear/Sideways/Bull for 3-state labels

    # ── Build matrices ─────────────────────────────────────────────────────
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

    # ── Multi-step forecast ────────────────────────────────────────────────
    print(f"\n  Multi-step forecast from {state_names[current_state]}:")
    print(f"  {'Step':>5}  {'Bear':>8}  {'Sideways':>10}  {'Bull':>8}  {'Signal':>8}")
    for n in range(1, 6):
        Pn = n_step_forecast(P_stride, n)
        row = Pn[current_state]
        sig_n = float(row[2] - row[0])
        print(f"  {n:>5}  {row[0]*100:7.2f}%  {row[1]*100:9.2f}%  {row[2]*100:7.2f}%  {sig_n:+7.3f}")
    print(f"  {'(∞)':>5}  {pi[0]*100:7.2f}%  {pi[1]*100:9.2f}%  {pi[2]*100:7.2f}%  converged")

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

    print(f"  Sharpe (gross, annualised):   {_fmt(result['sharpe_gross'])}")
    print(f"  Sharpe (net of costs):        {_fmt(result['sharpe_net'])}")
    print(f"  Buy-and-hold Sharpe:          {_fmt(result['bh_sharpe'])}")
    print(f"  Excess Sharpe (net − B&H):    {_fmt(result['excess_sharpe'])}")
    print(f"  Max drawdown:                 {_fmt(result['max_drawdown']*100, '.2f', '%')}")
    print(f"  Win rate:                     {_fmt(result['win_rate']*100, '.1f', '%')}")
    print(f"  Profit factor:                {_fmt(result['profit_factor'])}")
    print(f"  Bars evaluated:               {result['n_trades']}")

    if np.isfinite(result['excess_sharpe']) and result['excess_sharpe'] < 0:
        print("  ⚠ Negative excess Sharpe: this model underperformed buy-and-hold.")
        print("    Review the signal threshold or operating mode.")

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
    print(" Framework: Roan (@RohOnChain). Extended by Lewis Jackson.")
    print(" Backtests are historical, not forward-looking.")
    print(" Excess Sharpe < 0 means buy-and-hold beat this model here.")
    print("=" * 64 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
