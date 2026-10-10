"""Real Alembic upgrade/downgrade against an explicitly isolated SQLite DB."""
from datetime import datetime
from unittest.mock import patch

from alembic import command
from alembic.config import Config
import pytest
import sqlalchemy as sa


def test_evidence_migration_preserves_legacy_rows_and_delivery_on_run_delete(tmp_path, monkeypatch):
    path = tmp_path / "migration.sqlite"
    url = f"sqlite+aiosqlite:///{path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("DATABASE_URL_SYNC", f"sqlite:///{path.as_posix()}")
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    engine = sa.create_engine(f"sqlite:///{path.as_posix()}")

    def migrate(target, downgrade=False):
        # Alembic env normally calls load_dotenv; never load it in this check.
        with patch("dotenv.load_dotenv", return_value=False):
            (command.downgrade if downgrade else command.upgrade)(config, target)

    def tables(connection):
        metadata = sa.MetaData()
        metadata.reflect(connection)
        return metadata.tables

    try:
        migrate("0005")
        with engine.begin() as conn:
            t = tables(conn)
            now = datetime(2026, 10, 10)
            conn.execute(t["locations"].insert().values(id=1, name="Migration Area", slug="migration",
                         latitude=13, longitude=100, created_at=now, updated_at=now))
            conn.execute(t["forecast_runs"].insert().values(id=1, location_id=1, provider="mock",
                         retrieved_at=now, forecast_days=7))
            conn.execute(t["notification_deliveries"].insert().values(id=1, location_id=1, channel="line",
                         recipient_id="U_LEGACY", dedupe_key="legacy", created_at=now))
        migrate("0006")
        with engine.begin() as conn:
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
            t = tables(conn)
            delivery = t["notification_deliveries"]
            legacy = conn.execute(sa.select(delivery)).mappings().one()
            assert legacy["forecast_run_id"] is None and legacy["rain_evidence"] is None
            assert legacy["dedupe_key"] == "legacy"
            evidence = {"source": {"forecast_run_id": 1}, "message_text": "frozen mock message"}
            conn.execute(delivery.insert().values(id=2, location_id=1, channel="line",
                         recipient_id="U_MOCK", dedupe_key="rain:1:2026-10-10", created_at=now,
                         forecast_run_id=1, rain_evidence=evidence))
            with pytest.raises(sa.exc.IntegrityError):
                conn.execute(delivery.insert().values(id=3, location_id=1, channel="line",
                             recipient_id="U_BAD", dedupe_key="invalid", created_at=now,
                             forecast_run_id=999))
            conn.execute(t["forecast_runs"].delete().where(t["forecast_runs"].c.id == 1))
            sent = conn.execute(sa.select(delivery).where(delivery.c.id == 2)).mappings().one()
            assert sent["forecast_run_id"] is None and sent["rain_evidence"] == evidence
            assert conn.execute(sa.select(sa.func.count()).select_from(delivery)).scalar_one() == 2
            assert conn.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        migrate("0005", downgrade=True)
        with engine.connect() as conn:
            t = tables(conn)
            delivery = t["notification_deliveries"]
            assert "rain_evidence" not in delivery.c and "forecast_run_id" not in delivery.c
            assert conn.execute(sa.select(delivery.c.dedupe_key).order_by(delivery.c.id)).scalars().all() == [
                "legacy", "rain:1:2026-10-10"]
        migrate("0006")
        with engine.connect() as conn:
            delivery = tables(conn)["notification_deliveries"]
            rows = conn.execute(sa.select(delivery.c.forecast_run_id, delivery.c.rain_evidence)).all()
            assert rows == [(None, None), (None, None)]  # Never infer provenance on re-upgrade.
    finally:
        engine.dispose()
