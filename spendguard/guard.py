"""Budget policy — pure evaluation over the ledger, plus human text.

State machine per period (day / month):
  ok    — under the first warning threshold (or no budget set)
  warn  — at or past a warning threshold, still under the cap
  over  — spend has reached the cap; with enforcement='hard' new turns
          are blocked before they reach the model (zero model calls,
          zero additional spend)
"""

from __future__ import annotations

from datetime import datetime

from .ledger import Ledger, day_bounds, month_bounds


def _period(totals: dict, cap) -> dict:
    spent = float(totals["spent"])
    pct = None
    if cap:
        pct = round(100.0 * spent / float(cap), 1)
    return {
        "spent": round(spent, 4),
        "cap": float(cap) if cap else None,
        "pct": pct,
        "calls": totals["calls"],
        "unpriced": totals["unpriced"],
        "input_tokens": totals["input_tokens"],
        "output_tokens": totals["output_tokens"],
        "over": bool(cap) and spent >= float(cap),
    }


def evaluate(cfg: dict, ledger: Ledger, now: datetime | None = None) -> dict:
    now = now or datetime.now().astimezone()
    d0, d1 = day_bounds(now)
    m0, m1 = month_bounds(now)
    day = _period(ledger.totals(d0, d1), cfg.get("daily_budget_usd"))
    month = _period(ledger.totals(m0, m1), cfg.get("monthly_budget_usd"))

    over = None
    if day["over"]:
        over = "daily"
    elif month["over"]:
        over = "monthly"

    thresholds = sorted({int(t) for t in (cfg.get("warn_at_percent") or []) if t})
    warn = None
    for period in (day, month):
        if period["pct"] is not None:
            for t in thresholds:
                if period["pct"] >= t and (warn is None or t > warn):
                    warn = t

    if over:
        state = "over"
    elif not day["cap"] and not month["cap"]:
        state = "unbudgeted"
    elif warn is not None:
        state = "warn"
    else:
        state = "ok"

    return {
        "state": state,
        "over": over,
        "warn_threshold": warn,
        "enforcement": cfg.get("enforcement", "hard"),
        "day": day,
        "month": month,
    }


def money(x) -> str:
    if x is None:
        return "—"
    return f"${float(x):,.2f}"


def _period_line(label: str, p: dict) -> str:
    if not p["cap"]:
        return f"{label}: {money(p['spent'])} spent · no budget set · {p['calls']} calls"
    line = (f"{label}: {money(p['spent'])} of {money(p['cap'])} "
            f"({p['pct']:.0f}%) · {p['calls']} calls")
    if p["unpriced"]:
        line += f" · ⚠ {p['unpriced']} unpriced calls (tokens counted, cost unknown)"
    return line


def status_text(st: dict) -> str:
    icon = {"ok": "🟢", "warn": "🟡", "over": "🔴", "unbudgeted": "⚪"}[st["state"]]
    lines = [f"💸 SpendGuard {icon}"]
    lines.append(_period_line("Today", st["day"]))
    lines.append(_period_line("This month", st["month"]))
    if st["state"] == "over":
        lines.append(
            f"⛔ {st['over'].capitalize()} budget reached — "
            + ("new turns are BLOCKED before they reach the model (zero spend). "
               "Raise it yourself with /spendguard set "
               f"{'daily' if st['over'] == 'daily' else 'monthly'} <amount>."
               if st["enforcement"] == "hard"
               else "enforcement is 'warn', so turns continue — you are over budget."))
    elif st["state"] == "warn":
        lines.append(f"⚠ Past the {st['warn_threshold']}% warning line.")
    elif st["state"] == "unbudgeted":
        lines.append("Set a cap with /spendguard set daily <amount> or /spendguard set monthly <amount>.")
    return "\n".join(lines)


def block_message(st: dict) -> str:
    period = "daily" if st["over"] == "daily" else "monthly"
    p = st["day"] if st["over"] == "daily" else st["month"]
    return (
        f"💸 SpendGuard stopped this turn before it reached the model: "
        f"{period} spend is {money(p['spent'])}, at the {money(p['cap'])} budget you set "
        f"(this month: {money(st['month']['spent'])}"
        + (f" of {money(st['month']['cap'])}" if st["month"]["cap"] else "") + "). "
        "No model call was made and nothing was spent. "
        "Only you can raise the budget — the agent cannot — with: "
        f"/spendguard set {period} <new amount>  ·  check /spendguard for status."
    )


def warning_context(st: dict) -> str:
    parts = []
    for label, p in (("today", st["day"]), ("this month", st["month"])):
        if p["cap"]:
            parts.append(f"{label} {money(p['spent'])} of {money(p['cap'])} ({p['pct']:.0f}%)")
    return ("💸 SpendGuard budget warning: " + " · ".join(parts) +
            ". Spend carefully; at 100% new turns are blocked before reaching the model.")


def report_text(cfg: dict, ledger: Ledger, period: str = "day",
                now: datetime | None = None) -> str:
    now = now or datetime.now().astimezone()
    start, end = day_bounds(now) if period == "day" else month_bounds(now)
    rows = ledger.by_model(start, end)
    st = evaluate(cfg, ledger, now)
    p = st["day"] if period == "day" else st["month"]
    label = "Today" if period == "day" else "This month"
    lines = [f"💸 SpendGuard report — {label}: {money(p['spent'])}"
             + (f" of {money(p['cap'])} ({p['pct']:.0f}%)" if p["cap"] else "")
             + f" · {p['calls']} calls · {p['input_tokens']:,} in / {p['output_tokens']:,} out tokens"]
    if not rows:
        lines.append("No API calls recorded yet.")
    for r in rows:
        name = r["model"] or "(unknown model)"
        extra = f" · {r['unpriced']} unpriced" if r["unpriced"] else ""
        lines.append(f"  {name}: {money(r['spent'])} · {r['calls']} calls{extra}")
    if p["unpriced"]:
        lines.append(f"⚠ {p['unpriced']} calls had no known price — tokens counted, cost unknown. "
                     "Add one with /spendguard price <model> <in $/1M> <out $/1M>.")
    return "\n".join(lines)
