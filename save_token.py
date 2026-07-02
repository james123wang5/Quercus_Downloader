#!/usr/bin/env python3
"""Save local Quercus/Canvas token for this project only."""

from __future__ import annotations

import getpass
import json
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "config" / "local.json"


def main() -> int:
    base_url = input("Canvas/Quercus base URL [https://q.utoronto.ca]: ").strip() or "https://q.utoronto.ca"
    token = getpass.getpass("Quercus token: ").strip()
    if not token:
        print("No token saved.")
        return 1

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps({"base_url": base_url.rstrip("/"), "token": token}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except OSError:
        pass

    print(f"Saved local config: {CONFIG_PATH}")
    print("Future sync/probe commands will read this token automatically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
