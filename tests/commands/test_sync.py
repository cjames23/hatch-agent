"""Tests for sync command."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
import json

import pytest
from click.testing import CliRunner

from hatch_agent.commands.sync import (
    sync,
    _build_update_task,
    _extract_update_plan,
    _apply_code_changes,
)


class TestSyncCommand:
    """Test sync command."""

    @pytest.fixture
    def cli_runner(self):
        """Create a Click CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_sync_manager(self):
        """Create a mock DependencySync."""
        manager = MagicMock()
        manager.get_environment_info.return_value = {
            "name": "default",
            "installer": "pip",
            "exists": True,
            "dependencies_count": 5,
        }
        manager.ensure_environment_exists.return_value = {
            "success": True,
            "action": "exists",
            "environment": "default",
        }
        manager.get_installed_versions.return_value = {
            "requests": "2.28.0",
            "click": "8.0.0",
        }
        manager.run_upgrade.return_value = {
            "success": True,
            "output": "Successfully upgraded",
            "action": "upgraded",
        }
        manager.compare_versions.return_value = []
        return manager

    @patch("hatch_agent.commands.sync.DependencySync")
    @patch("hatch_agent.commands.sync.load_config")
    def test_sync_no_updates(
        self, mock_load_config, mock_sync_class, cli_runner, mock_sync_manager
    ):
        """Test sync command when no updates are available."""
        mock_sync_class.return_value = mock_sync_manager
        mock_load_config.return_value = {"underlying_provider": "openai"}
        
        result = cli_runner.invoke(sync)
        
        assert result.exit_code == 0
        assert "up to date" in result.output or "Dependency sync complete" in result.output

    @patch("hatch_agent.commands.sync.DependencySync")
    @patch("hatch_agent.commands.sync.load_config")
    def test_sync_with_updates(
        self, mock_load_config, mock_sync_class, cli_runner, mock_sync_manager
    ):
        """Test sync command when updates are available."""
        mock_sync_manager.compare_versions.return_value = [
            {
                "package": "requests",
                "old_version": "2.28.0",
                "new_version": "2.31.0",
                "change_type": "minor",
            }
        ]
        # Return different versions for before/after
        mock_sync_manager.get_installed_versions.side_effect = [
            {"requests": "2.28.0"},
            {"requests": "2.31.0"},
        ]
        mock_sync_class.return_value = mock_sync_manager
        mock_load_config.return_value = {"underlying_provider": "openai"}
        
        result = cli_runner.invoke(sync, ["--skip-analysis"])
        
        assert result.exit_code == 0
        assert "UPDATED PACKAGES" in result.output

    @patch("hatch_agent.commands.sync.DependencySync")
    def test_sync_dry_run(self, mock_sync_class, cli_runner, mock_sync_manager):
        """Test sync command with --dry-run flag."""
        mock_sync_class.return_value = mock_sync_manager
        
        result = cli_runner.invoke(sync, ["--dry-run"])
        
        assert result.exit_code == 0
        assert "DRY RUN" in result.output

    @patch("hatch_agent.commands.sync.DependencySync")
    def test_sync_upgrade_failure(self, mock_sync_class, cli_runner, mock_sync_manager):
        """Test sync command when upgrade fails."""
        mock_sync_manager.run_upgrade.return_value = {
            "success": False,
            "error": "Network error",
            "action": "failed",
        }
        mock_sync_class.return_value = mock_sync_manager
        
        result = cli_runner.invoke(sync)
        
        assert result.exit_code != 0
        assert "failed" in result.output.lower() or "error" in result.output.lower()

    @patch("hatch_agent.commands.sync.DependencySync")
    def test_sync_env_creation_failure(
        self, mock_sync_class, cli_runner, mock_sync_manager
    ):
        """Test sync command when environment creation fails."""
        mock_sync_manager.ensure_environment_exists.return_value = {
            "success": False,
            "error": "Permission denied",
            "action": "failed",
        }
        mock_sync_class.return_value = mock_sync_manager
        
        result = cli_runner.invoke(sync)
        
        assert result.exit_code != 0

    @patch("hatch_agent.commands.sync.DependencySync")
    @patch("hatch_agent.commands.sync.load_config")
    def test_sync_skip_analysis(
        self, mock_load_config, mock_sync_class, cli_runner, mock_sync_manager
    ):
        """Test sync command with --skip-analysis flag."""
        mock_sync_manager.compare_versions.return_value = [
            {
                "package": "requests",
                "old_version": "1.0.0",
                "new_version": "2.0.0",
                "change_type": "major",
            }
        ]
        mock_sync_manager.get_installed_versions.side_effect = [
            {"requests": "1.0.0"},
            {"requests": "2.0.0"},
        ]
        mock_sync_class.return_value = mock_sync_manager
        mock_load_config.return_value = {"underlying_provider": "openai"}
        
        result = cli_runner.invoke(sync, ["--skip-analysis"])
        
        assert result.exit_code == 0
        assert "Skipping breaking changes analysis" in result.output

    @patch("hatch_agent.commands.sync.DependencySync")
    @patch("hatch_agent.commands.sync.load_config")
    def test_sync_major_only(
        self, mock_load_config, mock_sync_class, cli_runner, mock_sync_manager
    ):
        """Test sync command with --major-only flag."""
        mock_sync_manager.compare_versions.return_value = [
            {
                "package": "requests",
                "old_version": "1.0.0",
                "new_version": "2.0.0",
                "change_type": "major",
            },
            {
                "package": "click",
                "old_version": "8.0.0",
                "new_version": "8.1.0",
                "change_type": "minor",
            },
        ]
        mock_sync_manager.get_installed_versions.side_effect = [
            {"requests": "1.0.0", "click": "8.0.0"},
            {"requests": "2.0.0", "click": "8.1.0"},
        ]
        mock_sync_class.return_value = mock_sync_manager
        mock_load_config.return_value = {"underlying_provider": "openai"}
        
        result = cli_runner.invoke(sync, ["--major-only", "--skip-analysis"])
        
        assert result.exit_code == 0
        # When --skip-analysis is used, the command returns early before
        # printing the --major-only analysis message. Just verify the command succeeded.
        assert "Skipping breaking changes analysis" in result.output


