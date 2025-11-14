"""Agent tool definitions and small adapters.

Tools are lightweight callables the Agent can use to interact with the
environment (filesystem, shell, package manager). This module contains
placeholder tool signatures to be implemented later.
"""

from dataclasses import dataclass
from typing import Any, Dict, Callable


@dataclass
class Tool:
    name: str
    description: str
    func: Callable[..., Any]


# Example tool: read a file

def read_file(path: str) -> Dict[str, str]:
    """Read a file and return its contents; returns structured result."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = f.read()
        return {"success": True, "content": data}
    except Exception as exc:  # pragma: no cover - simple shim
        return {"success": False, "error": str(exc)}


# Tool registry (placeholder)
TOOL_REGISTRY: Dict[str, Tool] = {
    "read_file": Tool(name="read_file", description="Read a file from disk", func=read_file),
}

