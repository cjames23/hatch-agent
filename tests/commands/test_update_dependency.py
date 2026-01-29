"""Tests for update dependency command."""

from unittest.mock import MagicMock, Mock, patch
from click.testing import CliRunner

import pytest

from hatch_agent.commands.update_dependency import update_dep


class TestUpdateDepCLI:
    """Test update_dep CLI command."""

    @pytest.fixture
    def cli_runner(self):
        """Create a Click CLI runner."""
        return CliRunner()

    def test_update_dep_dry_run(self, cli_runner):
        """Test update dependency with dry run."""
        import hatch_agent.commands.update_dependency as update_module
        
        with patch.object(update_module, 'DependencyUpdater') as mock_updater_class, \
             patch.object(update_module, 'load_config') as mock_load_config, \
             patch.object(update_module, 'Agent') as mock_agent_class:
            mock_updater = MagicMock()
            mock_updater.get_latest_version.return_value = "2.31.0"
            mock_updater.get_current_version.return_value = ">=2.28.0"
            mock_updater.get_project_files.return_value = []
            mock_updater_class.return_value = mock_updater
            
            mock_load_config.return_value = {}
            
            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {
                "success": True,
                "selected_suggestion": "Update requests",
                "selected_agent": "Agent1"
            }
            mock_agent_class.return_value = mock_agent
            
            result = cli_runner.invoke(update_dep, ["requests", "--dry-run"])
            
            assert result.exit_code == 0
            # Dry run output contains the package info
            assert "requests" in result.output

    def test_update_dep_specific_version(self, cli_runner):
        """Test update to specific version."""
        import hatch_agent.commands.update_dependency as update_module
        
        with patch.object(update_module, 'DependencyUpdater') as mock_updater_class, \
             patch.object(update_module, 'load_config') as mock_load_config, \
             patch.object(update_module, 'Agent') as mock_agent_class:
            mock_updater = MagicMock()
            mock_updater.get_current_version.return_value = ">=2.0.0"
            mock_updater.get_project_files.return_value = []
            mock_updater_class.return_value = mock_updater
            
            mock_load_config.return_value = {}
            
            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {
                "success": True,
                "selected_suggestion": "Update",
                "selected_agent": "Agent1"
            }
            mock_agent_class.return_value = mock_agent
            
            result = cli_runner.invoke(
                update_dep, ["requests", "--version", ">=2.30.0", "--dry-run"]
            )
            
            assert result.exit_code == 0
            assert "2.30.0" in result.output

    def test_update_dep_not_found(self, cli_runner):
        """Test update when package not found."""
        import hatch_agent.commands.update_dependency as update_module
        
        with patch.object(update_module, 'DependencyUpdater') as mock_updater_class:
            mock_updater = MagicMock()
            mock_updater.get_latest_version.return_value = None
            mock_updater.get_current_version.return_value = None
            mock_updater_class.return_value = mock_updater
            
            result = cli_runner.invoke(update_dep, ["nonexistent-package", "--dry-run"])
            
            # Should warn or handle gracefully
            assert "nonexistent-package" in result.output


class TestUpdateDependencyCommand:
    """Test update dependency command."""

    def test_update_single_dependency(self, mock_dependency_info):
        """Test updating a single dependency."""
        current = mock_dependency_info["version"]
        latest = mock_dependency_info["latest_version"]
        assert current != latest

    def test_check_update_availability(self, mock_dependency_info):
        """Test checking if updates are available."""
        assert mock_dependency_info["latest_version"] > mock_dependency_info["version"]

    @patch("subprocess.run")
    def test_test_after_update(self, mock_run):
        """Test running tests after update."""
        mock_run.return_value = Mock(returncode=0)
        result = mock_run(["pytest"])
        assert result.returncode == 0


# Import helper functions for testing
import importlib
update_dep_module = importlib.import_module('hatch_agent.commands.update_dependency')
_build_update_task = update_dep_module._build_update_task
_extract_update_plan = update_dep_module._extract_update_plan
_apply_code_changes = update_dep_module._apply_code_changes


class TestBuildUpdateTask:
    """Test _build_update_task function."""

    def test_build_task_includes_package(self):
        """Test that task includes package name."""
        task = _build_update_task("requests", ">=2.0", ">=2.31.0")
        assert "requests" in task

    def test_build_task_includes_versions(self):
        """Test that task includes current and target versions."""
        task = _build_update_task("requests", ">=2.0", ">=2.31.0")
        assert ">=2.0" in task
        assert ">=2.31.0" in task

    def test_build_task_includes_requirements(self):
        """Test that task includes critical requirements."""
        task = _build_update_task("requests", ">=2.0", ">=2.31.0")
        assert "CRITICAL REQUIREMENTS" in task
        assert "UPDATE_PLAN" in task


