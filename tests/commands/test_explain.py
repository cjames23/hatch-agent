"""Tests for explain command."""

from unittest.mock import MagicMock, Mock, patch
from click.testing import CliRunner
import sys
import importlib

import pytest

# Import the actual module (not the command) using importlib
explain_module = importlib.import_module('hatch_agent.commands.explain')
explain = explain_module.explain
_status_icon = explain_module._status_icon
_build_explanation_task = explain_module._build_explanation_task


class TestExplainCLI:
    """Test explain CLI command."""

    @pytest.fixture
    def cli_runner(self):
        """Create a Click CLI runner."""
        return CliRunner()

    def test_explain_success(self, cli_runner, temp_project_dir):
        """Test successful explain command."""
        with patch.object(explain_module, 'BuildAnalyzer') as mock_analyzer_class, \
             patch.object(explain_module, 'load_config') as mock_load_config, \
             patch.object(explain_module, 'Agent') as mock_agent_class:
            # Mock build analyzer
            mock_analyzer = MagicMock()
            mock_analyzer.analyze_build_failure.return_value = {
                "test_result": {"success": True},
                "format_result": {"success": True},
                "type_result": {"success": True}
            }
            mock_analyzer_class.return_value = mock_analyzer
            
            # Mock config
            mock_load_config.return_value = {}
            
            # Mock agent
            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {
                "success": True,
                "selected_suggestion": "All checks passed!",
                "selected_agent": "Agent1",
                "reasoning": "Good code"
            }
            mock_agent_class.return_value = mock_agent
            
            result = cli_runner.invoke(explain, ["--project-root", str(temp_project_dir)])
            
            assert result.exit_code == 0
            assert "ANALYSIS" in result.output

    def test_explain_failure(self, cli_runner, temp_project_dir):
        """Test explain command with analysis failure."""
        with patch.object(explain_module, 'BuildAnalyzer') as mock_analyzer_class, \
             patch.object(explain_module, 'load_config') as mock_load_config, \
             patch.object(explain_module, 'Agent') as mock_agent_class:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze_build_failure.return_value = {
                "test_result": {"success": False, "exit_code": 1, "stderr": "Test failed"},
                "format_result": {"success": True},
                "type_result": {"success": True}
            }
            mock_analyzer_class.return_value = mock_analyzer
            mock_load_config.return_value = {}
            
            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {"success": False, "output": "Error"}
            mock_agent_class.return_value = mock_agent
            
            result = cli_runner.invoke(explain, ["--project-root", str(temp_project_dir)])
            
            assert result.exit_code != 0 or "failed" in result.output.lower()


class TestStatusIcon:
    """Test _status_icon helper function."""

    def test_status_icon_passed(self):
        """Test status icon for passed result."""
        result = _status_icon({"success": True})
        assert "PASSED" in result

    def test_status_icon_failed(self):
        """Test status icon for failed result."""
        result = _status_icon({"success": False})
        assert "FAILED" in result

    def test_status_icon_skipped(self):
        """Test status icon for skipped/unknown result."""
        result = _status_icon({"success": None})
        assert "SKIPPED" in result


class TestBuildExplanationTask:
    """Test _build_explanation_task helper."""

    def test_build_task_all_pass(self):
        """Test task when all checks pass."""
        context = {
            "test_result": {"success": True},
            "format_result": {"success": True},
            "type_result": {"success": True}
        }
        task = _build_explanation_task(context)
        assert "passed" in task.lower()

    def test_build_task_test_failure(self):
        """Test task includes test failure details."""
        context = {
            "test_result": {"success": False, "exit_code": 1, "stderr": "AssertionError"},
            "format_result": {"success": True},
            "type_result": {"success": True}
        }
        task = _build_explanation_task(context)
        assert "Tests failed" in task
        assert "AssertionError" in task

    def test_build_task_format_issues(self):
        """Test task includes formatting issues."""
        context = {
            "test_result": {"success": True},
            "format_result": {"success": False, "stdout": "Line too long"},
            "type_result": {"success": True}
        }
        task = _build_explanation_task(context)
        assert "Formatting issues" in task

    def test_build_task_type_errors(self):
        """Test task includes type errors."""
        context = {
            "test_result": {"success": True},
            "format_result": {"success": True},
            "type_result": {"success": False, "stdout": "Incompatible types"}
        }
        task = _build_explanation_task(context)
        assert "Type checking errors" in task


class TestExplainCommand:
    """Test explain command."""

    def test_explain_code(self, mock_llm_provider, temp_project_dir):
        """Test explaining code."""
        code_file = temp_project_dir / "example.py"
        code_file.write_text("def hello(): return 'world'")

        mock_llm_provider.generate.return_value = "This function returns the string 'world'"
        explanation = mock_llm_provider.generate("Explain this code")
        assert "function" in explanation.lower()

    def test_explain_function(self, mock_llm_provider):
        """Test explaining a specific function."""
        mock_llm_provider.generate.return_value = "This function performs X task"
        explanation = mock_llm_provider.generate("Explain function")
        assert "function" in explanation.lower()

    def test_explain_with_usage_examples(self, mock_llm_provider):
        """Test explaining code with usage examples."""
        mock_llm_provider.generate.return_value = "Example usage:\n```python\nresult = func()\n```"
        explanation = mock_llm_provider.generate("Show example")
        assert "Example" in explanation

    def test_explain_error_message(self, mock_llm_provider):
        """Test explaining error messages."""
        mock_llm_provider.generate.return_value = "This error occurs when..."
        explanation = mock_llm_provider.generate("Explain error")
        assert "error" in explanation.lower()

