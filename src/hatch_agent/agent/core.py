"""Agent orchestration: simple, testable Agent class."""

from typing import Any

from hatch_agent.agent.llm import LLMClient
from hatch_agent.agent.multi_agent import MultiAgentOrchestrator
from hatch_agent.agent.prompts import default_prompt


class Agent:
    """Minimal agent orchestration class used by commands and tests.

    This is a small, synchronous, dependency-free implementation intended as
    a scaffold for integrating an LLM or other execution engine later.

    Can be configured to use either:
    - Single LLM provider (traditional approach)
    - Multi-agent orchestration (2 suggestion agents + 1 judge)
    """

    def __init__(
        self,
        name: str = "hatch-agent",
        llm_client: LLMClient | None = None,
        use_multi_agent: bool = False,
        provider_name: str = "mock",
        provider_config: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.state: dict[str, Any] = {}
        self.llm = llm_client
        self.use_multi_agent = use_multi_agent

        # Initialize multi-agent orchestrator if requested
        if use_multi_agent:
            self.orchestrator = MultiAgentOrchestrator(
                provider_name=provider_name, provider_config=provider_config or {}
            )
        else:
            self.orchestrator = None

    def prepare(self, context: dict[str, Any] | None = None) -> None:
        """Prepare the agent with optional context."""
        self.state.update(context or {})

    def run_task(self, task_description: str) -> dict[str, Any]:
        """Run a one-shot task described by `task_description`.

        Returns a result dict with keys: success (bool) and output (str).
        """
        # Use multi-agent orchestration if enabled
        if self.use_multi_agent and self.orchestrator:
            try:
                result = self.orchestrator.run(task=task_description, context=self.state)
                return result
            except Exception as exc:
                return {"success": False, "output": str(exc)}

        # Otherwise use single LLM client
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
