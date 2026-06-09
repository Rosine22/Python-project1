#!/usr/bin/env python3
import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# FEATURE 1: 

def read_log_file(filepath: str):
    """Open a log file and yield lines one by one."""
    path = Path(filepath)
    if not path.exists():
        print(f"[ERROR] File not found: {filepath}")
        sys.exit(1)
    if not path.is_file():
        print(f"[ERROR] Not a file: {filepath}")
        sys.exit(1)

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.strip():          
                yield line

# FEATURE 2: 
PLAIN_TEXT_PATTERN = re.compile(
    r"(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})"
    r".*?\b(?P<level>ERROR|WARNING|WARN|INFO|DEBUG|CRITICAL)\b"
    r"\s*[-:–]?\s*(?P<message>.+)",
    re.IGNORECASE,
)

PLAIN_TEXT_LEVEL_FIRST = re.compile(
    r"\b(?P<level>ERROR|WARNING|WARN|INFO|DEBUG|CRITICAL)\b"
    r".*?(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})"
    r"\s*[-:–]?\s*(?P<message>.+)",
    re.IGNORECASE,
)

TIMESTAMP_FORMATS = [
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S.%f",
]


def parse_timestamp(ts_str: str) -> datetime | None:
    """Try several formats and return a datetime, or None."""
    ts_str = ts_str.strip()
    for fmt in TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            continue
    return None


def normalize_level(raw: str) -> str:
    """Normalize WARN → WARNING, etc."""
    raw = raw.upper()
    return "WARNING" if raw == "WARN" else raw


def parse_line(line: str) -> dict | None:
    """
    Try JSON first; fall back to plain-text regex.
    Returns {"timestamp": datetime|None, "level": str, "message": str} or None.
    """

    if line.lstrip().startswith("{"):
        try:
            obj = json.loads(line)
            level = normalize_level(
                obj.get("level") or obj.get("severity") or obj.get("lvl") or "INFO"
            )
            message = (
                obj.get("message") or obj.get("msg") or obj.get("event") or ""
            )
            ts_raw = (
                obj.get("timestamp") or obj.get("time") or obj.get("ts") or ""
            )
            ts = parse_timestamp(str(ts_raw)) if ts_raw else None
            return {"timestamp": ts, "level": level, "message": str(message)}
        except json.JSONDecodeError:
            pass

    for pattern in (PLAIN_TEXT_PATTERN, PLAIN_TEXT_LEVEL_FIRST):
        m = pattern.search(line)
        if m:
            level = normalize_level(m.group("level"))
            message = m.group("message").strip()
            ts = parse_timestamp(m.group("ts"))
            return {"timestamp": ts, "level": level, "message": message}

    return None          


# FEATURE 3 + 4 + 5: 
def analyze_logs(
    lines,
    filter_level: str | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
):
    """
    Iterate over raw log lines, parse each one, apply filters,
    and collect statistics.

    Returns a dict with keys:
        total, errors, warnings, info, other,
        error_counts (dict), timestamps (list), skipped
    """
    counters = {"ERROR": 0, "WARNING": 0, "INFO": 0, "OTHER": 0}
    error_counts: dict[str, int] = defaultdict(int)
    timestamps: list[datetime] = []
    skipped = 0
    total = 0

    for line in lines:
        entry = parse_line(line)
        if entry is None:
            skipped += 1
            continue

        level   = entry["level"]
        message = entry["message"]
        ts      = entry["timestamp"]

        # ── FEATURE 5: filter by level ──
        if filter_level and level != filter_level.upper():
            continue

        # ── FEATURE 5: filter by time range ──
        if ts:
            if from_ts and ts < from_ts:
                continue
            if to_ts and ts > to_ts:
                continue

        # ── FEATURE 3: count levels ──
        if level in counters:
            counters[level] += 1
        else:
            counters["OTHER"] += 1
        total += 1

        # ── FEATURE 4: track error messages ──
        if level == "ERROR":
            error_counts[message] += 1

        if ts:
            timestamps.append(ts)

    most_common_error = (
        max(error_counts, key=lambda k: error_counts[k])
        if error_counts
        else "N/A"
    )

    return {
        "total":              total,
        "errors":             counters["ERROR"],
        "warnings":           counters["WARNING"],
        "info":               counters["INFO"],
        "other":              counters["OTHER"],
        "error_counts":       dict(error_counts),
        "most_common_error":  most_common_error,
        "timestamps":         sorted(timestamps),
        "skipped":            skipped,
    }


# FEATURE 6: Export to CSV


