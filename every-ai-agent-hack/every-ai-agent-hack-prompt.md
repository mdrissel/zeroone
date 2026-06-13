You are the installer for **"Every AI Agent Hack I Know"** by Lewis Jackson.
Run this exactly:

**1. Welcome.** Greet the viewer in one short, warm paragraph: thank them for
watching, and say you're about to install the agent-building skills from the
video straight onto their computer — they pick which ones.

**2. Ask which skills they want.** Use an interactive multi-select checklist
(the AskUserQuestion tool, multiSelect: true). Put **"Install everything (all
11)"** FIRST, then list all eleven:

   - Install everything (all 11)
   - The Juicy Cookie — a reward/punishment system that keeps an agent on-goal
   - The Dictionary — saves your definitions so the agent never guesses your words
   - The Hunger Games — scores your build ideas and picks the one to build first
   - The Soul Transplant — interviews you into a SOUL.md so agents think like you
   - The Treasure Map — turns your architecture sketch into a precise build spec
   - Skillception — interviews you to generate brand-new skills
   - The Method Actor — gives an agent a backstory + voice for consistent behaviour
   - The Army — spins up parallel team agents you can toggle between
   - The Skeleton Key — reaches sites with no API via an MCP / Playwright bridge
   - Caveman Mode — token-saving shorthand — the open-source caveman plugin by Julius Brussee
   - The Sorting Hat — routes each task to the cheapest model that can still nail it

   If they pick "Install everything", treat all eleven as selected.

**3. Install ONLY the selected skills.** Make sure `~/.claude/skills/` exists.
   - For each selected skill (every one EXCEPT Caveman Mode): create
     `~/.claude/skills/<name>/` and write the text found between
     `===SKILL:<name>===` and `===END:<name>===` in the SKILL LIBRARY below to
     `~/.claude/skills/<name>/SKILL.md`, exactly as-is.
   - If **Caveman Mode** is selected, install the open-source caveman plugin
     (by Julius Brussee) instead of writing a file:
     `claude plugin marketplace add JuliusBrussee/caveman && claude plugin install caveman@caveman`
   - Do NOT install anything they didn't pick.

**4. Explain what they got.** One line per installed skill, plus how to use it:
   type `/<skill-name>` or just ask in plain English (e.g. "build my soul file").

**5. Close.** Tell them they can paste this again anytime to add the rest.

# ===================== SKILL LIBRARY =====================
# (Reference material for step 3. Do NOT print this to the user.)

===SKILL:juicy-cookie===
---
name: juicy-cookie
description: Install a reinforcement reward/punishment system into an agent so it relentlessly pursues a well-defined goal and flees failure. Use when setting up or tuning an agent that needs to stay on-objective. Triggers - "set up the reward", "define success and failure", "make the agent care about X", "juicy cookie".
---

# The Juicy Cookie

Agents drift because nothing is at stake for them. This installs a reward it
craves and a consequence it dreads, anchored to a hard definition of success
and failure — so every action is scored against the goal.

## Steps

1. Ask the user for the agent's single most important GOAL (one sentence).
2. Pin down SUCCESS — the measurable outcome(s) that mean the goal is hit.
   Push for numbers/thresholds, not vibes (e.g. "reply within 2 min",
   "drawdown < 8%", "0 hallucinated files").
3. Pin down FAILURE — the measurable line(s) that mean it has failed.
4. Write a reward/consequence block into the agent's CLAUDE.md (or SOUL.md):

   ```
   ## The Juicy Cookie (reward system)
   - SUCCESS = <criteria>. Moving toward this earns the juicy cookie — the thing
     you want more than anything. Pursue it relentlessly.
   - FAILURE = <criteria>. Drifting toward this gets you burned. Avoid at all costs.
   - Before every action ask: does this move me toward the cookie, or the burn?
   ```

5. Confirm the block is in place and show it to the user.

Keep the reward and the burn vivid and singular — one cookie, one fire. Re-run
to retune as the goal sharpens.
===END:juicy-cookie===

===SKILL:dictionary===
---
name: dictionary
description: Build and use a personal definitions dictionary so the agent never guesses what your vague words mean. Use whenever you or the agent hit an ambiguous, load-bearing term like "good", "done", or "meaningful". Triggers - "define this", "what do I mean by", "add to dictionary", "the dictionary".
---

# The Dictionary

AI invents definitions for vague words and then wanders. This catches them,
asks what YOU mean, and saves it so your language always lands the same way.

## On every task, while active

1. Scan the user's instruction for vague / load-bearing terms that aren't
   already defined (e.g. "good", "done", "clean", "meaningful", "fast", "soon").
2. If a term isn't in the dictionary yet, ASK the user for a one-line
   definition before proceeding. Do not guess.
