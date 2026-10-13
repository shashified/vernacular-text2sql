"""Index study: times the 40 reference queries on copies of the crop database with
different index sets (median of 7 runs each) and records the EXPLAIN QUERY PLAN.
    python scripts/index_study.py
"""
import os, tempfile
import json, sqlite3, shutil, statistics, time, re, sys
REPO = os.path.join(os.path.dirname(__file__), "..")
Q = json.load(open(f"{REPO}/data/agri/questions.json"))
configs = {
  "none": [],
  "current": ["CREATE INDEX idx_prod_year ON crop_production(year)",
              "CREATE INDEX idx_prod_crop ON crop_production(crop_id)",
              "CREATE INDEX idx_prod_dist ON crop_production(district_id)"],
  "composite": ["CREATE INDEX idx_prod_year ON crop_production(year)",
                "CREATE INDEX idx_prod_crop ON crop_production(crop_id)",
                "CREATE INDEX idx_prod_dist ON crop_production(district_id)",
                "CREATE INDEX idx_prod_crop_year ON crop_production(crop_id, year)"],
  "final": ["CREATE INDEX idx_prod_year ON crop_production(year)",
            "CREATE INDEX idx_prod_crop ON crop_production(crop_id)",
            "CREATE INDEX idx_prod_dist ON crop_production(district_id)",
            "CREATE INDEX idx_prod_crop_year ON crop_production(crop_id, year)",
            "CREATE UNIQUE INDEX uq_prod_key ON crop_production(district_id, crop_id, season_id, year)"],
}
res = {}
for name, ddl in configs.items():
    path = os.path.join(tempfile.gettempdir(), f"agri_{name}.db")
    shutil.copy(f"{REPO}/data/agri/agri_india.db", path)
    c = sqlite3.connect(path)
    for (n,) in c.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%' OR name LIKE 'uq_%'").fetchall():
        c.execute(f"DROP INDEX {n}")
    for d in ddl: c.execute(d)
    c.execute("ANALYZE"); c.commit(); c.execute("VACUUM")
    size = sum(1 for _ in [0])
    per = {}
    scans = 0
    for q in Q:
        sql = q["gold_sql"]
        plan = " | ".join(r[3] for r in c.execute("EXPLAIN QUERY PLAN " + sql))
        full = bool(re.search(r"SCAN (crop_production|p)\b(?! USING)", plan))
        scans += full
        c.execute(sql).fetchall()  # warm
        ts = []
        for _ in range(7):
            t = time.perf_counter(); c.execute(sql).fetchall(); ts.append((time.perf_counter() - t) * 1000)
        per[q["id"]] = {"ms": statistics.median(ts), "cat": q["category"], "full_scan": full, "plan": plan}
    c.close()
    import os
    res[name] = {"per": per, "full_scans": scans, "size_mb": os.path.getsize(path) / 1e6,
                 "total_ms": sum(v["ms"] for v in per.values()),
                 "median_ms": statistics.median(v["ms"] for v in per.values())}
    print(name, round(res[name]["total_ms"], 1), "ms total;", round(res[name]["median_ms"], 2), "median;", scans, "full scans of crop_production;", round(res[name]["size_mb"], 1), "MB")
json.dump(res, open(os.path.join(REPO, "results", "index_study.json"), "w"), indent=1)
# per-category
for name in res:
    cats = {}
    for v in res[name]["per"].values(): cats.setdefault(v["cat"], []).append(v["ms"])
    print(name, {k: round(statistics.median(v), 2) for k, v in cats.items()})
