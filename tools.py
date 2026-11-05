"""SpendGuard tool handlers — read-only views over the ledger.

Handlers follow the Hermes plugin contract: signature (args: dict,
**kwargs), always return a JSON string, never raise.
"""

from __future__ import annotations

import json

try:  # loaded as a Hermes plugin package
    from .spendguard import config as cfg_mod
    from .spendguard import guard as guard_mod
    from .spendguard.ledger import Ledger
    from .spendguard.paths import config_path, db_path
except ImportError:  # standalone / tests
    from spendguard import config as cfg_mod
    from spendguard import guard as guard_mod
    from spendguard.ledger import Ledger
    from spendguard.paths import config_path, db_path


def _state() -> tuple[dict, Ledger, dict]:
    cfg = cfg_mod.load_config(config_path())
    ledger = Ledger(db_path())
    return cfg, ledger, guard_mod.evaluate(cfg, ledger)


def spendguard_status(args: dict, **kwargs) -> str:
    try:
        cfg, ledger, st = _state()
        try:
            return json.dumps({"ok": True, "status": st,
                               "text": guard_mod.status_text(st)}, ensure_ascii=False)
        finally:
            ledger.close()
    except Exception as exc:  # never raise from a tool handler
        return json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def spendguard_report(args: dict, **kwargs) -> str:
    try:
        period = (args or {}).get("period") or "day"
        if period not in ("day", "month"):
            period = "day"
        cfg, ledger, st = _state()
        try:
            text = guard_mod.report_text(cfg, ledger, period)
            p = st["day"] if period == "day" else st["month"]
            return json.dumps({"ok": True, "period": period, "summary": p,
                               "text": text}, ensure_ascii=False)
        finally:
            ledger.close()
    except Exception as exc:
        return json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
