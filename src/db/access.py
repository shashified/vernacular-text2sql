"""
Role-based access control for the crop database.

SQLite has no users or GRANT statements, so roles are enforced in two layers:
  1. the connection mode: read-only roles open the file with mode=ro, so the
     storage engine itself refuses every write;
  2. an authorizer callback (sqlite3.Connection.set_authorizer): SQLite asks it
     about every action while compiling a statement, and anything the role is
     not granted is denied before the statement can run.

Roles
  viewer  - SELECT on the six data tables only. Used for every model-generated
            query (demo, evaluation). Cannot write, change the schema, ATTACH
            another file or change PRAGMAs.
  loader  - what the ETL script needs: CREATE TABLE/INDEX and INSERT. Cannot
            DROP, DELETE or UPDATE, so a buggy load cannot destroy data.
"""
from __future__ import annotations

import sqlite3

DATA_TABLES = frozenset({"states", "districts", "crop_categories", "crops", "seasons", "crop_production"})
# SQLite reads its own catalog while compiling; allowing reads of it is harmless.
CATALOG = frozenset({"sqlite_master", "sqlite_schema", "sqlite_stat1"})

A = sqlite3
_READ = {A.SQLITE_SELECT, A.SQLITE_READ, A.SQLITE_FUNCTION}
_LOAD = {A.SQLITE_INSERT, A.SQLITE_CREATE_TABLE, A.SQLITE_CREATE_INDEX, A.SQLITE_TRANSACTION,
         A.SQLITE_ANALYZE}

ROLES = {
    "viewer": {"actions": _READ, "read_only": True},
    "loader": {"actions": _READ | _LOAD, "read_only": False},
}


class AccessDenied(sqlite3.DatabaseError):
    pass


def _authorizer(role: str):
    allowed = ROLES[role]["actions"]

    def check(action, arg1, arg2, dbname, source):
        if action not in allowed:
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_READ and arg1 not in DATA_TABLES | CATALOG:
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_INSERT and arg1 not in DATA_TABLES | CATALOG:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    return check


def connect(db_path: str, role: str = "viewer") -> sqlite3.Connection:
    """Open the database as `role`. Unknown roles are refused."""
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r}; roles: {sorted(ROLES)}")
    if ROLES[role]["read_only"]:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    else:
        con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")  # before the authorizer: PRAGMA is not granted to roles
    con.set_authorizer(_authorizer(role))
    return con
