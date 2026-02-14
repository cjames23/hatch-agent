"""Tests for fix command."""

import importlib
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

fix_module = importlib.import_module("hatch_agent.commands.fix")
fix = fix_module.fix
_build_fix_task = fix_module._build_fix_task
_extract_fix_plan = fix_module._extract_fix_plan


class TestFixCLI:
    """Test fix CLI command."""

    @pytest.fixture
    def cli_runner(self):
        return CliRunner()

    def test_fix_no_errors(self, cli_runner, temp_project_dir):
        """Test fix command when no errors remain."""
        with patch.object(fix_module, "BuildFixer") as mock_fixer_class:
            mock_fixer = MagicMock()
            mock_fixer.run_autofix.return_value = {
                "success": True,
                "fix_output": "",
                "format_output": "",
                "files_fixed": 0,
            }
            mock_fixer.get_remaining_errors.return_value = []
            mock_fixer_class.return_value = mock_fixer

            result = cli_runner.invoke(fix, ["--project-root", str(temp_project_dir)])

            assert result.exit_code == 0
            assert "No remaining errors" in result.output

    def test_fix_with_autofix(self, cli_runner, temp_project_dir):
        """Test fix command runs autofix and finds no remaining errors."""
        with patch.object(fix_module, "BuildFixer") as mock_fixer_class:
            mock_fixer = MagicMock()
            mock_fixer.run_autofix.return_value = {
                "success": True,
                "fix_output": "Fixed 3 errors",
                "format_output": "1 file reformatted",
                "files_fixed": 4,
            }
            mock_fixer.get_remaining_errors.return_value = []
            mock_fixer_class.return_value = mock_fixer

            result = cli_runner.invoke(fix, ["--project-root", str(temp_project_dir)])

            assert result.exit_code == 0
            assert "Auto-fixed 4" in result.output

    def test_fix_dry_run(self, cli_runner, temp_project_dir):
        """Test fix command with --dry-run."""
        with patch.object(fix_module, "BuildFixer") as mock_fixer_class:
            mock_fixer = MagicMock()
            mock_fixer.run_autofix.return_value = {
                "success": True,
                "files_fixed": 0,
            }
            mock_fixer.get_remaining_errors.return_value = [
                {
                    "file": "src/test.py",
                    "line": "10",
                    "code": "E501",
                    "message": "Line too long",
                    "tool": "ruff",
                }
            ]
            mock_fixer_class.return_value = mock_fixer

            result = cli_runner.invoke(fix, ["--project-root", str(temp_project_dir), "--dry-run"])

            assert result.exit_code == 0
            assert "DRY RUN" in result.output

    def test_fix_no_autofix(self, cli_runner, temp_project_dir):
        """Test fix command with --no-autofix."""
        with patch.object(fix_module, "BuildFixer") as mock_fixer_class:
            mock_fixer = MagicMock()
            mock_fixer.get_remaining_errors.return_value = []
            mock_fixer_class.return_value = mock_fixer

            result = cli_runner.invoke(
                fix, ["--project-root", str(temp_project_dir), "--no-autofix"]
            )

            assert result.exit_code == 0
            assert "Skipped autofix" in result.output
            mock_fixer.run_autofix.assert_not_called()

    def test_fix_with_ai_errors(self, cli_runner, temp_project_dir):
        """Test fix command with remaining errors triggers AI."""
        # Create a source file for the fix command to read
        src_dir = temp_project_dir / "src"
        src_dir.mkdir()
        test_file = src_dir / "test.py"
        test_file.write_text("x = 1\n")

        with (
            patch.object(fix_module, "BuildFixer") as mock_fixer_class,
            patch.object(fix_module, "load_config") as mock_load_config,
            patch.object(fix_module, "Agent") as mock_agent_class,
        ):
            mock_fixer = MagicMock()
            mock_fixer.run_autofix.return_value = {"success": True, "files_fixed": 0}
            mock_fixer.get_remaining_errors.return_value = [
                {
                    "file": "src/test.py",
                    "line": "10",
                    "code": "E501",
                    "message": "Line too long",
                    "tool": "ruff",
                }
            ]
            mock_fixer_class.return_value = mock_fixer
            mock_load_config.return_value = {}

            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {
                "success": True,
                "selected_suggestion": "No structured fix available",
                "selected_agent": "WorkflowSpecialist",
                "reasoning": "Manual fix needed",
            }
            mock_agent_class.return_value = mock_agent

            result = cli_runner.invoke(fix, ["--project-root", str(temp_project_dir)])

            assert result.exit_code == 0
            assert "PROPOSED FIXES" in result.output


