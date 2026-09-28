import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
import os
from dotenv import load_dotenv

load_dotenv()

# Import all models so Alembic can detect them
from app.core.database import Base  # noqa: E402
import app.models  # noqa: E402, F401  — registers all ORM models

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    # Offline mode uses the synchronous psycopg2 URL (no live DB connection).
    url = os.getenv("DATABASE_URL_SYNC") or config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    # Online mode uses the async asyncpg URL.
    async_url = os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    # Ensure the URL uses an async driver scheme.
    if async_url and async_url.startswith("postgresql+psycopg2"):
        async_url = async_url.replace("postgresql+psycopg2", "postgresql+asyncpg", 1)
    elif async_url and async_url.startswith("postgresql://"):
        async_url = async_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Build a minimal config section with the corrected async URL.
    section = dict(config.get_section(config.config_ini_section, {}))
    section["sqlalchemy.url"] = async_url

    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
