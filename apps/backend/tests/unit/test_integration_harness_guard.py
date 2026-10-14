"""QA-00: the integration harness refuses any database that is not explicitly disposable.

The harness drops and recreates databases (`fresh-db`) and downgrades schemas (`roundtrip`), so it
must never reach a development or shared database. These tests make every connection and every
`alembic` call fail, then prove the guard refuses before either happens.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "integration_harness.py"


def _load_harness(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    spec = importlib.util.spec_from_file_location("integration_harness", _SCRIPT)
    assert spec is not None and spec.loader is not None
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)

    def no_connection(*args: object, **kwargs: object) -> None:
        raise AssertionError("guard let the harness connect to a database")

    def no_alembic(*args: object, **kwargs: object) -> None:
        raise AssertionError("guard let the harness run alembic")

    monkeypatch.setattr(harness.sa, "create_engine", no_connection)
    monkeypatch.setattr(harness.subprocess, "run", no_alembic)
    return harness


@pytest.mark.parametrize(
    "database_url",
    [
        # Main Compose database and a developer database on another port (e.g. from .env).
        "postgresql+psycopg://postgres:synthetic@localhost:5432/sawakli",
        "postgresql+psycopg://postgres:synthetic@localhost:5433/sawakli",
        # Names that merely contain "test" or use another case.
        "postgresql+psycopg://postgres:synthetic@localhost:5434/sawakli_test_backup",
        "postgresql+psycopg://postgres:synthetic@localhost:5434/SAWAKLI_TEST",
        # A quote would break out of the quoted identifier in DROP DATABASE.
        'postgresql+psycopg://postgres:synthetic@localhost:5434/x"; DROP DATABASE sawakli; --_test',
        # No database name at all.
        "postgresql+psycopg://postgres:synthetic@localhost:5434",
    ],
)
def test_fresh_db_refuses_non_test_database(
    monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    harness = _load_harness(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", database_url)

    with pytest.raises(SystemExit) as refused:
        harness.fresh_db(["DATABASE_URL"])

    assert "refusing" in str(refused.value)
    assert "synthetic" not in str(refused.value)  # password never echoed


def test_fresh_db_checks_every_name_before_touching_any(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = _load_harness(monkeypatch)
    monkeypatch.setenv(
        "TEST_DATABASE_URL", "postgresql+psycopg://postgres:synthetic@localhost:5434/ok_test"
    )
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://postgres:synthetic@localhost/sawakli")

    with pytest.raises(SystemExit, match="refusing: DATABASE_URL"):
        harness.fresh_db(["TEST_DATABASE_URL", "DATABASE_URL"])


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+psycopg://postgres:synthetic@localhost:5433/sawakli",
        "postgresql+psycopg://postgres:synthetic@localhost:5434/sawakli_test",
    ],
)
def test_roundtrip_refuses_non_roundtrip_database(
    monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    harness = _load_harness(monkeypatch)
    monkeypatch.setenv("ROUNDTRIP_DATABASE_URL", database_url)

    with pytest.raises(SystemExit, match="refusing: ROUNDTRIP_DATABASE_URL"):
        harness.roundtrip()


def test_guard_accepts_disposable_names(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = _load_harness(monkeypatch)
    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://postgres:synthetic@localhost:5434/sawakli_integration_test",
    )
    monkeypatch.setenv(
        "ROUNDTRIP_DATABASE_URL",
        "postgresql+psycopg://postgres:synthetic@localhost:5433/sawakli_roundtrip",
    )

    # Past the guard, the stubbed connection is the first thing reached.
    with pytest.raises(AssertionError, match="connect to a database"):
        harness.fresh_db(["TEST_DATABASE_URL"])
    with pytest.raises(AssertionError, match="connect to a database"):
        harness.roundtrip()
