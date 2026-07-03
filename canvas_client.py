#!/usr/bin/env python3
"""Small Canvas/Quercus API client used by the archive tools."""

from __future__ import annotations

import json
import http.client
import mimetypes
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
LOCAL_CONFIG_PATH = PROJECT_ROOT / "config" / "local.json"


@dataclass
class ApiError(Exception):
    code: int
    url: str
    detail: str

    def __str__(self) -> str:
        return f"HTTP {self.code}: {self.url}\n{self.detail[:1000]}"


def safe_name(value: str, fallback: str = "untitled") -> str:
    cleaned = re.sub(r"[^\w .()\-\[\]]+", "_", value, flags=re.UNICODE).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:160] or fallback


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 2
    while True:
        candidate = parent / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate
        index += 1


class CanvasClient:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.max_retries = 3

    @classmethod
    def from_env(cls) -> "CanvasClient":
        local_config = load_local_config()
        token = os.environ.get("QUERCUS_TOKEN") or local_config.get("token")
        if not token:
            raise SystemExit(
                "Missing Quercus token. Run once:\n"
                "  python3 save_token.py\n"
                "Or set QUERCUS_TOKEN in the shell."
            )
        base_url = os.environ.get("QUERCUS_BASE_URL") or local_config.get("base_url") or "https://q.utoronto.ca"
        return cls(base_url, token)

    def api_url(self, path: str, params: dict[str, Any] | None = None) -> str:
        query_items: list[tuple[str, str]] = []
        for key, value in (params or {}).items():
            if isinstance(value, (list, tuple)):
                query_items.extend((key, str(item)) for item in value)
            else:
                query_items.append((key, str(value)))
        query = urllib.parse.urlencode(query_items)
        url = f"{self.base_url}{path}"
        return f"{url}?{query}" if query else url

    def request(self, url: str, accept: str = "application/json") -> urllib.response.addinfourl:
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": accept,
                "User-Agent": "quercus-archive-tool/0.1",
            },
        )
        return self._open_with_retries(req, url)

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = self.api_url(path, params)
        with self.request(url) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def get_page(self, path: str, params: dict[str, Any] | None = None) -> tuple[Any, str]:
        url = self.api_url(path, params)
        with self.request(url) as resp:
            link = resp.headers.get("Link", "")
            data = json.loads(resp.read().decode("utf-8"))
            return data, link

    def paged_get(self, path: str, params: dict[str, Any] | None = None) -> list[Any]:
        merged = {"per_page": 100}
        if params:
            merged.update(params)

        url = self.api_url(path, merged)
        items: list[Any] = []
        while url:
            with self.request(url) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list):
                    items.extend(data)
                else:
                    return [data]
                url = self._next_url(resp.headers.get("Link", ""))
                time.sleep(0.05)
        return items

    @staticmethod
    def _next_url(link_header: str) -> str | None:
        for part in link_header.split(","):
            if 'rel="next"' not in part:
                continue
            match = re.search(r"<([^>]+)>", part)
            if match:
                return match.group(1)
        return None

    def try_paged_get(self, path: str, params: dict[str, Any] | None = None) -> tuple[list[Any], str | None]:
        try:
            return self.paged_get(path, params), None
        except ApiError as exc:
            return [], str(exc)

    def list_courses(self) -> list[dict[str, Any]]:
        courses: dict[int, dict[str, Any]] = {}
        for state in ("active", "completed"):
            data, warning = self.try_paged_get(
                "/api/v1/courses",
                {
                    "enrollment_state": state,
                    "include[]": ["term", "total_scores"],
                },
            )
            if warning:
                print(f"Could not list {state} courses: {warning}")
            for course in data:
                if isinstance(course, dict) and isinstance(course.get("id"), int):
                    course["_archive_enrollment_state"] = state
                    courses[course["id"]] = course
        return list(courses.values())

    def download_url(self, url: str, dest: Path, authenticated: bool = True) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        last_error: BaseException | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                opener = self.request(url, accept="*/*") if authenticated else self.public_request(url)
                with opener as resp:
                    content_type = resp.headers.get("Content-Type", "").split(";")[0]
                    content_length = resp.headers.get("Content-Length")
                    expected_bytes = int(content_length) if content_length and content_length.isdigit() else None
                    suffix = mimetypes.guess_extension(content_type) or ""
                    final_dest = dest
                    if not final_dest.suffix and suffix:
                        final_dest = final_dest.with_suffix(suffix)
                    final_dest = unique_path(final_dest)
                    partial_dest = final_dest.with_name(f"{final_dest.name}.part")
                    if partial_dest.exists():
                        partial_dest.unlink()
                    written = 0
                    with partial_dest.open("wb") as out:
                        while True:
                            chunk = resp.read(1024 * 1024)
                            if not chunk:
                                break
                            out.write(chunk)
                            written += len(chunk)
                    if expected_bytes is not None and written != expected_bytes:
                        raise OSError(f"Incomplete download: expected {expected_bytes} bytes, received {written}")
                    partial_dest.replace(final_dest)
                return final_dest
            except ApiError as exc:
                if exc.code != 0:
                    raise
                last_error = exc
            except (http.client.HTTPException, urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                last_error = exc
            if attempt < self.max_retries:
                time.sleep(1.5 * attempt)

        detail = getattr(last_error, "reason", None) or str(last_error)
        raise ApiError(0, url, f"Download interrupted after {self.max_retries} attempts: {detail}") from last_error

    def public_request(self, url: str) -> urllib.response.addinfourl:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "*/*",
                "User-Agent": "quercus-archive-tool/0.1",
            },
        )
        return self._open_with_retries(req, url)

    def _open_with_retries(self, req: urllib.request.Request, url: str) -> urllib.response.addinfourl:
        last_error: BaseException | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return urllib.request.urlopen(req, timeout=60)
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                raise ApiError(exc.code, url, detail) from exc
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(1.5 * attempt)
                    continue
                detail = getattr(exc, "reason", None) or str(exc)
                raise ApiError(0, url, f"Network error after {self.max_retries} attempts: {detail}") from exc
        raise ApiError(0, url, f"Network error: {last_error}")


def load_local_config() -> dict[str, str]:
    if not LOCAL_CONFIG_PATH.exists():
        return {}
    try:
        data = json.loads(LOCAL_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        "base_url": str(data.get("base_url") or "").strip(),
        "token": str(data.get("token") or "").strip(),
    }
