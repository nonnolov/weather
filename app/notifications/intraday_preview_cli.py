"""Manual committed-snapshot preview. No ingestion, scheduler, or send switch."""
import argparse
import asyncio
import json
from collections import Counter


def parser():
    result = argparse.ArgumentParser(description="Preview committed intraday snapshots; never sends LINE")
    result.add_argument("--recipient", action="append", required=True,
                        help="Explicit U-prefixed recipient; repeat for a batch")
    result.add_argument("--show-messages", action="store_true",
                        help="Include location-bearing preview text in output")
    return result


async def run(args, sessions):
    from app.notifications.intraday_preview import preview_committed_snapshots
    results = await preview_committed_snapshots(sessions, args.recipient)
    # Default output contains counts/reasons only, no recipient identifiers.
    counts = Counter(item.result.status for item in results)
    reasons = Counter(reason for item in results for reason in item.result.decision.reasons)
    output = {"mode": "preview", "processed": len(results),
              "statuses": dict(sorted(counts.items())), "reasons": dict(sorted(reasons.items()))}
    if args.show_messages:
        output["messages"] = [item.result.message for item in results if item.result.message]
    print(json.dumps(output, ensure_ascii=False))
    return 1 if counts.get("error") else 0


def main(argv=None):
    args = parser().parse_args(argv)
    if any(not recipient.startswith("U") for recipient in args.recipient):
        parser().error("--recipient must start with U")
    # Lazy import keeps --help and argument validation independent of DB config.
    from app.core.database import AsyncSessionLocal, engine
    async def execute():
        try:
            return await run(args, AsyncSessionLocal)
        finally:
            await engine.dispose()
    return asyncio.run(execute())


if __name__ == "__main__":
    raise SystemExit(main())
