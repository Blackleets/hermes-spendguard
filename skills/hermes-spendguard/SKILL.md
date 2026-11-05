---
name: hermes-spendguard
description: Work under a SpendGuard budget — check spend before expensive work, respect warnings, and never try to change the budget yourself.
---

# SpendGuard — working under a budget

This installation has **SpendGuard**, a budget guard for model API spend.
It records every provider call's cost locally and enforces the daily /
monthly USD budgets the user set.

## Rules for the agent

1. **Check before expensive work.** Before a long task, a big research
   sweep, a multi-agent fan-out or anything likely to make many model
   calls, call `spendguard_status` and look at today's and this month's
   remaining budget. If the work plausibly exceeds what is left, tell the
   user the numbers and let them decide.
2. **Warnings are real.** When a SpendGuard budget warning appears in
   context (75% / 90%), say so plainly to the user once, keep calls
   lean, and avoid optional expensive detours.
3. **A block is final.** When SpendGuard blocks a turn or a tool call,
   the budget is spent. Do NOT retry, rephrase, split the work to sneak
   under the cap, or look for another route around it. Tell the user the
   exact figures and the one command that changes them:
   `/spendguard set daily <amount>` or `/spendguard set monthly <amount>`.
4. **You cannot change budgets.** There is deliberately no tool for it.
   Budgets change only when the human types the /spendguard command.
   Never ask the user for their password or payment details to "fix" a
   budget, and never claim to have raised one.
5. **Report with `spendguard_report`** when the user asks what something
   cost, which model spent the most, or where the money went. Use the
   `day` period for today and `month` for the running month.

## What the numbers mean

- Costs are provider-reported when the provider includes the actual cost
  in its response; otherwise they are estimates from public list prices
  (table dated in the plugin README). Estimates can differ from the
  invoice, especially where prompt-cache discounts apply.
- "Unpriced" calls are counted by tokens with cost unknown — the model
  has no price in the table and reported none. The user can add a price
  with `/spendguard price <model> <in $/1M> <out $/1M>`.
