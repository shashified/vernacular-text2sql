# DBMS study: indexes, access control, integrity

## Index study (`python scripts/index_study.py`)
All 40 reference queries, timed on copies of the database (median of 7 runs, after ANALYZE and VACUUM).

| Index set | Full scans of crop_production | Median ms | Total ms | File MB |
|---|---|---|---|---|
| none | 33/40 | 22.62 | 894 | 10.5 |
| current | 0/40 | 2.60 | 342 | 20.9 |
| composite | 0/40 | 0.58 | 234 | 25.1 |
| final | 0/40 | 0.47 | 225 | 30.9 |

`none` = no secondary index; `current` = year, crop_id, district_id; `composite` adds (crop_id, year);
`final` (adopted in `scripts/build_agri_db.py`) also adds the UNIQUE natural key (district_id, crop_id, season_id, year).

## Access control (`src/db/access.py`, tests in `tests/test_access.py`)
- `viewer`: read-only connection + authorizer allowing SELECT on the six data tables only. Used for every generated query in the demo.
- `loader`: may INSERT and CREATE TABLE/INDEX, may not DROP, DELETE or UPDATE.
Nine attack statements are refused for the viewer; re-running every model query from the three evaluation runs under the viewer blocked none.

## Integrity
Tests confirm the DBMS rejects a bad foreign key, a duplicate crop name, a NULL year and a duplicate natural key.
