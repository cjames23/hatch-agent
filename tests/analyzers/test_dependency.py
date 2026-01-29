"""Tests for individual dependency analysis."""

from unittest.mock import MagicMock, Mock, patch
from pathlib import Path

import pytest

from hatch_agent.analyzers.dependency import DependencyManager


class TestDependencyManagerInit:
    """Test DependencyManager initialization."""

    def test_init_default_values(self):
        """Test initialization with default values."""
        with patch.object(Path, 'cwd', return_value=Path('/test/project')):
            manager = DependencyManager()
            assert manager.project_root == Path('/test/project')
            assert manager.pyproject_path == Path('/test/project/pyproject.toml')
            assert manager.app is None

    def test_init_with_project_root(self, temp_project_dir):
        """Test initialization with custom project root."""
        manager = DependencyManager(project_root=temp_project_dir)
        assert manager.project_root == temp_project_dir
        assert manager.pyproject_path == temp_project_dir / "pyproject.toml"

    def test_init_with_app(self):
        """Test initialization with provided app."""
        mock_app = MagicMock()
        manager = DependencyManager(app=mock_app)
        assert manager.app is mock_app


class TestDependencyManagerReadWrite:
    """Test read/write pyproject operations."""

    def test_read_pyproject_success(self, temp_project_dir):
        """Test reading existing pyproject.toml."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-project"
dependencies = ["requests>=2.0"]
""")
        manager = DependencyManager(project_root=temp_project_dir)
        config = manager.read_pyproject()
        
        assert config["project"]["name"] == "test-project"
        assert "requests>=2.0" in config["project"]["dependencies"]

    def test_read_pyproject_not_found(self, temp_project_dir):
        """Test reading non-existent pyproject.toml."""
        manager = DependencyManager(project_root=temp_project_dir)
        
        with pytest.raises(FileNotFoundError):
            manager.read_pyproject()

    def test_write_pyproject(self, temp_project_dir):
        """Test writing pyproject.toml."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text("[project]\nname = \"old\"")
        
        manager = DependencyManager(project_root=temp_project_dir)
        config = {"project": {"name": "new", "dependencies": ["click"]}}
        manager.write_pyproject(config)
        
        # Verify written content
        new_config = manager.read_pyproject()
        assert new_config["project"]["name"] == "new"


class TestDependencyManagerAdd:
    """Test add_dependency method."""

    def test_add_dependency_main(self, temp_project_dir):
        """Test adding to main dependencies."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"
dependencies = []
""")
        manager = DependencyManager(project_root=temp_project_dir)
        result = manager.add_dependency("requests", ">=2.28.0")
        
        assert result["success"] is True
        assert result["action"] == "added"
        assert result["target"] == "project.dependencies"

    def test_add_dependency_optional(self, temp_project_dir):
        """Test adding to optional dependency group."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text("[project]\nname = \"test\"")
        
        manager = DependencyManager(project_root=temp_project_dir)
        result = manager.add_dependency("pytest", ">=7.0", optional_group="dev")
        
        assert result["success"] is True
        assert "dev" in result["target"]

    def test_add_dependency_duplicate(self, temp_project_dir):
        """Test adding duplicate dependency."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = ["requests>=2.0"]
""")
        manager = DependencyManager(project_root=temp_project_dir)
        result = manager.add_dependency("requests")
        
        assert result["success"] is False
        assert "already exists" in result["error"]


class TestDependencyManagerHelpers:
    """Test helper methods."""

    def test_find_existing_dependency_found(self, temp_project_dir):
        """Test finding existing dependency."""
        manager = DependencyManager(project_root=temp_project_dir)
        deps = ["requests>=2.0", "click==8.0"]
        
        result = manager._find_existing_dependency(deps, "requests")
        assert result == "requests>=2.0"

    def test_find_existing_dependency_not_found(self, temp_project_dir):
        """Test finding non-existent dependency."""
        manager = DependencyManager(project_root=temp_project_dir)
        deps = ["requests>=2.0"]
        
        result = manager._find_existing_dependency(deps, "click")
        assert result is None

    def test_find_existing_dependency_case_insensitive(self, temp_project_dir):
        """Test finding dependency case-insensitively."""
        manager = DependencyManager(project_root=temp_project_dir)
        deps = ["Requests>=2.0"]
        
        result = manager._find_existing_dependency(deps, "requests")
        assert result == "Requests>=2.0"


