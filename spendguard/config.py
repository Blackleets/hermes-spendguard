"""SpendGuard configuration — a small JSON file in the plugin data dir.

Budgets are changed ONLY through the human-typed /spendguard slash
command (or by editing this file). There is deliberately no tool that
changes a budget: the agent can read its spend, never raise its own cap.
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULTS: dict = {
    "daily_budget_usd": None,      # None = no daily cap
    "monthly_budget_usd": None,    # None = no monthly cap
    "enforcement": "hard",         # "hard" = block turns at the cap | "warn" = only warn
    "strict_tools": True,          # also block tool calls mid-turn once over budget
    "warn_at_percent": [75, 90],   # inject a context warning at these % of any cap
    "count_auxiliary": True,       # count titling/compression/vision calls too
    "prices": {},                  # overrides: model -> [input $/1M, output $/1M]
    "fallback_rate_per_1m": None,  # [in, out] applied to otherwise-unpriced models
}


def load_config(path: str | Path) -> dict:
    cfg = dict(DEFAULTS)
    p = Path(path)
    if p.exists():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for key in DEFAULTS:
                    if key in raw:
                        cfg[key] = raw[key]
        except Exception:
            pass  # a broken config must never break the agent; defaults apply
    return cfg


def save_config(path: str | Path, cfg: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    clean = {k: cfg.get(k, DEFAULTS[k]) for k in DEFAULTS}
    p.write_text(json.dumps(clean, indent=2, ensure_ascii=False), encoding="utf-8")


def fallback_rate(cfg: dict) -> tuple[float, float] | None:
    val = cfg.get("fallback_rate_per_1m")
    if isinstance(val, (list, tuple)) and len(val) == 2:
        try:
            return float(val[0]), float(val[1])
        except (TypeError, ValueError):
            return None
    return None


def price_overrides(cfg: dict) -> dict:
    raw = cfg.get("prices") or {}
    out = {}
    if isinstance(raw, dict):
        for model, pair in raw.items():
            if isinstance(pair, (list, tuple)) and len(pair) == 2:
                try:
                    out[str(model)] = (float(pair[0]), float(pair[1]))
                except (TypeError, ValueError):
                    continue
    return out
