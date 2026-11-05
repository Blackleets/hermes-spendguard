# Changelog

## 0.1.0 — 2026-11-05

First release, built for the Hermes Agent Plugin Hackathon.

- Local SQLite ledger of every provider API call (`post_api_request` +
  `post_auxiliary_call` hooks): model, provider, tokens, cost and the
  cost's source. No message text is ever stored.
- Price engine: provider-reported cost when present, otherwise public
  list-price estimates (table dated 2026-11-04) with per-user overrides
  and an optional fallback rate; unknown models are counted by tokens
  and marked unpriced — never priced by invention.
- Daily and monthly USD budgets with warning thresholds (75% / 90% by
  default, injected into turn context).
- Hard enforcement: `pre_llm_call` blocks new turns at the cap before
  any inference (zero model calls), plus an optional strict
  `pre_tool_call` backstop that pauses tool calls mid-turn.
- Human-only budget control via the /spendguard slash command; the two
  agent tools (`spendguard_status`, `spendguard_report`) are read-only
  by design.
- Dashboard tab + Hermes Desktop page with live budget bars and
  per-model breakdowns; bundled agent skill for working under a budget.
- 14 offline tests covering pricing, ledger math, policy states, hook
  behavior, commands and registration.
