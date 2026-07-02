#!/usr/bin/env python3
"""Local web server for browsing the Quercus archive."""

from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from canvas_client import safe_name


ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"


class ArchiveHandler(SimpleHTTPRequestHandler):
    archive_dir: Path = ROOT / "archive"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/" or path == "/index.html":
            return self.serve_file(WEB_DIR / "index.html")
        if path.startswith("/web/"):
            return self.serve_file(WEB_DIR / path.removeprefix("/web/"))
        if path == "/api/manifest":
            return self.serve_json(self.archive_dir / "manifest.json")
        if path.startswith("/api/course/"):
            course_id = path.removeprefix("/api/course/").strip("/")
            return self.serve_course(course_id)
        if path.startswith("/archive/"):
            return self.serve_file(self.archive_dir / path.removeprefix("/archive/"))

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def serve_course(self, course_id: str) -> None:
        manifest_path = self.archive_dir / "manifest.json"
        if not manifest_path.exists():
            return self.send_error(HTTPStatus.NOT_FOUND, "Archive manifest not found. Run sync_quercus.py first.")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for course in manifest.get("courses", []):
            if str(course.get("id")) == course_id:
                course_manifest = course.get("course_manifest")
                if not course_manifest:
                    break
                course_path = self.archive_dir / str(course_manifest)
                if not self.is_allowed(course_path) or not course_path.exists():
                    return self.send_error(HTTPStatus.NOT_FOUND, "Course JSON file not found")
                data = json.loads(course_path.read_text(encoding="utf-8"))
                self.augment_course_json(course_path, data)
                return self.serve_json_data(data)

        self.send_error(HTTPStatus.NOT_FOUND, "Course not found")

    def augment_course_json(self, course_path: Path, data: dict) -> None:
        raw_path = course_path.parent / "raw" / "course.json"
        if not raw_path.exists() or not self.is_allowed(raw_path):
            self.attach_existing_file_paths(course_path, data)
            return
        try:
            raw = json.loads(raw_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self.attach_existing_file_paths(course_path, data)
            return
        for key in ("default_view", "course_code", "name"):
            if not data.get(key) and raw.get(key):
                data[key] = raw[key]
        if not data.get("home_url"):
            data["home_url"] = f"/courses/{data.get('id')}"
        self.attach_existing_file_paths(course_path, data)

    def attach_existing_file_paths(self, course_path: Path, data: dict) -> None:
        files = data.get("files")
        if not isinstance(files, list):
            return
        files_dir = course_path.parent / "files"
        if not self.is_allowed(files_dir) or not files_dir.exists() or not files_dir.is_dir():
            return

        existing = {
            path.name: path
            for path in files_dir.iterdir()
            if path.is_file() and not path.name.endswith(".part")
        }
        if not existing:
            return

        name_counts: dict[str, int] = {}
        for entry in files:
            if not isinstance(entry, dict):
                continue
            base = self.primary_file_name(entry)
            if base:
                name_counts[base] = name_counts.get(base, 0) + 1

        claimed: set[Path] = set()
        for entry in files:
            if not isinstance(entry, dict):
                continue
            local_path = entry.get("local_path")
            if local_path:
                existing_path = self.archive_dir / str(local_path)
                if existing_path.exists():
                    claimed.add(existing_path.resolve())
                    continue

            match = self.find_existing_file(entry, existing, name_counts, claimed)
            if not match:
                continue
            claimed.add(match.resolve())
            entry["local_path"] = match.resolve().relative_to(self.archive_dir.resolve()).as_posix()
            entry["download_size"] = match.stat().st_size

    def primary_file_name(self, entry: dict) -> str:
        raw = (
            entry.get("display_name")
            or entry.get("filename")
            or (f"file-{entry.get('id')}" if entry.get("id") is not None else "")
        )
        return safe_name(str(raw), "file")

    def find_existing_file(
        self,
        entry: dict,
        existing: dict[str, Path],
        name_counts: dict[str, int],
        claimed: set[Path],
    ) -> Path | None:
        file_id = entry.get("id")
        base_name = self.primary_file_name(entry)
        expected_size = entry.get("size")
        candidates: list[tuple[str, bool]] = []

        if base_name:
            base_path = Path(base_name)
            if file_id is not None:
                candidates.append((f"{base_path.stem} [{file_id}]{base_path.suffix}", True))
                candidates.append((f"{base_path.stem} ({file_id}){base_path.suffix}", True))
            candidates.append((base_name, name_counts.get(base_name, 0) <= 1))

        if file_id is not None:
            candidates.append((f"file-{file_id}", True))

        seen: set[str] = set()
        for name, allow_without_size in candidates:
            if not name or name in seen:
                continue
            seen.add(name)
            path = existing.get(name)
            if not path or path.resolve() in claimed:
                continue
            if isinstance(expected_size, int):
                if path.stat().st_size == expected_size:
                    return path
                continue
            if allow_without_size:
                return path
        return None

    def serve_json(self, path: Path) -> None:
        if not self.is_allowed(path) or not path.exists():
            return self.send_error(HTTPStatus.NOT_FOUND, "JSON file not found")
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_json_data(self, payload: object) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_file(self, path: Path) -> None:
        if not self.is_allowed(path) or not path.exists() or not path.is_file():
            return self.send_error(HTTPStatus.NOT_FOUND, "File not found")

        data = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix == ".js":
            content_type = "text/javascript"
        elif path.suffix == ".css":
            content_type = "text/css"
        elif path.suffix == ".html":
            content_type = "text/html; charset=utf-8"

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def is_allowed(self, path: Path) -> bool:
        resolved = path.resolve()
        allowed_roots = [WEB_DIR.resolve(), self.archive_dir.resolve()]
        return any(resolved == root or root in resolved.parents for root in allowed_roots)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the local Quercus archive web app.")
    parser.add_argument("--archive-dir", default=str(ROOT / "archive"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ArchiveHandler.archive_dir = Path(args.archive_dir).resolve()
    server = ThreadingHTTPServer((args.host, args.port), ArchiveHandler)
    url = f"http://{args.host}:{args.port}"
    print(f"Serving Quercus archive at {url}")
    print(f"Archive directory: {ArchiveHandler.archive_dir}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