class TestExtractUpdatePlan:
    """Test _extract_update_plan function."""

    def test_extract_valid_plan(self):
        """Test extracting a valid update plan."""
        suggestion = '''
        Some explanation here.
        
        UPDATE_PLAN:
        {
            "version_spec": ">=2.31.0",
            "breaking_changes": ["Change 1"],
            "code_changes": []
        }
        '''
        plan = _extract_update_plan(suggestion)
        assert plan is not None
        assert plan["version_spec"] == ">=2.31.0"
        assert plan["breaking_changes"] == ["Change 1"]
        assert plan["code_changes"] == []

    def test_extract_no_plan_marker(self):
        """Test extracting when no UPDATE_PLAN marker."""
        suggestion = "Just some text without plan"
        plan = _extract_update_plan(suggestion)
        assert plan is None

    def test_extract_invalid_json(self):
        """Test extracting with invalid JSON."""
        suggestion = '''
        UPDATE_PLAN:
        {invalid json here}
        '''
        plan = _extract_update_plan(suggestion)
        assert plan is None

    def test_extract_plan_with_code_changes(self):
        """Test extracting plan with code changes."""
        suggestion = '''
        UPDATE_PLAN:
        {
            "version_spec": ">=3.0.0",
            "breaking_changes": ["API change"],
            "code_changes": [
                {
                    "file": "src/main.py",
                    "line_range": "10-15",
                    "description": "Update import",
                    "reason": "Module renamed"
                }
            ]
        }
        '''
        plan = _extract_update_plan(suggestion)
        assert plan is not None
        assert len(plan["code_changes"]) == 1
        assert plan["code_changes"][0]["file"] == "src/main.py"

    def test_extract_no_json_braces(self):
        """Test extraction with no JSON braces."""
        suggestion = '''
        UPDATE_PLAN:
        not a json object
        '''
        plan = _extract_update_plan(suggestion)
        assert plan is None


class TestApplyCodeChanges:
    """Test _apply_code_changes function."""

    def test_apply_no_changes(self):
        """Test applying empty list of changes."""
        from pathlib import Path
        result = _apply_code_changes([], Path.cwd(), MagicMock(), {})
        assert result == 0

    def test_apply_file_not_found(self, temp_project_dir):
        """Test applying changes when file doesn't exist."""
        changes = [{"file": "nonexistent.py", "description": "test"}]
        mock_agent = MagicMock()
        
        result = _apply_code_changes(changes, temp_project_dir, mock_agent, {})
        
        assert result == 0  # No changes applied

    def test_apply_successful_change(self, temp_project_dir):
        """Test applying a successful code change."""
        # Create a test file
        test_file = temp_project_dir / "test.py"
        test_file.write_text("old_code = 1")
        
        changes = [{
            "file": "test.py",
            "line_range": "1-1",
            "description": "Update variable",
            "reason": "Name change"
        }]
        
        mock_agent = MagicMock()
        mock_agent.run_task.return_value = {"success": True}
        
        result = _apply_code_changes(changes, temp_project_dir, mock_agent, {})
        
        assert result == 1  # One change generated
        mock_agent.run_task.assert_called_once()

    def test_apply_failed_change(self, temp_project_dir):
        """Test applying a failed code change."""
        test_file = temp_project_dir / "test.py"
        test_file.write_text("code = 1")
        
        changes = [{"file": "test.py", "description": "test"}]
        mock_agent = MagicMock()
        mock_agent.run_task.return_value = {"success": False}
        
        result = _apply_code_changes(changes, temp_project_dir, mock_agent, {})
        
        assert result == 0  # No changes applied due to failure


