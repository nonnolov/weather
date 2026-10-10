"""Opt-in PostgreSQL 16 verification; only a fresh, disposable local schema.

Set P003_TEST_POSTGRES_URL in the parent process, then run this file with
pytest -v -s. No target is read from dotenv or saved in this repository.
"""
import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_engine_from_config,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from tests import test_rain_delivery_evidence as evidence_tests


pytestmark = pytest.mark.skipif(
    not os.environ.get("P003_TEST_POSTGRES_URL"),
    reason="Set P003_TEST_POSTGRES_URL explicitly to opt into local PostgreSQL tests",
)
ROOT = Path(__file__).resolve().parents[1]


def _local_urls():
    raw = os.environ.get("P003_TEST_POSTGRES_URL")
    if not raw:
        pytest.skip("P003_TEST_POSTGRES_URL is absent")
    try:
        url = sa.engine.make_url(raw)
    except (ValueError, sa.exc.ArgumentError):
        pytest.fail("P003_TEST_POSTGRES_URL must be a valid PostgreSQL URL", pytrace=False)
    if url.drivername not in {"postgresql", "postgresql+psycopg2", "postgresql+asyncpg"}:
        pytest.fail("Only PostgreSQL URLs are permitted", pytrace=False)
    if url.host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("Only localhost/127.0.0.1/::1 targets are permitted", pytrace=False)
    # Query parameters can override the host or search_path in a driver.
    if url.query:
        pytest.fail("URL query parameters are forbidden for isolation", pytrace=False)
    if not url.database:
        pytest.fail("An explicit local database is required", pytrace=False)
    return (url.set(drivername="postgresql+psycopg2"),
            url.set(drivername="postgresql+asyncpg"))


def _assert_search_path(connection, schema):
    assert connection.exec_driver_sql("SHOW search_path").scalar_one() == schema
    assert connection.exec_driver_sql("SELECT current_schemas(false)").scalar_one() == [schema]


@pytest.fixture
def pg_schema(monkeypatch):
    sync_url, async_url = _local_urls()
    schema = f"weather_p003_test_{uuid4().hex}"
    monkeypatch.setenv("DATABASE_URL", async_url.render_as_string(hide_password=False))
    monkeypatch.setenv("DATABASE_URL_SYNC", sync_url.render_as_string(hide_password=False))
    engine = sa.create_engine(
        sync_url, poolclass=NullPool,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    config.set_main_option(
        "sqlalchemy.url", async_url.render_as_string(hide_password=False).replace("%", "%%"),
    )

    def migrate(revision, *, downgrade=False):
        engines = []

        def isolated_factory(*args, **kwargs):
            kwargs["connect_args"] = {"server_settings": {"search_path": schema}}
            kwargs["poolclass"] = NullPool
            migration_engine = async_engine_from_config(*args, **kwargs)
            engines.append(migration_engine)
            return migration_engine

        try:
            # env.py imports this symbol; do not patch production code or settings.
            with patch("dotenv.load_dotenv", return_value=False), patch(
                "sqlalchemy.ext.asyncio.async_engine_from_config", isolated_factory,
            ):
                (command.downgrade if downgrade else command.upgrade)(config, revision)
        finally:
            # NullPool avoids connections surviving Alembic's asyncio.run loop.
            for migration_engine in engines:
                asyncio.run(migration_engine.dispose())
        with engine.connect() as connection:
            _assert_search_path(connection, schema)
            assert connection.exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).scalar_one() == revision

    created = False
    try:
        with engine.begin() as connection:
            version_number = int(connection.exec_driver_sql("SHOW server_version_num").scalar_one())
            version = connection.exec_driver_sql("SHOW server_version").scalar_one()
            assert 160000 <= version_number < 170000, "PostgreSQL 16 is required"
            print(f"P0-03 PostgreSQL server_version={version}; isolated schema={schema}")
            connection.execute(sa.schema.CreateSchema(schema))
        created = True
        with engine.connect() as connection:
            _assert_search_path(connection, schema)
        yield engine, async_url, schema, migrate
    finally:
        engine.dispose()
        try:
            if created:
                # Only the exact schema successfully created above is eligible.
                with engine.begin() as connection:
                    connection.execute(sa.schema.DropSchema(schema, cascade=True))
        finally:
            engine.dispose()


def _tables(connection):
    metadata = sa.MetaData()
    metadata.reflect(connection)
    return metadata.tables


