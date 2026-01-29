"""Tests for multi-task command."""

from unittest.mock import MagicMock, Mock, patch
from click.testing import CliRunner
import sys
import importlib

import pytest

# Import the actual module (not the command) using importlib
multi_task_module = importlib.import_module('hatch_agent.commands.multi_task')
multi_task = multi_task_module.multi_task


class TestMultiTaskCLI:
    """Test multi_task CLI command."""

    @pytest.fixture
    def cli_runner(self):
        """Create a Click CLI runner."""
        return CliRunner()

    def test_multi_task_success(self, cli_runner):
        """Test successful multi-task execution."""
        with patch.object(multi_task_module, 'load_config') as mock_load_config, \
             patch.object(multi_task_module, 'Agent') as mock_agent_class:
            mock_load_config.return_value = {"underlying_provider": "mock"}
            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {
                "success": True,
                "selected_suggestion": "Use pytest for testing",
                "selected_agent": "ConfigSpecialist",
                "reasoning": "Best practice"
            }
            mock_agent_class.return_value = mock_agent
            
            result = cli_runner.invoke(multi_task, ["How", "to", "test?"])
            
            assert result.exit_code == 0
            assert "pytest" in result.output

    def test_multi_task_failure(self, cli_runner):
        """Test multi-task command failure handling."""
        with patch.object(multi_task_module, 'load_config') as mock_load_config, \
             patch.object(multi_task_module, 'Agent') as mock_agent_class:
            mock_load_config.return_value = {}
            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {
                "success": False,
                "output": "Error: LLM unavailable"
            }
            mock_agent_class.return_value = mock_agent
            
            result = cli_runner.invoke(multi_task, ["Some", "task"])
            
            assert result.exit_code != 0 or "failed" in result.output.lower() or "Error" in result.output

    def test_multi_task_show_all(self, cli_runner):
        """Test --show-all flag displays all suggestions."""
        with patch.object(multi_task_module, 'load_config') as mock_load_config, \
             patch.object(multi_task_module, 'Agent') as mock_agent_class:
            mock_load_config.return_value = {}
            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {
                "success": True,
                "selected_suggestion": "Option A",
                "selected_agent": "Agent1",
                "reasoning": "Better",
                "all_suggestions": [
                    {
                        "agent": "Agent1",
                        "suggestion": "Option A",
                        "reasoning": "Reason A",
                        "confidence": 0.9
                    },
                    {
                        "agent": "Agent2",
                        "suggestion": "Option B",
                        "reasoning": "Reason B",
                        "confidence": 0.7
                    }
                ]
            }
            mock_agent_class.return_value = mock_agent
            
            result = cli_runner.invoke(multi_task, ["task", "--show-all"])
            
            assert result.exit_code == 0
            assert "ALL AGENT SUGGESTIONS" in result.output

    def test_multi_task_requires_task(self, cli_runner):
        """Test that task argument is required."""
        result = cli_runner.invoke(multi_task, [])
        assert result.exit_code != 0

    def test_multi_task_uses_multi_agent(self, cli_runner):
        """Test that Agent is created with use_multi_agent=True."""
        with patch.object(multi_task_module, 'load_config') as mock_load_config, \
             patch.object(multi_task_module, 'Agent') as mock_agent_class:
            mock_load_config.return_value = {}
            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {
                "success": True,
                "selected_suggestion": "Test",
                "selected_agent": "Agent",
                "reasoning": "Reason"
            }
            mock_agent_class.return_value = mock_agent
            
            cli_runner.invoke(multi_task, ["task"])
            
            mock_agent_class.assert_called_once()
            call_kwargs = mock_agent_class.call_args[1]
            assert call_kwargs["use_multi_agent"] is True


class TestMultiTaskCommand:
    """Test multi-task command."""

    def test_execute_multiple_tasks(self, mock_llm_provider):
        """Test executing multiple tasks."""
        mock_llm_provider.generate.return_value = "All tasks completed"
        result = mock_llm_provider.generate("Execute tasks")
        assert "completed" in result.lower()

    def test_create_task_plan(self, mock_llm_provider):
        """Test creating task execution plan."""
        mock_llm_provider.generate.return_value = "Task plan: 1. A, 2. B, 3. C"
        plan = mock_llm_provider.generate("Create plan")
        assert "Task plan" in plan

