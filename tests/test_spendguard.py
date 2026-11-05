"""Offline tests for Hermes SpendGuard — no network, no Hermes install.

Run:  python3 -m pytest tests/ -q     (or: python3 tests/test_spendguard.py)
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from spendguard import prices  # noqa: E402
from spendguard.config import load_config, save_config  # noqa: E402
from spendguard.guard import evaluate  # noqa: E402
from spendguard.ledger import Ledger  # noqa: E402

import commands  # noqa: E402
import hooks  # noqa: E402
import tools  # noqa: E402


def fresh_env():
    tmp = tempfile.mkdtemp(prefix="spendguard-test-")
    os.environ["SPENDGUARD_DATA_DIR"] = tmp
    hooks.reset_state()
    return Path(tmp)


# ------------------------------------------------------------------- prices

def test_normalize_and_lookup():
    assert prices.normalize("Anthropic/Claude-Sonnet-4.5") == "claude-sonnet-4-5"
    found = prices.price_for("claude-sonnet-4-5-20250929")  # dated snapshot
    assert found is not None and found[0] == (3.00, 15.00)
    assert prices.price_for("openai/gpt-5")[0] == (1.25, 10.00)
    assert prices.price_for("some-unknown-model") is None


def test_override_wins():
    found = prices.price_for("gpt-5", overrides={"gpt-5": (9.0, 9.0)})
    assert found == ((9.0, 9.0), "override")


def test_estimate_and_unpriced():
    cost, source = prices.estimate("gpt-5", 1_000_000, 1_000_000)
    assert source == "table" and abs(cost - 11.25) < 1e-9
    cost, source = prices.estimate("mystery-model", 5_000, 5_000)
    assert cost is None and source == "unpriced"
    cost, source = prices.estimate("mystery-model", 1_000_000, 0, fallback=(2.0, 2.0))
    assert source == "fallback" and abs(cost - 2.0) < 1e-9


def test_provider_cost_and_token_shapes():
    assert prices.provider_cost({"cost": 0.42}) == 0.42
    assert prices.provider_cost({"total_tokens": 10}) is None
    assert prices.token_counts({"prompt_tokens": 7, "completion_tokens": 3}) == (7, 3)
    assert prices.token_counts({"input_tokens": 11, "output_tokens": 5}) == (11, 5)
    assert prices.token_counts(None) == (0, 0)


# ------------------------------------------------------------------- ledger

def test_ledger_totals_and_unpriced():
    db = Path(tempfile.mkdtemp()) / "t.db"
    led = Ledger(db)
    now = time.time()
    led.record(ts=now, model="gpt-5", input_tokens=100, output_tokens=50, cost_usd=0.01)
    led.record(ts=now, model="mystery", input_tokens=10, output_tokens=5, cost_usd=None)
    led.record(ts=now - 40 * 86400, model="gpt-5", cost_usd=99.0)  # last month
    from spendguard.ledger import day_bounds, month_bounds
    d = led.totals(*day_bounds())
    assert d["calls"] == 2 and abs(d["spent"] - 0.01) < 1e-9 and d["unpriced"] == 1
    m = led.totals(*month_bounds())
    assert m["calls"] == 2  # the 40-day-old call is outside this month
    rows = led.by_model(*day_bounds())
    assert rows[0]["model"] == "gpt-5"
    led.close()


# --------------------------------------------------------------------- guard

def _ledger_with(spend_today: float) -> Ledger:
    led = Ledger(Path(tempfile.mkdtemp()) / "g.db")
    if spend_today:
        led.record(model="gpt-5", cost_usd=spend_today)
    return led


def test_guard_states():
    led = _ledger_with(0.0)
    st = evaluate({}, led)
    assert st["state"] == "unbudgeted"

    led = _ledger_with(7.5)
    st = evaluate({"daily_budget_usd": 10.0, "warn_at_percent": [75, 90]}, led)
    assert st["state"] == "warn" and st["warn_threshold"] == 75 and not st["over"]

    led = _ledger_with(10.0)
    st = evaluate({"daily_budget_usd": 10.0}, led)
    assert st["state"] == "over" and st["over"] == "daily"

    led = _ledger_with(3.0)
    st = evaluate({"daily_budget_usd": 10.0, "monthly_budget_usd": 2.0}, led)
    assert st["over"] == "monthly"  # daily fine, month blown


# --------------------------------------------------------------------- hooks

def _sonnet_call(cost=None, in_tok=1_000_000, out_tok=100_000):
    usage = {"prompt_tokens": in_tok, "completion_tokens": out_tok}
    if cost is not None:
        usage["cost"] = cost
    return {"session_id": "s1", "model": "claude-sonnet-4-5",
            "response_model": "claude-sonnet-4-5", "provider": "anthropic",
            "usage": usage}


def test_hook_accounting_estimate_and_provider_cost():
    fresh_env()
    hooks.post_api_request(**_sonnet_call())
    hooks.post_api_request(**_sonnet_call(cost=0.5))
    led = Ledger(Path(os.environ["SPENDGUARD_DATA_DIR"]) / "spendguard.db")
    from spendguard.ledger import day_bounds
    t = led.totals(*day_bounds())
    # estimate: 1M in @ $3 + 100k out @ $15 = $4.50; plus provider-reported $0.50
    assert t["calls"] == 2 and abs(t["spent"] - 5.0) < 1e-6
    led.close()


def test_hook_block_and_escape_tools():
    d = fresh_env()
    save_config(d / "spendguard.config.json", {"daily_budget_usd": 1.0, "enforcement": "hard"})
    hooks.post_api_request(**_sonnet_call())  # $4.50 → over the $1 cap
    out = hooks.pre_llm_call(session_id="s1", user_message="hello")
    assert out and out["action"] == "block" and "SpendGuard" in out["message"]
    # mid-turn: other tools blocked, own read-only tools allowed
    assert hooks.pre_tool_call(tool_name="terminal", args={})["action"] == "block"
    assert hooks.pre_tool_call(tool_name="spendguard_status", args={}) is None


def test_hook_warn_mode_never_blocks():
    d = fresh_env()
    save_config(d / "spendguard.config.json",
                {"daily_budget_usd": 1.0, "enforcement": "warn"})
    hooks.post_api_request(**_sonnet_call())
    assert hooks.pre_llm_call(session_id="s1", user_message="hi") is None
    assert hooks.pre_tool_call(tool_name="terminal", args={}) is None


def test_hook_warning_context_at_threshold():
    d = fresh_env()
    save_config(d / "spendguard.config.json",
                {"daily_budget_usd": 5.0, "warn_at_percent": [75, 90]})
    hooks.post_api_request(**_sonnet_call())  # $4.50 = 90%
    out = hooks.pre_llm_call(session_id="s1", user_message="hi")
    assert out and "context" in out and "90%" in out["context"]


def test_auxiliary_counted():
    fresh_env()
    hooks.post_auxiliary_call(**_sonnet_call(in_tok=10_000, out_tok=1_000))
    led = Ledger(Path(os.environ["SPENDGUARD_DATA_DIR"]) / "spendguard.db")
    assert led.recent(1)[0]["kind"] == "aux"
    led.close()


# --------------------------------------------------------------------- tools

def test_tools_json():
    d = fresh_env()
    save_config(d / "spendguard.config.json", {"daily_budget_usd": 10.0})
    hooks.post_api_request(**_sonnet_call())
    st = json.loads(tools.spendguard_status({}))
    assert st["ok"] and st["status"]["day"]["spent"] == 4.5
    rep = json.loads(tools.spendguard_report({"period": "month"}))
    assert rep["ok"] and "claude-sonnet-4-5" in rep["text"]


# ------------------------------------------------------------------ commands

def test_command_sets_budget_for_humans():
    d = fresh_env()
    out = commands.spendguard_command("set daily 7")
    assert "Daily budget set" in out
    cfg = load_config(d / "spendguard.config.json")
    assert cfg["daily_budget_usd"] == 7.0
    out = commands.spendguard_command("set enforce warn")
    assert "warn" in out
    out = commands.spendguard_command("price my-model 1 2")
    assert "Price set" in out
    cfg = load_config(d / "spendguard.config.json")
    assert cfg["prices"]["my-model"] == [1.0, 2.0]
    out = commands.spendguard_command("off daily")
    assert "removed" in out
    assert load_config(d / "spendguard.config.json")["daily_budget_usd"] is None
    assert "SpendGuard commands" in commands.spendguard_command("bogus")


# ------------------------------------------------------------------ register

class StubCtx:
    def __init__(self):
        self.tools, self.hooks, self.commands, self.skills = [], [], [], []

    def register_tool(self, **kw): self.tools.append(kw)
    def register_hook(self, name, fn): self.hooks.append(name)
    def register_command(self, name, fn, description=""): self.commands.append(name)
    def register_skill(self, name, path): self.skills.append(name)


def test_register_wires_everything():
    spec = importlib.util.spec_from_file_location(
        "spendguard_plugin", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ctx = StubCtx()
    mod.register(ctx)
    assert [t["name"] for t in ctx.tools] == ["spendguard_status", "spendguard_report"]
    assert sorted(ctx.hooks) == ["post_api_request", "post_auxiliary_call",
                                 "pre_llm_call", "pre_tool_call"]
    assert ctx.commands == ["spendguard"]
    assert ctx.skills == ["hermes-spendguard"]


if __name__ == "__main__":
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
