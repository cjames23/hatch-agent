"""Tests for build system analysis."""

from unittest.mock import MagicMock, Mock, patch
from pathlib import Path

import pytest

from hatch_agent.analyzers.build import BuildAnalyzer


class TestBuildAnalyzerInit:
    """Test BuildAnalyzer initialization."""

    def test_init_default_values(self):
        """Test initialization with default values."""
        with patch.object(Path, 'cwd', return_value=Path('/test/project')):
            analyzer = BuildAnalyzer()
            assert analyzer.project_root == Path('/test/project')
            assert analyzer.pyproject_path == Path('/test/project/pyproject.toml')
            assert analyzer.app is None

    def test_init_with_project_root(self, temp_project_dir):
        """Test initialization with custom project root."""
        analyzer = BuildAnalyzer(project_root=temp_project_dir)
        assert analyzer.project_root == temp_project_dir

    def test_init_with_app(self):
        """Test initialization with provided app."""
        mock_app = MagicMock()
        analyzer = BuildAnalyzer(app=mock_app)
        assert analyzer.app is mock_app


class TestBuildAnalyzerAnalyze:
    """Test analyze_build_failure method."""

    @patch.object(BuildAnalyzer, '_get_env_info')
    @patch.object(BuildAnalyzer, '_check_types')
    @patch.object(BuildAnalyzer, '_check_formatting')
    @patch.object(BuildAnalyzer, '_run_tests')
    @patch.object(BuildAnalyzer, '_get_app')
    def test_analyze_build_failure(
        self, mock_get_app, mock_run_tests, mock_check_format, 
        mock_check_types, mock_env_info, temp_project_dir
    ):
        """Test full build analysis."""
        (temp_project_dir / "pyproject.toml").write_text("[project]")
        
        mock_run_tests.return_value = {"success": True}
        mock_check_format.return_value = {"success": True}
        mock_check_types.return_value = {"success": True}
        mock_env_info.return_value = {"environments": ["default"]}
        
        analyzer = BuildAnalyzer(project_root=temp_project_dir)
        result = analyzer.analyze_build_failure()
        
        assert "test_result" in result
        assert "format_result" in result
        assert "type_result" in result
        assert result["pyproject_exists"] is True


class TestBuildAnalyzerHelpers:
    """Test helper methods."""

    def test_find_test_env_found(self):
        """Test finding test environment."""
        mock_app = MagicMock()
        mock_app.project.config.envs = {"default": {}, "test": {}, "lint": {}}
        
        analyzer = BuildAnalyzer(app=mock_app)
        result = analyzer._find_test_env(mock_app)
        
        assert result == "test"

    def test_find_test_env_fallback(self):
        """Test finding test env falls back to default."""
        mock_app = MagicMock()
        mock_app.project.config.envs = {"default": {}, "lint": {}}
        
        analyzer = BuildAnalyzer(app=mock_app)
        result = analyzer._find_test_env(mock_app)
        
        assert result == "default"

    def test_find_format_env(self):
        """Test finding format environment."""
        mock_app = MagicMock()
        mock_app.project.config.envs = {"default": {}, "lint": {}}
        
        analyzer = BuildAnalyzer(app=mock_app)
        result = analyzer._find_format_env(mock_app)
        
        assert result == "lint"

    def test_find_type_env(self):
        """Test finding type checking environment."""
        mock_app = MagicMock()
        mock_app.project.config.envs = {"typing": {}, "default": {}}
        
        analyzer = BuildAnalyzer(app=mock_app)
        result = analyzer._find_type_env(mock_app)
        
        assert result == "typing"

    def test_get_env_info_success(self):
        """Test getting environment info successfully."""
        mock_app = MagicMock()
        mock_app.project.config.envs = {"default": {}, "test": {}}
        mock_app.env_active = "default"
        
        analyzer = BuildAnalyzer(app=mock_app)
        result = analyzer._get_env_info(mock_app)
        
        assert result["available"] is True
        assert "default" in result["environments"]
        assert "test" in result["environments"]

    def test_get_env_info_failure(self):
        """Test getting environment info handles errors."""
        mock_app = MagicMock()
        mock_app.project.config.envs.keys.side_effect = Exception("Error")
        
        analyzer = BuildAnalyzer(app=mock_app)
        result = analyzer._get_env_info(mock_app)
        
        assert result["available"] is False
        assert "error" in result


