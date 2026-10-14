"""Alembic environment: schema comes from app.models, URL from app settings (DATABASE_URL)."""
from __future__ import annotations

import app  # pyright: ignore[reportMissingImports,reportUnusedImport]  # noqa: F401  (sets the SQLAlchemy pure-Python flag before SQLAlchemy is imported)
from alembic import context
from sqlalchemy import engine_from_config, pool

import app.models  # pyright: ignore[reportMissingImports,reportUnusedImport]  # noqa: F401  (registers every table)
from app.core.config import get_settings  # pyright: ignore[reportMissingImports]
from app.db.base import Base  # pyright: ignore[reportMissingImports]

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))
target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    # SQLite FTS5 shadow tables are managed by migration 0003, not by the ORM.
    return not (type_ == "table" and name and name.startswith("legal_chunks_fts"))


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, include_object=include_object, literal_binds=True,
                      render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, include_object=include_object,
                          render_as_batch=connection.dialect.name == "sqlite")  # SQLite needs batch mode for ALTERs
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