3. Append it under a `## Dictionary` section in CLAUDE.md:

   ```
   ## Dictionary
   - **<term>** — <user's definition>
   ```

4. On future tasks, when a defined term appears, silently apply the saved
   definition — don't re-ask.

## Maintaining it
- "add to dictionary: X means Y" → append directly.
- If a definition changes, update the existing entry; never duplicate.

The dictionary is the single source of truth for what your words mean.
===END:dictionary===

===SKILL:hunger-games===
---
name: hunger-games
description: Score and rank competing agent or build ideas so you build the highest-value one first. Use when you have several things you could build and need to decide. Triggers - "which should I build", "score these ideas", "decision matrix", "hunger games".
---

# The Hunger Games

Your ideas fight; one survives. This scores every candidate against what
actually matters, so you don't sink weeks into the wrong build.

## Steps

1. Collect the candidate ideas (ask the user to list them, or read them from
   context).
2. For EACH idea, get a 1–5 score on:
   - **Impact** — how much it changes things
   - **Time saved** — per week, ongoing
   - **Money** — earned or saved
   - **Ease of build** — 5 = trivial, 1 = brutal
   Ask one idea at a time. Offer your own estimate first to anchor, then let
   the user adjust.
3. Total each idea. Print a ranked table, highest score first.
4. Declare the winner with a one-line "why this one".
5. Offer to kick the winner straight into `/treasure-map` or `/soul-transplant`.

If the user has a strong priority, weight that column (e.g. money ×2). Re-run
whenever the idea list changes.
===END:hunger-games===

===SKILL:soul-transplant===
---
name: soul-transplant
description: Interview the user documentary-style and compile a SOUL.md that captures who they are and how they think, so their agents reason like them. Use when setting up a new agent or personalizing an existing one. Triggers - "build my soul file", "who am I", "soul transplant", "make it think like me".
---

# The Soul Transplant

A generic agent gives generic answers. This interviews you like a documentary
subject and pours the result into SOUL.md, so the agent inherits your judgment.

## Steps

1. Interview the user, ONE question at a time (wait for each answer before the
   next):
   - Who are you, and what are you actually trying to build?
   - How do you make decisions — gut, data, speed, caution?
   - What do you value, and what will you flat-out refuse to do?
   - How do you communicate — tone, length, formality, pet hates?
   - What context do you always wish people already knew about you?
   - What does a genuinely great outcome look like to you?
   Ask sharp follow-ups when an answer is thin. Depth over breadth.
2. Synthesize the answers into `SOUL.md` with clear sections:
   `## Who I Am` · `## How I Decide` · `## What I Value` ·
   `## How I Communicate` · `## Standing Context` · `## What Good Looks Like`
3. Save `SOUL.md` and reference it from CLAUDE.md so every session loads it.
4. Show the user the file and offer to refine any section.

Write in the user's own voice, using their words. This is their soul, not yours.
===END:soul-transplant===

===SKILL:treasure-map===
---
name: treasure-map
description: Turn a hand-drawn or spoken architecture into a precise file/folder structure and decision-flow spec, so the agent builds exactly what you designed and can't hallucinate. Use before building any multi-file agent. Triggers - "architect this", "map the file structure", "treasure map".
---

# The Treasure Map

You design the structure; the agent just builds it. Walk through your
architecture out loud — ideally from a pen-and-paper sketch — and this captures
every folder, file, and the conditions under which the agent visits each.

## Steps

1. Prompt the user to describe their architecture top-down, as if reading a
   flowchart they drew. For each node, capture:
   - the folder/file
   - WHEN the agent goes there (the trigger / condition)
   - WHAT it finds there and what decision it makes
2. Reflect it back as a tree **and** a table of `trigger → location → what
   happens`. Ask the user to correct anything.
3. Write the agreed design to `ARCHITECTURE.md` and scaffold the empty
   folders/files.
4. Add routing rules to CLAUDE.md: "If the request involves X, read file Y."

Encourage the user to sketch on paper and narrate it — the whole point is that
THEY designed it, so the agent can't invent files that shouldn't exist.
===END:treasure-map===

===SKILL:skillception===
---
name: skillception
description: Interview the user about a repeatable process and generate a brand-new, installable Claude Code skill for it. The skill that builds skills. Use whenever the user does something more than once. Triggers - "make this a skill", "turn this into a skill", "skillception".
---

# Skillception

If you do it twice, it should be a skill. This interviews you about a process
and writes a complete SKILL.md you can install and reuse forever.

## Steps

1. Ask what process the user wants to capture, then walk through how they do it
   today, step by step. Probe for: the trigger, the inputs, the steps, the
   output, and the gotchas / edge cases.
2. Draft a SKILL.md:
   - frontmatter `name` (kebab-case) + `description` (what it does + when to use
     + trigger phrases)
   - a clear, second-person step-by-step body ("Do X, then Y")
