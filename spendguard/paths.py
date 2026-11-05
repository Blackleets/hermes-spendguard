"""Where SpendGuard keeps its state.

Everything lives in the per-plugin data dir (survives `hermes plugins
update`): a SQLite ledger + a small config file. Tests and power users can
point SPENDGUARD_DATA_DIR somewhere else.
"""

from __future__ import annotations

import os
from pathlib import Path

PLUGIN_NAME = "hermes-spendguard"


def data_dir() -> Path:
    env = os.environ.get("SPENDGUARD_DATA_DIR")
    if env:
        p = Path(env).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return p
    try:
        from plugins.plugin_storage import plugin_data_dir
        return Path(plugin_data_dir(PLUGIN_NAME))
    except Exception:
        fallback = Path.home() / ".hermes" / "plugin-data" / PLUGIN_NAME
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def db_path() -> Path:
    return data_dir() / "spendguard.db"


def config_path() -> Path:
    return data_dir() / "spendguard.config.json"
