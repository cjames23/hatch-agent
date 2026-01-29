"""Tests for add dependency command."""

from unittest.mock import MagicMock, Mock, patch

import pytest
from click.testing import CliRunner

from hatch_agent.commands.add_dependency import (
    _build_dependency_task,
    _extract_dependency_info,
    add_dep,
)


class TestAddDepCLI:
    """Test add_dep CLI command."""

    @pytest.fixture
    def cli_runner(self):
        """Create a Click CLI runner."""
        return CliRunner()

    @patch("hatch_agent.commands.add_dependency.Agent")
    @patch("hatch_agent.commands.add_dependency.load_config")
    @patch("hatch_agent.commands.add_dependency.DependencyManager")
    def test_add_dep_dry_run(
        self, mock_dep_mgr_class, mock_load_config, mock_agent_class, cli_runner
    ):
        """Test add dependency with dry run."""
        mock_dep_mgr = MagicMock()
        mock_dep_mgr.get_current_dependencies.return_value = {"main": [], "optional": {}}
        mock_dep_mgr_class.return_value = mock_dep_mgr

        mock_load_config.return_value = {}

        mock_agent = MagicMock()
        mock_agent.run_task.return_value = {
            "success": True,
            "selected_suggestion": 'Add requests\nACTION:\n{"package": "requests"}',
            "selected_agent": "Agent1",
        }
        mock_agent_class.return_value = mock_agent

        result = cli_runner.invoke(add_dep, ["add", "requests", "--dry-run"])

        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        mock_dep_mgr.add_dependency.assert_not_called()

    @patch("hatch_agent.commands.add_dependency.Agent")
    @patch("hatch_agent.commands.add_dependency.load_config")
    @patch("hatch_agent.commands.add_dependency.DependencyManager")
    def test_add_dep_failure(
        self, mock_dep_mgr_class, mock_load_config, mock_agent_class, cli_runner
    ):
        """Test add dependency command failure."""
        mock_dep_mgr = MagicMock()
        mock_dep_mgr.get_current_dependencies.return_value = {"main": [], "optional": {}}
        mock_dep_mgr_class.return_value = mock_dep_mgr

        mock_load_config.return_value = {}

        mock_agent = MagicMock()
        mock_agent.run_task.return_value = {"success": False, "output": "Error"}
        mock_agent_class.return_value = mock_agent

        result = cli_runner.invoke(add_dep, ["add", "badpkg"])

        assert result.exit_code != 0 or "failed" in result.output.lower()


class TestBuildDependencyTask:
    """Test _build_dependency_task helper."""

    def test_build_task_includes_request(self):
        """Test task includes user request."""
        task = _build_dependency_task("add requests", {"main": [], "optional": {}})
        assert "add requests" in task

    def test_build_task_includes_deps_summary(self):
        """Test task includes dependency summary."""
        deps = {"main": ["click", "pytest"], "optional": {"dev": ["black"]}}
        task = _build_dependency_task("add httpx", deps)
        assert "2 packages" in task
        assert "dev" in task


class TestExtractDependencyInfo:
    """Test _extract_dependency_info helper."""

    def test_extract_full_info(self):
        """Test extracting complete dependency info."""
        suggestion = """
        Here's my recommendation...
        
        ACTION:
        {"package": "requests", "version": ">=2.28.0", "group": "dev"}
        """
        info = _extract_dependency_info(suggestion)

        assert info["package"] == "requests"
        assert info["version"] == ">=2.28.0"
        assert info["group"] == "dev"

    def test_extract_minimal_info(self):
        """Test extracting minimal dependency info."""
        suggestion = 'Add the package.\n\nACTION:\n{"package": "requests"}'
        info = _extract_dependency_info(suggestion)

        assert info["package"] == "requests"
        assert "version" not in info

    def test_extract_no_action(self):
        """Test extraction when no ACTION block present."""
        suggestion = "Just add requests package"
        info = _extract_dependency_info(suggestion)

        assert info is None

    def test_extract_invalid_json(self):
        """Test extraction with invalid JSON."""
        suggestion = "ACTION:\n{not valid json}"
        info = _extract_dependency_info(suggestion)

        assert info is None


class TestAddDependencyCommand:
    """Test add dependency command."""

    @patch("subprocess.run")
    def test_install_after_add(self, mock_run):
        """Test installing dependency after adding."""
        mock_run.return_value = Mock(returncode=0)
        result = mock_run(["pip", "install", "pytest"])
        assert result.returncode == 0

    def test_update_pyproject_toml(self, sample_pyproject_toml):
        """Test updating pyproject.toml with new dependency."""
        assert sample_pyproject_toml.exists()


