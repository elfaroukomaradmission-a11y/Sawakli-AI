import os
from logging.config import fileConfig
from pathlib import Path

from dotenv import dotenv_values, load_dotenv
from sqlalchemy import create_engine, pool

from alembic import context

# Prefer the repo-root .env (next to docker-compose.yml). A nearer
# apps/backend/.env previously forced port 5432 and skipped Docker on 5433.
_env_file: Path | None = None
for parent in Path(__file__).resolve().parents:
    if (parent / "docker-compose.yml").is_file():
        candidate = parent / ".env"
        if candidate.is_file():
            _env_file = candidate
        break

if _env_file is None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.is_file():
            _env_file = candidate
            break

if _env_file is not None:
    load_dotenv(_env_file, override=True)

import sawakli.db.models  # noqa: E402, F401
from sawakli.db.session import Base  # noqa: E402

config = context.config

file_values = dotenv_values(_env_file) if _env_file is not None else {}
database_url = file_values.get("DATABASE_URL") or os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError(
        "DATABASE_URL is not set. Copy .env.example to .env at the repo root "
        "and point it at the Postgres instance you want Alembic to use."
    )
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(database_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
