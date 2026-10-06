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
    # Join whichever side is not in the query yet, in an order where each join
    # connects to a table already present. Models often write a join
    # "backwards" (right side = the table already in FROM); emitting that
    # literally gives "FROM t JOIN t" and an ambiguous-column error.
    joined = {from_clause}
    pending = list(plan.get("joins", []))
    while pending:
        for j in pending:
            lt, rt = j["left"].split(".")[0], j["right"].split(".")[0]
            if lt in joined or rt in joined:
                break
        else:  # no join touches the tables so far: keep the model's order
            j = pending[0]
            lt, rt = j["left"].split(".")[0], j["right"].split(".")[0]
        pending.remove(j)
        new_table = rt if rt not in joined else lt
        if new_table in joined:
            continue  # both sides already present: nothing to add
        joined.add(new_table)
        join_clauses.append(f"JOIN {new_table} ON {j['left']} = {j['right']}")

    where_clauses = []
    for f in plan.get("filters", []):
        v = f["value"]
        v_sql = "'" + v.replace("'", "''") + "'" if isinstance(v, str) else str(v)
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
    if plan.get("limit"):
        sql += f"\nLIMIT {int(plan['limit'])}"
    return sql + ";"