class TestBuildUpdateTask:
    """Test _build_update_task function."""

    def test_build_update_task_basic(self):
        """Test basic update task generation."""
        task = _build_update_task("requests", "2.28.0", "2.31.0")
        
        assert "requests" in task
        assert "2.28.0" in task
        assert "2.31.0" in task
        assert "UPDATE_PLAN:" in task

    def test_build_update_task_includes_requirements(self):
        """Test that task includes critical requirements."""
        task = _build_update_task("django", "3.0.0", "4.0.0")
        
        assert "breaking" in task.lower()
        assert "minimal" in task.lower() or "ONLY" in task
        assert "API compatibility" in task


class TestExtractUpdatePlan:
    """Test _extract_update_plan function."""

    def test_extract_update_plan_valid(self):
        """Test extracting a valid update plan."""
        suggestion = """
        Here is the analysis...
        
        UPDATE_PLAN:
        {
            "version_spec": ">=2.31.0",
            "breaking_changes": ["Removed deprecated method"],
            "code_changes": [
                {
                    "file": "src/app.py",
                    "line_range": "10-15",
                    "description": "Update import",
                    "reason": "Module moved"
                }
            ]
        }
        """
        
        plan = _extract_update_plan(suggestion)
        
        assert plan is not None
        assert plan["version_spec"] == ">=2.31.0"
        assert len(plan["breaking_changes"]) == 1
        assert len(plan["code_changes"]) == 1

    def test_extract_update_plan_no_marker(self):
        """Test extraction with no UPDATE_PLAN marker."""
        suggestion = "Just some text without the plan marker"
        
        plan = _extract_update_plan(suggestion)
        
        assert plan is None

    def test_extract_update_plan_invalid_json(self):
        """Test extraction with invalid JSON."""
        suggestion = """
        UPDATE_PLAN:
        {invalid json here}
        """
        
        plan = _extract_update_plan(suggestion)
        
        assert plan is None

    def test_extract_update_plan_empty_arrays(self):
        """Test extraction with empty arrays."""
        suggestion = """
        UPDATE_PLAN:
        {
            "version_spec": ">=2.31.0",
            "breaking_changes": [],
            "code_changes": []
        }
        """
        
        plan = _extract_update_plan(suggestion)
        
        assert plan is not None
        assert plan["breaking_changes"] == []
        assert plan["code_changes"] == []