class TestExtractFixPlan:
    """Test _extract_fix_plan helper."""

    def test_valid_plan(self):
        suggestion = (
            "Here's the fix.\n\n"
            'FIX_PLAN:\n'
            '{\n'
            '    "fixes": [\n'
            '        {\n'
            '            "file": "src/test.py",\n'
            '            "line": 10,\n'
            '            "error_code": "E501",\n'
            '            "description": "Split line",\n'
            '            "original": "long_line = 1",\n'
            '            "fixed": "long_line = (\\n    1\\n)"\n'
            '        }\n'
            '    ]\n'
            '}'
        )
        plan = _extract_fix_plan(suggestion)
        assert plan is not None
        assert len(plan["fixes"]) == 1
        assert plan["fixes"][0]["file"] == "src/test.py"

    def test_no_plan(self):
        assert _extract_fix_plan("Just a suggestion without structure") is None

    def test_invalid_json(self):
        assert _extract_fix_plan("FIX_PLAN:\n{invalid json}") is None


class TestBuildFixTask:
    """Test _build_fix_task helper."""

    def test_builds_task(self):
        errors = [
            {
                "file": "src/a.py",
                "line": "5",
                "code": "E501",
                "message": "Line too long",
                "tool": "ruff",
            }
        ]
        files = {"src/a.py": "x = 1\n"}
        task = _build_fix_task(errors, files)

        assert "E501" in task
        assert "src/a.py" in task
        assert "FIX_PLAN:" in task


class TestBuildFixer:
    """Test BuildFixer analyzer methods directly."""

    def test_parse_ruff_line(self):
        from hatch_agent.analyzers.fix import BuildFixer

        result = BuildFixer._parse_ruff_line("src/test.py:10:5: E501 Line too long")
        assert result is not None
        assert result["file"] == "src/test.py"
        assert result["line"] == "10"
        assert result["tool"] == "ruff"

    def test_parse_ruff_line_invalid(self):
        from hatch_agent.analyzers.fix import BuildFixer

        assert BuildFixer._parse_ruff_line("not an error line") is None

    def test_parse_mypy_line(self):
        from hatch_agent.analyzers.fix import BuildFixer

        result = BuildFixer._parse_mypy_line(
            "src/test.py:10: error: Incompatible types [assignment]"
        )
        assert result is not None
        assert result["file"] == "src/test.py"
        assert result["code"] == "assignment"
        assert result["tool"] == "mypy"

    def test_parse_mypy_line_no_code(self):
        from hatch_agent.analyzers.fix import BuildFixer

        result = BuildFixer._parse_mypy_line("src/test.py:5: error: Missing return")
        assert result is not None
        assert result["code"] == ""

    def test_apply_fix(self, tmp_path):
        from hatch_agent.analyzers.fix import BuildFixer

        fixer = BuildFixer(tmp_path)
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        result = fixer.apply_fix(test_file, "x = 1\n", "x = 2\n")

        assert result["success"] is True
        assert test_file.read_text() == "x = 2\n"
        assert (tmp_path / "test.py.bak").exists()

    def test_apply_fix_file_changed(self, tmp_path):
        from hatch_agent.analyzers.fix import BuildFixer

        fixer = BuildFixer(tmp_path)
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 99\n")

        result = fixer.apply_fix(test_file, "x = 1\n", "x = 2\n")

        assert result["success"] is False
        assert "modified" in result["error"]
