"""Bring an existing crop database up to the final design (no full rebuild needed).
    python scripts/add_indexes.py
Opening the file read-write first also clears any unfinished journal left by an interrupted write."""
import os
import sqlite3

DB = os.path.join(os.path.dirname(__file__), "..", "data", "agri", "agri_india.db")
con = sqlite3.connect(DB)
print("integrity:", con.execute("PRAGMA integrity_check").fetchone()[0])
con.execute("CREATE INDEX IF NOT EXISTS idx_prod_crop_year ON crop_production(crop_id, year)")
con.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_prod_key ON crop_production(district_id, crop_id, season_id, year)")
con.execute("ANALYZE")
con.commit()
print("indexes:", [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")])
print("rows:", con.execute("SELECT COUNT(*) FROM crop_production").fetchone()[0])
con.close()
