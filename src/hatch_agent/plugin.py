"""Hatch plugin implementation for hatch-agent.

This module provides the main plugin class that integrates with Hatch's
environment collector system to provide AI-powered project management assistance.
"""

from typing import Any

from hatch.env.collectors.plugin.interface import EnvironmentCollectorInterface


class AgentEnvironmentCollector(EnvironmentCollectorInterface):
    """Environment collector that provides AI-powered assistance for Hatch projects.

    This plugin integrates the multi-agent AI system into Hatch's workflow,
    making the AI commands available as part of the Hatch environment system.
    """

    PLUGIN_NAME = "agent"

    def get_initial_config(self) -> dict[str, Any]:
        """Return the initial configuration for the agent environment collector.

        This configuration will be merged with user configuration from pyproject.toml.
        """
        return {
            "agent": {
                "dependencies": [
                    "strands-agents",
                    "click>=8.0.0",
                ],
                "scripts": {
                    "explain": "hatch-agent-explain",
                    "add-dep": "hatch-agent-add-dep",
                    "task": "hatch-agent",
                },
            }
        }

    def finalize_config(self, config: dict[str, Any]) -> None:
        """Finalize the configuration after merging with user settings.

        This is called after the initial config is merged with user configuration
        from pyproject.toml [tool.hatch.env.collectors.agent] section.
        """
        # Nothing to finalize - the configuration is ready to use
        pass
