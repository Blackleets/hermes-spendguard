"""SpendGuard hooks — the eyes and the brake.

Accounting (observers, never raise):
  post_api_request    — every raw provider call of a turn
  post_auxiliary_call — titling / compression / vision / MoA calls

Enforcement:
  pre_llm_call  — once per turn, before the tool loop. Over budget with
                  enforcement='hard' → {"action": "block", ...}: the turn
                  makes ZERO model calls, so the block itself is free.
                  Near the cap → injects a short budget warning as context.
  pre_tool_call — mid-turn backstop ('strict_tools'): once over budget,
                  further tool calls are blocked so a long turn cannot
                  keep looping and spending. SpendGuard's own read-only
                  tools stay allowed so the agent can still report status.

A hook that crashes is logged and skipped by Hermes; every callback here
also guards itself, because a policy hook must never break the agent.
"""

from __future__ import annotations

import logging

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

logger = logging.getLogger(__name__)

OWN_TOOLS = {"spendguard_status", "spendguard_report"}

_ledger: Ledger | None = None


def _get_ledger() -> Ledger:
    global _ledger
    if _ledger is None:
        _ledger = Ledger(db_path())
    return _ledger


def _cfg() -> dict:
    return cfg_mod.load_config(config_path())


def reset_state() -> None:
    """Drop the cached ledger (used by tests after changing data dir)."""
    global _ledger
    if _ledger is not None:
        _ledger.close()
    _ledger = None


# ---------------------------------------------------------------- accounting

def _record(kwargs: dict, kind: str) -> None:
    usage = kwargs.get("usage") or {}
    in_tok, out_tok = prices_mod.token_counts(usage)
    model = kwargs.get("response_model") or kwargs.get("model") or ""
    cfg = _cfg()
    cost = prices_mod.provider_cost(usage)
    if cost is not None:
        source = "provider"
    else:
        cost, source = prices_mod.estimate(
            model, in_tok, out_tok,
            overrides=cfg_mod.price_overrides(cfg),
            fallback=cfg_mod.fallback_rate(cfg),
        )
    _get_ledger().record(
        session_id=kwargs.get("session_id") or "",
        model=model,
        provider=kwargs.get("provider") or "",
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=cost,
        cost_source=source,
        kind=kind,
    )


def post_api_request(**kwargs) -> None:
    try:
        _record(kwargs, "main")
    except Exception:
        logger.exception("spendguard: post_api_request accounting failed")


def post_auxiliary_call(**kwargs) -> None:
    try:
        if _cfg().get("count_auxiliary", True):
            _record(kwargs, "aux")
    except Exception:
        logger.exception("spendguard: post_auxiliary_call accounting failed")


# ---------------------------------------------------------------- enforcement

def _evaluate() -> tuple[dict, dict]:
    cfg = _cfg()
    return cfg, guard_mod.evaluate(cfg, _get_ledger())


def pre_llm_call(session_id=None, user_message=None, **kwargs):
    try:
        cfg, st = _evaluate()
        if st["over"] and cfg.get("enforcement", "hard") == "hard":
            return {"action": "block", "message": guard_mod.block_message(st)}
        if st["state"] == "warn":
            return {"context": guard_mod.warning_context(st)}
        return None
    except Exception:
        logger.exception("spendguard: pre_llm_call failed — turn proceeds")
        return None


def pre_tool_call(tool_name=None, args=None, **kwargs):
    try:
        if tool_name in OWN_TOOLS:
            return None
        cfg, st = _evaluate()
        if (st["over"] and cfg.get("enforcement", "hard") == "hard"
                and cfg.get("strict_tools", True)):
            return {"action": "block",
                    "message": ("💸 SpendGuard: budget reached "
                                f"({guard_mod.money(st['day']['spent'])} today"
                                f" · {guard_mod.money(st['month']['spent'])} this month). "
                                "Tool calls are paused until the user raises the budget "
                                "with /spendguard set — the agent cannot raise it.")}
        return None
    except Exception:
        logger.exception("spendguard: pre_tool_call failed — call proceeds")
        return None
