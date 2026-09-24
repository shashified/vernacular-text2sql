"""
Final step of Stage 2: synthesize SQL from a *validated* plan.

Kept deliberately simple/explicit (not another LLM call) so that once the plan
passes validation, SQL generation is mechanical and can't reintroduce the
aggregation-omission failure mode.
"""
from __future__ import annotations


def plan_to_sql(plan: dict) -> str:
    select_parts = list(plan.get("group_by", []))
    for agg in plan.get("aggregations", []):
        select_parts.append(f"{agg['func']}({agg['column']}) AS {agg['as']}")
    if not select_parts:
        select_parts = ["*"]

    from_clause = plan["tables"][0]
    join_clauses = []
    for j in plan.get("joins", []):
        right_table = j["right"].split(".")[0]
        join_clauses.append(f"JOIN {right_table} ON {j['left']} = {j['right']}")

    where_clauses = []
    for f in plan.get("filters", []):
        v = f["value"]
        v_sql = f"'{v}'" if isinstance(v, str) else str(v)
        where_clauses.append(f"{f['column']} {f['op']} {v_sql}")

    sql = f"SELECT {', '.join(select_parts)}\nFROM {from_clause}"
    if join_clauses:
        sql += "\n" + "\n".join(join_clauses)
    if where_clauses:
        sql += "\nWHERE " + " AND ".join(where_clauses)
    if plan.get("group_by"):
        sql += "\nGROUP BY " + ", ".join(plan["group_by"])
    if plan.get("order_by"):
        sql += "\nORDER BY " + ", ".join(plan["order_by"])
    return sql + ";"
