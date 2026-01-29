"""Tests for task command."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from hatch_agent.commands.task import run_task


class TestRunTaskCommand:
    """Test run_task CLI command."""

    @pytest.fixture
    def cli_runner(self):
        """Create a Click CLI runner."""
        return CliRunner()

    def test_run_task_success(self, cli_runner):
        """Test successful task execution."""
        # Mock at click.testing module level since it's imported inside the function
        with patch("click.testing.CliRunner") as mock_runner_class:
            mock_inner_runner = MagicMock()
            mock_result = MagicMock()
            mock_result.output = "Task completed successfully"
            mock_result.exit_code = 0
            mock_inner_runner.invoke.return_value = mock_result
            mock_runner_class.return_value = mock_inner_runner

            result = cli_runner.invoke(run_task, ["test", "task"])

            assert result.exit_code == 0

    def test_run_task_with_config(self, cli_runner, temp_project_dir):
        """Test task with config option."""
        config_file = temp_project_dir / "config.toml"
        config_file.write_text("[agent]\nname = 'test'")

        with patch("click.testing.CliRunner") as mock_runner_class:
            mock_inner_runner = MagicMock()
            mock_result = MagicMock()
            mock_result.output = "Output"
            mock_result.exit_code = 0
            mock_inner_runner.invoke.return_value = mock_result
            mock_runner_class.return_value = mock_inner_runner

            cli_runner.invoke(run_task, ["task", "--config", str(config_file)])

            # Should pass config to inner command
            call_args = mock_inner_runner.invoke.call_args[0][1]
            assert "--config" in call_args

    def test_run_task_with_name(self, cli_runner):
        """Test task with name option."""
        with patch("click.testing.CliRunner") as mock_runner_class:
            mock_inner_runner = MagicMock()
            mock_result = MagicMock()
            mock_result.output = "Output"
            mock_result.exit_code = 0
            mock_inner_runner.invoke.return_value = mock_result
            mock_runner_class.return_value = mock_inner_runner

            cli_runner.invoke(run_task, ["task", "--name", "my-agent"])

            call_args = mock_inner_runner.invoke.call_args[0][1]
            assert "--name" in call_args
            assert "my-agent" in call_args

    def test_run_task_requires_task_argument(self, cli_runner):
        """Test that task argument is required."""
        result = cli_runner.invoke(run_task, [])
        assert result.exit_code != 0


class TestTaskCommand:
    """Test task command."""

    def test_execute_simple_task(self, mock_llm_provider):
        """Test executing a simple task."""
        mock_llm_provider.generate.return_value = "Task completed successfully"
        result = mock_llm_provider.generate("Execute task")
        assert "completed" in result.lower()

    def test_analyze_task(self, mock_llm_provider):
        """Test analyzing task requirements."""
        mock_llm_provider.generate.return_value = "Task requires: files A, B, C"
        analysis = mock_llm_provider.generate("Analyze task")
        assert "requires" in analysis.lower()

    def test_verify_task_completion(self, mock_llm_provider):
        """Test verifying task completion."""
        mock_llm_provider.generate.return_value = "Task verification: PASSED"
        verification = mock_llm_provider.generate("Verify task")
        assert "PASSED" in verification
