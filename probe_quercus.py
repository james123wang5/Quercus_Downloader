#!/usr/bin/env python3
"""Probe Quercus/Canvas API access without storing credentials."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


BASE_URL = os.environ.get("QUERCUS_BASE_URL", "https://q.utoronto.ca").rstrip("/")
TOKEN = os.environ.get("QUERCUS_TOKEN")
OUT_DIR = Path(os.environ.get("QUERCUS_OUT_DIR", "quercus_probe_output"))


class ApiError(Exception):
    def __init__(self, code: int, url: str, detail: str) -> None:
        super().__init__(f"HTTP {code}: {url}\n{detail[:1000]}")
        self.code = code
        self.url = url
        self.detail = detail


def api_get(path: str, params: dict[str, str | int] | None = None) -> tuple[object, dict[str, str]]:
    if not TOKEN:
        raise SystemExit(
            "Missing QUERCUS_TOKEN.\n"
            "Set it first, for example:\n"
            "  export QUERCUS_TOKEN='paste-token-here'"
        )

    query = urllib.parse.urlencode(params or {})
    url = f"{BASE_URL}{path}"
    if query:
        url = f"{url}?{query}"

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/json",
            "User-Agent": "quercus-archive-probe/0.1",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return json.loads(body), headers
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ApiError(exc.code, url, detail) from exc


def paged_get(path: str, params: dict[str, str | int] | None = None) -> list[object]:
    merged = {"per_page": 100}
    if params:
        merged.update(params)

    items: list[object] = []
    data, headers = api_get(path, merged)
    if isinstance(data, list):
        items.extend(data)
    else:
        return [data]

    # Canvas pagination exposes the next URL in the Link header. For this probe,
    # walking the first page is enough to prove access and shape the downloader.
    link = headers.get("link", "")
    if 'rel="next"' in link:
        print("Note: more pages exist; full downloader will follow pagination.")
    return items


def try_paged_get(
    path: str,
    params: dict[str, str | int] | None = None,
) -> tuple[list[object], str | None]:
    try:
        return paged_get(path, params), None
    except ApiError as exc:
        return [], f"HTTP {exc.code}: {exc.detail[:300]}"


def safe_name(value: str) -> str:
    keep = []
    for ch in value.strip():
        keep.append(ch if ch.isalnum() or ch in " ._()-[]" else "_")
    cleaned = "".join(keep).strip()
    return cleaned or "untitled"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    courses_by_id: dict[int, dict] = {}
    for enrollment_state in ("active", "completed"):
        courses, warning = try_paged_get(
            "/api/v1/courses",
            {
                "enrollment_state": enrollment_state,
                "include[]": "term",
            },
        )
        if warning:
            print(f"Could not list {enrollment_state} courses: {warning}")
        for course in courses:
            if isinstance(course, dict) and isinstance(course.get("id"), int):
                course["_probe_enrollment_state"] = enrollment_state
                courses_by_id[course["id"]] = course

    courses = list(courses_by_id.values())
    (OUT_DIR / "courses.json").write_text(
        json.dumps(courses, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Canvas base: {BASE_URL}")
    print(f"Visible courses: {len(courses)}")

    for course in courses[:10]:
        if not isinstance(course, dict):
            continue
        course_id = course.get("id")
        name = str(course.get("name") or course.get("course_code") or course_id)
        state = course.get("_probe_enrollment_state", "unknown")
        print(f"- {course_id}: {name} [{state}]")

        if not course_id:
            continue

        course_dir = OUT_DIR / safe_name(name)
        course_dir.mkdir(parents=True, exist_ok=True)

        modules, modules_warning = try_paged_get(
            f"/api/v1/courses/{course_id}/modules",
            {"include[]": "items"},
        )
        pages, pages_warning = try_paged_get(f"/api/v1/courses/{course_id}/pages")
        assignments, assignments_warning = try_paged_get(
            f"/api/v1/courses/{course_id}/assignments"
        )
        files, files_warning = try_paged_get(f"/api/v1/courses/{course_id}/files")

        (course_dir / "modules.json").write_text(
            json.dumps(modules, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (course_dir / "pages.json").write_text(
            json.dumps(pages, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (course_dir / "assignments.json").write_text(
            json.dumps(assignments, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (course_dir / "files.json").write_text(
            json.dumps(files, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        warnings = {
            "modules": modules_warning,
            "pages": pages_warning,
            "assignments": assignments_warning,
            "files": files_warning,
        }
        for label, warning in warnings.items():
            if warning:
                (course_dir / f"{label}.warning.txt").write_text(warning, encoding="utf-8")

        print(
            "  "
            f"modules: {len(modules)}, pages: {len(pages)}, "
            f"assignments: {len(assignments)}, files: {len(files)}"
        )
        for label, warning in warnings.items():
            if warning:
                print(f"  {label} warning: {warning}")

    print(f"\nProbe output written to: {OUT_DIR.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
