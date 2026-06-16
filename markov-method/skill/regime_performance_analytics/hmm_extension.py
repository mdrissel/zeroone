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
) -> dict:
    """Print where the HMM disagrees with threshold labels.

    Returns a dict with disagreement data for use in the interpretation block.
    Keys: agree_pct, disagree_pct, disagree_returns (daily returns on disagree bars).

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

    order = np.argsort(means)
    remap = {old: new for new, old in enumerate(order)}
    hmm_semantic = np.array([remap[s] for s in hmm_arr])

    agree_mask = thresh_arr == hmm_semantic
    agree_pct = agree_mask.mean() * 100

    print(f"\n  HMM vs threshold-label agreement: {agree_pct:.1f}%")
    print(f"  Disagreement: {100 - agree_pct:.1f}% of bars")
    print()

    print("  Disagreement map (read: threshold says X, HMM says Y):")
    disagree_idx = np.where(~agree_mask)[0]
    confusion: dict[tuple[str, str], int] = {}
    n_names = len(state_names)
    for i in disagree_idx:
        t_idx = int(thresh_arr[i])
        h_idx = int(hmm_semantic[i])
        t_name = state_names[t_idx] if t_idx < n_names else f"State{t_idx}"
        h_name = state_names[h_idx] if h_idx < n_names else f"State{h_idx}"
        key = (t_name, h_name)
        confusion[key] = confusion.get(key, 0) + 1

    for (thresh_state, hmm_state), count in sorted(confusion.items(), key=lambda x: -x[1]):
        print(f"    Threshold={thresh_state:>9s}, HMM={hmm_state:>9s}: {count:4d} bars")

    print()
    print("  ⚠ Bars where models DISAGREE are the research opportunity.")
    print("    Pull those periods and ask: which model was right?")
    print("    The HMM is fitting return distributions; the threshold is fitting levels.")
    print("    They should agree on obvious regimes and diverge on transitions.")

    # Return disagree returns for the interpretation block
    ret_arr = returns.dropna().iloc[:len(hmm_arr)].to_numpy()
    disagree_returns = ret_arr[disagree_idx] if len(disagree_idx) > 0 else np.array([])

    return {
        "agree_pct": float(agree_pct),
        "disagree_pct": float(100 - agree_pct),
        "disagree_returns": disagree_returns,
    }
