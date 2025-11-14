"""Agent orchestration: simple, testable Agent class."""

from typing import Optional, Dict, Any
from .prompts import default_prompt
from hatch_agent.agent.llm import LLMClient


class Agent:
    """Minimal agent orchestration class used by commands and tests.

    This is a small, synchronous, dependency-free implementation intended as
    a scaffold for integrating an LLM or other execution engine later.
    """

    def __init__(self, name: str = "hatch-agent", llm_client: Optional[LLMClient] = None) -> None:
        self.name = name
        self.state: Dict[str, Any] = {}
        self.llm = llm_client

    def prepare(self, context: Optional[Dict[str, Any]] = None) -> None:
        """Prepare the agent with optional context."""
        self.state.update(context or {})

    def run_task(self, task_description: str) -> Dict[str, Any]:
        """Run a one-shot task described by `task_description`.

        Returns a result dict with keys: success (bool) and output (str).
        """
        prompt = default_prompt(task_description)
        if self.llm is not None:
            # Use the configured LLM client to execute the prompt
            try:
                output = self.llm.complete(prompt)
                return {"success": True, "output": output}
            except Exception as exc:
                return {"success": False, "output": str(exc)}

        # Fallback simulation
        output = f"(simulated) executed task: {task_description}\nusing prompt: {prompt}"
        return {"success": True, "output": output}

    def chat(self, message: str) -> str:
        """Return a simulated chat response for interactive sessions."""
        if self.llm is not None:
            return self.llm.chat(message)
        # Simple echo-style response for now.
        return f"Agent {self.name} received: {message}"
