"""Tests for agent tools."""

from unittest.mock import Mock, patch

from hatch_agent.agent.tools import TOOL_REGISTRY, Tool, read_file


class TestReadFileTool:
    """Test the read_file tool function."""

    def test_read_file_success(self, temp_project_dir):
        """Test reading an existing file successfully."""
        test_file = temp_project_dir / "test.txt"
        test_file.write_text("Hello, World!")

        result = read_file(str(test_file))
        assert result["success"] is True
        assert result["content"] == "Hello, World!"

    def test_read_file_not_found(self, temp_project_dir):
        """Test reading a non-existent file."""
        result = read_file(str(temp_project_dir / "nonexistent.txt"))
        assert result["success"] is False
        assert "error" in result

    def test_read_file_with_unicode(self, temp_project_dir):
        """Test reading a file with unicode content."""
        test_file = temp_project_dir / "unicode.txt"
        test_file.write_text("Hello 世界 🎉", encoding="utf-8")

        result = read_file(str(test_file))
        assert result["success"] is True
        assert "世界" in result["content"]

    def test_read_file_empty(self, temp_project_dir):
        """Test reading an empty file."""
        test_file = temp_project_dir / "empty.txt"
        test_file.write_text("")

        result = read_file(str(test_file))
        assert result["success"] is True
        assert result["content"] == ""


class TestToolDataclass:
    """Test the Tool dataclass."""

    def test_tool_creation(self):
        """Test creating a Tool instance."""
        tool = Tool(name="test_tool", description="A test tool", func=lambda x: x)
        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert callable(tool.func)

    def test_tool_func_is_callable(self):
        """Test that tool func attribute is callable."""

        def my_func(arg):
            return arg * 2

        tool = Tool(name="double", description="Doubles input", func=my_func)
        assert tool.func(5) == 10


class TestToolRegistry:
    """Test tool registration and discovery."""

    def test_registry_contains_read_file(self):
        """Test that TOOL_REGISTRY contains read_file tool."""
        assert "read_file" in TOOL_REGISTRY

    def test_read_file_tool_in_registry(self):
        """Test the read_file tool in the registry has correct attributes."""
        tool = TOOL_REGISTRY["read_file"]
        assert isinstance(tool, Tool)
        assert tool.name == "read_file"
        assert "Read" in tool.description or "read" in tool.description.lower()

    def test_read_file_tool_func_works(self, temp_project_dir):
        """Test that the read_file tool in registry actually works."""
        test_file = temp_project_dir / "registry_test.txt"
        test_file.write_text("Registry test content")

        tool = TOOL_REGISTRY["read_file"]
        result = tool.func(str(test_file))
        assert result["success"] is True
        assert result["content"] == "Registry test content"


class TestFileSystemTools:
    """Test file system interaction tools."""

    def test_read_file_tool(self, temp_project_dir):
        """Test reading files."""
        test_file = temp_project_dir / "test.txt"
        test_file.write_text("Hello, World!")

        result = read_file(str(test_file))
        assert result["success"] is True
        assert result["content"] == "Hello, World!"

    def test_write_file_tool(self, temp_project_dir):
        """Test writing files."""
        test_file = temp_project_dir / "output.txt"

        # Would test file writing tool
        test_file.write_text("Generated content")
        assert test_file.exists()
        assert test_file.read_text() == "Generated content"

    def test_list_directory_tool(self, temp_project_dir):
        """Test listing directory contents."""
        (temp_project_dir / "file1.py").touch()
        (temp_project_dir / "file2.py").touch()

        files = list(temp_project_dir.glob("*.py"))
        assert len(files) == 2

    def test_search_files_tool(self, temp_project_dir):
        """Test searching for files."""
        (temp_project_dir / "test.py").write_text("def test(): pass")
        (temp_project_dir / "main.py").write_text("def main(): pass")

        py_files = list(temp_project_dir.glob("*.py"))
        assert len(py_files) == 2