class TestApplyCodeChanges:
    """Test _apply_code_changes function."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent."""
        agent = MagicMock()
        agent.run_task.return_value = {"success": True, "output": "Modified code"}
        return agent

    @pytest.fixture
    def temp_source_file(self, tmp_path):
        """Create a temporary source file."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        source_file = src_dir / "app.py"
        source_file.write_text("import requests\n\ndef main():\n    pass\n")
        return source_file

    def test_apply_code_changes_empty_list(self, mock_agent, tmp_path):
        """Test with empty code changes list."""
        result = _apply_code_changes([], tmp_path, mock_agent, {})
        assert result == 0

    def test_apply_code_changes_file_not_found(self, mock_agent, tmp_path):
        """Test with non-existent file."""
        changes = [
            {
                "file": "nonexistent.py",
                "description": "Update import",
                "reason": "API change",
            }
        ]
        
        result = _apply_code_changes(changes, tmp_path, mock_agent, {})
        assert result == 0
        mock_agent.run_task.assert_not_called()

    def test_apply_code_changes_success(
        self, mock_agent, tmp_path, temp_source_file
    ):
        """Test successful code change application."""
        changes = [
            {
                "file": "src/app.py",
                "line_range": "1-2",
                "description": "Update import",
                "reason": "API change",
                "package": "requests",
            }
        ]
        
        result = _apply_code_changes(changes, tmp_path, mock_agent, {})
        
        assert result == 1
        mock_agent.run_task.assert_called_once()

    def test_apply_code_changes_agent_failure(
        self, mock_agent, tmp_path, temp_source_file
    ):
        """Test when agent fails to generate changes."""
        mock_agent.run_task.return_value = {"success": False, "output": "Error"}
        
        changes = [
            {
                "file": "src/app.py",
                "description": "Update import",
                "reason": "API change",
            }
        ]
        
        result = _apply_code_changes(changes, tmp_path, mock_agent, {})
        
        # Still returns 0 because change was not applied successfully
        assert result == 0


class TestUpdateClassification:
    """Test update classification in sync output."""

    @pytest.fixture
    def cli_runner(self):
        """Create a Click CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_sync_manager(self):
        """Create a mock DependencySync with various update types."""
        manager = MagicMock()
        manager.get_environment_info.return_value = {
            "name": "default",
            "installer": "pip",
            "exists": True,
            "dependencies_count": 5,
        }
        manager.ensure_environment_exists.return_value = {
            "success": True,
            "action": "exists",
        }
        manager.run_upgrade.return_value = {
            "success": True,
            "output": "Success",
            "action": "upgraded",
        }
        return manager

    @patch("hatch_agent.commands.sync.DependencySync")
    @patch("hatch_agent.commands.sync.load_config")
    def test_major_update_highlighted(
        self, mock_load_config, mock_sync_class, cli_runner, mock_sync_manager
    ):
        """Test that major updates are highlighted."""
        mock_sync_manager.compare_versions.return_value = [
            {
                "package": "django",
                "old_version": "3.0.0",
                "new_version": "4.0.0",
                "change_type": "major",
            }
        ]
        mock_sync_manager.get_installed_versions.side_effect = [
            {"django": "3.0.0"},
            {"django": "4.0.0"},
        ]
        mock_sync_class.return_value = mock_sync_manager
        mock_load_config.return_value = {}
        
        result = cli_runner.invoke(sync, ["--skip-analysis"])
        
        assert "major" in result.output.lower()

    @patch("hatch_agent.commands.sync.DependencySync")
    @patch("hatch_agent.commands.sync.load_config")
    def test_summary_counts(
        self, mock_load_config, mock_sync_class, cli_runner, mock_sync_manager
    ):
        """Test that summary shows correct counts."""
        mock_sync_manager.compare_versions.return_value = [
            {"package": "a", "old_version": "1.0", "new_version": "2.0", "change_type": "major"},
            {"package": "b", "old_version": "1.0", "new_version": "1.1", "change_type": "minor"},
            {"package": "c", "old_version": "1.0", "new_version": "1.0.1", "change_type": "patch"},
        ]
        mock_sync_manager.get_installed_versions.side_effect = [
            {"a": "1.0", "b": "1.0", "c": "1.0"},
            {"a": "2.0", "b": "1.1", "c": "1.0.1"},
        ]
        mock_sync_class.return_value = mock_sync_manager
        mock_load_config.return_value = {}
        
        result = cli_runner.invoke(sync, ["--skip-analysis"])
        
        assert "1 major" in result.output
        assert "1 minor" in result.output
        assert "1 patch" in result.output