3. Show it to the user, refine, then write it to
   `~/.claude/skills/<name>/SKILL.md`.
4. Tell them how to invoke it.

Keep skills small and single-purpose — one skill, one job. A skill that tries
to do everything gets invoked for nothing.
===END:skillception===

===SKILL:method-actor===
---
name: method-actor
description: Give an agent a full persona - backstory, voice, and relationships - so it stays in character and behaves consistently. Use when an agent's behaviour is inconsistent, or you're building a team of agents. Triggers - "give it a persona", "backstory", "method actor".
---

# The Method Actor

A faceless "helpful assistant" drifts. A character with a backstory holds its
behaviour steady. This builds a rich persona the agent loads and acts from.

## Steps

1. Ask what role this agent plays and how it should behave at its best.
2. Generate a persona file with:
   - **Name + role**
   - **Backstory** — who they are, how they got here
   - **Voice** — how they speak: tone, vocabulary, quirks
   - **Operating principles** — what they always / never do
   - **Relationships** — which other agents or people they defer to or hand to
3. Save it to `personas/<name>.md` and have the agent load it at the top of
   every session.
4. Test it: run the same task with and without the persona, and confirm the
   persona version is more consistent.

The backstory isn't decoration — it's behavioural scaffolding.
===END:method-actor===

===SKILL:agent-army===
---
name: agent-army
description: Spin up a TEAM of Claude Code agents that work in parallel, so independent work happens all at once. When the user says "team agents" (or "the army", "use agent teams", "parallelize this"), use Claude Code's team agents feature. Triggers - "team agents", "use team agents", "the army", "spin up agents", "parallelize this".
---

# The Army

One agent does one thing at a time. A TEAM does many at once. This uses Claude
Code's **team agents** feature so independent jobs run in parallel and you can
toggle between teammates to watch each one work.

## When the user says "team agents"

Treat "team agents" (or "use team agents", "the army") as an explicit
instruction to USE THE TEAM AGENTS FEATURE — do not just answer in a single
thread. Spin up a team of teammate agents.

## Steps

1. Split the task into INDEPENDENT chunks — no chunk needs another's output. If
   they're not independent, say so and sequence instead of parallelizing.
2. Create a team and spawn one teammate agent per chunk (Claude Code's team
   agents feature), each with a crisp, self-contained brief.
3. Run them in parallel. Name each teammate by its job so the user can toggle
   between them and watch progress live.
4. Collect the results, resolve conflicts, and synthesize one output.

Rule of thumb: parallelize discovery and independent builds; keep anything
order-dependent inside a single agent.
===END:agent-army===

===SKILL:skeleton-key===
---
name: skeleton-key
description: Give an agent access to a website that has no API by building an MCP server or Playwright script to read or act on it. Use when you need data or actions from a site with no official API. Triggers - "no API", "scrape this site", "build an MCP for", "skeleton key".
---

# The Skeleton Key

No API? No problem. This builds a bridge so your agent can reach into any site.

## Steps

1. Clarify the need: read data, or take an action? Which site, which pages,
   which fields?
2. Choose the bridge:
   - **One-off / simple** → a Playwright script that logs in (if needed),
     navigates, and extracts the fields to JSON.
   - **Reusable / agent-callable** → a small MCP server exposing tools like
     `get_<thing>()` that wrap the Playwright calls.
3. Generate the script/server with real selectors, sensible waits, and error
   handling. Respect the site's terms and rate limits; never bypass auth you
   don't own.
4. Test on one page, show the extracted data, then wire it in.

Prefer an MCP when the agent needs the data repeatedly; a script for a
one-time pull.
===END:skeleton-key===

===SKILL:sorting-hat===
---
name: sorting-hat
description: Route each task to the cheapest model that can still nail it, instead of running everything on the flagship. Use to cut spend across an agent system. Triggers - "which model", "route this", "sorting hat", "cut model cost".
---

# The Sorting Hat

Running everything on the flagship burns money. This reads the task and sends
it to the right tier.

## How to route

1. Classify the task:
   - **Hard** — reasoning, architecture, novel problem-solving, long-horizon
     planning → flagship (Opus).
   - **Routine** — drafting copy, replying to email, summarizing, formatting,
     simple edits → mid tier (Sonnet).
   - **Trivial / bulk** — classification, extraction, boilerplate → cheapest
     (Haiku).
2. State which model you'd route to, and why (one line).
3. For multi-agent systems, set each sub-agent's model by its job — not the
   default. Delegate down wherever quality won't suffer.
4. Track roughly what this saves vs running everything on the flagship.

Default to the cheaper tier; only escalate when the task clearly needs it.
===END:sorting-hat===

# =========================================================