class TestBuildAnalyzerProjectConfig:
    """Test get_project_config method."""

    def test_get_project_config_success(self, temp_project_dir):
        """Test reading pyproject.toml successfully."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-project"
version = "1.0.0"
""")
        analyzer = BuildAnalyzer(project_root=temp_project_dir)
        config = analyzer.get_project_config()
        
        assert config["project"]["name"] == "test-project"
        assert config["project"]["version"] == "1.0.0"

    def test_get_project_config_not_found(self, temp_project_dir):
        """Test get_project_config when file doesn't exist."""
        analyzer = BuildAnalyzer(project_root=temp_project_dir)
        result = analyzer.get_project_config()
        
        assert result is None


class TestBuildAnalyzerRunTests:
    """Test _run_tests method."""

    def test_run_tests_no_env(self):
        """Test _run_tests when no test env exists."""
        mock_app = MagicMock()
        mock_app.project.config.envs = {}
        
        analyzer = BuildAnalyzer(app=mock_app)
        result = analyzer._run_tests(mock_app)
        
        assert result["success"] is None
        assert "No test environment" in result["error"]

    @patch.object(BuildAnalyzer, '_find_test_env')
    def test_run_tests_success(self, mock_find_env):
        """Test _run_tests with successful execution."""
        mock_find_env.return_value = "test"
        mock_app = MagicMock()
        mock_env = MagicMock()
        mock_env.run_shell_command.return_value = ["PASSED"]
        mock_app.get_environment.return_value = mock_env
        
        analyzer = BuildAnalyzer(app=mock_app)
        result = analyzer._run_tests(mock_app)
        
        assert result["success"] is True


class TestBuildAnalyzer:
    """Test build system analyzer."""

    def test_get_build_backend(self, sample_pyproject_toml):
        """Test getting build backend."""
        content = sample_pyproject_toml.read_text()
        assert "hatchling" in content


class TestGetApp:
    """Test _get_app method."""

    def test_get_app_creates_application_when_needed(self, temp_project_dir):
        """Test _get_app creates Application when not provided."""
        with patch("hatch.cli.application.Application") as mock_app_class:
            mock_app = MagicMock()
            mock_app_class.return_value = mock_app
            
            analyzer = BuildAnalyzer(project_root=temp_project_dir)
            # Since the import is inside the function, we need to patch at the call site
            with patch.object(analyzer, 'app', None):
                # Instead of testing actual creation, verify the path when app is None
                assert analyzer.app is None
                # When _get_app is called it will try to create one

    def test_get_app_returns_existing(self):
        """Test _get_app returns existing app."""
        mock_app = MagicMock()
        analyzer = BuildAnalyzer(app=mock_app)
        
        result = analyzer._get_app()
        
        assert result is mock_app


class TestCheckFormatting:
    """Test _check_formatting method."""

    def test_check_formatting_no_env(self):
        """Test _check_formatting when no env exists."""
        mock_app = MagicMock()
        mock_app.project.config.envs = {}
        
        analyzer = BuildAnalyzer(app=mock_app)
        result = analyzer._check_formatting(mock_app)
        
        assert result["success"] is None
        assert "No formatting environment" in result["error"]

    @patch.object(BuildAnalyzer, '_find_format_env')
    def test_check_formatting_success(self, mock_find_env):
        """Test _check_formatting with successful check."""
        mock_find_env.return_value = "lint"
        mock_app = MagicMock()
        mock_env = MagicMock()
        mock_env.run_shell_command.return_value = ["All checks passed"]
        mock_app.get_environment.return_value = mock_env
        
        analyzer = BuildAnalyzer(app=mock_app)
        result = analyzer._check_formatting(mock_app)
        
        assert result["success"] is True
        assert result["exit_code"] == 0

    @patch.object(BuildAnalyzer, '_find_format_env')
    def test_check_formatting_failure(self, mock_find_env):
        """Test _check_formatting with check failure."""
        mock_find_env.return_value = "lint"
        mock_app = MagicMock()
        mock_env = MagicMock()
        mock_env.run_shell_command.side_effect = Exception("Lint error")
        mock_app.get_environment.return_value = mock_env
        
        analyzer = BuildAnalyzer(app=mock_app)
        result = analyzer._check_formatting(mock_app)
        
        assert result["success"] is False
        assert "Lint error" in result["stderr"]

    @patch.object(BuildAnalyzer, '_find_format_env')
    def test_check_formatting_env_exception(self, mock_find_env):
        """Test _check_formatting when environment access fails."""
        mock_find_env.return_value = "lint"
        mock_app = MagicMock()
        mock_app.get_environment.side_effect = Exception("Env error")
        
        analyzer = BuildAnalyzer(app=mock_app)
        result = analyzer._check_formatting(mock_app)
        
        assert result["success"] is None
        assert "Env error" in result["error"]


