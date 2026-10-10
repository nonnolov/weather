"""Real PostgreSQL migration and partial uniqueness protect pending scopes."""
from datetime import datetime, timezone
import pytest
import sqlalchemy as sa
from tests.test_rain_evidence_postgres import pg_schema


@pytest.fixture(autouse=True)
def preserve_existing_loggers():
    # Alembic fileConfig disables unrelated existing loggers by default.
    # A migration test in this process must not silence later caplog assertions.
    import logging
    previous = {logger: logger.disabled for logger in logging.Logger.manager.loggerDict.values()
                if isinstance(logger, logging.Logger)}
    yield
    for logger, disabled in previous.items():
        logger.disabled = disabled


def test_upgrade_adds_guard_without_altering_accepted_history(pg_schema):
    engine, _, _, migrate = pg_schema
    migrate("0006")
    now = datetime.now(timezone.utc)
    with engine.begin() as db:
        locations = sa.Table("locations", sa.MetaData(), autoload_with=db)
        deliveries = sa.Table("notification_deliveries", sa.MetaData(), autoload_with=db)
        db.execute(locations.insert().values(id=101, name="test", slug="guard-test",
                   latitude=0, longitude=0, created_at=now, updated_at=now))
        db.execute(deliveries.insert().values(id=1, location_id=101, channel="line",
                   recipient_id="U_LEGACY", dedupe_key="legacy", created_at=now,
                   rain_evidence={"message_text": "original frozen text"}))
        before = db.exec_driver_sql("SELECT count(*) FROM notification_deliveries").scalar_one()
        assert before == 1
    migrate("0007")
    with engine.connect() as db:
        assert db.exec_driver_sql("SELECT count(*) FROM notification_deliveries").scalar_one() == before
        assert db.exec_driver_sql("SELECT count(*) FROM intraday_send_attempts").scalar_one() == 0
        assert db.exec_driver_sql("SELECT rain_evidence FROM notification_deliveries WHERE id=1").scalar_one() == {"message_text": "original frozen text"}
    attempt = sa.Table("intraday_send_attempts", sa.MetaData(), autoload_with=engine)
    data = dict(recipient_id="U_TEST", location_id=101, event_id="a"*64, status="pending",
                evidence={"message_text":"mock"}, created_at=datetime.now(timezone.utc))
    with engine.begin() as db:
        db.execute(attempt.insert().values(**data))
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as db:
            db.execute(attempt.insert().values(**{**data, "event_id":"b"*64}))
    with engine.begin() as db:
        db.execute(attempt.update().values(status="accepted", delivery_id=1))
        db.execute(attempt.insert().values(**{**data, "event_id":"b"*64}))
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as db:
            db.execute(attempt.insert().values(**{**data, "status":"accepted"}))
