"""Tests for dependency sync analyzer."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, PropertyMock

import pytest

from hatch_agent.analyzers.sync import DependencySync


class TestDependencySync:
    """Test DependencySync class."""

    @pytest.fixture
    def mock_hatch_app(self):
        """Create a mock Hatch Application."""
        app = MagicMock()
        app.project.config.envs.keys.return_value = ["default", "dev"]
        return app

    @pytest.fixture
    def mock_hatch_env(self):
        """Create a mock Hatch environment."""
        env = MagicMock()
        env.name = "default"
        env.use_uv = False
        env.dependencies = ["requests>=2.28.0", "click>=8.0.0"]
        env.exists.return_value = True
        env.construct_pip_install_command.return_value = ["pip", "install"]
        return env

    @pytest.fixture
    def sync_manager(self, temp_project_dir, mock_hatch_app):
        """Create a DependencySync instance with mocked app."""
        return DependencySync(project_root=temp_project_dir, app=mock_hatch_app)

    def test_init_with_defaults(self):
        """Test DependencySync initialization with defaults."""
        sync = DependencySync()
        assert sync.project_root == Path.cwd()
        assert sync._app is None
        assert sync._env_cache == {}

    def test_init_with_project_root(self, temp_project_dir):
        """Test DependencySync initialization with custom project root."""
        sync = DependencySync(project_root=temp_project_dir)
        assert sync.project_root == temp_project_dir

    def test_get_app_creates_application(self, temp_project_dir):
        """Test that _get_app creates Application when not provided."""
        sync = DependencySync(project_root=temp_project_dir)
        with patch("hatch_agent.analyzers.sync.Application") as mock_app_class:
            mock_app_class.return_value = MagicMock()
            app = sync._get_app()
            mock_app_class.assert_called_once_with(temp_project_dir)
            assert app is not None

    def test_get_app_returns_existing(self, sync_manager, mock_hatch_app):
        """Test that _get_app returns existing Application."""
        app1 = sync_manager._get_app()
        app2 = sync_manager._get_app()
        assert app1 is app2
        assert app1 is mock_hatch_app

    def test_get_installer_pip(self, sync_manager, mock_hatch_app, mock_hatch_env):
        """Test get_installer returns 'pip' when use_uv is False."""
        mock_hatch_env.use_uv = False
        mock_hatch_app.get_environment.return_value = mock_hatch_env
        
        installer = sync_manager.get_installer()
        assert installer == "pip"

    def test_get_installer_uv(self, sync_manager, mock_hatch_app, mock_hatch_env):
        """Test get_installer returns 'uv' when use_uv is True."""
        mock_hatch_env.use_uv = True
        mock_hatch_app.get_environment.return_value = mock_hatch_env
        
        installer = sync_manager.get_installer()
        assert installer == "uv"

    def test_get_dependencies(self, sync_manager, mock_hatch_app, mock_hatch_env):
        """Test get_dependencies returns environment dependencies."""
        mock_hatch_app.get_environment.return_value = mock_hatch_env
        
        deps = sync_manager.get_dependencies()
        assert deps == ["requests>=2.28.0", "click>=8.0.0"]

    def test_get_environment_info(self, sync_manager, mock_hatch_app, mock_hatch_env):
        """Test get_environment_info returns correct info."""
        mock_hatch_app.get_environment.return_value = mock_hatch_env
        
        info = sync_manager.get_environment_info()
        assert info["name"] == "default"
        assert info["installer"] == "pip"
        assert info["exists"] is True
        assert info["dependencies_count"] == 2

    def test_ensure_environment_exists_already_exists(
        self, sync_manager, mock_hatch_app, mock_hatch_env
    ):
        """Test ensure_environment_exists when env already exists."""
        mock_hatch_env.exists.return_value = True
        mock_hatch_app.get_environment.return_value = mock_hatch_env
        
        result = sync_manager.ensure_environment_exists()
        assert result["success"] is True
        assert result["action"] == "exists"
        mock_hatch_env.create.assert_not_called()

    def test_ensure_environment_exists_creates(
        self, sync_manager, mock_hatch_app, mock_hatch_env
    ):
        """Test ensure_environment_exists creates env when missing."""
        mock_hatch_env.exists.return_value = False
        mock_hatch_app.get_environment.return_value = mock_hatch_env
        
        result = sync_manager.ensure_environment_exists()
        assert result["success"] is True
        assert result["action"] == "created"
        mock_hatch_env.create.assert_called_once()


class TestVersionComparison:
    """Test version comparison functionality."""

    @pytest.fixture
    def sync_manager(self, temp_project_dir):
        """Create a DependencySync instance."""
        return DependencySync(project_root=temp_project_dir)

    def test_compare_versions_no_changes(self, sync_manager):
        """Test compare_versions with no changes."""
        before = {"requests": "2.28.0", "click": "8.0.0"}
        after = {"requests": "2.28.0", "click": "8.0.0"}
        
        updates = sync_manager.compare_versions(before, after)
        assert len(updates) == 0

    def test_compare_versions_with_updates(self, sync_manager):
        """Test compare_versions identifies updates."""
        before = {"requests": "2.28.0", "click": "8.0.0"}
        after = {"requests": "2.31.0", "click": "8.0.0"}
        
        updates = sync_manager.compare_versions(before, after)
        assert len(updates) == 1
        assert updates[0]["package"] == "requests"
        assert updates[0]["old_version"] == "2.28.0"
        assert updates[0]["new_version"] == "2.31.0"

    def test_compare_versions_with_new_packages(self, sync_manager):
        """Test compare_versions identifies new packages."""
        before = {"requests": "2.28.0"}
        after = {"requests": "2.28.0", "httpx": "0.24.0"}
        
        updates = sync_manager.compare_versions(before, after)
        assert len(updates) == 1
        assert updates[0]["package"] == "httpx"
        assert updates[0]["old_version"] is None
        assert updates[0]["new_version"] == "0.24.0"
        assert updates[0]["change_type"] == "new"

    def test_classify_version_change_major(self, sync_manager):
        """Test _classify_version_change for major updates."""
        result = sync_manager._classify_version_change("1.0.0", "2.0.0")
        assert result == "major"

    def test_classify_version_change_minor(self, sync_manager):
        """Test _classify_version_change for minor updates."""
        result = sync_manager._classify_version_change("1.0.0", "1.1.0")
        assert result == "minor"

    def test_classify_version_change_patch(self, sync_manager):
        """Test _classify_version_change for patch updates."""
        result = sync_manager._classify_version_change("1.0.0", "1.0.1")
        assert result == "patch"

    def test_classify_version_change_unknown(self, sync_manager):
        """Test _classify_version_change for unparseable versions."""
        result = sync_manager._classify_version_change("invalid", "also-invalid")
        assert result == "unknown"

    def test_parse_version_standard(self, sync_manager):
        """Test _parse_version with standard semver."""
        result = sync_manager._parse_version("1.2.3")
        assert result == (1, 2, 3)

    def test_parse_version_two_parts(self, sync_manager):
        """Test _parse_version with two-part version."""
        result = sync_manager._parse_version("1.2")
        assert result == (1, 2, 0)

    def test_parse_version_single_part(self, sync_manager):
        """Test _parse_version with single-part version."""
        result = sync_manager._parse_version("1")
        assert result == (1, 0, 0)

    def test_parse_version_with_suffix(self, sync_manager):
        """Test _parse_version with post/dev suffix."""
        result = sync_manager._parse_version("1.2.3.post1")
        assert result == (1, 2, 3)

    def test_parse_version_invalid(self, sync_manager):
        """Test _parse_version with invalid version."""
        result = sync_manager._parse_version("invalid-version")
        assert result is None


class TestUpgradeExecution:
    """Test upgrade execution functionality."""

    @pytest.fixture
    def mock_hatch_app(self):
        """Create a mock Hatch Application."""
        app = MagicMock()
        app.project.config.envs.keys.return_value = ["default"]
        return app

    @pytest.fixture
    def mock_hatch_env(self):
        """Create a mock Hatch environment."""
        env = MagicMock()
        env.name = "default"
        env.use_uv = False
        env.dependencies = ["requests>=2.28.0"]
        env.exists.return_value = True
        env.construct_pip_install_command.return_value = ["pip", "install"]
        
        # Mock platform.run_command
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b"Successfully installed requests-2.31.0"
        mock_result.stderr = b""
        env.platform.run_command.return_value = mock_result
        
        # Mock command_context
        env.command_context.return_value.__enter__ = MagicMock()
        env.command_context.return_value.__exit__ = MagicMock()
        
        return env

    @pytest.fixture
    def sync_manager(self, temp_project_dir, mock_hatch_app):
        """Create a DependencySync instance with mocked app."""
        return DependencySync(project_root=temp_project_dir, app=mock_hatch_app)

    def test_run_upgrade_success(self, sync_manager, mock_hatch_app, mock_hatch_env):
        """Test successful upgrade execution."""
        mock_hatch_app.get_environment.return_value = mock_hatch_env
        
        result = sync_manager.run_upgrade()
        assert result["success"] is True
        assert result["action"] == "upgraded"

    def test_run_upgrade_dry_run(self, sync_manager, mock_hatch_app, mock_hatch_env):
        """Test dry-run upgrade."""
        mock_hatch_app.get_environment.return_value = mock_hatch_env
        
        result = sync_manager.run_upgrade(dry_run=True)
        assert result["success"] is True
        assert result["action"] == "dry_run"

    def test_run_upgrade_no_dependencies(self, sync_manager, mock_hatch_app, mock_hatch_env):
        """Test upgrade with no dependencies."""
        mock_hatch_env.dependencies = []
        mock_hatch_app.get_environment.return_value = mock_hatch_env
        
        result = sync_manager.run_upgrade()
        assert result["success"] is True
        assert result["action"] == "none"

    def test_run_upgrade_specific_packages(
        self, sync_manager, mock_hatch_app, mock_hatch_env
    ):
        """Test upgrade with specific packages."""
        mock_hatch_app.get_environment.return_value = mock_hatch_env
        
        result = sync_manager.run_upgrade(packages=["requests"])
        assert result["success"] is True
        mock_hatch_env.construct_pip_install_command.assert_called()

    def test_run_upgrade_failure(self, sync_manager, mock_hatch_app, mock_hatch_env):
        """Test failed upgrade execution."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = b""
        mock_result.stderr = b"Error: Package not found"
        mock_hatch_env.platform.run_command.return_value = mock_result
        mock_hatch_app.get_environment.return_value = mock_hatch_env
        
        result = sync_manager.run_upgrade()
        assert result["success"] is False
        assert result["action"] == "failed"
        assert "Error" in result.get("error", "")


