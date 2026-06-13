Paste everything below the horizontal rule into Claude Code and hit Enter.

## Requirements: Claude Code (running), Git, Node.js (for the Railway CLI — the agent installs it for you if missing).

## What this builds:

- A trading worker deployed to a Railway service that runs your strategy 24/7 in paper mode.

- A goal config you build on camera — what success looks like, what failure looks like.

- A local Hermes install (Nous Research's open agent) that takes over as the brain at the end. Hermes watches the worker's outcomes, writes hypotheses, and edits the strategy file — one variable at a time, scientific-method style.

The whole flow runs in one terminal session. No tab-switching, no re-pasting the prompt.