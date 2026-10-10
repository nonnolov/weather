"""Opt-in P2 report on the disposable PostgreSQL instance only."""
import os

import pytest
from sqlalchemy import func, select, text

from app.evaluation.audit import evaluate_location_audit
from app.models.observation import Observation
from tests.test_evaluation_audit import START, END, insert_fixture
from tests.test_rain_locking_postgres import pg_sessions

pytestmark = pytest.mark.skipif(
    not os.environ.get("P104_TEST_POSTGRES_URL"),
    reason="Explicit isolated PostgreSQL URL required",
)


@pytest.mark.asyncio
async def test_postgres_audit_runs_in_read_only_transaction(pg_sessions):
    async with pg_sessions() as db:
        await insert_fixture(db, location_id=101)
        await db.commit()
    async with pg_sessions() as db:
        await db.execute(text("SET TRANSACTION READ ONLY"))
        before = await db.scalar(select(func.count()).select_from(Observation))
        result = await evaluate_location_audit(db, 101, since=START, as_of=END)
        assert result["candidate_pairs"] == 4
        assert result["selected_pairs"] == result["matched_pairs"] == 2
        assert result["excluded_by_reason"] == {"missing_reference": 2}
        assert result["accuracy_claim_available"] is False
        assert await db.scalar(select(func.count()).select_from(Observation)) == before
        assert not db.new and not db.dirty and not db.deleted
        await db.commit()
