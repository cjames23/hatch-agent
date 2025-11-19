"""Project structure analysis utilities.

This analyzer inspects the file/directory layout and will parse a
`pyproject.toml` if present to expose project metadata and dependencies.
"""

from typing import Dict, Any
import os
import tomli
from hatch_agent.analyzers.dependencies import analyze_dependencies


def analyze_project(path: str) -> Dict[str, Any]:
    """Return a small summary of files and directories under `path`.

    The result includes top-level files and directories, and if a
    `pyproject.toml` is present it will be parsed and its dependencies
    extracted using `analyze_dependencies`.
    """
    summary: Dict[str, Any] = {"path": path, "files": [], "dirs": [], "pyproject": None, "dependencies": {}}
    # Top-level listing
    try:
        entries = sorted(os.listdir(path))
    except FileNotFoundError:
        return {"path": path, "error": "path not found"}

    for name in entries:
        full = os.path.join(path, name)
        if os.path.isdir(full):
            summary["dirs"].append(name)
        else:
            summary["files"].append(name)

    # Parse pyproject.toml if present
    pyproject_path = os.path.join(path, "pyproject.toml")
    if os.path.exists(pyproject_path):
        try:
            with open(pyproject_path, "rb") as f:
                data = tomli.load(f)
            summary["pyproject"] = {"has_pyproject": True, "project": data.get("project")}
            summary["dependencies"] = analyze_dependencies(pyproject_path)
        except Exception as exc:
            summary["pyproject"] = {"has_pyproject": True, "error": str(exc)}

    return summary