def test_revision_0006_preserves_history_and_constraints(pg_schema):
    engine, _, _, migrate = pg_schema
    now = datetime(2026, 10, 10, tzinfo=timezone.utc)
    migrate("0005")
    with engine.begin() as connection:
        tables = _tables(connection)
        connection.execute(tables["locations"].insert().values(
            id=1, name="Migration Area", slug="migration", latitude=13, longitude=100,
            created_at=now, updated_at=now,
        ))
        connection.execute(tables["forecast_runs"].insert().values(
            id=1, location_id=1, provider="mock", retrieved_at=now, forecast_days=7,
        ))
        connection.execute(tables["notification_deliveries"].insert().values(
            id=1, location_id=1, channel="line", recipient_id="U_LEGACY",
            dedupe_key="legacy", created_at=now,
        ))
    migrate("0006")
    evidence = {"source": {"forecast_run_id": 1}, "message_text": "frozen mock message",
                "selected_periods": [], "daily_aggregate": None}
    with engine.begin() as connection:
        tables = _tables(connection)
        delivery = tables["notification_deliveries"]
        assert delivery.c.forecast_run_id.nullable and delivery.c.rain_evidence.nullable
        legacy = connection.execute(sa.select(delivery)).mappings().one()
        assert legacy["forecast_run_id"] is None and legacy["rain_evidence"] is None
        assert legacy["dedupe_key"] == "legacy"
        values = dict(location_id=1, channel="line", recipient_id="U_MOCK",
                      dedupe_key="rain:1:2026-10-10", created_at=now,
                      forecast_run_id=1, rain_evidence=evidence)
        connection.execute(delivery.insert().values(id=2, **values))
        assert connection.execute(sa.select(delivery.c.rain_evidence).where(
            delivery.c.id == 2,
        )).scalar_one() == evidence
        for invalid, code, constraint in [
            ({**values, "id": 3, "dedupe_key": "invalid", "forecast_run_id": 999},
             "23503", "fk_notification_forecast_run"),
            ({**values, "id": 4}, "23505", "uq_notification_dedupe"),
        ]:
            # PostgreSQL errors abort a transaction unless isolated by SAVEPOINT.
            with pytest.raises(sa.exc.IntegrityError) as error:
                with connection.begin_nested():
                    connection.execute(delivery.insert().values(**invalid))
            assert error.value.orig.pgcode == code
            assert error.value.orig.diag.constraint_name == constraint
        connection.execute(tables["forecast_runs"].delete().where(
            tables["forecast_runs"].c.id == 1,
        ))
        sent = connection.execute(sa.select(delivery).where(delivery.c.id == 2)).mappings().one()
        assert sent["forecast_run_id"] is None and sent["rain_evidence"] == evidence
        assert connection.execute(sa.select(sa.func.count()).select_from(delivery)).scalar_one() == 2
    migrate("0005", downgrade=True)
    with engine.connect() as connection:
        delivery = _tables(connection)["notification_deliveries"]
        assert "rain_evidence" not in delivery.c and "forecast_run_id" not in delivery.c
        assert connection.execute(sa.select(delivery.c.dedupe_key).order_by(
            delivery.c.id,
        )).scalars().all() == ["legacy", "rain:1:2026-10-10"]
    migrate("0006")
    with engine.connect() as connection:
        delivery = _tables(connection)["notification_deliveries"]
        assert connection.execute(sa.select(
            delivery.c.forecast_run_id, delivery.c.rain_evidence,
        ).order_by(delivery.c.id)).all() == [(None, None), (None, None)]


@pytest.fixture
def pg_ready(pg_schema):
    pg_schema[3]("0006")
    return pg_schema


@pytest_asyncio.fixture
async def db_session(pg_ready):
    """Override SQLite only for this module; roll back every behavioral case."""
    _, url, schema, _ = pg_ready
    engine = create_async_engine(
        url, poolclass=NullPool,
        connect_args={"server_settings": {"search_path": schema}},
    )
    try:
        async with engine.connect() as connection:
            async with connection.begin() as transaction:
                await connection.run_sync(lambda sync: _assert_search_path(sync, schema))
                async with AsyncSession(
                    bind=connection, expire_on_commit=False, autoflush=False,
                    join_transaction_mode="create_savepoint",
                ) as session:
                    try:
                        yield session
                    finally:
                        await session.rollback()
                        await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("probability,mode", [
    (80, "strong_rain"), (35, "daily_peak"), (20, "below_threshold_daily_summary"),
])
async def test_three_modes_dedupe_and_frozen_source_on_postgres(db_session, probability, mode):
    # Reuse the complete regression, including mocked LINE and source mutation.
    await evidence_tests.test_exact_formatted_run_survives_source_and_latest_changes(
        db_session, probability, mode,
    )