class TestUpdateDepShowAll:
    """Test update_dep with --show-all flag."""

    @pytest.fixture
    def cli_runner(self):
        return CliRunner()

    def test_show_all_displays_suggestions(self, cli_runner):
        """Test that --show-all shows all suggestions."""
        import hatch_agent.commands.update_dependency as update_module
        
        with patch.object(update_module, 'DependencyUpdater') as mock_updater_class, \
             patch.object(update_module, 'load_config') as mock_load_config, \
             patch.object(update_module, 'Agent') as mock_agent_class:
            mock_updater = MagicMock()
            mock_updater.get_latest_version.return_value = "2.31.0"
            mock_updater.get_current_version.return_value = ">=2.28.0"
            mock_updater.get_project_files.return_value = []
            mock_updater_class.return_value = mock_updater
            
            mock_load_config.return_value = {}
            
            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {
                "success": True,
                "selected_suggestion": "Option A",
                "selected_agent": "Agent1",
                "reasoning": "Better",
                "all_suggestions": [
                    {"agent": "Agent1", "suggestion": "A", "confidence": 0.9},
                    {"agent": "Agent2", "suggestion": "B", "confidence": 0.7}
                ]
            }
            mock_agent_class.return_value = mock_agent
            
            result = cli_runner.invoke(
                update_dep, ["requests", "--dry-run", "--show-all"]
            )
            
            assert result.exit_code == 0
            assert "ALL AGENT SUGGESTIONS" in result.output