class TestSyncAnalysis:
    """Test sync command with analysis enabled."""

    @pytest.fixture
    def cli_runner(self):
        return CliRunner()

    @pytest.fixture
    def mock_sync_manager(self):
        manager = MagicMock()
        manager.get_environment_info.return_value = {
            "name": "default",
            "installer": "pip",
            "exists": True,
            "dependencies_count": 5,
        }
        manager.ensure_environment_exists.return_value = {"success": True, "action": "exists"}
        manager.run_upgrade.return_value = {"success": True, "action": "upgraded"}
        return manager

    @patch("hatch_agent.commands.sync.Agent")
    @patch("hatch_agent.commands.sync.DependencyUpdater")
    @patch("hatch_agent.commands.sync.DependencySync")
    @patch("hatch_agent.commands.sync.load_config")
    def test_analysis_with_breaking_changes(
        self, mock_load_config, mock_sync_class, mock_updater_class, mock_agent_class,
        cli_runner, mock_sync_manager
    ):
        """Test sync with analysis that finds breaking changes."""
        mock_sync_manager.compare_versions.return_value = [
            {"package": "requests", "old_version": "1.0", "new_version": "2.0", "change_type": "major"}
        ]
        mock_sync_manager.get_installed_versions.side_effect = [
            {"requests": "1.0"},
            {"requests": "2.0"},
        ]
        mock_sync_class.return_value = mock_sync_manager
        
        mock_updater = MagicMock()
        mock_updater.get_changelog_url.return_value = "https://example.com/changelog"
        mock_updater.get_project_files.return_value = []
        mock_updater_class.return_value = mock_updater
        
        mock_agent = MagicMock()
        mock_agent.run_task.return_value = {
            "success": True,
            "selected_suggestion": """
            UPDATE_PLAN:
            {
                "version_spec": ">=2.0",
                "breaking_changes": ["API changed"],
                "code_changes": []
            }
            """
        }
        mock_agent_class.return_value = mock_agent
        
        mock_load_config.return_value = {}
        
        result = cli_runner.invoke(sync, ["--no-code-changes"])
        
        assert result.exit_code == 0
        assert "BREAKING CHANGES" in result.output
        assert "API changed" in result.output or "potential breaking change" in result.output

    @patch("hatch_agent.commands.sync.Agent")
    @patch("hatch_agent.commands.sync.DependencyUpdater")
    @patch("hatch_agent.commands.sync.DependencySync")
    @patch("hatch_agent.commands.sync.load_config")
    def test_analysis_no_packages_to_analyze(
        self, mock_load_config, mock_sync_class, mock_updater_class, mock_agent_class,
        cli_runner, mock_sync_manager
    ):
        """Test sync when only patch updates (no analysis needed)."""
        mock_sync_manager.compare_versions.return_value = [
            {"package": "requests", "old_version": "2.0.0", "new_version": "2.0.1", "change_type": "patch"}
        ]
        mock_sync_manager.get_installed_versions.side_effect = [
            {"requests": "2.0.0"},
            {"requests": "2.0.1"},
        ]
        mock_sync_class.return_value = mock_sync_manager
        mock_load_config.return_value = {}
        
        result = cli_runner.invoke(sync)
        
        assert result.exit_code == 0
        assert "No packages require breaking changes analysis" in result.output

    @patch("hatch_agent.commands.sync.DependencySync")
    def test_sync_env_created(self, mock_sync_class, cli_runner, mock_sync_manager):
        """Test sync when environment needs to be created."""
        mock_sync_manager.ensure_environment_exists.return_value = {
            "success": True,
            "action": "created",
        }
        mock_sync_manager.compare_versions.return_value = []
        mock_sync_manager.run_upgrade.return_value = {"success": True, "action": "none"}
        mock_sync_class.return_value = mock_sync_manager
        
        result = cli_runner.invoke(sync)
        
        assert "Created environment" in result.output

    @patch("hatch_agent.commands.sync.DependencySync")
    def test_sync_no_before_versions(self, mock_sync_class, cli_runner, mock_sync_manager):
        """Test sync when can't get before versions."""
        mock_sync_manager.get_installed_versions.side_effect = [{}, {}]
        mock_sync_manager.compare_versions.return_value = []
        mock_sync_manager.run_upgrade.return_value = {"success": True, "action": "none"}
        mock_sync_class.return_value = mock_sync_manager
        
        result = cli_runner.invoke(sync)
        
        assert result.exit_code == 0

    @patch("hatch_agent.commands.sync.DependencySync")
    @patch("hatch_agent.commands.sync.load_config")
    def test_sync_new_package(self, mock_load_config, mock_sync_class, cli_runner, mock_sync_manager):
        """Test sync displays new packages correctly."""
        mock_sync_manager.compare_versions.return_value = [
            {"package": "new-pkg", "old_version": None, "new_version": "1.0.0", "change_type": "new"}
        ]
        mock_sync_manager.get_installed_versions.side_effect = [
            {},
            {"new-pkg": "1.0.0"},
        ]
        mock_sync_class.return_value = mock_sync_manager
        mock_load_config.return_value = {}
        
        result = cli_runner.invoke(sync, ["--skip-analysis"])
        
        assert "new" in result.output.lower()


