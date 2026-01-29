"""Environment configuration generation utilities."""

import json
from typing import Any


def generate_environment(metadata: dict[str, Any], out_path: str) -> bool:
    """Generate a small environment JSON file from project metadata.

    Returns True on success.
    """
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"generated_from": metadata}, f, indent=2)
        return True
    except Exception:
        return False
