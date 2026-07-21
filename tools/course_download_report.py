#!/usr/bin/env python3
"""Print a compact per-course download report for the local archive."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
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

CATEGORY_LABELS = {
    "retryable-network": "retry",
    "permission-or-private": "private",
    "missing-or-deleted": "404",
    "bad-or-nonfile-link": "bad-link",
    "external-file": "external",
    "local-file-missing": "local-missing",
    "not-attempted": "not-tried",
    "other": "other",
}


def classify(entry: dict[str, Any], archive_dir: Path) -> str:
    local_path = entry.get("local_path")
    if local_path:
        if (archive_dir / str(local_path)).exists():
            return "downloaded"
        return "local-file-missing"

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


def compact(text: Any, limit: int = 120) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    return value if len(value) <= limit else value[: limit - 1] + "..."


def load_courses(archive_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    courses: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(archive_dir.glob("courses/**/course.json")):
        if path.parent.name == "raw":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            courses.append((path, data))
    return courses


def course_label(course: dict[str, Any], path: Path) -> str:
    return str(course.get("course_code") or course.get("name") or path.parent.name)


def file_name(entry: dict[str, Any]) -> str:
    return compact(entry.get("display_name") or entry.get("filename") or entry.get("title") or entry.get("url") or "")


def file_url(entry: dict[str, Any]) -> str:
    return compact(entry.get("url") or entry.get("html_url") or entry.get("external_url") or "", 180)


def iter_rows(archive_dir: Path, courses: list[tuple[Path, dict[str, Any]]]):
    for path, course in courses:
        files = course.get("files") or []
        if not isinstance(files, list):
            files = []
        counts: Counter[str] = Counter()
        missing: list[tuple[str, dict[str, Any]]] = []
        for entry in files:
            if not isinstance(entry, dict):
                continue
            category = classify(entry, archive_dir)
            counts[category] += 1
            if category != "downloaded":
                missing.append((category, entry))
        yield path, course, counts, missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir", default="archive")
    parser.add_argument("--course-id", type=int, action="append", help="Only show this Canvas course id. Repeatable.")
    parser.add_argument("--details", action="store_true", help="Show missing file rows under each course.")
    parser.add_argument("--category", help="Only show detail rows from one category, for example retryable-network.")
    parser.add_argument("--all-courses", action="store_true", help="Show courses even when all known files are downloaded.")
    parser.add_argument("--limit", type=int, default=999, help="Maximum detail rows to print.")
    args = parser.parse_args()

    archive_dir = Path(args.archive_dir)
    courses = load_courses(archive_dir)
    if args.course_id:
        allowed = set(args.course_id)
        courses = [(path, course) for path, course in courses if course.get("id") in allowed]

    rows = list(iter_rows(archive_dir, courses))
    total_files = sum(sum(counts.values()) for _, _, counts, _ in rows)
    total_downloaded = sum(counts.get("downloaded", 0) for _, _, counts, _ in rows)
    total_missing = total_files - total_downloaded
    total_retry = sum(counts.get("retryable-network", 0) + counts.get("not-attempted", 0) for _, _, counts, _ in rows)

    print(f"courses: {len(rows)}")
    print(f"known files: {total_downloaded}/{total_files} downloaded, {total_missing} missing, {total_retry} worth retry/check")
    print()
    print("course_id | course | downloaded/known | missing | retry | private | 404 | bad-link | local-missing")

    detail_count = 0
    for path, course, counts, missing in rows:
        known = sum(counts.values())
        downloaded = counts.get("downloaded", 0)
        missing_count = known - downloaded
        if not args.all_courses and missing_count == 0:
            continue
        shown_missing = [(category, entry) for category, entry in missing if not args.category or category == args.category]
        if args.category and args.details and not shown_missing:
            continue
        retry_count = counts.get("retryable-network", 0) + counts.get("not-attempted", 0)
        print(
            " | ".join(
                [
                    str(course.get("id") or ""),
                    course_label(course, path),
                    f"{downloaded}/{known}",
                    str(missing_count),
                    str(retry_count),
                    str(counts.get("permission-or-private", 0)),
                    str(counts.get("missing-or-deleted", 0)),
                    str(counts.get("bad-or-nonfile-link", 0)),
                    str(counts.get("local-file-missing", 0)),
                ]
            )
        )

        if not args.details:
            continue
        for category, entry in shown_missing:
            if detail_count >= max(args.limit, 0):
                continue
            detail_count += 1
            label = CATEGORY_LABELS.get(category, category)
            print(f"  - [{label}] {file_name(entry)}")
            url = file_url(entry)
            if url:
                print(f"    {url}")
            warning = compact(entry.get("warning"), 220)
            if warning:
                print(f"    {warning}")
        if args.details and missing:
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
