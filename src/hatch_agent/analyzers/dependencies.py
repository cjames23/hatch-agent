"""Dependency graph and lockfile analysis utilities.

This module uses `tomli` to robustly parse PEP 621 `pyproject.toml` files and
extract the declared dependencies.
"""

from typing import Dict, Any
import tomli


def analyze_dependencies(pyproject_path: str) -> Dict[str, Any]:
    """Parse a pyproject.toml to extract declared dependencies.

    Returns a dict containing the path and a list of dependencies (may be empty).
    """
    deps: Dict[str, Any] = {"path": pyproject_path, "dependencies": []}
    try:
        with open(pyproject_path, "rb") as f:
            data = tomli.load(f)
    except FileNotFoundError:
        return {"path": pyproject_path, "error": "file not found"}
    except Exception as exc:
        return {"path": pyproject_path, "error": str(exc)}

    project = data.get("project") or {}
    # PEP 621 style
    p_deps = project.get("dependencies") or []
    if isinstance(p_deps, list):
        deps["dependencies"].extend(p_deps)

    # Check optional tool-specific places (e.g., poetry or other tooling)
    # e.g. [tool.poetry.dependencies]
    tool = data.get("tool") or {}
    poetry = tool.get("poetry") or {}
    poetry_deps = poetry.get("dependencies") or {}
    if isinstance(poetry_deps, dict):
        # poetry lists dependencies as a mapping
        deps["dependencies"].extend([f"{k}{v if v is not True else ''}" for k, v in poetry_deps.items()])

    return deps
