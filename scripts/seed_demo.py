#!/usr/bin/env python3
"""Seed the SpendGuard ledger with clearly-fake demo calls.

For screenshots and demo videos ONLY — writes to the data dir selected by
SPENDGUARD_DATA_DIR (or the real plugin data dir if unset; point the env
var at a scratch dir for demos). The seeded rows use plausible models and
list-price estimates, spread across today and earlier this month.
"""

from __future__ import annotations

import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from spendguard import prices as prices_mod  # noqa: E402
from spendguard.ledger import Ledger  # noqa: E402
from spendguard.paths import db_path  # noqa: E402

MODELS = [
    ("claude-sonnet-4-5", "anthropic", 14),
    ("gpt-5", "openai", 9),
    ("gemini-2-5-flash", "google", 7),
    ("claude-haiku-4-5", "anthropic", 6),
    ("deepseek-chat", "deepseek", 4),
]


def main() -> None:
    rng = random.Random(20261105)
    ledger = Ledger(db_path())
    now = datetime.now().astimezone()
    made = 0
    for model, provider, weight in MODELS:
        for _ in range(weight * 3):
            days_ago = rng.choice([0, 0, 0, 1, 2, 4, 6])
            ts = (now - timedelta(days=days_ago, hours=rng.randint(0, 9),
                                  minutes=rng.randint(0, 59))).timestamp()
            in_tok = rng.randint(2_000, 60_000)
            out_tok = rng.randint(200, 6_000)
            cost, source = prices_mod.estimate(model, in_tok, out_tok)
            ledger.record(ts=ts, session_id="demo", model=model, provider=provider,
                          input_tokens=in_tok, output_tokens=out_tok,
                          cost_usd=cost, cost_source=source,
                          kind="main" if rng.random() > 0.15 else "aux")
            made += 1
    ledger.close()
    print(f"Seeded {made} demo calls into {db_path()}")


if __name__ == "__main__":
    main()
