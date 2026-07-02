#!/usr/bin/env python3
"""Archive Quercus course materials into a local browsable folder."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import html as html_lib
from html.parser import HTMLParser
import json
import re
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from canvas_client import ApiError, CanvasClient, safe_name


DEFAULT_ARCHIVE_DIR = Path("archive")
DOC_EXTENSIONS = {
    ".pdf",
    ".ppt",
    ".pptx",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".csv",
    ".zip",
    ".py",
    ".java",
    ".r",
    ".txt",
    ".md",
    ".ipynb",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_html_page(path: Path, title: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape_html(title)}</title>
  <link rel="stylesheet" href="/web/page.css">
</head>
<body>
  <main class="canvas-page">
    <h1>{escape_html(title)}</h1>
    <article>{body}</article>
  </main>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def escape_html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def relative_to_archive(path: Path, archive_dir: Path) -> str:
    return path.resolve().relative_to(archive_dir.resolve()).as_posix()


def looks_like_document(name: str) -> bool:
    return Path(name).suffix.lower() in DOC_EXTENSIONS


def extract_canvas_file_ids_from_html(html: str) -> set[int]:
    ids: set[int] = set()
    patterns = [
        r"/courses/\d+/files/(\d+)",
        r"/api/v1/courses/\d+/files/(\d+)",
        r"verifier=[^\"'&]+[^\"']*?files/(\d+)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, html):
            ids.add(int(match.group(1)))
    return ids


class LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.lower()
        attrs_dict = dict(attrs)
        if tag_name != "a":
            source = attrs_dict.get("data") if tag_name == "object" else attrs_dict.get("src")
            if tag_name in {"img", "iframe", "embed", "object", "source", "video", "audio"} and source:
                title = attrs_dict.get("title") or attrs_dict.get("alt") or source
                self.links.append({"href": source, "title": title})
            return
        href = attrs_dict.get("href") or ""
        endpoint = attrs_dict.get("data-api-endpoint") or ""
        self._href = endpoint if first_file_id(endpoint) and not first_file_id(href) else href or endpoint
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._href:
            return
        text = " ".join("".join(self._text).split())
        self.links.append({"href": self._href, "title": text or self._href})
        self._href = None
        self._text = []


class ToolLaunchExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_tool_form = False
        self.form_action = ""
        self.inputs: dict[str, str] = {}
        self.title_parts: list[str] = []
        self.in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): value for key, value in attrs if key}
        tag = tag.lower()
        if tag == "title":
            self.in_title = True
            return
        if tag == "form":
            form_id = str(attrs_dict.get("id") or "")
            target = str(attrs_dict.get("target") or "")
            if form_id == "tool_form" or target == "tool_content":
                self.in_tool_form = True
                self.form_action = str(attrs_dict.get("action") or "")
            return
        if self.in_tool_form and tag == "input":
            name = attrs_dict.get("name")
            if not name:
                return
            self.inputs[str(name)] = str(attrs_dict.get("value") or "")

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "form":
            self.in_tool_form = False
        elif tag == "title":
            self.in_title = False

    @property
    def title(self) -> str:
        return " ".join("".join(self.title_parts).split())


def extract_canvas_file_links_from_html(html: str, base_url: str = "") -> list[dict[str, Any]]:
    parser = LinkExtractor()
    parser.feed(html)
    links: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str]] = set()
    for link in parser.links:
        href = urllib.parse.urljoin(base_url, link["href"]) if base_url else link["href"]
        file_id = first_file_id(href)
        is_file = file_id is not None or looks_like_document(urllib.parse.urlparse(href).path)
        if not is_file:
            continue
        key = (str(file_id) if file_id else None, href)
        if key in seen:
            continue
        seen.add(key)
        links.append(
            {
                "file_id": file_id,
                "title": link["title"],
                "href": href,
            }
        )
    return links


def extract_links_from_html(html: str, base_url: str = "") -> list[dict[str, str]]:
    parser = LinkExtractor()
    parser.feed(html)
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in parser.links:
        href = urllib.parse.urljoin(base_url, link["href"]) if base_url else link["href"]
        normalized = urllib.parse.urldefrag(href)[0]
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        links.append({"href": href, "title": link["title"]})
    return links


def extract_tool_launch(html: str) -> dict[str, Any]:
    parser = ToolLaunchExtractor()
    parser.feed(html)
    return {
        "form_action": parser.form_action,
        "inputs": parser.inputs,
        "title": html_lib.unescape(parser.title),
    }


def external_tool_id_from_item(item: dict[str, Any]) -> int | None:
    for key in ("id", "html_url", "url"):
        value = str(item.get(key) or "")
        match = re.search(r"context_external_tool_(\d+)|/external_tools/[^?]*?(\d+)|[?&]id=(\d+)", value)
        if match:
            return int(next(group for group in match.groups() if group))
    if item.get("type") == "ExternalTool" and isinstance(item.get("content_id"), int):
        return int(item["content_id"])
    return None


def sessionless_launch_params(item: dict[str, Any], tool_id: int | None) -> dict[str, str]:
    raw_url = str(item.get("url") or "")
    parsed = urllib.parse.urlparse(raw_url)
    params = {
        key: values[-1]
        for key, values in urllib.parse.parse_qs(parsed.query).items()
        if values
    }
    if tool_id is not None:
        params.setdefault("id", str(tool_id))
    params.setdefault("launch_type", "course_navigation")
    return params


def canvas_url_path(client: CanvasClient, url: str) -> str | None:
    absolute = resolve_canvas_url(client, url)
    parsed = urllib.parse.urlparse(absolute)
    base_host = urllib.parse.urlparse(client.base_url).netloc
    if parsed.netloc != base_host:
        return None
    return urllib.parse.unquote(parsed.path)


def canvas_page_slug_from_url(client: CanvasClient, course_id: int, url: str) -> str | None:
    path = canvas_url_path(client, url)
    if not path:
        return None
    match = re.match(rf"/courses/{course_id}/pages/([^/?#]+)", path)
    return urllib.parse.unquote(match.group(1)) if match else None


def manifest_page_key(page: dict[str, Any] | None) -> str:
    if not page:
        return ""
    return str(page.get("html_url") or page.get("local_path") or page.get("title") or "")


def extract_canvas_page_urls_from_html(html: str, course_id: int) -> list[str]:
    parser = LinkExtractor()
    parser.feed(html)
    page_urls: list[str] = []
    seen: set[str] = set()
    pattern = re.compile(rf"/courses/{course_id}/pages/([^/?#]+)")
    for link in parser.links:
        match = pattern.search(urllib.parse.unquote(link["href"]))
        if not match:
            continue
        page_url = match.group(1)
        if page_url in seen:
            continue
        seen.add(page_url)
        page_urls.append(page_url)
    return page_urls


def first_file_id(value: str) -> int | None:
    for pattern in (r"/files/(\d+)", r"files%2F(\d+)"):
        match = re.search(pattern, value)
        if match:
            return int(match.group(1))
    return None


def external_file_key(href: str) -> str:
    normalized = urllib.parse.urldefrag(href)[0]
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]
    return f"url:{digest}"


def is_external_document_url(client: CanvasClient, href: str) -> bool:
    if not looks_like_document(urllib.parse.urlparse(href).path):
        return False
    parsed = urllib.parse.urlparse(href)
    if parsed.scheme not in {"http", "https"}:
        return False
    canvas_host = urllib.parse.urlparse(client.base_url).netloc
    return parsed.netloc != canvas_host


def file_name_from_link(link: dict[str, Any]) -> str:
    title = str(link.get("title") or "").strip()
    path_name = urllib.parse.unquote(Path(urllib.parse.urlparse(str(link.get("href") or "")).path).name)
    if title and looks_like_document(title):
        return title
    if path_name:
        return path_name
    return title or "linked-document"


def resolve_canvas_url(client: CanvasClient, url: str) -> str:
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return f"{client.base_url}{url if url.startswith('/') else '/' + url}"


def fetch_course_detail(client: CanvasClient, course_id: int) -> tuple[dict[str, Any], str | None]:
    try:
        data = client.get(
            f"/api/v1/courses/{course_id}",
            {"include[]": ["term", "syllabus_body"]},
        )
    except ApiError as exc:
        return {}, str(exc)
    return data if isinstance(data, dict) else {}, None


def archive_syllabus_entry(
    client: CanvasClient,
    course_id: int,
    course: dict[str, Any],
    pages_dir: Path,
    archive_dir: Path,
) -> dict[str, Any] | None:
    body = str(course.get("syllabus_body") or "")
    if not body.strip():
        return None
    title = "Syllabus"
    page_path = pages_dir / "Syllabus.html"
    write_html_page(page_path, title, body)
    return {
        "title": title,
        "type": "Syllabus",
        "body": body,
        "local_path": relative_to_archive(page_path, archive_dir),
        "html_url": resolve_canvas_url(client, f"/courses/{course_id}/assignments/syllabus"),
        "linked_files": extract_canvas_file_links_from_html(body, resolve_canvas_url(client, f"/courses/{course_id}/assignments/syllabus")),
    }


def archive_course(
    client: CanvasClient,
    course: dict[str, Any],
    archive_dir: Path,
    download_files: bool,
) -> dict[str, Any]:
    course_id = course["id"]
    title = course.get("name") or course.get("course_code") or str(course_id)
    course_dir = archive_dir / "courses" / f"{course_id}-{safe_name(str(title))}"
    files_dir = course_dir / "files"
    pages_dir = course_dir / "pages"
    raw_dir = course_dir / "raw"
    course_dir.mkdir(parents=True, exist_ok=True)
    previous_file_entries = load_previous_file_entries(course_dir / "course.json")

    print(f"\nCourse {course_id}: {title}")

    course_detail, course_detail_warning = fetch_course_detail(client, course_id)
    course_metadata = {**course, **course_detail}
    if course.get("_archive_enrollment_state"):
        course_metadata["_archive_enrollment_state"] = course["_archive_enrollment_state"]

    modules, modules_warning = client.try_paged_get(
        f"/api/v1/courses/{course_id}/modules",
        {"include[]": "items"},
    )
    pages, pages_warning = client.try_paged_get(f"/api/v1/courses/{course_id}/pages")
    assignments, assignments_warning = client.try_paged_get(f"/api/v1/courses/{course_id}/assignments")
    gradebook, gradebook_warning = fetch_gradebook(client, course_id)
    quizzes, quizzes_warning = client.try_paged_get(f"/api/v1/courses/{course_id}/quizzes")
    discussions, discussions_warning = client.try_paged_get(f"/api/v1/courses/{course_id}/discussion_topics")
    announcements, announcements_warning = client.try_paged_get(
        "/api/v1/announcements",
        {
            "context_codes[]": f"course_{course_id}",
            "start_date": "2000-01-01",
            "end_date": "2035-12-31",
            "include[]": "sections",
        },
    )
    tabs, tabs_warning = client.try_paged_get(f"/api/v1/courses/{course_id}/tabs")
    files, files_warning = fetch_course_files(client, course_id)

    warnings = {
        "course": course_detail_warning,
        "modules": modules_warning,
        "pages": pages_warning,
        "assignments": assignments_warning,
        "grades": gradebook_warning,
        "quizzes": quizzes_warning,
        "discussions": discussions_warning,
        "announcements": announcements_warning,
        "tabs": tabs_warning,
        "files": files_warning,
    }

    write_json(raw_dir / "course.json", course_metadata)
    write_json(raw_dir / "modules.json", modules)
    write_json(raw_dir / "pages.json", pages)
    write_json(raw_dir / "assignments.json", assignments)
    write_json(raw_dir / "grades.json", gradebook)
    write_json(raw_dir / "quizzes.json", quizzes)
    write_json(raw_dir / "discussions.json", discussions)
    write_json(raw_dir / "announcements.json", announcements)
    write_json(raw_dir / "tabs.json", tabs)
    write_json(raw_dir / "files.json", files)
    write_json(raw_dir / "warnings.json", warnings)

    module_entries: list[dict[str, Any]] = []
    file_entries: dict[int | str, dict[str, Any]] = {}
    page_entries: dict[str, dict[str, Any]] = {}
    syllabus_entry = archive_syllabus_entry(client, course_id, course_metadata, pages_dir, archive_dir)

    for file_obj in files:
        if isinstance(file_obj, dict) and isinstance(file_obj.get("id"), int):
            file_entries[file_obj["id"]] = normalize_file_entry(file_obj)
    merge_previous_file_entries(file_entries, previous_file_entries)

    def register_linked_files(links: list[dict[str, Any]]) -> None:
        for link in links:
            file_id = link.get("file_id")
            source_url = resolve_canvas_url(client, str(link.get("href") or ""))
            if not isinstance(file_id, int):
                is_external = is_external_document_url(client, source_url)
                is_canvas_document = looks_like_document(urllib.parse.urlparse(source_url).path)
                if not is_external and not is_canvas_document:
                    continue
                key = external_file_key(source_url)
                if key not in file_entries:
                    file_entries[key] = {
                        "id": key,
                        "display_name": link.get("title") or file_name_from_link({**link, "href": source_url}),
                        "filename": file_name_from_link({**link, "href": source_url}),
                        "html_url": source_url,
                        "url": source_url,
                        "external_url": source_url if is_external else None,
                        "external_file": is_external,
                    }
                continue
            if file_id not in file_entries:
                file_entries[file_id] = {
                    "id": file_id,
                    "display_name": link.get("title") or f"Canvas file {file_id}",
                    "html_url": source_url,
                }
                continue
            entry = file_entries[file_id]
            if not entry.get("html_url"):
                entry["html_url"] = source_url
            if not entry.get("display_name") and link.get("title"):
                entry["display_name"] = link["title"]

    def archive_page(page_url: str, fallback_title: str | None = None) -> dict[str, Any]:
        if page_url in page_entries and page_entries[page_url].get("local_path"):
            return page_entries[page_url]
        try:
            detail = client.get(f"/api/v1/courses/{course_id}/pages/{urllib.parse.quote(page_url, safe='')}")
        except ApiError as exc:
            page_entries[page_url] = {"title": fallback_title or page_url, "type": "Page", "warning": str(exc)}
            return page_entries[page_url]

        page_title = str(detail.get("title") or fallback_title or page_url)
        body = str(detail.get("body") or "")
        page_path = pages_dir / f"{safe_name(page_title)}.html"
        write_html_page(page_path, page_title, body)
        page_html_url = detail.get("html_url") or resolve_canvas_url(client, f"/courses/{course_id}/pages/{page_url}")
        linked_files = extract_canvas_file_links_from_html(body, str(page_html_url))
        page_entries[page_url] = {
            "title": page_title,
            "type": "Page",
            "body": body,
            "local_path": relative_to_archive(page_path, archive_dir),
            "html_url": page_html_url,
            "linked_files": linked_files,
        }

        register_linked_files(linked_files)
        for file_id in extract_canvas_file_ids_from_html(body):
            if file_id not in file_entries:
                file_entries[file_id] = {"id": file_id, "display_name": f"Canvas file {file_id}"}
        for linked_page_url in extract_canvas_page_urls_from_html(body, course_id):
            archive_page(linked_page_url)
        archive_html_canvas_links(body, str(page_html_url), page_title)
        return page_entries[page_url]

    def archive_external_tool_item(item: dict[str, Any], fallback_title: str | None = None) -> dict[str, Any] | None:
        title = str(fallback_title or item.get("label") or item.get("title") or "External Tool")
        html_url = str(item.get("html_url") or "")
        raw_url = str(item.get("url") or "")
        external_url = str(item.get("external_url") or "")
        stable_tool_url = resolve_canvas_url(
            client,
            html_url or f"/courses/{course_id}/external_tools/{external_tool_id_from_item(item) or ''}",
        )

        if external_url and canvas_url_path(client, external_url) is None and not looks_like_document(urllib.parse.urlparse(external_url).path):
            return {
                "kind": "external",
                "title": title,
                "external_url": external_url,
                "html_url": stable_tool_url,
                "external_kind": classify_external_kind(title, external_url, str(item.get("type") or "")),
            }

        tool_id = external_tool_id_from_item(item)
        if tool_id is None and "sessionless_launch" not in raw_url:
            return None

        params = sessionless_launch_params(item, tool_id)
        if not params.get("id"):
            return None

        warning_key = f"external_tool_{course_id}_{params.get('id')}"
        try:
            launch = client.get(f"/api/v1/courses/{course_id}/external_tools/sessionless_launch", params)
        except ApiError as exc:
            warnings[warning_key] = str(exc)
            return None

        launch_url = str(launch.get("url") or "") if isinstance(launch, dict) else ""
        if not launch_url:
            warnings[warning_key] = "Sessionless launch did not return a launch URL."
            return None
        if canvas_url_path(client, launch_url) is None:
            return {
                "kind": "external",
                "title": title,
                "external_url": launch_url,
                "html_url": stable_tool_url,
                "launch_url": launch_url,
                "external_kind": classify_external_kind(title, launch_url, str(item.get("type") or "")),
            }

        try:
            with client.request(launch_url, accept="text/html,*/*") as resp:
                launch_html = resp.read().decode("utf-8", errors="replace")
        except ApiError as exc:
            warnings[warning_key] = str(exc)
            return None

        launch_data = extract_tool_launch(launch_html)
        inputs = launch_data.get("inputs") if isinstance(launch_data.get("inputs"), dict) else {}
        form_action = str(launch_data.get("form_action") or "")
        external_target_url = ""
        if form_action and canvas_url_path(client, form_action) is None:
            external_target_url = form_action
        target_url = str(inputs.get("custom_url") or "")
        if not target_url:
            target_url = next(
                (
                    str(value)
                    for key, value in inputs.items()
                    if key.lower().endswith("url")
                    and not any(skip in key.lower() for skip in ("return", "callback"))
                    and "/courses/" in str(value)
                ),
                "",
            )
        if not external_target_url:
            external_target_url = next(
                (
                    str(value)
                    for key, value in inputs.items()
                    if key.lower().endswith("url")
                    and not any(skip in key.lower() for skip in ("return", "callback"))
                    and canvas_url_path(client, str(value)) is None
                ),
                "",
            )

        if not target_url:
            if external_target_url:
                return {
                    "kind": "external",
                    "title": title,
                    "external_url": external_target_url,
                    "html_url": stable_tool_url,
                    "launch_url": launch_url,
                    "external_kind": classify_external_kind(title, external_target_url, str(item.get("type") or "")),
                }
            warnings[warning_key] = "Sessionless launch did not expose an archiveable Canvas or external URL."
            return {
                "kind": "external",
                "title": title,
                "external_url": launch_url,
                "html_url": stable_tool_url,
                "launch_url": launch_url,
                "external_kind": classify_external_kind(title, launch_url, str(item.get("type") or "")),
            }

        page_slug = canvas_page_slug_from_url(client, course_id, target_url)
        if page_slug:
            page_entry = archive_page(page_slug, title)
            aliases = page_entry.setdefault("aliases", [])
            if stable_tool_url not in aliases:
                aliases.append(stable_tool_url)
            page_entry["source_kind"] = "external_tool"
            page_entry["external_tool_id"] = int(params["id"]) if str(params["id"]).isdigit() else params["id"]
            page_entry["external_tool_title"] = title
            page_entry["external_tool_url"] = stable_tool_url
            return {"kind": "page", "entry": page_entry}

        file_id = first_file_id(target_url)
        if file_id is not None or looks_like_document(urllib.parse.urlparse(target_url).path):
            register_linked_files(
                [
                    {
                        "file_id": file_id,
                        "title": title if not looks_like_document(title) else file_name_from_link({"title": title, "href": target_url}),
                        "href": target_url,
                    }
                ]
            )
            return {"kind": "file", "file_id": file_id, "href": target_url}

        if canvas_url_path(client, target_url) is None:
            return {
                "kind": "external",
                "title": title,
                "external_url": target_url,
                "html_url": stable_tool_url,
                "launch_url": launch_url,
                "external_kind": classify_external_kind(title, target_url, str(item.get("type") or "")),
            }

        target_path = canvas_url_path(client, target_url)
        if target_path and re.match(rf"/courses/{course_id}(/|$)", target_path):
            warnings[warning_key] = f"Canvas target preserved but no page/file handler exists yet: {target_path}"
        return None

    def archive_canvas_link(url: str, fallback_title: str | None = None) -> dict[str, Any] | None:
        if not url:
            return None
        absolute_url = resolve_canvas_url(client, url)
        target_path = canvas_url_path(client, absolute_url)
        if not target_path:
            return None

        course_match = re.search(r"/courses/(\d+)(/|$)", target_path)
        if course_match and int(course_match.group(1)) != int(course_id):
            return None

        page_slug = canvas_page_slug_from_url(client, course_id, absolute_url)
        if page_slug:
            return {"kind": "page", "entry": archive_page(page_slug, fallback_title)}

        file_id = first_file_id(absolute_url)
        if file_id is not None or looks_like_document(urllib.parse.urlparse(absolute_url).path):
            register_linked_files(
                [
                    {
                        "file_id": file_id,
                        "title": fallback_title or file_name_from_link({"title": "", "href": absolute_url}),
                        "href": absolute_url,
                    }
                ]
            )
            return {"kind": "file", "file_id": file_id, "href": absolute_url}

        if re.search(rf"/courses/{course_id}/modules/items/\d+", target_path):
            return {"kind": "module_item", "href": absolute_url}
        if re.search(rf"/courses/{course_id}/assignments/\d+", target_path):
            return {"kind": "assignment", "href": absolute_url}
        if re.search(rf"/courses/{course_id}/quizzes/\d+", target_path):
            return {"kind": "quiz", "href": absolute_url}
        if re.search(rf"/courses/{course_id}/discussion_topics/\d+", target_path):
            return {"kind": "discussion", "href": absolute_url}
        if re.search(rf"/courses/{course_id}/(modules|pages|files|assignments|quizzes|discussion_topics|announcements)(/|$)", target_path):
            return {"kind": "course_section", "href": absolute_url}
        return None

    def archive_html_canvas_links(body: str, base_url: str = "", fallback_title: str | None = None) -> None:
        for link in extract_links_from_html(body, base_url):
            archive_canvas_link(link["href"], link.get("title") or fallback_title)

    if syllabus_entry:
        register_linked_files(syllabus_entry.get("linked_files", []))
        for linked_page_url in extract_canvas_page_urls_from_html(
            str(syllabus_entry.get("body") or ""),
            course_id,
        ):
            archive_page(linked_page_url)
        archive_html_canvas_links(
            str(syllabus_entry.get("body") or ""),
            str(syllabus_entry.get("html_url") or ""),
            str(syllabus_entry.get("title") or "Syllabus"),
        )

    front_page_entry: dict[str, Any] | None = None
    try:
        front_page = client.get(f"/api/v1/courses/{course_id}/front_page")
        if isinstance(front_page, dict) and front_page.get("url"):
            front_page_entry = archive_page(str(front_page["url"]), str(front_page.get("title") or front_page["url"]))
    except ApiError as exc:
        if (course_metadata.get("default_view") or course.get("default_view")) == "wiki":
            warnings["front_page"] = str(exc)

    for page in pages:
        if not isinstance(page, dict):
            continue
        url = page.get("url")
        if not url:
            continue
        archive_page(str(url), str(page.get("title") or url))

    tab_entries: list[dict[str, Any]] = []
    for item in tabs:
        if not isinstance(item, dict) or item.get("visibility") == "none":
            continue
        tab_entry = {
            "id": item.get("id"),
            "label": item.get("label"),
            "html_url": item.get("html_url"),
        }
        direct_canvas_target = archive_canvas_link(
            str(item.get("html_url") or ""),
            str(item.get("label") or "Course tab"),
        )
        if direct_canvas_target and direct_canvas_target.get("kind") == "page":
            resolved_page = direct_canvas_target["entry"]
            tab_entry["resolved_page_key"] = manifest_page_key(resolved_page)
            tab_entry["resolved_page_title"] = resolved_page.get("title")
            tab_entry["resolved_local_path"] = resolved_page.get("local_path")
        if item.get("type") == "external" or "sessionless_launch" in str(item.get("url") or ""):
            tool_target = archive_external_tool_item(item, str(item.get("label") or "External Tool"))
            if tool_target and tool_target.get("kind") == "page":
                resolved_page = tool_target["entry"]
                tab_entry["resolved_page_key"] = manifest_page_key(resolved_page)
                tab_entry["resolved_page_title"] = resolved_page.get("title")
                tab_entry["resolved_local_path"] = resolved_page.get("local_path")
            elif tool_target and tool_target.get("kind") == "external":
                tab_entry["resolved_external_url"] = tool_target.get("external_url")
                tab_entry["launch_url"] = tool_target.get("launch_url")
                tab_entry["external_kind"] = tool_target.get("external_kind")
            elif tool_target and tool_target.get("kind") == "file":
                tab_entry["resolved_file_id"] = tool_target.get("file_id")
                tab_entry["resolved_file_href"] = tool_target.get("href")
        tab_entries.append(tab_entry)

    for module in modules:
        if not isinstance(module, dict):
            continue
        items = module.get("items")
        if not isinstance(items, list):
            items, _ = client.try_paged_get(f"/api/v1/courses/{course_id}/modules/{module.get('id')}/items")

        normalized_items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "Page" and item.get("page_url"):
                archive_page(str(item["page_url"]), str(item.get("title") or item["page_url"]))
            resolved_external_page = None
            resolved_external_file = None
            tool_target = None
            if item.get("type") == "ExternalUrl" or item.get("external_url"):
                target = archive_canvas_link(
                    str(item.get("external_url") or item.get("html_url") or ""),
                    str(item.get("title") or "Link"),
                )
                if target and target.get("kind") == "page":
                    resolved_external_page = target["entry"]
                elif target and target.get("kind") == "file":
                    resolved_external_file = target
            if item.get("type") == "ExternalTool" or "sessionless_launch" in str(item.get("url") or ""):
                tool_target = archive_external_tool_item(item, str(item.get("title") or "External Tool"))
                if tool_target and tool_target.get("kind") == "page":
                    resolved_external_page = tool_target["entry"]
                elif tool_target and tool_target.get("kind") == "file":
                    resolved_external_file = tool_target
            normalized = normalize_module_item(client, course_id, item, page_entries)
            if tool_target and tool_target.get("kind") == "external":
                normalized["resolved_external_url"] = tool_target.get("external_url")
                normalized["launch_url"] = tool_target.get("launch_url")
                normalized["external_kind"] = tool_target.get("external_kind")
            if resolved_external_page:
                normalized["page"] = resolved_external_page
                normalized["resolved_page_key"] = manifest_page_key(resolved_external_page)
            if resolved_external_file:
                normalized["resolved_file_id"] = resolved_external_file.get("file_id")
                normalized["resolved_file_href"] = resolved_external_file.get("href")
            normalized_items.append(normalized)
            if item.get("type") == "File" and isinstance(item.get("content_id"), int):
                file_entries.setdefault(
                    item["content_id"],
                    {
                        "id": item["content_id"],
                        "display_name": item.get("title") or f"File {item['content_id']}",
                        "html_url": item.get("html_url"),
                        "api_url": item.get("url"),
                    },
                )
                merge_previous_file_entries(file_entries, previous_file_entries)
        module_entries.append(
            {
                "id": module.get("id"),
                "name": module.get("name"),
                "position": module.get("position"),
                "items": normalized_items,
            }
        )

    assignment_entries: list[dict[str, Any]] = []
    for item in assignments:
        if not isinstance(item, dict):
            continue
        item = fetch_assignment_detail(client, course_id, item, warnings)
        description = str(item.get("description") or "")
        linked_files = extract_canvas_file_links_from_html(description, str(item.get("html_url") or ""))
        register_linked_files(linked_files)
        for linked_page_url in extract_canvas_page_urls_from_html(description, course_id):
            archive_page(linked_page_url)
        archive_html_canvas_links(description, str(item.get("html_url") or ""), str(item.get("name") or "Assignment"))
        assignment_entries.append(normalize_assignment(item, linked_files))

    quiz_entries: list[dict[str, Any]] = []
    for item in quizzes:
        if not isinstance(item, dict):
            continue
        item = fetch_quiz_detail(client, course_id, item, warnings)
        description = str(item.get("description") or "")
        linked_files = extract_canvas_file_links_from_html(description, str(item.get("html_url") or ""))
        register_linked_files(linked_files)
        for linked_page_url in extract_canvas_page_urls_from_html(description, course_id):
            archive_page(linked_page_url)
        archive_html_canvas_links(description, str(item.get("html_url") or ""), str(item.get("title") or "Quiz"))
        quiz_entries.append(normalize_quiz(item, linked_files))

    discussion_entries: list[dict[str, Any]] = []
    for item in discussions:
        if not isinstance(item, dict):
            continue
        message = str(item.get("message") or "")
        linked_files = extract_canvas_file_links_from_html(message, str(item.get("html_url") or ""))
        register_linked_files(linked_files)
        for linked_page_url in extract_canvas_page_urls_from_html(message, course_id):
            archive_page(linked_page_url)
        archive_html_canvas_links(message, str(item.get("html_url") or ""), str(item.get("title") or "Discussion"))
        discussion_entries.append(normalize_discussion(item, linked_files))

    announcement_entries: list[dict[str, Any]] = []
    for item in announcements:
        if not isinstance(item, dict):
            continue
        message = str(item.get("message") or "")
        linked_files = extract_canvas_file_links_from_html(message, str(item.get("html_url") or ""))
        register_linked_files(linked_files)
        for linked_page_url in extract_canvas_page_urls_from_html(message, course_id):
            archive_page(linked_page_url)
        archive_html_canvas_links(message, str(item.get("html_url") or ""), str(item.get("title") or "Announcement"))
        announcement_entries.append(normalize_announcement(item, linked_files))

    if download_files:
        merge_previous_file_entries(file_entries, previous_file_entries)
        download_course_files(client, course_id, archive_dir, files_dir, file_entries)

    course_manifest = {
        "id": course_id,
        "name": course_metadata.get("name") or title,
        "course_code": course_metadata.get("course_code"),
        "term": (course_metadata.get("term") or {}).get("name") if isinstance(course_metadata.get("term"), dict) else None,
        "state": course_metadata.get("_archive_enrollment_state"),
        "default_view": course_metadata.get("default_view"),
        "home_url": course_metadata.get("html_url") or resolve_canvas_url(client, f"/courses/{course_id}"),
        "local_dir": relative_to_archive(course_dir, archive_dir),
        "syllabus": syllabus_entry,
        "front_page": front_page_entry,
        "modules": module_entries,
        "pages": list(page_entries.values()),
        "files": list(file_entries.values()),
        "assignments": assignment_entries,
        "grades": gradebook,
        "quizzes": quiz_entries,
        "discussions": discussion_entries,
        "announcements": announcement_entries,
        "tabs": tab_entries,
        "warnings": {key: value for key, value in warnings.items() if value},
    }

    write_json(course_dir / "course.json", course_manifest)
    print(
        f"  modules={len(module_entries)} pages={len(page_entries)} "
        f"files={len(file_entries)} assignments={len(course_manifest['assignments'])} "
        f"announcements={len(course_manifest['announcements'])}"
    )
    if course_manifest["warnings"]:
        print(f"  warnings: {', '.join(course_manifest['warnings'].keys())}")
    return course_manifest


def fetch_course_files(client: CanvasClient, course_id: int) -> tuple[list[Any], str | None]:
    files, files_warning = client.try_paged_get(f"/api/v1/courses/{course_id}/files")
    by_id: dict[int, dict[str, Any]] = {
        item["id"]: item
        for item in files
        if isinstance(item, dict) and isinstance(item.get("id"), int)
    }

    folders, folders_warning = client.try_paged_get(f"/api/v1/courses/{course_id}/folders")
    folder_warnings: list[str] = []
    for folder in folders:
        if not isinstance(folder, dict) or not isinstance(folder.get("id"), int):
            continue
        folder_files, folder_warning = client.try_paged_get(f"/api/v1/folders/{folder['id']}/files")
        if folder_warning:
            folder_name = folder.get("full_name") or folder.get("name") or folder["id"]
            folder_warnings.append(f"{folder_name}: {folder_warning}")
            continue
        for file_obj in folder_files:
            if isinstance(file_obj, dict) and isinstance(file_obj.get("id"), int):
                by_id[file_obj["id"]] = file_obj

    warnings = []
    if files_warning:
        warnings.append(f"course files: {files_warning}")
    if folders_warning:
        warnings.append(f"folders: {folders_warning}")
    warnings.extend(folder_warnings[:10])
    if len(folder_warnings) > 10:
        warnings.append(f"{len(folder_warnings) - 10} more folder file warnings")
    return list(by_id.values()), "; ".join(warnings) or None


def fetch_gradebook(client: CanvasClient, course_id: int) -> tuple[dict[str, Any], str | None]:
    groups, groups_warning = client.try_paged_get(
        f"/api/v1/courses/{course_id}/assignment_groups",
        {
            "include[]": ["assignments"],
            "override_assignment_dates": "true",
        },
    )
    assignments, assignments_warning = client.try_paged_get(
        f"/api/v1/courses/{course_id}/assignments",
        {
            "include[]": ["submission"],
            "override_assignment_dates": "true",
        },
    )
    enrollments, enrollments_warning = client.try_paged_get(
        f"/api/v1/courses/{course_id}/enrollments",
        {
            "user_id": "self",
            "include[]": ["total_scores", "current_grading_period_scores"],
        },
    )

    warnings = {
        "assignment_groups": groups_warning,
        "assignments": assignments_warning,
        "enrollments": enrollments_warning,
    }
    warning_text = "; ".join(f"{key}: {value}" for key, value in warnings.items() if value) or None
    return normalize_gradebook(groups, assignments, enrollments, warning_text), warning_text


def fetch_assignment_detail(
    client: CanvasClient,
    course_id: int,
    item: dict[str, Any],
    warnings: dict[str, str | None],
) -> dict[str, Any]:
    assignment_id = item.get("id")
    if not isinstance(assignment_id, int):
        return item
    try:
        detail = client.get(
            f"/api/v1/courses/{course_id}/assignments/{assignment_id}",
            {"include[]": ["submission", "rubric"]},
        )
    except ApiError as exc:
        warnings[f"assignment_{assignment_id}"] = str(exc)
        return item
    return {**item, **detail} if isinstance(detail, dict) else item


def fetch_quiz_detail(
    client: CanvasClient,
    course_id: int,
    item: dict[str, Any],
    warnings: dict[str, str | None],
) -> dict[str, Any]:
    quiz_id = item.get("id")
    if not isinstance(quiz_id, int):
        return item
    try:
        detail = client.get(f"/api/v1/courses/{course_id}/quizzes/{quiz_id}")
    except ApiError as exc:
        warnings[f"quiz_{quiz_id}"] = str(exc)
        return item
    return {**item, **detail} if isinstance(detail, dict) else item


def normalize_assignment(item: dict[str, Any], linked_files: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "description": item.get("description") or "",
        "html_url": item.get("html_url"),
        "due_at": item.get("due_at"),
        "unlock_at": item.get("unlock_at"),
        "lock_at": item.get("lock_at"),
        "points_possible": item.get("points_possible"),
        "grading_type": item.get("grading_type"),
        "submission_types": item.get("submission_types") or [],
        "workflow_state": item.get("workflow_state"),
        "published": item.get("published"),
        "rubric": normalize_rubric(item.get("rubric")),
        "rubric_settings": normalize_rubric_settings(item.get("rubric_settings")),
        "linked_files": linked_files,
    }


def normalize_rubric(raw_rubric: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_rubric, list):
        return []
    rubric = []
    for criterion in raw_rubric:
        if not isinstance(criterion, dict):
            continue
        ratings = []
        for rating in criterion.get("ratings") or []:
            if isinstance(rating, dict):
                ratings.append(
                    {
                        "id": rating.get("id"),
                        "description": rating.get("description"),
                        "long_description": rating.get("long_description"),
                        "points": rating.get("points"),
                    }
                )
        rubric.append(
            {
                "id": criterion.get("id"),
                "description": criterion.get("description"),
                "long_description": criterion.get("long_description"),
                "points": criterion.get("points"),
                "criterion_use_range": criterion.get("criterion_use_range"),
                "ratings": ratings,
            }
        )
    return rubric


def normalize_rubric_settings(settings: Any) -> dict[str, Any]:
    if not isinstance(settings, dict):
        return {}
    return {
        key: settings.get(key)
        for key in ("title", "points_possible", "free_form_criterion_comments")
        if settings.get(key) is not None
    }


def normalize_quiz(item: dict[str, Any], linked_files: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "description": item.get("description") or "",
        "html_url": item.get("html_url"),
        "due_at": item.get("due_at"),
        "unlock_at": item.get("unlock_at"),
        "lock_at": item.get("lock_at"),
        "points_possible": item.get("points_possible"),
        "quiz_type": item.get("quiz_type"),
        "published": item.get("published"),
        "workflow_state": item.get("workflow_state"),
        "allowed_attempts": item.get("allowed_attempts"),
        "time_limit": item.get("time_limit"),
        "question_count": item.get("question_count"),
        "linked_files": linked_files,
    }


def normalize_discussion(item: dict[str, Any], linked_files: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "message": item.get("message") or "",
        "html_url": item.get("html_url"),
        "posted_at": item.get("posted_at"),
        "delayed_post_at": item.get("delayed_post_at"),
        "discussion_type": item.get("discussion_type"),
        "published": item.get("published"),
        "locked": item.get("locked"),
        "read_state": item.get("read_state"),
        "user_name": (item.get("user") or {}).get("display_name") if isinstance(item.get("user"), dict) else None,
        "linked_files": linked_files,
    }


def normalize_gradebook(
    groups: list[Any],
    assignments: list[Any],
    enrollments: list[Any],
    warning: str | None,
) -> dict[str, Any]:
    assignments_by_id = {
        item["id"]: item
        for item in assignments
        if isinstance(item, dict) and isinstance(item.get("id"), int)
    }

    normalized_groups: list[dict[str, Any]] = []
    seen_assignment_ids: set[int] = set()
    for group in groups:
        if not isinstance(group, dict):
            continue
        group_assignments = []
        for item in group.get("assignments") or []:
            if not isinstance(item, dict) or not isinstance(item.get("id"), int):
                continue
            seen_assignment_ids.add(item["id"])
            merged = {**item, **assignments_by_id.get(item["id"], {})}
            grade_item = normalize_grade_assignment(merged)
            if grade_item:
                group_assignments.append(grade_item)
        normalized_group = {
            "id": group.get("id"),
            "name": group.get("name") or "Assignments",
            "position": group.get("position"),
            "group_weight": group.get("group_weight"),
            "assignments": group_assignments,
        }
        normalized_group.update(compute_grade_totals(group_assignments))
        normalized_groups.append(normalized_group)

    remaining = [
        normalize_grade_assignment(item)
        for item in assignments
        if isinstance(item, dict) and isinstance(item.get("id"), int) and item["id"] not in seen_assignment_ids
    ]
    remaining = [item for item in remaining if item]
    if remaining or not normalized_groups:
        fallback_group = {
            "id": "ungrouped",
            "name": "Assignments",
            "position": 999999,
            "group_weight": None,
            "assignments": remaining,
        }
        fallback_group.update(compute_grade_totals(remaining))
        normalized_groups.append(fallback_group)

    all_assignments = [
        assignment
        for group in normalized_groups
        for assignment in group.get("assignments", [])
    ]
    summary = compute_grade_totals(all_assignments)
    enrollment_grades = extract_enrollment_grades(enrollments)
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            **summary,
            **enrollment_grades,
        },
        "groups": normalized_groups,
        "warning": warning,
    }


def normalize_grade_assignment(item: dict[str, Any]) -> dict[str, Any] | None:
    if item.get("hide_in_gradebook"):
        return None
    submission = item.get("submission") if isinstance(item.get("submission"), dict) else {}
    score = first_number(submission.get("entered_score"), submission.get("score"))
    points_possible = first_number(item.get("points_possible"))
    return {
        "id": item.get("id"),
        "name": item.get("name") or "Untitled Assignment",
        "assignment_group_id": item.get("assignment_group_id"),
        "position": item.get("position"),
        "due_at": item.get("due_at"),
        "points_possible": points_possible,
        "grading_type": item.get("grading_type"),
        "omit_from_final_grade": bool(item.get("omit_from_final_grade")),
        "published": item.get("published"),
        "html_url": item.get("html_url"),
        "submission": {
            "score": score,
            "grade": submission.get("entered_grade") or submission.get("grade"),
            "submitted_at": submission.get("submitted_at"),
            "graded_at": submission.get("graded_at"),
            "posted_at": submission.get("posted_at"),
            "workflow_state": submission.get("workflow_state"),
            "late": bool(submission.get("late")),
            "missing": bool(submission.get("missing")),
            "excused": bool(submission.get("excused")),
        },
        "status": grade_status(submission, score),
    }


def first_number(*values: Any) -> float | None:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def grade_status(submission: dict[str, Any], score: float | None) -> str:
    if submission.get("excused"):
        return "Excused"
    if submission.get("missing"):
        return "Missing"
    if submission.get("late"):
        return "Late"
    if score is not None or submission.get("grade") or submission.get("entered_grade"):
        return "Graded"
    if submission.get("submitted_at"):
        return "Submitted"
    workflow = str(submission.get("workflow_state") or "").replace("_", " ").strip()
    return workflow.title() if workflow else "No submission"


def compute_grade_totals(assignments: list[dict[str, Any]]) -> dict[str, Any]:
    earned = 0.0
    possible = 0.0
    graded_count = 0
    for item in assignments:
        if item.get("omit_from_final_grade"):
            continue
        submission = item.get("submission") if isinstance(item.get("submission"), dict) else {}
        if submission.get("excused"):
            continue
        score = first_number(submission.get("score"))
        points = first_number(item.get("points_possible"))
        if score is None or points is None:
            continue
        earned += score
        possible += points
        graded_count += 1
    percent = (earned / possible * 100) if possible else None
    return {
        "earned_points": round(earned, 4),
        "possible_points": round(possible, 4),
        "percent": round(percent, 4) if percent is not None else None,
        "graded_count": graded_count,
        "assignment_count": len(assignments),
    }


def extract_enrollment_grades(enrollments: list[Any]) -> dict[str, Any]:
    for enrollment in enrollments:
        if not isinstance(enrollment, dict):
            continue
        grades = enrollment.get("grades")
        if not isinstance(grades, dict):
            continue
        return {
            key: grades.get(key)
            for key in (
                "current_score",
                "final_score",
                "current_grade",
                "final_grade",
                "html_url",
            )
            if grades.get(key) is not None
        }
    return {}


def normalize_file_entry(file_obj: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": file_obj.get("id"),
        "display_name": file_obj.get("display_name") or file_obj.get("filename"),
        "filename": file_obj.get("filename"),
        "size": file_obj.get("size"),
        "content-type": file_obj.get("content-type"),
        "url": file_obj.get("url"),
        "html_url": file_obj.get("html_url"),
        "preview_url": file_obj.get("preview_url") or file_obj.get("public_url"),
        "updated_at": file_obj.get("updated_at"),
    }


def load_previous_file_entries(course_manifest_path: Path) -> dict[int | str, dict[str, Any]]:
    if not course_manifest_path.exists():
        return {}
    try:
        data = json.loads(course_manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    previous: dict[int | str, dict[str, Any]] = {}
    for entry in data.get("files", []):
        if isinstance(entry, dict) and isinstance(entry.get("id"), (int, str)):
            previous[entry["id"]] = entry
    return previous


def merge_previous_file_entries(
    file_entries: dict[int | str, dict[str, Any]],
    previous_file_entries: dict[int | str, dict[str, Any]],
) -> None:
    for file_id, previous in previous_file_entries.items():
        if file_id not in file_entries:
            file_entries[file_id] = previous
            continue
        current = file_entries[file_id]
        for key in ("local_path", "downloaded_at", "download_size", "warning"):
            if previous.get(key) and not current.get(key):
                current[key] = previous[key]
        if previous.get("preview_url") and not current.get("preview_url"):
            current["preview_url"] = previous["preview_url"]


def attach_preview_url(client: CanvasClient, entry: dict[str, Any]) -> None:
    if entry.get("preview_url") or not isinstance(entry.get("id"), int):
        return
    try:
        data = client.get(f"/api/v1/files/{entry['id']}/public_url")
    except ApiError:
        return
    if isinstance(data, dict):
        preview_url = data.get("public_url") or data.get("url")
        if preview_url:
            entry["preview_url"] = preview_url


def normalize_announcement(
    item: dict[str, Any],
    linked_files: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "message": item.get("message") or "",
        "posted_at": item.get("posted_at"),
        "delayed_post_at": item.get("delayed_post_at"),
        "html_url": item.get("html_url"),
        "user_name": (item.get("user") or {}).get("display_name") if isinstance(item.get("user"), dict) else None,
        "read_state": item.get("read_state"),
        "linked_files": linked_files or [],
    }


def normalize_module_item(
    client: CanvasClient,
    course_id: int,
    item: dict[str, Any],
    page_entries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    item_type = item.get("type")
    title = item.get("title") or "Untitled"
    normalized = {
        "id": item.get("id"),
        "title": title,
        "type": item_type,
        "indent": item.get("indent", 0),
        "html_url": item.get("html_url"),
        "external_url": item.get("external_url"),
        "content_id": item.get("content_id"),
    }
    if item_type == "Page" and item.get("page_url"):
        normalized["page"] = page_entries.get(str(item["page_url"]))
    if item_type == "ExternalUrl" and item.get("external_url"):
        normalized["display_only"] = is_external_placeholder(str(title), str(item["external_url"]))
    if item_type in {"ExternalUrl", "ExternalTool"} or item.get("external_url"):
        target_url = str(item.get("external_url") or item.get("html_url") or "")
        normalized["external_kind"] = classify_external_kind(str(title), target_url, str(item_type or ""))
    if item_type == "File" and item.get("url"):
        normalized["api_url"] = item.get("url")
    elif isinstance(item.get("url"), str) and str(item["url"]).startswith("/api/"):
        normalized["api_url"] = resolve_canvas_url(client, str(item["url"]))
    return normalized


def is_external_placeholder(title: str, url: str) -> bool:
    value = f"{title} {url}".lower()
    return "piazza" in value or "markus" in value


def classify_external_kind(title: str, url: str, item_type: str = "") -> str:
    value = f"{title} {url} {item_type}".lower()
    if re.search(r"youtube|youtu\.be|vimeo|panopto|kaltura|mediasite|screenpal|h5p|lecture|video|zoom", value):
        return "video"
    if re.search(r"piazza|markus|gradescope|wileyplus|mathmatize|connect\.mheducation|externaltool", value):
        return "tool"
    if "mailto:" in value:
        return "email"
    if re.search(r"q\.utoronto\.ca/courses/\d+|/api/v1/courses/\d+", value):
        return "canvas"
    return "link"


def download_course_files(
    client: CanvasClient,
    course_id: int,
    archive_dir: Path,
    files_dir: Path,
    file_entries: dict[int | str, dict[str, Any]],
) -> None:
    files_dir.mkdir(parents=True, exist_ok=True)
    entries = sorted(file_entries.items(), key=lambda pair: str(pair[0]))
    total = len(entries)
    downloaded = 0
    skipped = 0
    failed = 0
    reserved_targets: set[Path] = set()
    prepared: list[tuple[int, int | str, dict[str, Any], dict[str, Any]]] = []

    print(f"  files to check: {total}")
    metadata_jobs = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        for index, (file_id, entry) in enumerate(entries, start=1):
            label = str(entry.get("display_name") or entry.get("filename") or f"file-{file_id}")
            local_path = entry.get("local_path")
            if local_path:
                existing = archive_dir / str(local_path)
                recorded_size = entry.get("download_size")
                if existing.exists() and (
                    not isinstance(recorded_size, int) or existing.stat().st_size == recorded_size
                ):
                    reserved_targets.add(existing)
                    skipped += 1
                    print_progress(index, total, "skipped", label)
                    continue
            if entry.get("external_file") or not isinstance(file_id, int):
                prepared.append((index, file_id, entry, entry.copy()))
                continue
            future = executor.submit(fetch_file_metadata, client, course_id, file_id)
            metadata_jobs[future] = (index, file_id, entry, label)

        for future in as_completed(metadata_jobs):
            index, file_id, entry, label = metadata_jobs[future]
            try:
                file_obj = future.result()
            except ApiError as exc:
                entry["warning"] = str(exc)
                failed += 1
                print_progress(index, total, "failed", label)
                continue
            except Exception as exc:
                entry["warning"] = f"Unexpected metadata error: {exc}"
                failed += 1
                print_progress(index, total, "failed", label)
                continue
            prepared.append((index, file_id, entry, file_obj))

    download_jobs = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        for index, file_id, entry, file_obj in sorted(prepared):
            if not entry.get("external_file"):
                entry.update(normalize_file_entry(file_obj))
            download_url = file_obj.get("url") or file_obj.get("external_url") or file_obj.get("html_url")
            filename = str(file_obj.get("display_name") or file_obj.get("filename") or f"file-{file_id}")
            if not download_url:
                entry["warning"] = "File metadata did not include a download URL."
                failed += 1
                print_progress(index, total, "failed", filename)
                continue

            target = files_dir / safe_name(filename, f"file-{file_id}")
            expected_size = file_obj.get("size")
            if target in reserved_targets or (
                target.exists()
                and isinstance(expected_size, int)
                and target.stat().st_size != expected_size
            ):
                target = target.with_name(f"{target.stem} [{safe_name(str(file_id))}]{target.suffix}")

            if target.exists():
                actual_size = target.stat().st_size
                if not isinstance(expected_size, int) or expected_size == actual_size:
                    reserved_targets.add(target)
                    entry["local_path"] = relative_to_archive(target, archive_dir)
                    entry["download_size"] = actual_size
                    skipped += 1
                    print_progress(index, total, "skipped", target.name)
                    continue
                target.unlink()

            reserved_targets.add(target)
            future = executor.submit(
                client.download_url,
                str(download_url),
                target,
                not bool(entry.get("external_file")),
            )
            download_jobs[future] = (index, entry, filename)

        for future in as_completed(download_jobs):
            index, entry, filename = download_jobs[future]
            try:
                saved = future.result()
            except ApiError as exc:
                entry["warning"] = str(exc)
                failed += 1
                print_progress(index, total, "failed", filename)
                continue
            except Exception as exc:
                entry["warning"] = f"Unexpected download error: {exc}"
                failed += 1
                print_progress(index, total, "failed", filename)
                continue

            entry["local_path"] = relative_to_archive(saved, archive_dir)
            entry["download_size"] = saved.stat().st_size
            entry["downloaded_at"] = datetime.now(timezone.utc).isoformat()
            downloaded += 1
            print_progress(index, total, "downloaded", saved.name, entry["download_size"])

    print(f"  file summary: downloaded={downloaded}, skipped={skipped}, failed={failed}, total={total}")


def fetch_file_metadata(
    client: CanvasClient,
    course_id: int,
    file_id: int,
) -> dict[str, Any]:
    try:
        data = client.get(f"/api/v1/files/{file_id}")
    except ApiError as global_error:
        try:
            data = client.get(f"/api/v1/courses/{course_id}/files/{file_id}")
        except ApiError as course_error:
            raise ApiError(
                course_error.code,
                course_error.url,
                f"{global_error}\nCourse file lookup also failed:\n{course_error}",
            ) from course_error
    if not isinstance(data, dict):
        raise ApiError(500, f"/api/v1/files/{file_id}", "File metadata was not a JSON object.")
    return data


def print_progress(index: int, total: int, status: str, name: str, size: int | None = None) -> None:
    suffix = f" ({format_bytes(size)})" if size is not None else ""
    print(f"    [{index}/{total}] {status}: {name}{suffix}", flush=True)


def format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"
        value /= 1024
    return f"{size} B"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive Quercus course materials locally.")
    parser.add_argument("--archive-dir", default=str(DEFAULT_ARCHIVE_DIR), help="Output archive directory.")
    parser.add_argument(
        "--download-files",
        action="store_true",
        help="Download linked course files into the archive. Default is metadata/pages only.",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Deprecated compatibility flag. Metadata/pages only is now the default.",
    )
    parser.add_argument("--course-id", action="append", type=int, help="Archive only this Canvas course id. Repeatable.")
    parser.add_argument("--limit", type=int, help="Limit number of courses for testing.")
    return parser.parse_args()


def manifest_course_entry(course: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": course["id"],
        "name": course["name"],
        "course_code": course.get("course_code"),
        "term": course.get("term"),
        "state": course.get("state"),
        "default_view": course.get("default_view"),
        "local_dir": course.get("local_dir"),
        "course_manifest": f"{course.get('local_dir')}/course.json",
    }


def build_manifest(
    archive_dir: Path,
    base_url: str,
    course_manifests: list[dict[str, Any]],
    merge_existing: bool,
) -> dict[str, Any]:
    existing_courses: list[dict[str, Any]] = []
    manifest_path = archive_dir / "manifest.json"
    if merge_existing and manifest_path.exists():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
            existing_courses = [
                course for course in existing.get("courses", [])
                if isinstance(course, dict) and course.get("id") is not None
            ]
        except json.JSONDecodeError:
            existing_courses = []

    by_id = {course["id"]: course for course in existing_courses}
    for course in course_manifests:
        by_id[course["id"]] = manifest_course_entry(course)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "courses": list(by_id.values()),
    }


def main() -> int:
    args = parse_args()
    client = CanvasClient.from_env()
    archive_dir = Path(args.archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)

    courses = client.list_courses()
    if args.course_id:
        by_id = {course.get("id"): course for course in courses}
        missing = [course_id for course_id in args.course_id if course_id not in by_id]
        if missing:
            print("Warning: course id not found or not accessible:", ", ".join(map(str, missing)))
        courses = [by_id[course_id] for course_id in args.course_id if course_id in by_id]
    if args.limit:
        courses = courses[: args.limit]

    download_files = bool(args.download_files and not args.no_download)
    print("Mode:", "metadata + file download" if download_files else "metadata/pages only")

    course_manifests: list[dict[str, Any]] = []
    failed_courses: list[tuple[int | str, str, str]] = []
    for course in courses:
        course_id = course.get("id", "unknown")
        course_title = str(course.get("name") or course.get("course_code") or course_id)
        try:
            course_manifests.append(archive_course(client, course, archive_dir, download_files=download_files))
        except Exception as exc:
            failed_courses.append((course_id, course_title, str(exc)))
            print(f"\nCourse {course_id}: {course_title}")
            print(f"  failed: {exc}")
            continue

    manifest = build_manifest(
        archive_dir,
        client.base_url,
        course_manifests,
        merge_existing=True,
    )
    write_json(archive_dir / "manifest.json", manifest)
    print(f"\nArchive manifest written to {archive_dir.resolve() / 'manifest.json'}")
    if failed_courses:
        failed_path = archive_dir / "failed_courses.json"
        write_json(
            failed_path,
            [
                {"id": course_id, "name": title, "error": error}
                for course_id, title, error in failed_courses
            ],
        )
        print(f"Failed courses recorded at {failed_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