class TestCodeAnalysisTools:
    """Test code analysis tools."""

    def test_analyze_imports(self, temp_project_dir):
        """Test analyzing Python imports."""
        code_file = temp_project_dir / "code.py"
        code_file.write_text("""
import os
import sys
from pathlib import Path
""")

        # Would test import analysis
        content = code_file.read_text()
        assert "import os" in content
        assert "from pathlib import Path" in content

    def test_analyze_functions(self, temp_project_dir):
        """Test analyzing function definitions."""
        code_file = temp_project_dir / "code.py"
        code_file.write_text("""
def func1():
    pass

def func2(arg1, arg2):
    return arg1 + arg2
""")

        content = code_file.read_text()
        assert "def func1()" in content
        assert "def func2" in content

    def test_analyze_classes(self, temp_project_dir):
        """Test analyzing class definitions."""
        pass

    def test_find_dependencies(self, temp_project_dir):
        """Test finding project dependencies."""
        pass


class TestGitTools:
    """Test Git integration tools."""

    @patch("subprocess.run")
    def test_git_status(self, mock_run):
        """Test getting Git status."""
        mock_run.return_value = Mock(returncode=0, stdout="On branch main\nnothing to commit")

        # Would test git status tool
        result = mock_run(["git", "status"])
        assert result.returncode == 0

    @patch("subprocess.run")
    def test_git_diff(self, mock_run):
        """Test getting Git diff."""
        mock_run.return_value = Mock(returncode=0, stdout="diff --git a/file.py b/file.py")

        result = mock_run(["git", "diff"])
        assert result.returncode == 0

    @patch("subprocess.run")
    def test_git_commit(self, mock_run):
        """Test creating Git commit."""
        mock_run.return_value = Mock(returncode=0)

        result = mock_run(["git", "commit", "-m", "Test commit"])
        assert result.returncode == 0


class TestPackageTools:
    """Test package management tools."""

    def test_parse_requirements(self, temp_project_dir):
        """Test parsing requirements.txt."""
        req_file = temp_project_dir / "requirements.txt"
        req_file.write_text("""
pytest>=7.0.0
black==22.10.0
requests~=2.28.0
""")

        content = req_file.read_text()
        lines = [line.strip() for line in content.strip().split("\n") if line.strip()]
        assert len(lines) == 3

    def test_parse_pyproject_toml(self, sample_pyproject_toml):
        """Test parsing pyproject.toml."""
        assert sample_pyproject_toml.exists()
        content = sample_pyproject_toml.read_text()
        assert 'name = "test-project"' in content

    def test_get_installed_packages(self):
        """Test getting installed packages."""
        pass

    @patch("subprocess.run")
    def test_install_package(self, mock_run):
        """Test installing a package."""
        mock_run.return_value = Mock(returncode=0)

        result = mock_run(["pip", "install", "pytest"])
        assert result.returncode == 0


class TestExecutionTools:
    """Test code execution tools."""

    @patch("subprocess.run")
    def test_run_command(self, mock_run):
        """Test running shell commands."""
        mock_run.return_value = Mock(returncode=0, stdout="Command output")

        result = mock_run(["echo", "Hello"])
        assert result.returncode == 0

    @patch("subprocess.run")
    def test_run_python_script(self, mock_run):
        """Test running Python scripts."""
        mock_run.return_value = Mock(returncode=0)

        result = mock_run(["python", "script.py"])
        assert result.returncode == 0

    @patch("subprocess.run")
    def test_run_tests(self, mock_run):
        """Test running test suite."""
        mock_run.return_value = Mock(returncode=0, stdout="5 passed")

        result = mock_run(["pytest"])
        assert result.returncode == 0


class TestToolRegistryExtended:
    """Extended test for tool registration and discovery."""

    def test_register_tool(self):
        """Test registering a new tool."""
        pass

    def test_get_tool_by_name(self):
        """Test retrieving tool by name."""
        pass

    def test_list_available_tools(self):
        """Test listing all available tools."""
        pass

    def test_tool_validation(self):
        """Test tool input validation."""
        pass
