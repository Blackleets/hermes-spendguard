# 💸 Hermes SpendGuard

**A wallet guard for Hermes Agent.** SpendGuard prices every provider API
call your agent makes, tracks it against daily and monthly **dollar**
budgets, warns you as you approach the cap — and when the budget runs
out, it **hard-stops new turns before they reach the model**. The block
itself makes zero model calls, so hitting the wall is free.

> Analytics tell you what you spent. SpendGuard decides when you stop.

## Why

An autonomous agent with tools, cron jobs and subagents can burn real
money while you sleep — a stuck loop, a retry storm, a research task
that fan-outs further than you meant. Subscription-allowance guards
don't help when you pay per token, and spend dashboards only show you
the damage afterwards. SpendGuard is the missing enforcement layer:
**cross-provider, money-first, and impossible for the agent to talk its
way around** — budgets change only when the human types the command.

## How it works

| Piece | What it does |
|---|---|
| `post_api_request` hook | Records every raw provider call: model, tokens, cost |
| `post_auxiliary_call` hook | Also counts titling, compression, vision and MoA calls |
| Local SQLite ledger | One row per call in the plugin data dir. No message text, ever |
| Price engine | Provider-reported cost when the response carries one; otherwise public list-price estimates (table dated 2026-11-04, overridable). Unknown models are counted by tokens and marked **unpriced** — a price is never invented |
| `pre_llm_call` hook | Over budget → the turn is blocked *before any inference*: zero model calls, zero spend. Near the cap (75% / 90%, configurable) → a short warning is injected into context |
| `pre_tool_call` hook | Mid-turn backstop: once over budget, further tool calls pause so a long turn can't keep looping. SpendGuard's own read-only tools stay available so the agent can still report the numbers |

## Quickstart

```bash
hermes plugins install Blackleets/hermes-spendguard
```

Then, in any Hermes chat (typed by you — that's the point):

```
/spendguard set daily 10        # $10/day cap
/spendguard set monthly 200     # $200/month cap
/spendguard                     # status
/spendguard report month        # per-model breakdown
```

## Commands

```
/spendguard                          status (today + this month vs budgets)
/spendguard report [month]           per-model spend breakdown
/spendguard set daily <usd>          set the daily budget
/spendguard set monthly <usd>        set the monthly budget
/spendguard off daily|monthly        remove a budget (spend still recorded)
/spendguard set enforce hard|warn    hard = block turns at the cap; warn = advise only
/spendguard set strict on|off        also block tool calls mid-turn once over
/spendguard price <model> <in> <out> add/override a price (USD per 1M tokens)
/spendguard prices                   list your price overrides
```

Tools for the agent (both **read-only** — there is no tool that changes
a budget): `spendguard_status`, `spendguard_report`. Plus a dashboard
tab and a Hermes Desktop page with live budget bars.

## Honest limits

- **Turn-granular enforcement.** The hard stop is evaluated when a turn
  starts (and at each tool call in strict mode). A single turn already
  in flight can overshoot by its own remaining calls; the next turn is
  blocked. SpendGuard caps your bleed, it cannot rewind a call.
- **Estimates are estimates.** Unless the provider reports the actual
  cost, figures come from public list prices and don't model prompt-
  cache discounts, so they can run slightly high. Set your own prices
  with `/spendguard price` when a number matters.
- **Local time.** "Today" and "this month" follow the machine's local
  timezone, like your billing day does not — check the dashboard if you
  live near a boundary.

## Privacy & safety disclosure

- **Network:** none. SpendGuard makes no outbound requests of any kind.
- **Credentials:** none read, held or needed.
- **Data stored:** timestamp, session id, model, provider, token counts
  and the dollar figure (plus its source: provider / table / override /
  fallback / unpriced) in `spendguard.db` in the plugin data dir. No
  prompts, replies or tool arguments are recorded.
- **Shell / subprocess / self-update:** none.

## Development

```bash
python3 tests/test_spendguard.py   # 14 offline tests, no Hermes needed
SPENDGUARD_DATA_DIR=/tmp/sg-demo python3 scripts/seed_demo.py  # demo data
```

MIT © Lee Renteria (Blackleets)
