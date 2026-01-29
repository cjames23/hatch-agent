"""Tests for agent module initialization."""


class TestAgentInit:
    """Test the agent module exports."""

    def test_agent_module_importable(self):
        """Test that agent module can be imported."""
        import hatch_agent.agent

        assert hatch_agent.agent is not None
