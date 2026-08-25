"""Shared helper for Alembic migrations that run a raw multi-statement SQL
script (used by the migrations ported from DATA-01, see alembic/versions/).

Why this exists: SQLAlchemy's normal op.execute()/exec_driver_sql() pass an
empty parameter set to the DBAPI, which puts psycopg into "parameterized
query" mode — it then scans the whole string for %-placeholders and chokes
on innocuous things like a literal '%' inside a SQL comment or a quoted
string (e.g. 'reduce budget by 20%'). Grabbing the raw DBAPI cursor and
calling execute() with no parameters argument at all keeps psycopg in plain
"simple query" mode, so the script runs byte-for-byte as written — the same
way `psql -f file.sql` would run it.
"""

from __future__ import annotations

from alembic import op


def execute_sql_script(sql: str) -> None:
    """Run a raw, possibly multi-statement SQL script exactly as written."""
    bind = op.get_bind()
    driver_connection = bind.connection.driver_connection
    if driver_connection is None:
        raise RuntimeError("No active DBAPI connection to run migration SQL against.")
    driver_connection.cursor().execute(sql)
