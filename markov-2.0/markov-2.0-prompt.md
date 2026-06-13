You are installing the **Markov 2.0 — Hedge Fund Method (corrected)** as a skill
on this machine. This is the upgraded version of the original Markov hedge fund
method: same core (states → transition matrix → stickiness → signal), with three
documented flaws fixed. Walk the user through onboarding conversationally: tell
them what you're about to do (~2 minutes, no keys, no accounts, no admin
passwords), then wait for them to type **go**.

## The method you implement

1. **States.** Default: 20-day cumulative return ≥ +5% = BULL, ≤ −5% = BEAR,
   else SIDEWAYS. Label the asset's full history.
2. **Transition matrix.** Count state→state transitions, convert rows to
   probabilities (rows sum to 1). Report stickiness (the diagonal).
3. **Signal.** P(bull tomorrow) − P(bear tomorrow). Sign = direction, magnitude
   = conviction.
4. **Multi-day forecasts** by matrix powers; note convergence to the stationary
   distribution (long-horizon forecasts carry no signal).
5. **Hidden Markov mode (optional):** fit an HMM with no hand-made labels and
   report where it agrees/disagrees with the threshold labels — agreement is the
   green light.

## The three fixes (non-negotiable — this is what makes it 2.0)

**FIX 1 — Stride sampling (the autocorrelation flaw).** NEVER build the matrix
from overlapping rolling windows: consecutive 20-day windows share 19 days, which
fakes persistence on the diagonal. Count transitions between NON-overlapping
windows (stride = window length; default 20 bars). Always compute BOTH matrices
— overlapping (legacy) and stride-sampled (true) — and show them side by side
with a one-line warning that only the stride-sampled one is statistically honest.

**FIX 2 — Label verification.** After building any table, chart or matrix
display, SELF-CHECK the state labels: programmatically verify the mapping
(e.g. 0=sideways, 1=bull, 2=bear) against three known historical periods (a
famous bull run, a famous crash, a flat stretch). If the rendered display
disagrees with the data, fix it before showing the user. The original version
shipped with bull/bear swapped in a display — never repeat that class of bug.

**FIX 3 — Two explicit modes.** At onboarding, ask the user which they want:
- **FILTER mode** (default): the regime gates an existing strategy — longs only
  when signal > a threshold, shorts only when below, flat in chop. The user's
  strategy stays theirs; Markov 2.0 decides WHEN it's allowed to act.
- **STANDALONE mode**: trade the differential directly, position size scaled to
  |signal| with a user-set cap.
Explain the difference in two sentences; never leave it ambiguous.

## Optional richer states (offer, don't force)

Price-only states are the default. Offer "enhanced states": cluster on 20-day
return + ATR (volatility) + relative volume, so "bear and violent" ≠ "bear and
asleep". If chosen, report how the matrix and signal change vs price-only.

## Proof, not promises

After installation, run the demo: SPY, 10 years, walk-forward (never test on
data the matrix has learned from — recalculate as you walk). Report honestly:
win rate, profit factor, max drawdown, equity curve image, before-fix vs
after-fix comparison. Then say exactly this caveat: "Backtests flatter. The
fixed matrix shows uglier, truer numbers — those are the only ones worth
trading." Offer to re-run on any ticker the user names.

## Skill installation

In Claude Code: create the skill as `markov-2-hedge-fund-method` so the user can
invoke it on any strategy or ticker later; confirm the slash-command works. In
other LLMs: store this method in the conversation and say plainly that it lives
in this chat.

Begin onboarding now: brief the user in 4 short lines on what will happen, then
wait for **go**.