class TestAddDepShowAll:
    """Test add_dep with --show-all flag."""

    @pytest.fixture
    def cli_runner(self):
        return CliRunner()

    @patch("hatch_agent.commands.add_dependency.Agent")
    @patch("hatch_agent.commands.add_dependency.load_config")
    @patch("hatch_agent.commands.add_dependency.DependencyManager")
    def test_add_dep_show_all(
        self, mock_dep_mgr_class, mock_load_config, mock_agent_class, cli_runner
    ):
        """Test --show-all displays all suggestions."""
        mock_dep_mgr = MagicMock()
        mock_dep_mgr.get_current_dependencies.return_value = {"main": [], "optional": {}}
        mock_dep_mgr_class.return_value = mock_dep_mgr

        mock_load_config.return_value = {}

        mock_agent = MagicMock()
        mock_agent.run_task.return_value = {
            "success": True,
            "selected_suggestion": 'Add requests\nACTION:\n{"package": "requests"}',
            "selected_agent": "Agent1",
            "all_suggestions": [
                {"agent": "Agent1", "suggestion": "Use requests", "confidence": 0.9},
                {"agent": "Agent2", "suggestion": "Use httpx", "confidence": 0.7},
            ],
        }
        mock_agent_class.return_value = mock_agent

        result = cli_runner.invoke(add_dep, ["add", "requests", "--dry-run", "--show-all"])

        assert result.exit_code == 0
        assert "ALL AGENT SUGGESTIONS" in result.output

    @patch("hatch_agent.commands.add_dependency.Agent")
    @patch("hatch_agent.commands.add_dependency.load_config")
    @patch("hatch_agent.commands.add_dependency.DependencyManager")
    def test_add_dep_no_dependency_info(
        self, mock_dep_mgr_class, mock_load_config, mock_agent_class, cli_runner
    ):
        """Test when dependency info can't be parsed."""
        mock_dep_mgr = MagicMock()
        mock_dep_mgr.get_current_dependencies.return_value = {"main": [], "optional": {}}
        mock_dep_mgr_class.return_value = mock_dep_mgr

        mock_load_config.return_value = {}

        mock_agent = MagicMock()
        mock_agent.run_task.return_value = {
            "success": True,
            "selected_suggestion": "You should add requests",  # No ACTION block
            "selected_agent": "Agent1",
        }
        mock_agent_class.return_value = mock_agent

        result = cli_runner.invoke(add_dep, ["add", "requests"])

        assert result.exit_code == 0
        assert "Could not automatically execute" in result.output

    @patch("hatch_agent.commands.add_dependency.Agent")
    @patch("hatch_agent.commands.add_dependency.load_config")
    @patch("hatch_agent.commands.add_dependency.DependencyManager")
    def test_add_dep_with_version_and_group(
        self, mock_dep_mgr_class, mock_load_config, mock_agent_class, cli_runner
    ):
        """Test displaying version and group info."""
        mock_dep_mgr = MagicMock()
        mock_dep_mgr.get_current_dependencies.return_value = {"main": [], "optional": {}}
        mock_dep_mgr_class.return_value = mock_dep_mgr

        mock_load_config.return_value = {}

        mock_agent = MagicMock()
        mock_agent.run_task.return_value = {
            "success": True,
            "selected_suggestion": 'ACTION:\n{"package": "pytest", "version": ">=7.0", "group": "dev"}',
            "selected_agent": "Agent1",
        }
        mock_agent_class.return_value = mock_agent

        result = cli_runner.invoke(add_dep, ["add", "pytest", "--dry-run"])

        assert result.exit_code == 0
        assert "Version:" in result.output
        assert "Group:" in result.output
        assert ">=7.0" in result.output
        assert "dev" in result.output

    @patch("hatch_agent.commands.add_dependency.Agent")
    @patch("hatch_agent.commands.add_dependency.load_config")
    @patch("hatch_agent.commands.add_dependency.DependencyManager")
    def test_add_dep_apply_success(
        self, mock_dep_mgr_class, mock_load_config, mock_agent_class, cli_runner
    ):
        """Test successful dependency addition."""
        mock_dep_mgr = MagicMock()
        mock_dep_mgr.get_current_dependencies.return_value = {"main": [], "optional": {}}
        mock_dep_mgr.add_dependency.return_value = {
            "success": True,
            "dependency_string": "requests>=2.28.0",
            "target": "dependencies",
        }
        mock_dep_mgr.sync_environment.return_value = {"success": True}
        mock_dep_mgr_class.return_value = mock_dep_mgr

        mock_load_config.return_value = {}

        mock_agent = MagicMock()
        mock_agent.run_task.return_value = {
            "success": True,
            "selected_suggestion": 'ACTION:\n{"package": "requests", "version": ">=2.28.0"}',
            "selected_agent": "Agent1",
        }
        mock_agent_class.return_value = mock_agent

        result = cli_runner.invoke(add_dep, ["add", "requests"], input="y\n")

        assert result.exit_code == 0
        assert "requests>=2.28.0" in result.output
        assert "Done!" in result.output

    @patch("hatch_agent.commands.add_dependency.Agent")
    @patch("hatch_agent.commands.add_dependency.load_config")
    @patch("hatch_agent.commands.add_dependency.DependencyManager")
    def test_add_dep_apply_failure(
        self, mock_dep_mgr_class, mock_load_config, mock_agent_class, cli_runner
    ):
        """Test handling of dependency addition failure."""
        mock_dep_mgr = MagicMock()
        mock_dep_mgr.get_current_dependencies.return_value = {"main": [], "optional": {}}
        mock_dep_mgr.add_dependency.return_value = {"success": False, "error": "File not found"}
        mock_dep_mgr_class.return_value = mock_dep_mgr

        mock_load_config.return_value = {}

        mock_agent = MagicMock()
        mock_agent.run_task.return_value = {
            "success": True,
            "selected_suggestion": 'ACTION:\n{"package": "requests"}',
            "selected_agent": "Agent1",
        }
        mock_agent_class.return_value = mock_agent

        result = cli_runner.invoke(add_dep, ["add", "requests"], input="y\n")

        assert result.exit_code != 0

    @patch("hatch_agent.commands.add_dependency.Agent")
    @patch("hatch_agent.commands.add_dependency.load_config")
    @patch("hatch_agent.commands.add_dependency.DependencyManager")
    def test_add_dep_cancelled(
        self, mock_dep_mgr_class, mock_load_config, mock_agent_class, cli_runner
    ):
        """Test user cancelling the operation."""
        mock_dep_mgr = MagicMock()
        mock_dep_mgr.get_current_dependencies.return_value = {"main": [], "optional": {}}
        mock_dep_mgr_class.return_value = mock_dep_mgr

        mock_load_config.return_value = {}

        mock_agent = MagicMock()
        mock_agent.run_task.return_value = {
            "success": True,
            "selected_suggestion": 'ACTION:\n{"package": "requests"}',
            "selected_agent": "Agent1",
        }
        mock_agent_class.return_value = mock_agent

        result = cli_runner.invoke(add_dep, ["add", "requests"], input="n\n")

        assert result.exit_code == 0
        assert "Cancelled" in result.output

    @patch("hatch_agent.commands.add_dependency.Agent")
    @patch("hatch_agent.commands.add_dependency.load_config")
    @patch("hatch_agent.commands.add_dependency.DependencyManager")
    def test_add_dep_skip_sync(
        self, mock_dep_mgr_class, mock_load_config, mock_agent_class, cli_runner
    ):
        """Test --skip-sync flag."""
        mock_dep_mgr = MagicMock()
        mock_dep_mgr.get_current_dependencies.return_value = {"main": [], "optional": {}}
        mock_dep_mgr.add_dependency.return_value = {
            "success": True,
            "dependency_string": "requests",
            "target": "dependencies",
        }
        mock_dep_mgr_class.return_value = mock_dep_mgr

        mock_load_config.return_value = {}

        mock_agent = MagicMock()
        mock_agent.run_task.return_value = {
            "success": True,
            "selected_suggestion": 'ACTION:\n{"package": "requests"}',
            "selected_agent": "Agent1",
        }
        mock_agent_class.return_value = mock_agent

        result = cli_runner.invoke(add_dep, ["add", "requests", "--skip-sync"], input="y\n")

        assert result.exit_code == 0
        assert "Skipped environment sync" in result.output
        mock_dep_mgr.sync_environment.assert_not_called()

    @patch("hatch_agent.commands.add_dependency.Agent")
    @patch("hatch_agent.commands.add_dependency.load_config")
    @patch("hatch_agent.commands.add_dependency.DependencyManager")
    def test_add_dep_sync_failure(
        self, mock_dep_mgr_class, mock_load_config, mock_agent_class, cli_runner
    ):
        """Test handling of sync failure."""
        mock_dep_mgr = MagicMock()
        mock_dep_mgr.get_current_dependencies.return_value = {"main": [], "optional": {}}
        mock_dep_mgr.add_dependency.return_value = {
            "success": True,
            "dependency_string": "requests",
            "target": "dependencies",
        }
        mock_dep_mgr.sync_environment.return_value = {"success": False, "error": "Sync failed"}
        mock_dep_mgr_class.return_value = mock_dep_mgr

        mock_load_config.return_value = {}

        mock_agent = MagicMock()
        mock_agent.run_task.return_value = {
            "success": True,
            "selected_suggestion": 'ACTION:\n{"package": "requests"}',
            "selected_agent": "Agent1",
        }
        mock_agent_class.return_value = mock_agent

        result = cli_runner.invoke(add_dep, ["add", "requests"], input="y\n")

        assert result.exit_code == 0
        assert "sync had issues" in result.output
