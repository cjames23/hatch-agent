"""One-shot task execution command that uses configured LLM provider."""

from typing import Optional
from ..agent import Agent
from ..config import load_config
from src.hatch_agent.agent.llm import LLMClient


def run_task(description: str, name: Optional[str] = None, config_path: Optional[str] = None) -> int:
    """Run a one-shot task via the Agent and print the result.

    The Agent will be created with an LLMClient constructed from the
    configuration file (XDG location by default).

    Returns an exit code (0 success, non-zero failure).
    """
    cfg = load_config(config_path)
    client = LLMClient.from_config(cfg)
    agent = Agent(name or "hatch-agent", llm_client=client)
    result = agent.run_task(description)
    if result.get("success"):
        print(result.get("output"))
        return 0
    else:
        print("Task failed:", result)
        return 1
