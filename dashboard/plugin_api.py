"""SpendGuard dashboard backend — FastAPI router at /api/plugins/hermes-spendguard/.

Read-only: it serves the local ledger's view of spend vs budgets. Opening
the tab never calls a model and never touches a provider.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

_PLUGIN_ROOT = Path(__file__).parent.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from spendguard import config as cfg_mod  # noqa: E402
from spendguard import guard as guard_mod  # noqa: E402
from spendguard.ledger import Ledger, day_bounds, month_bounds  # noqa: E402
from spendguard.paths import config_path, db_path  # noqa: E402


@router.get("/status")
def status():
    cfg = cfg_mod.load_config(config_path())
    ledger = Ledger(db_path())
    try:
        st = guard_mod.evaluate(cfg, ledger)
        now = datetime.now().astimezone()
        d0, d1 = day_bounds(now)
        m0, m1 = month_bounds(now)
        return JSONResponse({
            "ok": True,
            "status": st,
            "day_by_model": ledger.by_model(d0, d1),
            "month_by_model": ledger.by_model(m0, m1),
            "recent": ledger.recent(12),
        })
    finally:
        ledger.close()
