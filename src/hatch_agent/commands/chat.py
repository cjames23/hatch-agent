"""Interactive chat command implementation that uses configured LLM provider."""

from typing import Optional
from ..agent import Agent
from ..config import load_config
from src.hatch_agent.agent.llm import LLMClient


def main(name: Optional[str] = None, config_path: Optional[str] = None) -> None:
    """Run a simple REPL that talks to the Agent and uses configured LLM.

    The configuration is loaded from the XDG config location by default;
    set `config_path` to load a different file (useful for tests).
    """
    cfg = load_config(config_path)
    client = LLMClient.from_config(cfg)
    agent = Agent(name or "hatch-agent", llm_client=client)

    print(f"Starting interactive chat with agent: {agent.name} (provider={client.provider_name}, model={client.model})")
    try:
        while True:
            msg = input("> ")
            if not msg or msg.strip().lower() in {"exit", "quit"}:
                print("Goodbye")
                break
            resp = agent.chat(msg)
            print(resp)
    except (KeyboardInterrupt, EOFError):
        print("\nInterrupted. Exiting chat.")
