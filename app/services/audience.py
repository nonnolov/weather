"""One entry per browser or server-verified LINE account; retries are idempotent."""
import hashlib
from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.models.audience import AudienceMember

async def record_member(db, kind: str, identity: str):
    digest = hashlib.sha256((kind + ":" + identity).encode()).hexdigest()
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    await db.execute(insert(AudienceMember).values(
        kind=kind, identity_hash=digest, first_seen_at=datetime.now(timezone.utc)
    ).on_conflict_do_nothing(index_elements=["kind", "identity_hash"]))

async def audience_counts(db):
    rows = (await db.execute(select(AudienceMember.kind, func.count())
        .group_by(AudienceMember.kind))).all()
    counts = dict(rows)
    return {"line_accounts": counts.get("line", 0), "website_visitors": counts.get("browser", 0)}