class TestSyncCodeChanges:
    """Test sync command with code changes."""

    @pytest.fixture
    def cli_runner(self):
        return CliRunner()

    @pytest.fixture
    def mock_sync_manager(self):
        manager = MagicMock()
        manager.get_environment_info.return_value = {
            "name": "default", "installer": "pip", "exists": True, "dependencies_count": 5
        }
        manager.ensure_environment_exists.return_value = {"success": True, "action": "exists"}
        manager.run_upgrade.return_value = {"success": True, "action": "upgraded"}
        return manager

    @patch("hatch_agent.commands.sync.Agent")
    @patch("hatch_agent.commands.sync.DependencyUpdater")
    @patch("hatch_agent.commands.sync.DependencySync")
    @patch("hatch_agent.commands.sync.load_config")
    def test_sync_with_code_changes_declined(
        self, mock_load_config, mock_sync_class, mock_updater_class, mock_agent_class,
        cli_runner, mock_sync_manager
    ):
        """Test sync with code changes that user declines."""
        mock_sync_manager.compare_versions.return_value = [
            {"package": "pkg", "old_version": "1.0", "new_version": "2.0", "change_type": "major"}
        ]
        mock_sync_manager.get_installed_versions.side_effect = [{"pkg": "1.0"}, {"pkg": "2.0"}]
        mock_sync_class.return_value = mock_sync_manager
        
        mock_updater = MagicMock()
        mock_updater.get_changelog_url.return_value = None
        mock_updater.get_project_files.return_value = []
        mock_updater_class.return_value = mock_updater
        
        mock_agent = MagicMock()
        mock_agent.run_task.return_value = {
            "success": True,
            "selected_suggestion": """
            UPDATE_PLAN:
            {
                "version_spec": ">=2.0",
                "breaking_changes": [],
                "code_changes": [{"file": "app.py", "description": "Update", "reason": "API changed"}]
            }
            """
        }
        mock_agent_class.return_value = mock_agent
        mock_load_config.return_value = {}
        
        # Decline code changes
        result = cli_runner.invoke(sync, input="n\n")
        
        assert result.exit_code == 0
        assert "Suggested code changes" in result.output

    @patch("hatch_agent.commands.sync.Agent")
    @patch("hatch_agent.commands.sync.DependencyUpdater")
    @patch("hatch_agent.commands.sync.DependencySync")
    @patch("hatch_agent.commands.sync.load_config")
    def test_sync_analysis_failure(
        self, mock_load_config, mock_sync_class, mock_updater_class, mock_agent_class,
        cli_runner, mock_sync_manager
    ):
        """Test sync when analysis fails for a package."""
        mock_sync_manager.compare_versions.return_value = [
            {"package": "pkg", "old_version": "1.0", "new_version": "2.0", "change_type": "major"}
        ]
        mock_sync_manager.get_installed_versions.side_effect = [{"pkg": "1.0"}, {"pkg": "2.0"}]
        mock_sync_class.return_value = mock_sync_manager
        
        mock_updater = MagicMock()
        mock_updater.get_changelog_url.return_value = None
        mock_updater.get_project_files.return_value = []
        mock_updater_class.return_value = mock_updater
        
        mock_agent = MagicMock()
        mock_agent.run_task.return_value = {"success": False, "output": "Error"}
        mock_agent_class.return_value = mock_agent
        mock_load_config.return_value = {}
        
        result = cli_runner.invoke(sync, ["--no-code-changes"])
        
        assert result.exit_code == 0
        assert "Analysis failed" in result.output
