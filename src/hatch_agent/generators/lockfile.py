"""Lockfile read/write helpers (simple JSON-backed lockfile for tests)."""

import json
from typing import Any


def read_lockfile(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def write_lockfile(path: str, data: dict[str, Any]) -> bool:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False