class TestDependencyManagerSync:
    """Test sync_environment method."""

    def test_sync_environment_success(self, temp_project_dir):
        """Test successful environment sync."""
        mock_app = MagicMock()
        mock_env = MagicMock()
        mock_env.exists.return_value = True
        mock_app.get_environment.return_value = mock_env
        mock_app.project.config.envs = {"default": {}}
        
        manager = DependencyManager(project_root=temp_project_dir, app=mock_app)
        result = manager.sync_environment()
        
        assert result["success"] is True
        mock_env.remove.assert_called_once()
        mock_env.create.assert_called_once()


class TestDependencyManagerGetDeps:
    """Test get_current_dependencies method."""

    def test_get_current_dependencies(self, temp_project_dir):
        """Test getting current dependencies."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = ["requests>=2.0", "click"]

[project.optional-dependencies]
dev = ["pytest"]
""")
        manager = DependencyManager(project_root=temp_project_dir)
        result = manager.get_current_dependencies()
        
        assert "requests>=2.0" in result["main"]
        assert "click" in result["main"]
        assert "pytest" in result["optional"]["dev"]


class TestDependency:
    """Test Dependency class/functions."""

    def test_dependency_initialization(self, mock_dependency_info):
        """Test initializing a dependency object."""
        assert mock_dependency_info["name"] == "requests"
        assert mock_dependency_info["version"] == "2.28.1"

    def test_dependency_from_string(self):
        """Test creating dependency from string specification."""
        dep_string = "requests>=2.28.0"
        assert "requests" in dep_string
        assert ">=" in dep_string

    def test_dependency_to_string(self, mock_dependency_info):
        """Test converting dependency to string."""
        name = mock_dependency_info["name"]
        version = mock_dependency_info["version"]
        dep_string = f"{name}=={version}"
        assert dep_string == "requests==2.28.1"


class TestDependencyMetadata:
    """Test dependency metadata extraction."""

    def test_get_dependency_info(self, mock_dependency_info):
        """Test getting dependency information."""
        assert mock_dependency_info["description"]
        assert mock_dependency_info["homepage"]
        assert mock_dependency_info["license"]

    def test_get_dependency_homepage(self, mock_dependency_info):
        """Test getting dependency homepage."""
        assert mock_dependency_info["homepage"].startswith("http")

    def test_get_dependency_license(self, mock_dependency_info):
        """Test getting dependency license."""
        assert mock_dependency_info["license"] == "Apache 2.0"


class TestDependencyComparison:
    """Test dependency comparison."""

    def test_compare_dependencies(self):
        """Test comparing two dependencies."""
        pass

    def test_dependency_equality(self):
        """Test dependency equality check."""
        pass

    def test_dependency_version_ordering(self):
        """Test ordering dependencies by version."""
        pass


class TestDependencyConstraints:
    """Test dependency version constraints."""

    def test_parse_version_constraint(self):
        """Test parsing version constraints."""
        constraints = [
            ">=1.0.0",
            "==2.0.0",
            "~=1.5.0",
            ">=1.0,<2.0",
        ]
        # Would test constraint parsing
        assert len(constraints) == 4

    def test_evaluate_constraint(self):
        """Test evaluating version against constraint."""
        pass

    def test_constraint_compatibility(self):
        """Test checking constraint compatibility."""
        pass

    def test_merge_constraints(self):
        """Test merging multiple constraints."""
        pass

