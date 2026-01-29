"""Tests for plugin system."""

from unittest.mock import patch

from hatch_agent.plugin import AgentEnvironmentCollector


class TestAgentEnvironmentCollector:
    """Test AgentEnvironmentCollector class."""

    def test_plugin_name(self):
        """Test that PLUGIN_NAME is 'agent'."""
        assert AgentEnvironmentCollector.PLUGIN_NAME == "agent"

    @patch.object(AgentEnvironmentCollector, "__init__", lambda self, *args, **kwargs: None)
    def test_get_initial_config_returns_dict(self):
        """Test that get_initial_config returns a dictionary."""
        collector = AgentEnvironmentCollector()
        config = collector.get_initial_config()
        assert isinstance(config, dict)

    @patch.object(AgentEnvironmentCollector, "__init__", lambda self, *args, **kwargs: None)
    def test_get_initial_config_has_agent_key(self):
        """Test that get_initial_config returns config with 'agent' key."""
        collector = AgentEnvironmentCollector()
        config = collector.get_initial_config()
        assert "agent" in config

    @patch.object(AgentEnvironmentCollector, "__init__", lambda self, *args, **kwargs: None)
    def test_get_initial_config_has_dependencies(self):
        """Test that initial config includes required dependencies."""
        collector = AgentEnvironmentCollector()
        config = collector.get_initial_config()
        deps = config["agent"]["dependencies"]
        assert "strands-agents" in deps
        assert any("click" in d for d in deps)

    @patch.object(AgentEnvironmentCollector, "__init__", lambda self, *args, **kwargs: None)
    def test_get_initial_config_has_scripts(self):
        """Test that initial config includes script definitions."""
        collector = AgentEnvironmentCollector()
        config = collector.get_initial_config()
        scripts = config["agent"]["scripts"]
        assert "explain" in scripts
        assert "add-dep" in scripts
        assert "update-dep" in scripts
        assert "sync" in scripts
        assert "task" in scripts

    @patch.object(AgentEnvironmentCollector, "__init__", lambda self, *args, **kwargs: None)
    def test_finalize_config_accepts_config(self):
        """Test that finalize_config accepts config without error."""
        collector = AgentEnvironmentCollector()
        # Should not raise any exception
        collector.finalize_config({"agent": {"dependencies": []}})

    @patch.object(AgentEnvironmentCollector, "__init__", lambda self, *args, **kwargs: None)
    def test_finalize_config_with_empty_config(self):
        """Test that finalize_config handles empty config."""
        collector = AgentEnvironmentCollector()
        # Should not raise any exception
        collector.finalize_config({})

    @patch.object(AgentEnvironmentCollector, "__init__", lambda self, *args, **kwargs: None)
    def test_finalize_config_returns_none(self):
        """Test that finalize_config returns None."""
        collector = AgentEnvironmentCollector()
        result = collector.finalize_config({})
        assert result is None
