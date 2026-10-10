"""Offline P2 collector/report commands; never loads production credentials."""
import argparse
import json
from pathlib import Path

from app.evaluation.rain_evidence import (
    collect_station, evaluate_point_rain, record_point, save_json,
)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect-station")
    collect.add_argument("--directory", required=True)
    record = sub.add_parser("record-point")
    record.add_argument("--input", required=True)
    record.add_argument("--directory", required=True)
    report = sub.add_parser("report")
    report.add_argument("--forecasts", required=True)
    report.add_argument("--references", required=True)
    report.add_argument("--scope-id", required=True)
    report.add_argument("--since", required=True)
    report.add_argument("--as-of", required=True)
    report.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.command == "collect-station":
        _, data = collect_station(args.directory)
        print(json.dumps({"known_rows": data["known_rows"], "missing_rows": data["missing_rows"],
                          "evaluation_eligible": False, "blocked_by": data["blocked_by"]}))
    elif args.command == "record-point":
        record_point(read_json(args.input), args.directory)
        print(json.dumps({"recorded": True, "source": "manual_point_report"}))
    else:
        forecasts, references = read_json(args.forecasts), read_json(args.references)
        if not isinstance(forecasts, list) or not isinstance(references, list):
            raise ValueError("Forecasts and references must be JSON arrays")
        result = evaluate_point_rain(forecasts, references, scope_id=args.scope_id,
                                    since=args.since, as_of=args.as_of)
        save_json(args.output, result)
        print(json.dumps({"status": result["status"], "selected_pairs": result["selected_pairs"],
                          "unique_target_count": result["unique_target_count"]}))


if __name__ == "__main__":
    main()
