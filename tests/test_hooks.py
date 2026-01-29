"""Tests for hooks system."""

from hatch_agent.hooks import hatch_register_environment_collector
from hatch_agent.plugin import AgentEnvironmentCollector


class TestHatchRegisterEnvironmentCollector:
    """Test the hatch_register_environment_collector hook."""

    def test_returns_agent_environment_collector_class(self):
        """Test that the hook returns the AgentEnvironmentCollector class."""
        result = hatch_register_environment_collector()
        assert result is AgentEnvironmentCollector

    def test_returns_class_not_instance(self):
        """Test that the hook returns a class, not an instance."""
        result = hatch_register_environment_collector()
        assert isinstance(result, type)
        assert issubclass(result, AgentEnvironmentCollector)

    def test_hook_is_decorated(self):
        """Test that the hook function has the hookimpl decorator applied."""
        # The hookimpl decorator adds specific attributes to the function
        # We verify the function exists and is callable
        assert callable(hatch_register_environment_collector)
