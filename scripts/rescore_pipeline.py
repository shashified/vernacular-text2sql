"""
Re-build the pipeline's SQL from its SAVED plans and re-score it -- no model calls.

Use after a fix to the deterministic SQL synthesis step (src/generation/sql_synth.py):
the model's plans don't change, only how they are turned into SQL, so we can
update every saved pipeline result for free.

    python scripts/rescore_pipeline.py            # all results/agri_*.jsonl files
"""
from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.benchmark.agri import DB_PATH, load_questions
from src.eval.executor import execution_accuracy
from src.generation.sql_synth import plan_to_sql

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def main() -> None:
    gold = {q["id"]: q["gold_sql"] for q in load_questions()}
    for path in glob.glob(os.path.join(ROOT, "results", "agri_*.jsonl")):
        rows = [json.loads(l) for l in open(path, encoding="utf-8")]
        changed = 0
        for r in rows:
            if r["method"] != "pipeline" or not r.get("plan"):
                continue
            sql = plan_to_sql(r["plan"])
            if sql == r.get("sql"):
                continue
            ex = execution_accuracy(DB_PATH, sql, gold[r["id"]])
            print(f"{r['id']} {r['lang']:8s} ex {r['ex']} -> {ex['ex']}  ({ex['reason'][:50]})")
            r.update(sql=sql, ex=ex["ex"], reason=ex["reason"])
            changed += 1
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{os.path.relpath(path, ROOT)}: {changed} pipeline answers re-built")
    print("Re-run  python scripts/run_eval.py  to refresh the summary table.")


if __name__ == "__main__":
    main()
