"""QA-00 shared integration harness (same commands locally and in CI).

Run with the backend's Python environment (it needs SQLAlchemy, psycopg and Alembic):

  python scripts/integration_harness.py fresh-db ENV_VAR [ENV_VAR ...]
      For each named env var (e.g. DATABASE_URL TEST_DATABASE_URL): drop and recreate that
      database, then `alembic upgrade head`, so every run starts from the migrated seed state.
      Refuses, before connecting anywhere, unless every name is plain (a-z, 0-9, _) and ends in "_test".

  python scripts/integration_harness.py roundtrip
      On the database in ROUNDTRIP_DATABASE_URL: upgrade head -> downgrade base -> upgrade head,
      checking the schema is empty before, empty after the downgrade, and at head at the end.
      Refuses unless the name is plain and ends in "_roundtrip" (a dedicated throwaway server:
      the 0007 downgrade drops cluster-wide roles), and refuses a database that already has tables.

Passwords are never printed (URLs are rendered with the password hidden).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.engine import URL, make_url

BACKEND_DIR = Path(__file__).resolve().parents[1] / "apps" / "backend"


def _url(env_name: str) -> URL:
    raw = os.environ.get(env_name)
    if not raw:
        sys.exit(f"{env_name} is not set")
    return make_url(raw)


def _safe(url: URL) -> str:
    return url.render_as_string(hide_password=True)


def _require_disposable(env_name: str, url: URL, suffix: str) -> None:
    """Hard guard, checked before any connection: only plain names ending in `suffix` are touched.

    This is what keeps the harness away from development or shared databases such as `sawakli`,
    whatever host or port they are on. The strict character set also keeps the name safe to quote
    into DROP/CREATE DATABASE.
    """
    name = url.database or ""
    if not re.fullmatch(rf"[a-z0-9_]+{suffix}", name):
        sys.exit(
            f"refusing: {env_name} database {name!r} is not disposable; it must contain only "
            f"a-z, 0-9 and '_' and end in '{suffix}' ({_safe(url)})"
        )


def _alembic(url: URL, *args: str) -> str:
    env = {**os.environ, "DATABASE_URL": url.render_as_string(hide_password=False)}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    print(f"$ alembic {' '.join(args)}  [{_safe(url)}] -> exit {result.returncode}")
    if result.returncode != 0:
        sys.exit(f"alembic {' '.join(args)} failed:\n{result.stdout}{result.stderr}")
    return result.stdout


def _table_count(url: URL) -> int:
    engine = sa.create_engine(url)
    try:
        with engine.connect() as conn:
            return int(
                conn.execute(
                    sa.text(
                        "SELECT count(*) FROM pg_tables WHERE schemaname = 'public' "
                        "AND tablename <> 'alembic_version'"
                    )
                ).scalar_one()
            )
    finally:
        engine.dispose()


def fresh_db(env_names: list[str]) -> None:
    if not env_names:
        sys.exit("usage: integration_harness.py fresh-db ENV_VAR [ENV_VAR ...]")
    urls = [(name, _url(name)) for name in env_names]
    for name, url in urls:
        _require_disposable(name, url, "_test")
    for name, url in urls:
        admin = sa.create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
        try:
            with admin.connect() as conn:
                conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
                conn.execute(sa.text(f'CREATE DATABASE "{url.database}"'))
        finally:
            admin.dispose()
        _alembic(url, "upgrade", "head")
        print(f"PASS fresh-db {name}: {_safe(url)} recreated and migrated to head")


def roundtrip() -> None:
    url = _url("ROUNDTRIP_DATABASE_URL")
    # The 0007 downgrade drops cluster-wide roles, so the name must mark a dedicated throwaway server.
    _require_disposable("ROUNDTRIP_DATABASE_URL", url, "_roundtrip")
    if (before := _table_count(url)) != 0:
        sys.exit(
            f"refusing: {_safe(url)} already has {before} table(s); round-trip needs a fresh DB"
        )
    _alembic(url, "upgrade", "head")
    at_head = _table_count(url)
    _alembic(url, "downgrade", "base")
    after_down = _table_count(url)
    if after_down != 0:
        sys.exit(f"FAIL roundtrip: {after_down} table(s) left after downgrade base")
    _alembic(url, "upgrade", "head")
    again = _table_count(url)
    current = _alembic(url, "current")
    heads = _alembic(url, "heads")
    head_ids = {line.split()[0] for line in heads.splitlines() if line.strip()}
    if at_head == 0 or again != at_head or not head_ids or not all(h in current for h in head_ids):
        sys.exit(
            f"FAIL roundtrip: tables {at_head} -> {again}; current={current!r} heads={heads!r}"
        )
    print(
        f"PASS roundtrip: {at_head} tables at head, 0 after downgrade base, {again} after re-upgrade"
    )


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "fresh-db":
        fresh_db(sys.argv[2:])
    elif sys.argv[1:] == ["roundtrip"]:
        roundtrip()
    else:
        sys.exit("usage: integration_harness.py {fresh-db ENV_VAR [ENV_VAR ...] | roundtrip}")
