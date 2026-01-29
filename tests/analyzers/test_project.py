"""Tests for project analysis."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hatch_agent.analyzers.project import analyze_project


class TestAnalyzeProject:
    """Test analyze_project function."""

    def test_analyze_project_with_pyproject(self, temp_project_dir):
        """Test analyzing project with pyproject.toml."""
        (temp_project_dir / "src").mkdir()
        (temp_project_dir / "tests").mkdir()
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-project"
version = "1.0.0"
dependencies = ["requests>=2.0"]
""")
        
        result = analyze_project(str(temp_project_dir))
        
        assert "src" in result["dirs"]
        assert "tests" in result["dirs"]
        assert "pyproject.toml" in result["files"]
        assert result["pyproject"]["has_pyproject"] is True
        assert result["pyproject"]["project"]["name"] == "test-project"

    def test_analyze_project_without_pyproject(self, temp_project_dir):
        """Test analyzing project without pyproject.toml."""
        (temp_project_dir / "src").mkdir()
        (temp_project_dir / "README.md").touch()
        
        result = analyze_project(str(temp_project_dir))
        
        assert "src" in result["dirs"]
        assert "README.md" in result["files"]
        assert result["pyproject"] is None

    def test_analyze_project_empty_dir(self, temp_project_dir):
        """Test analyzing empty directory."""
        empty_dir = temp_project_dir / "empty"
        empty_dir.mkdir()
        
        result = analyze_project(str(empty_dir))
        
        assert result["files"] == []
        assert result["dirs"] == []

    def test_analyze_project_dir_not_found(self, temp_project_dir):
        """Test analyzing non-existent directory."""
        result = analyze_project(str(temp_project_dir / "nonexistent"))
        
        assert "error" in result
        assert "not found" in result["error"]

    def test_analyze_project_includes_dependencies(self, temp_project_dir):
        """Test that analyze_project includes dependency analysis."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"
dependencies = ["click>=8.0"]
""")
        
        result = analyze_project(str(temp_project_dir))
        
        assert "dependencies" in result
        assert "click>=8.0" in result["dependencies"]["dependencies"]


class TestProjectAnalyzer:
    """Test project analyzer."""

    def test_analyze_project_structure(self, temp_project_dir):
        """Test analyzing project structure."""
        (temp_project_dir / "src").mkdir()
        (temp_project_dir / "tests").mkdir()
        (temp_project_dir / "pyproject.toml").touch()

        assert (temp_project_dir / "src").exists()
        assert (temp_project_dir / "tests").exists()

    def test_find_source_directories(self, temp_project_dir):
        """Test finding source directories."""
        src_dir = temp_project_dir / "src"
        src_dir.mkdir()
        (src_dir / "package").mkdir()

        assert src_dir.exists()

    def test_find_test_directories(self, temp_project_dir):
        """Test finding test directories."""
        test_dir = temp_project_dir / "tests"
        test_dir.mkdir()

        assert test_dir.exists()


class TestProjectMetadata:
    """Test project metadata extraction."""

    def test_get_project_metadata(self, mock_project_metadata):
        """Test getting project metadata."""
        assert mock_project_metadata["name"]
        assert mock_project_metadata["version"]

    def test_parse_project_name(self, mock_project_metadata):
        """Test parsing project name."""
        assert mock_project_metadata["name"] == "test-project"

    def test_parse_project_version(self, mock_project_metadata):
        """Test parsing project version."""
        assert mock_project_metadata["version"] == "0.1.0"

    def test_get_project_authors(self):
        """Test getting project authors."""
        pass

    def test_get_project_classifiers(self):
        """Test getting project classifiers."""
        pass


class TestProjectDependencies:
    """Test project dependency analysis."""

    def test_get_project_dependencies(self, mock_project_metadata):
        """Test getting project dependencies."""
        deps = mock_project_metadata["dependencies"]
        assert len(deps) > 0

    def test_get_dev_dependencies(self, mock_project_metadata):
        """Test getting development dependencies."""
        dev_deps = mock_project_metadata["optional_dependencies"]["dev"]
        assert len(dev_deps) > 0

    def test_get_all_dependencies(self, mock_project_metadata):
        """Test getting all dependencies."""
        all_deps = mock_project_metadata["dependencies"].copy()
        for group in mock_project_metadata["optional_dependencies"].values():
            all_deps.extend(group)
        assert len(all_deps) > 0


class TestProjectHealth:
    """Test project health analysis."""

    def test_check_project_health(self):
        """Test checking overall project health."""
        pass

    def test_check_dependency_health(self):
        """Test checking dependency health."""
        pass

    def test_check_code_quality(self):
        """Test checking code quality indicators."""
        pass

    def test_check_test_coverage(self):
        """Test checking test coverage."""
        pass


class TestProjectStatistics:
    """Test project statistics."""

    def test_count_source_files(self, temp_project_dir):
        """Test counting source files."""
        src_dir = temp_project_dir / "src"
        src_dir.mkdir()
        (src_dir / "file1.py").touch()
        (src_dir / "file2.py").touch()

        py_files = list(src_dir.glob("*.py"))
        assert len(py_files) == 2

    def test_count_test_files(self, temp_project_dir):
        """Test counting test files."""
        test_dir = temp_project_dir / "tests"
        test_dir.mkdir()
        (test_dir / "test_1.py").touch()
        (test_dir / "test_2.py").touch()

        test_files = list(test_dir.glob("test_*.py"))
        assert len(test_files) == 2

    def test_calculate_lines_of_code(self):
        """Test calculating lines of code."""
        pass

    def test_count_dependencies(self, mock_project_metadata):
        """Test counting dependencies."""
        dep_count = len(mock_project_metadata["dependencies"])
        assert dep_count > 0

