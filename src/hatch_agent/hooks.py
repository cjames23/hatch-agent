"""Hatch plugin registration hooks.

This module provides the entry point for Hatch to discover the hatch-agent plugin.
Following Hatch's plugin architecture, we register our environment collector
that integrates AI-powered assistance into Hatch workflows.
"""

from hatchling.plugin import hookimpl

from hatch_agent.plugin import AgentEnvironmentCollector


@hookimpl
def hatch_register_environment_collector():
    """Register the hatch-agent environment collector.

    This allows hatch-agent to integrate with Hatch's environment system
    and provide AI-powered assistance for project management.
    """
    return AgentEnvironmentCollector
