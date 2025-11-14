"""LLM client using strands-agents for multi-agent orchestration.

This module provides a simplified LLM abstraction that uses strands-agents
exclusively. The strands-agents library handles integration with various
LLM providers (OpenAI, Azure, AWS Bedrock, etc.) and foundational models.

The multi-agent approach uses:
- 2 specialist agents that generate different suggestions
- 1 judge agent that evaluates and selects the best suggestion
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
import json


class ProviderError(RuntimeError):
    pass


class StrandsProvider:
    """Provider using strands-agents for multi-agent orchestration.

    This provider uses a multi-agent approach with 2 specialist agents
    and 1 judge agent to generate and evaluate suggestions.

    Config keys supported:
    - underlying_provider: The actual LLM provider to use (openai, anthropic, bedrock, etc.)
    - underlying_config: Configuration for the underlying provider
    - mode: 'multi-agent' (default) or 'single' for single agent mode
    - model: The model to use (e.g., 'gpt-4', 'claude-3', etc.)
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

    def _ensure_strands(self):
        try:
            from strands_agents import Agent, AgentConfig
            return Agent, AgentConfig
        except ImportError as exc:
            raise ProviderError(
                "Install 'strands-agents' package to use this provider "
                "(pip install strands-agents)"
            ) from exc

    def complete(self, prompt: str) -> str:
        """Complete a prompt using strands-agents."""
        mode = self.config.get("mode", "multi-agent")

        if mode == "multi-agent":
            # Use multi-agent orchestration
            from hatch_agent.agent.multi_agent import MultiAgentOrchestrator

            underlying_provider = self.config.get("underlying_provider", "openai")
            underlying_config = self.config.get("underlying_config", {})

            # Pass through model configuration
            if self.config.get("model") and "model" not in underlying_config:
                underlying_config = dict(underlying_config)
                underlying_config["model"] = self.config.get("model")

            orchestrator = MultiAgentOrchestrator(
                provider_name=underlying_provider,
                provider_config=underlying_config
            )

            result = orchestrator.run(task=prompt)

            # Format the response to include both the selected suggestion and reasoning
            output = f"{result['selected_suggestion']}\n\n"
            output += f"[Selected from {result['selected_agent']}]\n"
            output += f"Reasoning: {result['reasoning']}"

            return output
        else:
            # Single agent mode - use strands-agents directly
            Agent, AgentConfig = self._ensure_strands()

            underlying_provider = self.config.get("underlying_provider", "openai")
            underlying_config = self.config.get("underlying_config", {})

            # Pass through model configuration
            if self.config.get("model") and "model" not in underlying_config:
                underlying_config = dict(underlying_config)
                underlying_config["model"] = self.config.get("model")

            config = AgentConfig(
                name="HatchAgent",
                role="Hatch project management assistant",
                instructions="You are an expert in Hatch project management, configuration, and automation.",
                provider=underlying_provider,
                provider_config=underlying_config
            )

            agent = Agent(config)
            return agent.run(prompt)

    def chat(self, message: str) -> str:
        """Chat interface - routes to complete."""
        return self.complete(message)


@dataclass
class LLMClient:
    """LLM client that uses strands-agents for all LLM interactions.

    This client simplifies LLM access by using strands-agents as the sole
    provider, which in turn supports multiple underlying providers and models.
    """
    provider_config: Dict[str, Any]

    @classmethod
    def from_config(cls, cfg: Dict[str, Any]) -> "LLMClient":
        """Create an LLM client from configuration.

        Expected config structure:
        {
            "mode": "multi-agent",  # or "single"
            "underlying_provider": "openai",  # or "anthropic", "bedrock", etc.
            "model": "gpt-4",  # or other model name
            "underlying_config": {
                # Provider-specific configuration
                "api_key": "...",
                # ... other settings
            }
        }

        For backwards compatibility, also supports:
        {
            "provider": "strands",
            "model": "gpt-4",
            "providers": {
                "strands": {
                    "underlying_provider": "openai",
                    "underlying_config": {...}
                }
            }
        }
        """
        # Check for new-style config first
        if "underlying_provider" in cfg or "mode" in cfg:
            # Direct configuration
            return cls(provider_config=cfg)

        # Check for old-style config with nested providers
        provider = cfg.get("provider", "strands")
        if provider != "strands":
            # Convert to strands config
            cfg = {
                "underlying_provider": provider,
                "model": cfg.get("model"),
                "underlying_config": cfg.get("providers", {}).get(provider, {})
            }
            return cls(provider_config=cfg)

        # Get strands provider config
        provider_cfg = cfg.get("providers", {}).get("strands", {})

        # Ensure model is passed through
        if cfg.get("model") and "model" not in provider_cfg:
            provider_cfg = dict(provider_cfg)
            provider_cfg["model"] = cfg.get("model")

        return cls(provider_config=provider_cfg)

    def _provider(self) -> StrandsProvider:
        """Get the strands provider instance."""
        return StrandsProvider(self.provider_config)

    def complete(self, prompt: str) -> str:
        """Complete a prompt using the LLM."""
        prov = self._provider()
        return prov.complete(prompt)

    def chat(self, message: str) -> str:
        """Chat with the LLM."""
        prov = self._provider()
        return prov.chat(message)
