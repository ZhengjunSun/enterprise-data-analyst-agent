from __future__ import annotations

import json
import sqlite3
import tempfile
from dataclasses import asdict
from pathlib import Path

from .agent import AnalystAgent, RulePlanner
from .database import ReadOnlyDatabase, SqlPolicy


def build_demo_database(path: Path) -> None:
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE purchases(month TEXT, crude TEXT, volume REAL, cost REAL)")
        db.executemany("INSERT INTO purchases VALUES(?,?,?,?)", [
            ("2026-01", "Synthetic-A", 100.0, 61.5),
            ("2026-01", "Synthetic-B", 80.0, 64.0),
            ("2026-02", "Synthetic-A", 120.0, 60.5),
        ])


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "demo.db"
        build_demo_database(path)
        agent = AnalystAgent(ReadOnlyDatabase(str(path), SqlPolicy({"purchases"})), RulePlanner())
        print(json.dumps(asdict(agent.answer("Show average cost by crude")), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
