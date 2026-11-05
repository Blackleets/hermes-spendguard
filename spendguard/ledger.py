"""The spend ledger — one SQLite row per provider API call.

Only accounting metadata is stored: timestamp, session, model, provider,
token counts and the dollar figure (plus where that figure came from).
No prompts, no replies, no message text — ever.
"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    session_id TEXT DEFAULT '',
    model TEXT DEFAULT '',
    provider TEXT DEFAULT '',
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_usd REAL,
    cost_source TEXT DEFAULT 'unpriced',
    kind TEXT DEFAULT 'main'
);
CREATE INDEX IF NOT EXISTS idx_calls_ts ON calls(ts);
"""


def day_bounds(now: datetime | None = None) -> tuple[float, float]:
    n = now or datetime.now().astimezone()
    start = n.replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    end_dt = start + timedelta(days=1)
    return start.timestamp(), end_dt.timestamp()


def month_bounds(now: datetime | None = None) -> tuple[float, float]:
    n = now or datetime.now().astimezone()
    start = n.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end_dt = start.replace(year=start.year + 1, month=1)
    else:
        end_dt = start.replace(month=start.month + 1)
    return start.timestamp(), end_dt.timestamp()


class Ledger:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def record(self, *, ts: float | None = None, session_id: str = "",
               model: str = "", provider: str = "", input_tokens: int = 0,
               output_tokens: int = 0, cost_usd: float | None = None,
               cost_source: str = "unpriced", kind: str = "main") -> None:
        self._conn.execute(
            "INSERT INTO calls (ts, session_id, model, provider, input_tokens,"
            " output_tokens, cost_usd, cost_source, kind)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ts if ts is not None else time.time(), session_id or "", model or "",
             provider or "", int(input_tokens or 0), int(output_tokens or 0),
             cost_usd, cost_source, kind or "main"),
        )
        self._conn.commit()

    def totals(self, start: float, end: float) -> dict:
        row = self._conn.execute(
            "SELECT COUNT(*) AS calls,"
            " COALESCE(SUM(cost_usd), 0) AS spent,"
            " COALESCE(SUM(input_tokens), 0) AS tin,"
            " COALESCE(SUM(output_tokens), 0) AS tout,"
            " SUM(CASE WHEN cost_usd IS NULL THEN 1 ELSE 0 END) AS unpriced"
            " FROM calls WHERE ts >= ? AND ts < ?",
            (start, end),
        ).fetchone()
        return {
            "calls": int(row["calls"]),
            "spent": float(row["spent"]),
            "input_tokens": int(row["tin"]),
            "output_tokens": int(row["tout"]),
            "unpriced": int(row["unpriced"] or 0),
        }

    def by_model(self, start: float, end: float, limit: int = 12) -> list[dict]:
        rows = self._conn.execute(
            "SELECT model, COUNT(*) AS calls, COALESCE(SUM(cost_usd), 0) AS spent,"
            " COALESCE(SUM(input_tokens), 0) AS tin,"
            " COALESCE(SUM(output_tokens), 0) AS tout,"
            " SUM(CASE WHEN cost_usd IS NULL THEN 1 ELSE 0 END) AS unpriced"
            " FROM calls WHERE ts >= ? AND ts < ?"
            " GROUP BY model ORDER BY spent DESC, calls DESC LIMIT ?",
            (start, end, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def recent(self, limit: int = 10) -> list[dict]:
        rows = self._conn.execute(
            "SELECT ts, session_id, model, provider, input_tokens, output_tokens,"
            " cost_usd, cost_source, kind FROM calls ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
