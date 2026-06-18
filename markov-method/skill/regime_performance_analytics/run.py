"""CLI entry point: fetch → label → matrix → backtest → analytics → report.

Usage:
    uv run python -m regime_performance_analytics.run --ticker SPY --years 10
    uv run python -m regime_performance_analytics.run --ticker BTC-USD --cost-bps 20 --mar 0.05
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
from .analytics import (
    autocorr_sum,
    corrected_sharpe_monthly,
    corrected_sharpe_daily,
    regime_autocorr_flag,
    target_downside_deviation,
    skew_classification,
    compute_upr,
    compute_omega,
    classify_omega,
    classify_upr_sortino,
    classify_sortino_sharpe,
    classify_autocorr_sum,
)

_RED = "\033[91m" if sys.stdout.isatty() else ""
_RESET = "\033[0m" if sys.stdout.isatty() else ""


def _flag(text: str, condition: bool) -> str:
    return f"{_RED}{text}{_RESET}" if condition else text

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


def _resolve_mar(mar_arg: str) -> float:
    """Parse --mar argument to an annual decimal rate."""
    if mar_arg == "zero":
        return 0.0
    if mar_arg == "rfr":
        try:
            import yfinance as yf
            df = yf.download("^IRX", period="5d", progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            rate = float(df["Close"].dropna().iloc[-1]) / 100.0
            print(f"  MAR from ^IRX (3m T-bill): {rate*100:.2f}%/year")
            return rate
        except Exception:
            print("  ⚠ Could not fetch ^IRX, falling back to MAR=0.0")
            return 0.0
    try:
        return float(mar_arg)
    except ValueError:
        print(f"  ⚠ Unrecognised --mar value '{mar_arg}', using 0.0")
        return 0.0


def _fmt(v: float, fmt: str = ".3f", suffix: str = "") -> str:
    return f"{v:{fmt}}{suffix}" if np.isfinite(v) else "NaN"


def _print_bl_section(
    result: dict,
    state_names: list[str],
) -> dict:
    """Print Burghardt-Liu autocorrelation-corrected Sharpe section.

    Returns per-regime BL dicts for use in the interpretation block.
    """
    net_arr = np.array(result["daily_returns_net"], dtype=float)
    dates = pd.DatetimeIndex(result["date_series"])
    states = np.array(result["state_series"], dtype=int)

    # Overall monthly autocorrelation (Burghardt-Liu applied at intended frequency)
    if len(net_arr) > 0 and len(dates) > 0:
        monthly = (
            pd.Series(net_arr, index=dates)
            .resample("ME")
            .apply(lambda x: (1.0 + x).prod() - 1.0)
            .dropna()
        )
        bl_overall = corrected_sharpe_monthly(monthly.values)
    else:
        bl_overall = {k: float("nan") for k in
                      ["mean_annual", "sigma_naive", "sigma_corrected",
                       "sharpe_naive", "sharpe_corrected", "rho_sum"]}

    print("\n  ── Autocorrelation-Corrected Sharpe (Burghardt-Liu 2012) ──")
    print("  Overall (monthly return series):")
    print(f"    Σρ lags 1–5:         {_fmt(bl_overall['rho_sum'], '+.3f')}")
    print(f"    σ naive (annualised): {_fmt(bl_overall['sigma_naive']*100, '.2f', '%')}")
    print(f"    σ corrected:          {_fmt(bl_overall['sigma_corrected']*100, '.2f', '%')}")
    print(f"    Sharpe naive:         {_fmt(bl_overall['sharpe_naive'])}")
    print(f"    Sharpe corrected:     {_fmt(bl_overall['sharpe_corrected'])}")
    print(f"    → {regime_autocorr_flag(bl_overall['rho_sum'])}")

    # Per-regime daily autocorrelation
    print("\n  Per-regime (daily return sub-series, autocorrelation within each regime):")
    regime_bl: dict[int, dict] = {}
    for state_idx, name in enumerate(state_names):
        mask = states == state_idx
        regime_daily = net_arr[mask]
        bl = corrected_sharpe_daily(regime_daily)
        regime_bl[state_idx] = bl
        rho = bl["rho_sum"]
        flag = regime_autocorr_flag(rho)
        n_obs = int(mask.sum())
        print(f"    {name:>9s} (n={n_obs:4d}): Σρ={_fmt(rho, '+.3f')}  → {flag}")

    return {"overall": bl_overall, "per_regime": regime_bl}


def _print_sortino_section(
    result: dict,
    state_names: list[str],
    mar_annual: float,
) -> dict:
    """Print correct Sortino, UPR, and Omega sections (Red Rock / CME method).

    TDD is computed exactly once per series and reused across Sortino, UPR,
    and Omega — no redundant recalculation.

    Returns dict with overall and per-regime values for all three metrics,
    plus per-regime TDD (for downstream table/synthesis blocks).
    """
    net_arr = np.array(result["daily_returns_net"], dtype=float)
    states = np.array(result["state_series"], dtype=int)
    mar_daily = mar_annual / 252

    print(f"\n  ── Sortino / UPR / Omega (Red Rock / CME correct method, MAR={mar_annual*100:.1f}%) ──")
    print("  Correct TDD: all N observations in denominator (zeros above MAR included).")
    print("  Industry error: only N_negative in denominator — cannot distinguish")
    print("  occasional losses from persistent ones. See Red Rock Capital (2008).")

    # ── Overall ──────────────────────────────────────────────────────────────
    tdd_d = target_downside_deviation(net_arr, mar=mar_daily)
    tdd_a = tdd_d * np.sqrt(252)
    mean_a = float(net_arr.mean()) * 252 if len(net_arr) > 0 else float("nan")
    if np.isfinite(tdd_a) and tdd_a > 0 and np.isfinite(mean_a):
        overall_sortino = float((mean_a - mar_annual) / tdd_a)
    else:
        overall_sortino = float("nan")
    overall_upr = compute_upr(net_arr, mar_annual, tdd_a)
    overall_omega = compute_omega(net_arr, mar_annual)

    print(f"\n  Overall:")
    print(f"    TDD (daily→annual):  {_fmt(tdd_a*100, '.2f', '%')}")
    print(f"    Annualised return:   {_fmt(mean_a*100, '.2f', '%')}")
    print(f"    Sortino ratio:       {_fmt(overall_sortino)}")
    print(f"    UPR:                 {_fmt(overall_upr)}")
    omega_str = "∞" if np.isposinf(overall_omega) else _fmt(overall_omega)
    print(f"    Omega:               {omega_str}  [{classify_omega(overall_omega)}]")

    # ── Per-regime ───────────────────────────────────────────────────────────
    regime_sortino: dict[int, float] = {}
    regime_upr: dict[int, float] = {}
    regime_omega: dict[int, float] = {}
    regime_tdd: dict[int, float] = {}

    print(f"\n  Per-regime:")
    for state_idx, name in enumerate(state_names):
        mask = states == state_idx
        rd = net_arr[mask]
        n = int(mask.sum())

        # TDD computed once; Sortino, UPR, Omega all derived from it
        r_tdd_d = target_downside_deviation(rd, mar=mar_daily)
        r_tdd_a = r_tdd_d * np.sqrt(252) if n >= 5 else float("nan")
        r_mean_a = float(rd.mean()) * 252 if n >= 5 else float("nan")
        if np.isfinite(r_tdd_a) and r_tdd_a > 0 and np.isfinite(r_mean_a):
            s = float((r_mean_a - mar_annual) / r_tdd_a)
        else:
            s = float("nan")
        upr = compute_upr(rd, mar_annual, r_tdd_a)
        omega = compute_omega(rd, mar_annual) if n >= 5 else float("nan")

        regime_sortino[state_idx] = s
        regime_upr[state_idx] = upr
        regime_omega[state_idx] = omega
        regime_tdd[state_idx] = r_tdd_a

        omega_s = "∞" if np.isposinf(omega) else _fmt(omega)
        print(f"    {name:>9s} (n={n:4d}): Sortino={_fmt(s):>7s}  "
              f"UPR={_fmt(upr):>7s}  Omega={omega_s:>6s}")

    return {
        "overall": overall_sortino,
        "overall_upr": overall_upr,
        "overall_omega": overall_omega,
        "overall_tdd": tdd_a,
        "per_regime": regime_sortino,
        "upr": regime_upr,
        "omega": regime_omega,
        "tdd": regime_tdd,
    }


def _print_interpretation_block(
    state_names: list[str],
    P_stride: np.ndarray,
    bl_data: dict,
    sortino_data: dict,
    hmm_data: dict | None,
) -> None:
    """Regime-conditional interpretation synthesis."""
    print("\n  ── Regime-Conditional Interpretation ──")
    print(f"  {'Regime':>9s}  {'Corr.Sharpe':>11s}  {'Sortino':>8s}  "
          f"{'S÷Sr':>6s}  {'Skew':>8s}  {'Autocorr':>10s}")
    print("  " + "-" * 72)

    for state_idx, name in enumerate(state_names):
        bl = bl_data["per_regime"][state_idx]
        cs = bl.get("sharpe_corrected", float("nan"))
        s = sortino_data["per_regime"].get(state_idx, float("nan"))

        ratio_str = "NaN"
        if np.isfinite(s) and np.isfinite(cs) and cs != 0:
            ratio = s / cs
            ratio_str = f"{ratio:.2f}"

        skew = skew_classification(s, cs)
        skew_short = skew.split("(")[0].strip()[:18]
        rho = bl.get("rho_sum", float("nan"))
        rho_str = _fmt(rho, "+.3f") if np.isfinite(rho) else "NaN"

        print(f"  {name:>9s}  {_fmt(cs):>11s}  {_fmt(s):>8s}  "
              f"{ratio_str:>6s}  {skew_short:<18s}  Σρ={rho_str}")

    # High-persistence + negative autocorrelation flags
    print()
    high_persist_neg_ac = []
    for state_idx, name in enumerate(state_names):
        diag = float(P_stride[state_idx, state_idx])
        rho = bl_data["per_regime"][state_idx].get("rho_sum", float("nan"))
        if diag > 0.70 and np.isfinite(rho) and rho < -0.15:
            high_persist_neg_ac.append(
                f"{name} (diag={diag:.0%}, Σρ={rho:+.3f})"
            )

    if high_persist_neg_ac:
        print("  ✓ High-confidence trend-following environments")
        print("    (high transition persistence AND trend-favorable autocorrelation):")
        for item in high_persist_neg_ac:
            print(f"    · {item}")
    else:
        print("  — No regimes meet the high-persistence + negative-autocorrelation")
        print("    threshold for high-confidence trend-following classification.")

    # HMM/threshold disagreement + near-zero autocorrelation flag
    if hmm_data is not None:
        rho_disagree = autocorr_sum(hmm_data.get("disagree_returns", np.array([])))
        near_zero = np.isfinite(rho_disagree) and abs(rho_disagree) < 0.05
        print()
        if near_zero:
            print(f"  ⚠ HMM/threshold disagreement periods ({hmm_data['disagree_pct']:.1f}% of bars)")
            print(f"    show near-zero autocorrelation (Σρ={rho_disagree:+.3f}).")
            print("    These are ambiguous/choppy environments — suppress trend signals")
            print("    from the Markov matrix during these periods.")
        else:
            print(f"  — HMM/threshold disagreement periods ({hmm_data.get('disagree_pct', float('nan')):.1f}% of bars).")
            if np.isfinite(rho_disagree):
                print(f"    Autocorrelation Σρ={rho_disagree:+.3f} — not near-zero, regime signal may still apply.")


def _print_skewness_table(
    state_names: list[str],
    bl_data: dict,
    sortino_data: dict,
) -> None:
    """Print the per-regime skewness diagnostic table (Step 4)."""
    nan = float("nan")

    def _row(label: str, value: str, signal: str, flag: bool = False) -> None:
        signal_out = _flag(signal, flag)
        print(f"    {label:<26s}  {value:>8s}  {signal_out}")

    all_items = list(enumerate(state_names)) + [(-1, "Overall")]
    for state_idx, name in all_items:
        if state_idx == -1:
            bl = bl_data["overall"]
            cs = bl.get("sharpe_corrected", nan)
            s = sortino_data["overall"]
            upr = sortino_data["overall_upr"]
            omega = sortino_data["overall_omega"]
            rho = bl.get("rho_sum", nan)
        else:
            bl = bl_data["per_regime"][state_idx]
            cs = bl.get("sharpe_corrected", nan)
            s = sortino_data["per_regime"].get(state_idx, nan)
            upr = sortino_data["upr"].get(state_idx, nan)
            omega = sortino_data["omega"].get(state_idx, nan)
            rho = bl.get("rho_sum", nan)

        ss_ratio = s / cs if (np.isfinite(s) and s >= 0 and np.isfinite(cs) and cs > 0) else nan
        us_ratio = upr / s if (np.isfinite(upr) and np.isfinite(s) and s > 0) else nan
        omega_display = "∞" if np.isposinf(omega) else _fmt(omega)

        print(f"\n  Regime: {name}")
        print(f"    {'Metric':<26s}  {'Value':>8s}  Signal")
        print("    " + "-" * 60)
        _row("Corrected Sharpe", _fmt(cs), "—")
        _row("Sortino", _fmt(s), "—")
        _row("UPR", _fmt(upr), "—")
        _row("Omega", omega_display,
             classify_omega(omega),
             flag=np.isfinite(omega) and omega < 0.8)
        _row("Sortino/Sharpe", _fmt(ss_ratio),
             classify_sortino_sharpe(ss_ratio),
             flag=np.isfinite(ss_ratio) and ss_ratio < 0.8)
        _row("UPR/Sortino", _fmt(us_ratio),
             classify_upr_sortino(us_ratio),
             flag=np.isfinite(us_ratio) and us_ratio < 0.6)
        _row("Autocorrelation sum", _fmt(rho, "+.3f"),
             classify_autocorr_sum(rho))


def _print_regime_synthesis(
    state_names: list[str],
    current_state: int,
    P_stride: np.ndarray,
    bl_data: dict,
    sortino_data: dict,
) -> None:
    """Print regime signal synthesis for the current regime (Step 5)."""
    nan = float("nan")
    name = state_names[current_state]

    bl = bl_data["per_regime"][current_state]
    cs = bl.get("sharpe_corrected", nan)
    s = sortino_data["per_regime"].get(current_state, nan)
    upr = sortino_data["upr"].get(current_state, nan)
    omega = sortino_data["omega"].get(current_state, nan)
    rho = bl.get("rho_sum", nan)

    diag = float(P_stride[current_state, current_state])
    # Bear transition probability: P(current → Bear). When current_state IS Bear
    # (index 0), P_stride[0,0] is the self-persistence, not a cross-transition
    # risk signal — set to 0 so the DEFENSIVE bear_prob trigger only fires on
    # non-Bear regimes where transitioning into Bear is a forward-looking risk.
    bear_prob = float(P_stride[current_state, 0]) if current_state != 0 else 0.0

    # Require both metrics positive so negative/negative doesn't produce a
    # spurious positive ratio that masks a losing regime.
    ss_ratio = s / cs if (np.isfinite(s) and s >= 0 and np.isfinite(cs) and cs > 0) else nan
    us_ratio = upr / s if (np.isfinite(upr) and np.isfinite(s) and s > 0) else nan

    # Classify each dimension
    omega_class = classify_omega(omega)
    us_class = classify_upr_sortino(us_ratio)
    ss_class = classify_sortino_sharpe(ss_ratio)
    ac_class = classify_autocorr_sum(rho)

    # Signal determination — defensive checked first (overrides all others)
    defensive = (
        (np.isfinite(omega) and omega < 0.8)
        or (np.isfinite(rho) and rho > 0.10)
        or bear_prob > 0.35
        or (np.isfinite(ss_ratio) and ss_ratio < 0.8)
        or (np.isfinite(s) and s < 0)  # losing regime: Sortino negative
    )

    full_size = (
        not defensive
        and diag > 0.70
        and np.isfinite(rho) and rho < -0.15
        and (np.isposinf(omega) or (np.isfinite(omega) and omega > 1.5))
        and (np.isposinf(upr) or (np.isfinite(us_ratio) and us_ratio > 1.0))
        and np.isfinite(ss_ratio) and ss_ratio > 1.2
    )

    reduce = (
        not full_size and not defensive
        and (
            diag < 0.65
            or (np.isfinite(rho) and -0.15 <= rho <= 0.10)
            or (np.isfinite(omega) and 0.8 <= omega <= 1.0)
            or (np.isfinite(us_ratio) and us_ratio < 0.6)
        )
    )

    if full_size:
        signal_line = ">>> SIGNAL: FULL SIZE — all conditions met"
    elif defensive:
        signal_line = _flag(">>> SIGNAL: DEFENSIVE — reduce / hedge exposure", True)
    elif reduce:
        signal_line = ">>> SIGNAL: REDUCE — one or more thresholds not met"
    else:
        signal_line = ">>> SIGNAL: NEUTRAL — mixed conditions, use judgement"

    omega_display = "∞" if np.isposinf(omega) else _fmt(omega)

    print("\n  ── REGIME SIGNAL SYNTHESIS ──")
    print("  " + "=" * 50)
    print(f"  Current regime:        {name} (diagonal p={diag:.2f})")
    print(f"  Autocorrelation sum:   {_fmt(rho, '+.3f')}  [{ac_class}]")
    print(f"  Omega:                 {omega_display}  [{omega_class}]")
    print(f"  UPR/Sortino:           {_fmt(us_ratio)}  [{us_class}]")
    print(f"  Sortino/Sharpe:        {_fmt(ss_ratio)}  [{ss_class}]")
    print(f"  {signal_line}")
    print("  " + "=" * 50)


def main() -> int:
    parser = argparse.ArgumentParser(prog="regime-performance-analytics")
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
    parser.add_argument(
        "--mar", default="zero",
        help=(
            "Minimum acceptable return for Sortino calculation. "
            "'rfr' = 3m T-bill (fetched from ^IRX), "
            "'zero' = absolute return mandate (default), "
            "or a decimal float e.g. '0.07' for 7%%."
        ),
    )
    args = parser.parse_args()

    print(f"\nRegime Performance Analytics — ticker={args.ticker} years={args.years} "
          f"window={args.window} mode={args.mode} cost={args.cost_bps}bps")
    print(f"  fetching {args.ticker} from Yahoo Finance...")
    df = _fetch_with_retry(args.ticker, args.years)

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    close = df["Close"].dropna()
    print(f"  fetched {len(close)} rows | {close.index.min().date()} → {close.index.max().date()}")

    mar_annual = _resolve_mar(args.mar)

    # ── Label regimes ──────────────────────────────────────────────────────
    print(f"\n  Labeling regimes (adaptive z-score threshold = ±{args.z_thresh})...")
    labels = label_regimes_adaptive(close, window=args.window, z_thresh=args.z_thresh)

    freq = labels.value_counts(normalize=True).sort_index()
    print("  Regime frequencies:")
    for idx, name in enumerate(STATES_3):
        f = freq.get(idx, 0.0)
        print(f"    {name:>9s}: {f:.1%}")

    verify_labels(labels, close)

    # ── BIC model selection ────────────────────────────────────────────────
    if args.k_override:
        best_k = args.k_override
        print(f"\n  k overridden to {best_k} (skipping BIC)")
    else:
        bic_best = select_optimal_k(labels, args.window)
        best_k = 3
        if bic_best != 3:
            print(f"  (BIC prefers k={bic_best}, but defaulting to k=3 to match the 3-state labels.)")
            print(f"  Use --k-override {bic_best} to force BIC's choice.")

    state_names = STATES_3

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

    # ── Extension 1: Burghardt-Liu corrected Sharpe ────────────────────────
    bl_data = _print_bl_section(result, state_names)

    # ── Extension 2: Correct Sortino ratio ────────────────────────────────
    sortino_data = _print_sortino_section(result, state_names, mar_annual)

    # ── HMM extension ─────────────────────────────────────────────────────
    hmm_data: dict | None = None
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
                hmm_data = hmm_disagreement_map(labels, returns, hidden, state_names)
        except Exception as exc:
            print(f"  HMM skipped at runtime: {exc}")
    else:
        print("\n  HMM skipped (optional). Observable model complete.")

    # ── Extension 3: Regime-conditional interpretation ─────────────────────
    _print_interpretation_block(state_names, P_stride, bl_data, sortino_data, hmm_data)

    # ── Extension 4: Skewness diagnostic table ─────────────────────────────
    print("\n  ── Skewness Diagnostic Table ──")
    _print_skewness_table(state_names, bl_data, sortino_data)

    # ── Extension 5: Regime signal synthesis ───────────────────────────────
    _print_regime_synthesis(state_names, current_state, P_stride, bl_data, sortino_data)

    print("\n" + "=" * 64)
    print(" Regime Performance Analytics — run complete")
    print(" Markov framework: Roan (@RohOnChain). Extended by Lewis Jackson.")
    print(" Distributional metrics: UPR, Omega, regime signal synthesis added.")
    print(" Burghardt-Liu (2012) autocorrelation correction applied.")
    print(" Sortino/UPR: correct TDD method (Red Rock / CME, all N in denominator).")
    print(" Backtests are historical, not forward-looking.")
    print("=" * 64 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
