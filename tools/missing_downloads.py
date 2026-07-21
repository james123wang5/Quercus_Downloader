#!/usr/bin/env python3
"""Report archived Canvas files that are known but not downloaded locally."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


NETWORK_PATTERNS = (
    "HTTP 0:",
    "Network error",
    "Download interrupted",
    "timed out",
    "reset by peer",
    "nodename nor servname",
    "Incomplete download",
)


def classify(entry: dict[str, Any]) -> str:
    warning = str(entry.get("warning") or "")
    if not warning:
        return "not-attempted"
    if any(pattern in warning for pattern in NETWORK_PATTERNS):
        return "retryable-network"
    if "HTTP 401:" in warning or "HTTP 403:" in warning:
        return "permission-or-private"
    if "HTTP 404:" in warning:
        return "missing-or-deleted"
    if "HTTP 400:" in warning:
        return "bad-or-nonfile-link"
    if entry.get("external_file"):
        return "external-file"
    return "other"


def load_course(path: Path) -> dict[str, Any] | None:
    if path.parent.name == "raw":
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("files"), list):
        return None
    return data


def iter_missing(archive_dir: Path):
    for path in sorted(archive_dir.glob("courses/**/course.json")):
        course = load_course(path)
        if not course:
            continue
        course_label = course.get("course_code") or course.get("name") or path.parent.name
        for entry in course.get("files") or []:
            if not isinstance(entry, dict) or entry.get("local_path"):
                continue
            yield {
                "course_id": course.get("id"),
                "course": course_label,
                "name": entry.get("display_name") or entry.get("filename") or entry.get("title") or "",
                "category": classify(entry),
                "url": entry.get("url") or entry.get("html_url") or entry.get("external_url") or "",
                "warning": re.sub(r"\s+", " ", str(entry.get("warning") or "")).strip(),
            }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir", default="archive")
    parser.add_argument("--category", help="Only show one category")
    parser.add_argument("--limit", type=int, default=80, help="Rows to print after the summary")
    parser.add_argument("--tsv", action="store_true", help="Print tab-separated rows")
    args = parser.parse_args()

    rows = list(iter_missing(Path(args.archive_dir)))
    if args.category:
        rows = [row for row in rows if row["category"] == args.category]

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["category"]] = counts.get(row["category"], 0) + 1

    if not args.tsv:
        print(f"missing files: {len(rows)}")
        for category, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
            print(f"  {category}: {count}")
        print()

    for row in rows[: max(args.limit, 0)]:
        values = [
            str(row["course_id"] or ""),
            str(row["course"]),
            str(row["category"]),
            str(row["name"]),
            str(row["url"]),
            str(row["warning"]),
        ]
        if args.tsv:
            print("\t".join(values))
        else:
            print(" | ".join(values[:5]))
            if row["warning"]:
                print(f"  {row['warning'][:300]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
