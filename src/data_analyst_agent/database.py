from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: tuple[tuple, ...]
    elapsed_ms: float
    truncated: bool


class SqlPolicy:
    FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|attach|detach|pragma|vacuum|replace|create)\b", re.I)
    TABLE = re.compile(r"\b(?:from|join)\s+([a-z_][a-z0-9_]*)", re.I)

    def __init__(self, allowed_tables: set[str], max_rows: int = 100) -> None:
        self.allowed_tables = allowed_tables
        self.max_rows = max_rows

    def validate(self, sql: str) -> str:
        normalized = sql.strip().rstrip(";")
        if not re.match(r"^select\b", normalized, re.I):
            raise PermissionError("only SELECT queries are allowed")
        if self.FORBIDDEN.search(normalized) or "--" in normalized or "/*" in normalized:
            raise PermissionError("unsafe SQL token")
        tables = {name.lower() for name in self.TABLE.findall(normalized)}
        if not tables or not tables <= self.allowed_tables:
            raise PermissionError(f"table is not allowed: {sorted(tables - self.allowed_tables)}")
        if not re.search(r"\blimit\s+\d+\b", normalized, re.I):
            normalized += f" LIMIT {self.max_rows + 1}"
        return normalized


class ReadOnlyDatabase:
    def __init__(self, path: str, policy: SqlPolicy) -> None:
        self.path = path
        self.policy = policy

    def schema(self) -> dict[str, list[str]]:
        with sqlite3.connect(f"file:{self.path}?mode=ro", uri=True) as db:
            output = {}
            for table in sorted(self.policy.allowed_tables):
                output[table] = [row[1] for row in db.execute(f"PRAGMA table_info({table})")]
            return output

    def query(self, sql: str) -> QueryResult:
        safe_sql = self.policy.validate(sql)
        started = time.perf_counter_ns()
        with sqlite3.connect(f"file:{self.path}?mode=ro", uri=True) as db:
            db.set_progress_handler(lambda: 1 if (time.perf_counter_ns() - started) > 2_000_000_000 else 0, 1000)
            cursor = db.execute(safe_sql)
            rows = cursor.fetchmany(self.policy.max_rows + 1)
            columns = tuple(item[0] for item in cursor.description)
        truncated = len(rows) > self.policy.max_rows
        return QueryResult(columns, tuple(rows[:self.policy.max_rows]), (time.perf_counter_ns() - started) / 1_000_000, truncated)
