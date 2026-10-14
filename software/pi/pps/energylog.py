"""Keeps a day-by-day energy history in SQLite so the Energy tab can show the last week."""

import sqlite3
import time
from pathlib import Path


class EnergyLog:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS days (
            day TEXT PRIMARY KEY, solar REAL, pedal REAL, regen REAL,
            used REAL, assist REAL, updated REAL)""")
        self.db.commit()

    def record(self, day: str, today: dict) -> None:
        """Store the Pico's running totals for `day` (they only ever grow during a day)."""
        vals = [float(today.get(k, 0.0)) for k in ("solar", "pedal", "regen", "used", "assist")]
        self.db.execute("""INSERT INTO days VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(day) DO UPDATE SET
              solar=max(solar,excluded.solar), pedal=max(pedal,excluded.pedal),
              regen=max(regen,excluded.regen), used=max(used,excluded.used),
              assist=max(assist,excluded.assist), updated=excluded.updated""",
                        [day, *vals, time.time()])
        self.db.commit()

    def last_days(self, n: int = 7) -> list[dict]:
        rows = self.db.execute(
            "SELECT day, solar, pedal, regen, used, assist FROM days ORDER BY day DESC LIMIT ?",
            (n,)).fetchall()
        keys = ("day", "solar", "pedal", "regen", "used", "assist")
        return [dict(zip(keys, r)) for r in reversed(rows)]
