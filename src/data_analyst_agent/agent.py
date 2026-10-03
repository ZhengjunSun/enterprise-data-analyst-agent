from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from typing import Protocol

from .database import QueryResult, ReadOnlyDatabase


class Planner(Protocol):
    def plan(self, question: str, schema: dict[str, list[str]]) -> str: ...


class RulePlanner:
    """Offline demonstration planner; replaceable with a governed LLM adapter."""

    def plan(self, question: str, schema: dict[str, list[str]]) -> str:
        lowered = question.lower()
        if "average" in lowered or "平均" in question:
            return "SELECT crude, ROUND(AVG(cost), 2) AS average_cost FROM purchases GROUP BY crude ORDER BY average_cost"
        if "monthly" in lowered or "每月" in question:
            return "SELECT month, SUM(volume) AS total_volume FROM purchases GROUP BY month ORDER BY month"
        return "SELECT month, crude, volume, cost FROM purchases ORDER BY month, crude"


@dataclass(frozen=True)
class AnalysisResult:
    run_id: str
    question: str
    sql: str
    columns: tuple[str, ...]
    rows: tuple[tuple, ...]
    summary: str
    chart: dict | None
    audit: tuple[dict, ...]


class AnalystAgent:
    def __init__(self, database: ReadOnlyDatabase, planner: Planner) -> None:
        self.database = database
        self.planner = planner

    def answer(self, question: str) -> AnalysisResult:
        run_id = uuid.uuid4().hex
        audit: list[dict] = [{"event": "question_received", "run_id": run_id}]
        schema = self.database.schema()
        sql = self.planner.plan(question, schema)
        audit.append({"event": "sql_planned", "sql": sql})
        result = self.database.query(sql)
        self._verify(result)
        audit.append({"event": "query_completed", "rows": len(result.rows), "elapsed_ms": round(result.elapsed_ms, 3), "truncated": result.truncated})
        chart = self._chart(result)
        summary = "No matching rows." if not result.rows else f"Returned {len(result.rows)} verified rows across {len(result.columns)} columns."
        return AnalysisResult(run_id, question, sql, result.columns, result.rows, summary, chart, tuple(audit))

    @staticmethod
    def _verify(result: QueryResult) -> None:
        for row in result.rows:
            for value in row:
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError("non-finite database result")

    @staticmethod
    def _chart(result: QueryResult) -> dict | None:
        if len(result.columns) != 2 or not result.rows:
            return None
        return {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "mark": "bar",
            "data": {"values": [dict(zip(result.columns, row)) for row in result.rows]},
            "encoding": {
                "x": {"field": result.columns[0], "type": "nominal"},
                "y": {"field": result.columns[1], "type": "quantitative"},
            },
        }