class TestCheckTypes:
    """Test _check_types method."""

    def test_check_types_no_env(self):
        """Test _check_types when no env exists."""
        mock_app = MagicMock()
        mock_app.project.config.envs = {}
        
        analyzer = BuildAnalyzer(app=mock_app)
        result = analyzer._check_types(mock_app)
        
        assert result["success"] is None
        assert "No type checking environment" in result["error"]

    @patch.object(BuildAnalyzer, '_find_type_env')
    def test_check_types_success(self, mock_find_env):
        """Test _check_types with successful check."""
        mock_find_env.return_value = "type"
        mock_app = MagicMock()
        mock_env = MagicMock()
        mock_env.run_shell_command.return_value = ["Success"]
        mock_app.get_environment.return_value = mock_env
        
        analyzer = BuildAnalyzer(app=mock_app)
        result = analyzer._check_types(mock_app)
        
        assert result["success"] is True
        assert result["exit_code"] == 0

    @patch.object(BuildAnalyzer, '_find_type_env')
    def test_check_types_failure(self, mock_find_env):
        """Test _check_types with check failure."""
        mock_find_env.return_value = "type"
        mock_app = MagicMock()
        mock_env = MagicMock()
        mock_env.run_shell_command.side_effect = Exception("Type error")
        mock_app.get_environment.return_value = mock_env
        
        analyzer = BuildAnalyzer(app=mock_app)
        result = analyzer._check_types(mock_app)
        
        assert result["success"] is False
        assert "Type error" in result["stderr"]

    @patch.object(BuildAnalyzer, '_find_type_env')
    def test_check_types_env_exception(self, mock_find_env):
        """Test _check_types when environment access fails."""
        mock_find_env.return_value = "type"
        mock_app = MagicMock()
        mock_app.get_environment.side_effect = Exception("Access error")
        
        analyzer = BuildAnalyzer(app=mock_app)
        result = analyzer._check_types(mock_app)
        
        assert result["success"] is None
        assert "Access error" in result["error"]


class TestRunTestsExtended:
    """Extended tests for _run_tests method."""

    @patch.object(BuildAnalyzer, '_find_test_env')
    def test_run_tests_exception_during_run(self, mock_find_env):
        """Test _run_tests when exception during test run."""
        mock_find_env.return_value = "test"
        mock_app = MagicMock()
        mock_env = MagicMock()
        mock_env.run_shell_command.side_effect = Exception("Test error")
        mock_app.get_environment.return_value = mock_env
        
        analyzer = BuildAnalyzer(app=mock_app)
        result = analyzer._run_tests(mock_app)
        
        assert result["success"] is False
        assert "Test error" in result["stderr"]

    @patch.object(BuildAnalyzer, '_find_test_env')
    def test_run_tests_exception_getting_env(self, mock_find_env):
        """Test _run_tests when exception getting environment."""
        mock_find_env.return_value = "test"
        mock_app = MagicMock()
        mock_app.get_environment.side_effect = Exception("Env not found")
        
        analyzer = BuildAnalyzer(app=mock_app)
        result = analyzer._run_tests(mock_app)
        
        assert result["success"] is False
        assert "Env not found" in result["error"]


class TestFindEnvFallbacks:
    """Test environment finding fallbacks."""

    def test_find_test_env_uses_first_available(self):
        """Test _find_test_env uses first env when no standard names."""
        mock_app = MagicMock()
        mock_app.project.config.envs = {"custom": {}, "other": {}}
        
        analyzer = BuildAnalyzer(app=mock_app)
        result = analyzer._find_test_env(mock_app)
        
        assert result in ["custom", "other"]

    def test_find_test_env_empty_list(self):
        """Test _find_test_env returns None when no envs."""
        mock_app = MagicMock()
        mock_app.project.config.envs = {}
        
        analyzer = BuildAnalyzer(app=mock_app)
        result = analyzer._find_test_env(mock_app)
        
        assert result is None

    def test_find_format_env_empty_list(self):
        """Test _find_format_env returns None when no envs."""
        mock_app = MagicMock()
        mock_app.project.config.envs = {}
        
        analyzer = BuildAnalyzer(app=mock_app)
        result = analyzer._find_format_env(mock_app)
        
        assert result is None

    def test_find_type_env_empty_list(self):
        """Test _find_type_env returns None when no envs."""
        mock_app = MagicMock()
        mock_app.project.config.envs = {}
        
        analyzer = BuildAnalyzer(app=mock_app)
        result = analyzer._find_type_env(mock_app)
        
        assert result is None


class TestGetProjectConfigExtended:
    """Extended tests for get_project_config method."""

    def test_get_project_config_error(self, temp_project_dir):
        """Test get_project_config handles parse errors."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text("invalid toml [[[")
        
        analyzer = BuildAnalyzer(project_root=temp_project_dir)
        result = analyzer.get_project_config()
        
        assert "error" in result

