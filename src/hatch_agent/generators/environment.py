"""Environment configuration generation utilities."""

from typing import Dict, Any
import json


def generate_environment(metadata: Dict[str, Any], out_path: str) -> bool:
    """Generate a small environment JSON file from project metadata.

    Returns True on success.
    """
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"generated_from": metadata}, f, indent=2)
        return True
    except Exception:
        return False

