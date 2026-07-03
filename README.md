# Quercus & Canvas Course Downloader

Download University of Toronto Quercus and Canvas LMS courses, then browse them locally with a Canvas-style interface.

> This is an unofficial personal backup tool. It is not affiliated with Instructure, Canvas, Quercus, or the University of Toronto.

## Features

- Sync active and completed courses available to your account
- Archive Modules, Pages, Announcements, Assignments, Grades, Quizzes, Discussions, and course navigation
- Download PDFs, presentations, documents, ZIP files, source code, images, and other attachments
- Discover Canvas files embedded in pages, announcements, assignments, quizzes, and discussions
- Skip completed downloads and retry missing files
- Browse downloaded courses through a local Quercus / Canvas-style web interface
- Preserve links to external tools and video platforms

## Quick Start

Requires Python 3.10 or newer.

```bash
git clone https://github.com/james123wang5/QuercusCanvasDownloader.git
cd QuercusCanvasDownloader
python3 save_token.py
python3 sync_quercus.py --download-files --workers 1
python3 backend.py
```

Open:

```text
http://127.0.0.1:8765
```

`save_token.py` stores the token locally in `config/local.json`. This directory is ignored by Git.

## Commands

Sync course metadata and pages without downloading every file:

```bash
python3 sync_quercus.py
```

Download all accessible courses:

```bash
python3 sync_quercus.py --download-files --workers 1
```

Download one course:

```bash
python3 sync_quercus.py --course-id 123456 --download-files
```

Save a download log:

```bash
mkdir -p logs
PYTHONUNBUFFERED=1 python3 sync_quercus.py \
  --download-files \
  --workers 1 \
  2>&1 | tee "logs/download-$(date +%Y%m%d-%H%M%S).log"
```

Use more workers when the network and Canvas instance are stable:

```bash
python3 sync_quercus.py --download-files --workers 4
```

## Local Data

Downloaded content is stored under:

```text
archive/courses/<course-id-course-name>/
```

The following local data is excluded from Git:

```text
archive/
config/
logs/
.env
```

The public repository contains program code only. It does not include personal tokens, downloaded courses, grades, or local logs.

## Supported Content

The downloader can store:

- Course navigation, Modules, and course structure
- Pages, syllabi, and front pages
- Announcement and discussion topic content
- Assignment descriptions, rubrics, and grade information
- Quiz metadata and descriptions
- Canvas files and attachments discovered in course content

Some content can only be preserved as links or partial metadata:

- Piazza, MarkUs, Crowdmark, Gradescope, and other third-party tools
- YouTube, Zoom, U of T Play, Panopto, SharePoint, and other video services
- Quiz attempts and complete interactive quiz pages
- Complete discussion reply threads
- Deleted, expired, or permission-restricted content

The tool does not bypass Canvas permissions. It can only download content available to the configured token.

## Project Structure

```text
sync_quercus.py   Course sync and file discovery
canvas_client.py  Canvas API client and file downloader
save_token.py     Local token configuration
backend.py        Local web server
web/              Local course browser
```

## Privacy and Usage

- Never publish your Canvas token.
- Do not commit `archive/`, `config/`, `logs/`, or `.env`.
- Course materials may be protected by copyright or course policies. Use this tool for personal backups.
- Review `git status` before publishing changes.

---

# 中文说明

## Quercus / Canvas 课程下载器

把 Canvas LMS / U of T Quercus 课程下载到本地，并通过接近原课程网站的网页界面离线浏览。

> 非官方个人备份工具，与 Instructure、Canvas、Quercus 或 University of Toronto 无隶属关系。

## 功能

- 同步当前账号可访问的 active 和 completed 课程
- 保存 Modules、Pages、Announcements、Assignments、Grades、Quizzes、Discussions 和课程导航
- 下载 PDF、PPTX、DOCX、ZIP、代码、图片等课程文件
- 自动发现页面、公告和作业正文中的 Canvas 文件链接
- 已下载文件自动跳过，失败文件可以重新运行补下
- 本地 Quercus / Canvas 风格网页界面
- 记录外部工具和视频平台入口

## 快速开始

要求 Python 3.10 或更高版本。

```bash
git clone https://github.com/james123wang5/QuercusCanvasDownloader.git
cd QuercusCanvasDownloader
python3 save_token.py
python3 sync_quercus.py --download-files --workers 1
python3 backend.py
```

浏览器打开：

```text
http://127.0.0.1:8765
```

`save_token.py` 会把 token 保存在本机的 `config/local.json`。该目录已被 Git 忽略。

## 常用命令

只同步课程结构和页面：

```bash
python3 sync_quercus.py
```

下载所有可访问课程：

```bash
python3 sync_quercus.py --download-files --workers 1
```

只下载一门课程：

```bash
python3 sync_quercus.py --course-id 123456 --download-files
```

保存运行日志：

```bash
mkdir -p logs
PYTHONUNBUFFERED=1 python3 sync_quercus.py \
  --download-files \
  --workers 1 \
  2>&1 | tee "logs/download-$(date +%Y%m%d-%H%M%S).log"
```

网络稳定时可以提高并发数：

```bash
python3 sync_quercus.py --download-files --workers 4
```

## 本地数据

下载内容保存在：

```text
archive/courses/<course-id-course-name>/
```

以下本地数据不会提交到 GitHub：

```text
archive/
config/
logs/
.env
```

公开仓库只包含程序代码，不包含个人 token、课程文件、成绩或日志。

## 支持的内容

可以保存：

- 课程导航、Modules 和课程结构
- Pages、Syllabus 和 Front Page
- Announcements 和 Discussion 主题正文
- Assignments 描述、rubric 和成绩信息
- Quiz 基本信息和描述
- Canvas 文件及课程正文中的附件

只能保留链接或部分信息：

- Piazza、MarkUs、Crowdmark、Gradescope 等第三方工具
- YouTube、Zoom、U of T Play、Panopto、SharePoint 等视频
- Quiz 作答记录和完整交互页面
- Discussion 完整回复线程
- 已删除、已过期或当前账号无权访问的内容

工具不会绕过 Canvas 权限，只能下载当前 token 可以访问的内容。

## 项目结构

```text
sync_quercus.py   课程同步与文件发现
canvas_client.py  Canvas API 和文件下载
save_token.py     本地 token 配置
backend.py        本地网页服务器
web/              本地课程浏览界面
```

## 隐私与使用

- 不要公开分享 Canvas token。
- 不要提交 `archive/`、`config/`、`logs/` 或 `.env`。
- 课程资料可能受版权或课程政策限制，仅用于个人备份。
- 公开修改前请检查 `git status`。
