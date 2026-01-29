"""Configuration analysis helpers."""

from typing import Any


def analyze_config(config_path: str) -> dict[str, Any]:
    """Return a tiny inspection of a configuration file (exists + size)."""
    try:
        import os

        st = os.stat(config_path)
        return {"path": config_path, "exists": True, "size": st.st_size}
    except FileNotFoundError:
        return {"path": config_path, "exists": False}
