"""
Stage 4: execution & evaluation.

Runs generated SQL against the real database and computes Execution Accuracy
(EX) per IndicDB's own definition: exact match of the result set (as sets of
rows, order-insensitive unless the question asks for ordering), against a
gold SQL query.
"""
from __future__ import annotations
import sqlite3
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    ok: bool
    rows: list[tuple] | None
    error: str | None = None


def run_sql(db_path: str, sql: str, timeout_s: float = 20.0) -> ExecutionResult:
    """Run a query read-only, aborting it after timeout_s seconds (e.g. a runaway cross join)."""
    import time
    deadline = time.monotonic() + timeout_s
    con = None
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        con.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 100_000)
        rows = con.execute(sql).fetchall()
        return ExecutionResult(ok=True, rows=rows)
    except Exception as e:
        msg = "query timed out" if "interrupted" in str(e).lower() else str(e)
        return ExecutionResult(ok=False, rows=None, error=msg)
    finally:
        if con is not None:
            con.close()


def execution_accuracy(db_path: str, predicted_sql: str, gold_sql: str, order_sensitive: bool = False) -> dict:
    """Returns a dict with the EX verdict plus both result sets, for debugging/reporting."""
    pred = run_sql(db_path, predicted_sql)
    gold = run_sql(db_path, gold_sql)

    if not gold.ok:
        raise RuntimeError(f"Gold SQL itself failed to execute: {gold.error}")
    if not pred.ok:
        return {"ex": 0, "reason": f"predicted SQL failed to execute: {pred.error}",
                "predicted_rows": None, "gold_rows": gold.rows}

    def norm(rows):
        rows = [tuple(round(v, 4) if isinstance(v, float) else v for v in r) for r in rows]
        return rows if order_sensitive else sorted(rows)

    match = norm(pred.rows) == norm(gold.rows)
    return {"ex": 1 if match else 0, "reason": "match" if match else "result sets differ",
            "predicted_rows": pred.rows, "gold_rows": gold.rows}
