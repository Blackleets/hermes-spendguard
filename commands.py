"""The /spendguard slash command — the ONLY way budgets change.

Slash commands are typed by the human in the client, outside the model,
so anything set here is a human decision by construction. That is the
point of SpendGuard: the agent can watch the meter, never move the cap.
"""

from __future__ import annotations

try:  # loaded as a Hermes plugin package
    from .spendguard import config as cfg_mod
    from .spendguard import guard as guard_mod
    from .spendguard import prices as prices_mod
    from .spendguard.ledger import Ledger
    from .spendguard.paths import config_path, db_path
except ImportError:  # standalone / tests
    from spendguard import config as cfg_mod
    from spendguard import guard as guard_mod
    from spendguard import prices as prices_mod
    from spendguard.ledger import Ledger
    from spendguard.paths import config_path, db_path

HELP = (
    "💸 SpendGuard commands:\n"
    "  /spendguard — status\n"
    "  /spendguard report [month] — per-model breakdown\n"
    "  /spendguard set daily <usd> · set monthly <usd> — set a budget\n"
    "  /spendguard off daily · off monthly — remove a budget\n"
    "  /spendguard set enforce hard|warn — hard blocks turns at the cap\n"
    "  /spendguard set strict on|off — also block tool calls once over budget\n"
    "  /spendguard price <model> <in $/1M> <out $/1M> — add/override a price\n"
    "  /spendguard prices — your price overrides"
)


def _amount(text: str) -> float | None:
    try:
        val = float(str(text).replace("$", "").replace(",", "").strip())
        return val if val >= 0 else None
    except (TypeError, ValueError):
        return None


def spendguard_command(raw_args: str) -> str:
    try:
        cfg = cfg_mod.load_config(config_path())
        ledger = Ledger(db_path())
        try:
            parts = (raw_args or "").strip().split()
            if not parts or parts[0] in ("status", "show"):
                return guard_mod.status_text(guard_mod.evaluate(cfg, ledger))

            cmd = parts[0].lower()

            if cmd == "report":
                period = "month" if len(parts) > 1 and parts[1].lower().startswith("month") else "day"
                return guard_mod.report_text(cfg, ledger, period)

            if cmd == "prices":
                overrides = cfg.get("prices") or {}
                if not overrides:
                    return (f"No price overrides set (built-in table dated "
                            f"{prices_mod.PRICES_AS_OF}). Add one: "
                            "/spendguard price <model> <in $/1M> <out $/1M>")
                lines = [f"Your price overrides (table dated {prices_mod.PRICES_AS_OF}):"]
                for model, pair in sorted(overrides.items()):
                    lines.append(f"  {model}: ${pair[0]:g} in / ${pair[1]:g} out per 1M")
                return "\n".join(lines)

            if cmd == "price" and len(parts) == 4:
                model, rin, rout = parts[1], _amount(parts[2]), _amount(parts[3])
                if rin is None or rout is None:
                    return "Usage: /spendguard price <model> <input $/1M> <output $/1M>"
                cfg.setdefault("prices", {})[model] = [rin, rout]
                cfg_mod.save_config(config_path(), cfg)
                return f"✅ Price set: {model} at ${rin:g} in / ${rout:g} out per 1M tokens."

            if cmd == "off" and len(parts) == 2 and parts[1].lower() in ("daily", "monthly"):
                key = "daily_budget_usd" if parts[1].lower() == "daily" else "monthly_budget_usd"
                cfg[key] = None
                cfg_mod.save_config(config_path(), cfg)
                return f"✅ {parts[1].capitalize()} budget removed. Spend is still recorded."

            if cmd == "set" and len(parts) >= 3:
                what = parts[1].lower()
                if what in ("daily", "monthly") and len(parts) == 3:
                    amount = _amount(parts[2])
                    if amount is None:
                        return "Usage: /spendguard set daily <usd amount>"
                    key = "daily_budget_usd" if what == "daily" else "monthly_budget_usd"
                    cfg[key] = amount
                    cfg_mod.save_config(config_path(), cfg)
                    st = guard_mod.evaluate(cfg, ledger)
                    return (f"✅ {what.capitalize()} budget set to {guard_mod.money(amount)}.\n"
                            + guard_mod.status_text(st))
                if what == "enforce" and parts[2].lower() in ("hard", "warn"):
                    cfg["enforcement"] = parts[2].lower()
                    cfg_mod.save_config(config_path(), cfg)
                    return (f"✅ Enforcement: {cfg['enforcement']}"
                            + (" — turns will be blocked at the cap (zero model calls)."
                               if cfg["enforcement"] == "hard"
                               else " — warnings only, turns continue over budget."))
                if what == "strict" and parts[2].lower() in ("on", "off"):
                    cfg["strict_tools"] = parts[2].lower() == "on"
                    cfg_mod.save_config(config_path(), cfg)
                    return f"✅ Strict tool blocking: {'on' if cfg['strict_tools'] else 'off'}."

            return HELP
        finally:
            ledger.close()
    except Exception as exc:
        return f"💸 SpendGuard command failed: {type(exc).__name__}: {exc}"
