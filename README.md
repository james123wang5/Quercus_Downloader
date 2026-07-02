# Quercus / Canvas Download

## Quercus 课程资料下载器 / 本地 Canvas 课程归档工具

一个用于把 Quercus / Canvas 课程内容同步到本地电脑的工具。它会读取你自己的 Canvas access token，获取你账号可见的课程、课程栏目、Modules、Pages、Assignments、Announcements、Files、Grades 等结构，并生成一个本地可浏览的 Quercus / Canvas 风格网页。

> This is an unofficial local archive tool for Quercus / Canvas. It is not affiliated with, endorsed by, or maintained by Instructure, Canvas, Quercus, or the University of Toronto.

## What This Repository Contains

This repository contains only the program code:

- Python sync scripts
- A local Python web server
- A browser UI for viewing the local archive
- Dependency and configuration examples

This repository does **not** include downloaded course files, personal tokens, local logs, or private course data.

Ignored local-only folders/files include:

- `archive/`
- `config/`
- `logs/`
- `quercus_probe_output/`
- `.env`

## Features

- Sync all courses visible to your Canvas / Quercus account.
- Sync a single course by Canvas course ID.
- Preserve dynamic course navigation based on each user's real course tabs.
- Archive course metadata and structure:
  - Modules
  - Pages
  - Announcements
  - Assignments
  - Quizzes metadata
  - Discussions metadata
  - Grades summary
  - Files metadata
  - Course tabs and external tool entries
- Optionally download linked files such as PDF, PPTX, DOCX, ZIP, images, and other course materials.
- Browse the result in a local Quercus / Canvas style web UI.
- Re-run safely: already downloaded files are skipped when possible.

## Requirements

- Python 3.10+
- A valid Canvas / Quercus access token
- Network access to your Canvas / Quercus instance

Install dependencies:

```bash
pip3 install -r requirements.txt
```

## Get a Canvas / Quercus Token

This tool does not ask for or store your password. It uses a Canvas access token.

For Quercus, the default base URL is:

```text
https://q.utoronto.ca
```

Generate a token from your Canvas / Quercus account settings, then save it locally:

```bash
python3 save_token.py
```

The script writes your token to:

```text
config/local.json
```

`config/` is ignored by git. Do not share this file.

You can also use environment variables instead:

```bash
export QUERCUS_BASE_URL="https://q.utoronto.ca"
export QUERCUS_TOKEN="paste-your-token-here"
```

## Sync Course Structure

Sync all courses visible to your account:

```bash
python3 sync_quercus.py
```

Sync only one course:

```bash
python3 sync_quercus.py --course-id 123456
```

Limit the number of courses for testing:

```bash
python3 sync_quercus.py --limit 3
```

By default, this syncs course structure and metadata but does not download all files.

## Download Course Files

Download files for all synced/visible courses:

```bash
python3 sync_quercus.py --download-files
```

Download files for one course:

```bash
python3 sync_quercus.py --course-id 123456 --download-files
```

Save a download log locally:

```bash
mkdir -p logs
python3 sync_quercus.py --download-files 2>&1 | tee "logs/download-all-$(date +%Y%m%d-%H%M%S).log"
```

Downloaded files are stored under:

```text
archive/courses/<course-id-course-name>/files/
```

`archive/` is ignored by git because it contains private course data.

## Open the Local Web UI

Start the local server:

```bash
python3 backend.py
```

Open:

```text
http://127.0.0.1:8765
```

Use a different port if needed:

```bash
python3 backend.py --port 8766
```

The UI reads only local files from this project folder. It does not upload your token or course files to any remote server.

## Typical Workflow on a New Computer

```bash
git clone https://github.com/<your-username>/quercus-canvas-download.git
cd quercus-canvas-download
pip3 install -r requirements.txt
python3 save_token.py
python3 sync_quercus.py
python3 sync_quercus.py --download-files
python3 backend.py
```

Then open:

```text
http://127.0.0.1:8765
```

## Privacy and Usage Notes

- Keep your token private.
- Do not commit `config/`, `.env`, `archive/`, or `logs/`.
- Downloaded course materials may be copyrighted or restricted by course policy.
- This tool is intended for personal local backup of courses you can access.
- External tools such as Piazza, MarkUs, Gradescope, video platforms, and third-party interactive content may only be preserved as links or local records.

## Main Files

```text
backend.py          Local web server for browsing the archive
sync_quercus.py     Main Canvas / Quercus sync and download script
canvas_client.py    Canvas API client
save_token.py       Local token setup helper
probe_quercus.py    Optional API capability probe
web/                Local Quercus / Canvas style UI
requirements.txt    Python dependencies
```

## 中文快速说明

这是一个 Quercus / Canvas 课程资料本地下载和归档工具。别人拉取这个 GitHub 仓库后，不会拿到你的课程资料，也不会拿到你的 token。他们需要在自己的电脑上输入自己的 token，然后同步和下载他们自己账号能看到的课程。

最常用命令：

```bash
pip3 install -r requirements.txt
python3 save_token.py
python3 sync_quercus.py
python3 sync_quercus.py --download-files
python3 backend.py
```

打开：

```text
http://127.0.0.1:8765
```

