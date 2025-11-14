"""Hatch plugin hooks for hatch-agent.

This module provides lightweight entry points that Hatch can use to discover
and initialize the plugin. It's intentionally minimal — real plugins should
implement the required hook functions according to Hatch's plugin API.
"""

from typing import Any, Dict


def initialize(config: Dict[str, Any]) -> None:
    """Initialize the hatch-agent plugin.

    Args:
        config: A dictionary of plugin configuration from pyproject or Hatch.
    """
    # Placeholder: real initialization (register commands, configure logging, etc.)
    print("hatch-agent initialized with config:", config)


def get_version() -> str:
    """Return plugin version."""
    return "0.0.1"

