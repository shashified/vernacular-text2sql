import shutil
import sqlite3

import pytest

from src.benchmark.agri import DB_PATH
from src.db.access import connect

pytestmark = pytest.mark.skipif(not __import__("os").path.exists(DB_PATH), reason="crop database not built")

GOOD = ("SELECT s.state_name, SUM(p.production_quantity) FROM crop_production p "
        "JOIN districts d ON p.district_id = d.district_id JOIN states s ON d.state_id = s.state_id "
        "WHERE p.year = 2015 GROUP BY s.state_name")

ATTACKS = [
    "DROP TABLE crop_production",
    "DELETE FROM crops",
    "UPDATE crop_production SET production_quantity = 0",
    "INSERT INTO states(state_name) VALUES ('X')",
    "CREATE TABLE t(x)",
    "ALTER TABLE crops ADD COLUMN x",
    "ATTACH DATABASE ':memory:' AS other",
    "PRAGMA writable_schema = ON",
    "CREATE INDEX i ON crops(crop_name)",
]


def test_viewer_can_query():
    con = connect(DB_PATH, "viewer")
    assert len(con.execute(GOOD).fetchall()) > 10


@pytest.mark.parametrize("sql", ATTACKS)
def test_viewer_cannot_change_anything(sql):
    con = connect(DB_PATH, "viewer")
    with pytest.raises(sqlite3.DatabaseError):
        con.execute(sql)


@pytest.fixture
def copy(tmp_path):
    p = tmp_path / "copy.db"
    shutil.copy(DB_PATH, p)
    return str(p)


def test_loader_can_insert_but_not_destroy(copy):
    con = connect(copy, "loader")
    con.execute("INSERT INTO seasons(season_name) VALUES ('Test season')")
    for sql in ("DROP TABLE seasons", "DELETE FROM seasons", "UPDATE seasons SET season_name = 'x'"):
        with pytest.raises(sqlite3.DatabaseError):
            con.execute(sql)


@pytest.mark.parametrize("sql", [
    # foreign key: crop 99999 does not exist
    "INSERT INTO crop_production(district_id, crop_id, season_id, year) VALUES (1, 99999, 1, 2015)",
    # UNIQUE crop name
    "INSERT INTO crops(crop_name, category_id) VALUES ('Wheat', 1)",
    # NOT NULL year
    "INSERT INTO crop_production(district_id, crop_id, season_id, year) VALUES (1, 1, 1, NULL)",
])
def test_integrity_constraints_reject_bad_rows(copy, sql):
    con = connect(copy, "loader")
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(sql)


def test_unknown_role_refused():
    with pytest.raises(ValueError):
        connect(DB_PATH, "admin")


def test_duplicate_production_record_rejected(copy):
    con = connect(copy, "loader")
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'uq_prod_key'").fetchone():
        pytest.skip("database built before the natural-key index was added")
    d, c, s, y = con.execute("SELECT district_id, crop_id, season_id, year FROM crop_production LIMIT 1").fetchone()
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO crop_production(district_id, crop_id, season_id, year) VALUES (?,?,?,?)", (d, c, s, y))