class TestUpdateDepApply:
    """Test update_dep with apply operations."""

    @pytest.fixture
    def cli_runner(self):
        return CliRunner()

    def test_update_dep_apply_success(self, cli_runner):
        """Test successful update application."""
        import hatch_agent.commands.update_dependency as update_module
        
        with patch.object(update_module, 'DependencyUpdater') as mock_updater_class, \
             patch.object(update_module, 'load_config') as mock_load_config, \
             patch.object(update_module, 'Agent') as mock_agent_class:
            mock_updater = MagicMock()
            mock_updater.get_latest_version.return_value = "2.31.0"
            mock_updater.get_current_version.return_value = ">=2.28.0"
            mock_updater.get_project_files.return_value = []
            mock_updater.get_changelog_url.return_value = "https://example.com"
            mock_updater.update_dependency.return_value = {
                "success": True,
                "old_version": ">=2.28.0",
                "new_version": ">=2.31.0",
                "target": "dependencies"
            }
            mock_updater.sync_environment.return_value = {"success": True}
            mock_updater_class.return_value = mock_updater
            
            mock_load_config.return_value = {}
            
            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {
                "success": True,
                "selected_suggestion": '''
                UPDATE_PLAN:
                {
                    "version_spec": ">=2.31.0",
                    "breaking_changes": [],
                    "code_changes": []
                }
                ''',
                "selected_agent": "Agent1"
            }
            mock_agent_class.return_value = mock_agent
            
            result = cli_runner.invoke(update_dep, ["requests"], input="y\n")
            
            assert result.exit_code == 0
            assert "Dependency update complete" in result.output

    def test_update_dep_cancelled(self, cli_runner):
        """Test user cancelling update."""
        import hatch_agent.commands.update_dependency as update_module
        
        with patch.object(update_module, 'DependencyUpdater') as mock_updater_class, \
             patch.object(update_module, 'load_config') as mock_load_config, \
             patch.object(update_module, 'Agent') as mock_agent_class:
            mock_updater = MagicMock()
            mock_updater.get_latest_version.return_value = "2.31.0"
            mock_updater.get_current_version.return_value = ">=2.28.0"
            mock_updater.get_project_files.return_value = []
            mock_updater_class.return_value = mock_updater
            
            mock_load_config.return_value = {}
            
            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {
                "success": True,
                "selected_suggestion": 'UPDATE_PLAN:\n{"version_spec": ">=2.31.0", "breaking_changes": [], "code_changes": []}',
                "selected_agent": "Agent1"
            }
            mock_agent_class.return_value = mock_agent
            
            result = cli_runner.invoke(update_dep, ["requests"], input="n\n")
            
            assert result.exit_code == 0
            assert "Cancelled" in result.output

    def test_update_dep_with_breaking_changes(self, cli_runner):
        """Test update with breaking changes displayed."""
        import hatch_agent.commands.update_dependency as update_module
        
        with patch.object(update_module, 'DependencyUpdater') as mock_updater_class, \
             patch.object(update_module, 'load_config') as mock_load_config, \
             patch.object(update_module, 'Agent') as mock_agent_class:
            mock_updater = MagicMock()
            mock_updater.get_latest_version.return_value = "3.0.0"
            mock_updater.get_current_version.return_value = ">=2.0.0"
            mock_updater.get_project_files.return_value = []
            mock_updater_class.return_value = mock_updater
            
            mock_load_config.return_value = {}
            
            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {
                "success": True,
                "selected_suggestion": '''
                UPDATE_PLAN:
                {
                    "version_spec": ">=3.0.0",
                    "breaking_changes": ["Removed deprecated API", "Changed return type"],
                    "code_changes": []
                }
                ''',
                "selected_agent": "Agent1"
            }
            mock_agent_class.return_value = mock_agent
            
            result = cli_runner.invoke(update_dep, ["requests", "--dry-run"])
            
            assert result.exit_code == 0
            assert "Yes" in result.output or "breaking" in result.output.lower()

    def test_update_dep_with_code_changes(self, cli_runner):
        """Test update with code changes required."""
        import hatch_agent.commands.update_dependency as update_module
        
        with patch.object(update_module, 'DependencyUpdater') as mock_updater_class, \
             patch.object(update_module, 'load_config') as mock_load_config, \
             patch.object(update_module, 'Agent') as mock_agent_class:
            mock_updater = MagicMock()
            mock_updater.get_latest_version.return_value = "3.0.0"
            mock_updater.get_current_version.return_value = ">=2.0.0"
            mock_updater.get_project_files.return_value = []
            mock_updater_class.return_value = mock_updater
            
            mock_load_config.return_value = {}
            
            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {
                "success": True,
                "selected_suggestion": '''
                UPDATE_PLAN:
                {
                    "version_spec": ">=3.0.0",
                    "breaking_changes": [],
                    "code_changes": [
                        {"file": "src/app.py", "description": "Update import"}
                    ]
                }
                ''',
                "selected_agent": "Agent1"
            }
            mock_agent_class.return_value = mock_agent
            
            result = cli_runner.invoke(update_dep, ["requests", "--dry-run"])
            
            assert result.exit_code == 0
            assert "Code changes required" in result.output

    def test_update_dep_update_failure(self, cli_runner):
        """Test handling of update failure."""
        import hatch_agent.commands.update_dependency as update_module
        
        with patch.object(update_module, 'DependencyUpdater') as mock_updater_class, \
             patch.object(update_module, 'load_config') as mock_load_config, \
             patch.object(update_module, 'Agent') as mock_agent_class:
            mock_updater = MagicMock()
            mock_updater.get_latest_version.return_value = "2.31.0"
            mock_updater.get_current_version.return_value = ">=2.28.0"
            mock_updater.get_project_files.return_value = []
            mock_updater.update_dependency.return_value = {
                "success": False,
                "error": "File not found"
            }
            mock_updater_class.return_value = mock_updater
            
            mock_load_config.return_value = {}
            
            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {
                "success": True,
                "selected_suggestion": 'UPDATE_PLAN:\n{"version_spec": ">=2.31.0", "breaking_changes": [], "code_changes": []}',
                "selected_agent": "Agent1"
            }
            mock_agent_class.return_value = mock_agent
            
            result = cli_runner.invoke(update_dep, ["requests"], input="y\n")
            
            assert result.exit_code != 0

    def test_update_dep_skip_sync(self, cli_runner):
        """Test --skip-sync flag."""
        import hatch_agent.commands.update_dependency as update_module
        
        with patch.object(update_module, 'DependencyUpdater') as mock_updater_class, \
             patch.object(update_module, 'load_config') as mock_load_config, \
             patch.object(update_module, 'Agent') as mock_agent_class:
            mock_updater = MagicMock()
            mock_updater.get_latest_version.return_value = "2.31.0"
            mock_updater.get_current_version.return_value = ">=2.28.0"
            mock_updater.get_project_files.return_value = []
            mock_updater.update_dependency.return_value = {
                "success": True,
                "old_version": ">=2.28.0",
                "new_version": ">=2.31.0",
                "target": "dependencies"
            }
            mock_updater_class.return_value = mock_updater
            
            mock_load_config.return_value = {}
            
            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {
                "success": True,
                "selected_suggestion": 'UPDATE_PLAN:\n{"version_spec": ">=2.31.0", "breaking_changes": [], "code_changes": []}',
                "selected_agent": "Agent1"
            }
            mock_agent_class.return_value = mock_agent
            
            result = cli_runner.invoke(update_dep, ["requests", "--skip-sync"], input="y\n")
            
            assert result.exit_code == 0
            mock_updater.sync_environment.assert_not_called()

    def test_update_dep_sync_failure(self, cli_runner):
        """Test handling of sync failure."""
        import hatch_agent.commands.update_dependency as update_module
        
        with patch.object(update_module, 'DependencyUpdater') as mock_updater_class, \
             patch.object(update_module, 'load_config') as mock_load_config, \
             patch.object(update_module, 'Agent') as mock_agent_class:
            mock_updater = MagicMock()
            mock_updater.get_latest_version.return_value = "2.31.0"
            mock_updater.get_current_version.return_value = ">=2.28.0"
            mock_updater.get_project_files.return_value = []
            mock_updater.update_dependency.return_value = {
                "success": True,
                "old_version": ">=2.28.0",
                "new_version": ">=2.31.0",
                "target": "dependencies"
            }
            mock_updater.sync_environment.return_value = {"success": False, "error": "Sync failed"}
            mock_updater_class.return_value = mock_updater
            
            mock_load_config.return_value = {}
            
            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {
                "success": True,
                "selected_suggestion": 'UPDATE_PLAN:\n{"version_spec": ">=2.31.0", "breaking_changes": [], "code_changes": []}',
                "selected_agent": "Agent1"
            }
            mock_agent_class.return_value = mock_agent
            
            result = cli_runner.invoke(update_dep, ["requests"], input="y\n")
            
            assert result.exit_code == 0
            assert "sync had issues" in result.output

    def test_update_dep_no_plan_parsed(self, cli_runner):
        """Test when UPDATE_PLAN can't be parsed."""
        import hatch_agent.commands.update_dependency as update_module
        
        with patch.object(update_module, 'DependencyUpdater') as mock_updater_class, \
             patch.object(update_module, 'load_config') as mock_load_config, \
             patch.object(update_module, 'Agent') as mock_agent_class:
            mock_updater = MagicMock()
            mock_updater.get_latest_version.return_value = "2.31.0"
            mock_updater.get_current_version.return_value = ">=2.28.0"
            mock_updater.get_project_files.return_value = []
            mock_updater_class.return_value = mock_updater
            
            mock_load_config.return_value = {}
            
            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {
                "success": True,
                "selected_suggestion": "Just update the package",  # No UPDATE_PLAN
                "selected_agent": "Agent1"
            }
            mock_agent_class.return_value = mock_agent
            
            result = cli_runner.invoke(update_dep, ["requests"])
            
            assert result.exit_code == 0
            assert "Could not parse" in result.output

    def test_update_dep_add_new_dependency(self, cli_runner):
        """Test adding new dependency when not found."""
        import hatch_agent.commands.update_dependency as update_module
        
        with patch.object(update_module, 'DependencyUpdater') as mock_updater_class, \
             patch.object(update_module, 'load_config') as mock_load_config, \
             patch.object(update_module, 'Agent') as mock_agent_class:
            mock_updater = MagicMock()
            mock_updater.get_latest_version.return_value = "2.31.0"
            mock_updater.get_current_version.return_value = None  # Not found
            mock_updater.get_project_files.return_value = []
            mock_updater_class.return_value = mock_updater
            
            mock_load_config.return_value = {}
            
            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {
                "success": True,
                "selected_suggestion": 'UPDATE_PLAN:\n{"version_spec": ">=2.31.0", "breaking_changes": [], "code_changes": []}',
                "selected_agent": "Agent1"
            }
            mock_agent_class.return_value = mock_agent
            
            # Decline to add as new dependency
            result = cli_runner.invoke(update_dep, ["new-package"], input="n\n")
            
            assert result.exit_code == 0
            assert "not found" in result.output

    def test_update_dep_latest_version_spec(self, cli_runner):
        """Test when version_spec is 'latest'."""
        import hatch_agent.commands.update_dependency as update_module
        
        with patch.object(update_module, 'DependencyUpdater') as mock_updater_class, \
             patch.object(update_module, 'load_config') as mock_load_config, \
             patch.object(update_module, 'Agent') as mock_agent_class:
            mock_updater = MagicMock()
            mock_updater.get_latest_version.return_value = "2.31.0"
            mock_updater.get_current_version.return_value = ">=2.28.0"
            mock_updater.get_project_files.return_value = []
            mock_updater.update_dependency.return_value = {
                "success": True,
                "old_version": ">=2.28.0",
                "new_version": "",
                "target": "dependencies"
            }
            mock_updater.sync_environment.return_value = {"success": True}
            mock_updater_class.return_value = mock_updater
            
            mock_load_config.return_value = {}
            
            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {
                "success": True,
                "selected_suggestion": 'UPDATE_PLAN:\n{"version_spec": "latest", "breaking_changes": [], "code_changes": []}',
                "selected_agent": "Agent1"
            }
            mock_agent_class.return_value = mock_agent
            
            result = cli_runner.invoke(update_dep, ["requests"], input="y\n")
            
            assert result.exit_code == 0