class TestEnvironmentCaching:
    """Test environment caching behavior."""

    @pytest.fixture
    def mock_hatch_app(self):
        """Create a mock Hatch Application."""
        app = MagicMock()
        app.project.config.envs.keys.return_value = ["default", "dev"]
        return app

    @pytest.fixture
    def sync_manager(self, temp_project_dir, mock_hatch_app):
        """Create a DependencySync instance."""
        return DependencySync(project_root=temp_project_dir, app=mock_hatch_app)

    def test_environment_is_cached(self, sync_manager, mock_hatch_app):
        """Test that environment instances are cached."""
        mock_env = MagicMock()
        mock_env.name = "default"
        mock_env.use_uv = False
        mock_env.dependencies = []
        mock_hatch_app.get_environment.return_value = mock_env
        
        # Call twice
        env1 = sync_manager._get_environment()
        env2 = sync_manager._get_environment()
        
        # Should only call get_environment once due to caching
        assert mock_hatch_app.get_environment.call_count == 1
        assert env1 is env2

    def test_different_envs_not_shared(self, sync_manager, mock_hatch_app):
        """Test that different environments are cached separately."""
        mock_env_default = MagicMock()
        mock_env_default.name = "default"
        mock_env_dev = MagicMock()
        mock_env_dev.name = "dev"
        
        mock_hatch_app.get_environment.side_effect = [mock_env_default, mock_env_dev]
        
        env1 = sync_manager._get_environment("default")
        env2 = sync_manager._get_environment("dev")
        
        assert env1.name == "default"
        assert env2.name == "dev"
        assert env1 is not env2
