"""Command entry points for hatch-agent."""

from .chat import main as chat_main
from .task import run_task
from .config import generate_config

__all__ = ["chat_main", "run_task", "generate_config"]
