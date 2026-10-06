"""CLI for Phase 3 observation ingestion."""
import argparse
import asyncio
from datetime import date

from app.core.database import AsyncSessionLocal
from app.ingestion.service import ingest_seed_observations, ingest_user_observations


def _date(value: str) -> date:
    return date.fromisoformat(value)


async def _main(start_date: date | None, end_date: date | None, scope: str = "users") -> None:
    async with AsyncSessionLocal() as session:
        if scope == "seeds":
            counts = await ingest_seed_observations(session, start_date, end_date)
        else:
            counts = await ingest_user_observations(session, start_date, end_date)
        await session.commit()
    if scope == "users":
        print(f"User observation ingestion: {counts['locations']} locations, "
              f"{counts['created']} created, {counts['failed']} failed")
    else:
        for slug, count in counts.items():
            print(f"{slug}: {count} created")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", type=_date)
    parser.add_argument("--end-date", type=_date)
    parser.add_argument("--scope", choices=["users", "seeds"], default="users")
    args = parser.parse_args()
    asyncio.run(_main(args.start_date, args.end_date, args.scope))