def export_csv(stats: dict, output_path: str):
    """Write a summary CSV file."""
    ts_list = stats["timestamps"]
    first_event = ts_list[0].isoformat() if ts_list else "N/A"
    last_event  = ts_list[-1].isoformat() if ts_list else "N/A"

    rows = [
        ["Metric", "Value"],
        ["Total Logs",           stats["total"]],
        ["Errors",               stats["errors"]],
        ["Warnings",             stats["warnings"]],
        ["Info",                 stats["info"]],
        ["Other",                stats["other"]],
        ["Most Common Error",    stats["most_common_error"]],
        ["First Event",          first_event],
        ["Last Event",           last_event],
        ["Unparseable Lines",    stats["skipped"]],
    ]

    # Append per-error breakdown if any
    if stats["error_counts"]:
        rows.append([])
        rows.append(["Error Message", "Count"])
        for msg, count in sorted(
            stats["error_counts"].items(), key=lambda x: -x[1]
        ):
            rows.append([msg, count])

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    print(f"\n  Summary exported to: {output_path}")



# DISPLAY


def print_summary(stats: dict, filter_level: str | None, from_ts, to_ts):
    ts_list = stats["timestamps"]
    first_event = ts_list[0].strftime("%Y-%m-%d %H:%M:%S") if ts_list else "N/A"
    last_event  = ts_list[-1].strftime("%Y-%m-%d %H:%M:%S") if ts_list else "N/A"

    print("\n" + "═" * 46)
    print("           LOG ANALYSIS SUMMARY")
    print("═" * 46)

    # Active filters
    if filter_level or from_ts or to_ts:
        print("  Filters applied:")
        if filter_level:
            print(f"    Level  : {filter_level}")
        if from_ts:
            print(f"    From   : {from_ts}")
        if to_ts:
            print(f"    To     : {to_ts}")
        print()

    print(f"  Total logs parsed   : {stats['total']:>6}")
    print(f"  ├─ Errors           : {stats['errors']:>6}")
    print(f"  ├─ Warnings         : {stats['warnings']:>6}")
    print(f"  ├─ Info             : {stats['info']:>6}")
    if stats["other"]:
        print(f"  └─ Other            : {stats['other']:>6}")
    if stats["skipped"]:
        print(f"  Unparseable lines   : {stats['skipped']:>6}")
    print()
    print(f"  Most common error   : {stats['most_common_error']}")
    if stats["most_common_error"] != "N/A":
        count = stats["error_counts"][stats["most_common_error"]]
        print(f"  Occurrences         : {count}")
    print()
    print(f"  First event         : {first_event}")
    print(f"  Last event          : {last_event}")
    print("═" * 46)

    # Top errors breakdown
    if stats["error_counts"]:
        print("\n  Top Errors:")
        sorted_errors = sorted(
            stats["error_counts"].items(), key=lambda x: -x[1]
        )[:5]
        for msg, cnt in sorted_errors:
            bar = "█" * min(cnt, 30)
            print(f"  {cnt:>4}x  {bar}  {msg[:55]}")
        print()

# CLI ENTRY POINT

def parse_args():
    parser = argparse.ArgumentParser(
        prog="log_analyzer",
        description="Analyze log files — plain text or JSON structured.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "-file", "--file",
        required=True,
        metavar="PATH",
        help="Path to the log file (e.g. app.log)",
    )
    parser.add_argument(
        "--level",
        metavar="LEVEL",
        help="Filter by log level: ERROR | WARNING | INFO | DEBUG",
    )
    parser.add_argument(
        "--from",
        dest="from_ts",
        metavar="TIMESTAMP",
        help='Start of time range, e.g. "2024-01-15 10:00:00"',
    )
    parser.add_argument(
        "--to",
        dest="to_ts",
        metavar="TIMESTAMP",
        help='End of time range, e.g. "2024-01-15 12:00:00"',
    )
    parser.add_argument(
        "-export", "--export",
        metavar="PATH",
        help="Export summary to a CSV file (e.g. summary.csv)",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    # Parse optional time filters
    from_ts = parse_timestamp(args.from_ts) if args.from_ts else None
    to_ts   = parse_timestamp(args.to_ts)   if args.to_ts   else None

    if args.from_ts and from_ts is None:
        print(f"[ERROR] Could not parse --from timestamp: {args.from_ts}")
        sys.exit(1)
    if args.to_ts and to_ts is None:
        print(f"[ERROR] Could not parse --to timestamp: {args.to_ts}")
        sys.exit(1)

    print(f"\n  Reading: {args.file}")

    # Feature 1: read file
    lines = read_log_file(args.file)

    # Features 2–5: parse, detect format, count, filter
    stats = analyze_logs(
        lines,
        filter_level=args.level,
        from_ts=from_ts,
        to_ts=to_ts,
    )

    # Display
    print_summary(stats, args.level, from_ts, to_ts)

    # Feature 6: export
    if args.export:
        export_csv(stats, args.export)


if __name__ == "__main__":
    main()
