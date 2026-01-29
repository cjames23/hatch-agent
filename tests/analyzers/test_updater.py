"""Tests for dependency updater."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from hatch_agent.analyzers.updater import DependencyUpdater


class TestDependencyUpdaterInit:
    """Test DependencyUpdater initialization."""

    def test_init_default_values(self):
        """Test initialization with default values."""
        with patch.object(Path, "cwd", return_value=Path("/test/project")):
            updater = DependencyUpdater()
            assert updater.project_root == Path("/test/project")
            assert updater.pyproject_path == Path("/test/project/pyproject.toml")

    def test_init_with_project_root(self, temp_project_dir):
        """Test initialization with custom project root."""
        updater = DependencyUpdater(project_root=temp_project_dir)
        assert updater.project_root == temp_project_dir


class TestDependencyUpdaterLatestVersion:
    """Test get_latest_version method."""

    def test_get_latest_version_success(self):
        """Test getting latest version from PyPI."""
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"info": {"version": "2.31.0"}}
            mock_get.return_value = mock_response

            updater = DependencyUpdater()
            version = updater.get_latest_version("requests")

            assert version == "2.31.0"

    def test_get_latest_version_not_found(self):
        """Test get_latest_version when package not found."""
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response

            updater = DependencyUpdater()
            version = updater.get_latest_version("nonexistent-package")

            assert version is None

    def test_get_latest_version_network_error(self):
        """Test get_latest_version handles network errors."""
        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("Network error")

            updater = DependencyUpdater()
            version = updater.get_latest_version("requests")

            assert version is None


class TestDependencyUpdaterChangelogUrl:
    """Test get_changelog_url method."""

    def test_get_changelog_url_found(self):
        """Test getting changelog URL from PyPI."""
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "info": {"project_urls": {"Changelog": "https://example.com/changelog"}}
            }
            mock_get.return_value = mock_response

            updater = DependencyUpdater()
            url = updater.get_changelog_url("some-package")

            assert url == "https://example.com/changelog"

    def test_get_changelog_url_github_fallback(self):
        """Test changelog URL falls back to GitHub releases."""
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "info": {"home_page": "https://github.com/user/repo", "project_urls": {}}
            }
            mock_get.return_value = mock_response

            updater = DependencyUpdater()
            url = updater.get_changelog_url("some-package")

            assert url == "https://github.com/user/repo/releases"


class TestDependencyUpdaterUpdateDep:
    """Test update_dependency method."""

    def test_update_dependency_main_deps(self, temp_project_dir):
        """Test updating dependency in main dependencies."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"
dependencies = ["requests>=2.0.0"]
""")
        updater = DependencyUpdater(project_root=temp_project_dir)
        result = updater.update_dependency("requests", ">=2.31.0")

        assert result["success"] is True
        assert result["old_version"] == ">=2.0.0"
        assert result["new_version"] == ">=2.31.0"

    def test_update_dependency_optional_deps(self, temp_project_dir):
        """Test updating dependency in optional dependencies."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"

[project.optional-dependencies]
dev = ["pytest>=7.0"]
""")
        updater = DependencyUpdater(project_root=temp_project_dir)
        result = updater.update_dependency("pytest", ">=8.0", optional_group="dev")

        assert result["success"] is True
        assert "dev" in result["target"]

    def test_update_dependency_not_found(self, temp_project_dir):
        """Test updating non-existent dependency."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text("[project]\ndependencies = []")

        updater = DependencyUpdater(project_root=temp_project_dir)
        result = updater.update_dependency("nonexistent", ">=1.0")

        assert result["success"] is False
        assert "not found" in result["error"]


class TestDependencyUpdaterHelpers:
    """Test helper methods."""

    def test_matches_package(self, temp_project_dir):
        """Test package name matching."""
        updater = DependencyUpdater(project_root=temp_project_dir)

        assert updater._matches_package("requests>=2.0", "requests") is True
        assert updater._matches_package("Requests>=2.0", "requests") is True
        assert updater._matches_package("requests[socks]>=2.0", "requests") is True
        assert updater._matches_package("click>=8.0", "requests") is False

    def test_extract_package_name(self, temp_project_dir):
        """Test extracting package name from dep string."""
        updater = DependencyUpdater(project_root=temp_project_dir)

        assert updater._extract_package_name("requests>=2.0") == "requests"
        assert updater._extract_package_name("requests[socks]>=2.0") == "requests"
        assert updater._extract_package_name("click") == "click"

    def test_extract_version(self, temp_project_dir):
        """Test extracting version from dep string."""
        updater = DependencyUpdater(project_root=temp_project_dir)

        assert updater._extract_version("requests>=2.0") == ">=2.0"
        assert updater._extract_version("click==8.0.0") == "==8.0.0"
        assert updater._extract_version("package") is None


class TestDependencyUpdaterGetCurrentVersion:
    """Test get_current_version method."""

    def test_get_current_version_main(self, temp_project_dir):
        """Test getting current version from main deps."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = ["requests>=2.28.0"]
""")
        updater = DependencyUpdater(project_root=temp_project_dir)
        version = updater.get_current_version("requests")

        assert version == ">=2.28.0"

    def test_get_current_version_optional(self, temp_project_dir):
        """Test getting current version from optional deps."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text("""
[project]

[project.optional-dependencies]
dev = ["pytest>=7.0"]
""")
        updater = DependencyUpdater(project_root=temp_project_dir)
        version = updater.get_current_version("pytest")

        assert version == ">=7.0"


class TestDependencyUpdaterProjectFiles:
    """Test get_project_files method."""

    def test_get_project_files(self, temp_project_dir):
        """Test getting project source files."""
        src_dir = temp_project_dir / "src"
        src_dir.mkdir()
        (src_dir / "app.py").write_text("# app")
        (src_dir / "utils.py").write_text("# utils")

        updater = DependencyUpdater(project_root=temp_project_dir)
        files = updater.get_project_files()

        assert len(files) >= 2
        assert any("app.py" in str(f) for f in files)

    def test_get_project_files_excludes_pycache(self, temp_project_dir):
        """Test that __pycache__ is excluded."""
        src = temp_project_dir / "src"
        src.mkdir()
        (src / "app.py").write_text("# app")
        cache = src / "__pycache__"
        cache.mkdir()
        (cache / "app.cpython-310.pyc").write_text("")

        updater = DependencyUpdater(project_root=temp_project_dir)
        files = updater.get_project_files()

        assert not any("__pycache__" in str(f) for f in files)


class TestDependencyUpdaterSync:
    """Test sync_environment method."""

    def test_sync_environment_success(self):
        """Test successful environment sync."""
        mock_app = MagicMock()
        mock_env = MagicMock()
        mock_env.exists.return_value = True
        mock_app.get_environment.return_value = mock_env
        mock_app.project.config.envs = {"default": {}}

        updater = DependencyUpdater(app=mock_app)
        result = updater.sync_environment()

        assert result["success"] is True
        mock_env.remove.assert_called_once()
        mock_env.create.assert_called_once()
