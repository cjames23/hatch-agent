"""Tests for doctor command."""

import importlib
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

doctor_module = importlib.import_module("hatch_agent.commands.doctor")
doctor = doctor_module.doctor
_build_doctor_task = doctor_module._build_doctor_task


class TestDoctorCLI:
    """Test doctor CLI command."""

    @pytest.fixture
    def cli_runner(self):
        return CliRunner()

    def test_doctor_all_pass(self, cli_runner, temp_project_dir):
        """Test doctor command when all checks pass."""
        with (
            patch.object(doctor_module, "ProjectDoctor") as mock_doctor_class,
            patch.object(doctor_module, "load_config") as mock_load_config,
            patch.object(doctor_module, "Agent") as mock_agent_class,
        ):
            mock_doc = MagicMock()
            mock_doc.run_all_checks.return_value = {
                "checks": [
                    {"category": "PEP 621", "field": "name", "status": "pass", "message": "Present"},
                ],
                "summary": {"passed": 1, "warned": 0, "failed": 0},
            }
            mock_doctor_class.return_value = mock_doc

            mock_load_config.return_value = {}

            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {
                "success": True,
                "selected_suggestion": "Everything looks great!",
                "selected_agent": "ConfigSpecialist",
                "reasoning": "All checks passed",
            }
            mock_agent_class.return_value = mock_agent

            result = cli_runner.invoke(doctor, ["--project-root", str(temp_project_dir)])

            assert result.exit_code == 0
            assert "passed" in result.output.lower()
            assert "RECOMMENDATIONS" in result.output

    def test_doctor_with_warnings(self, cli_runner, temp_project_dir):
        """Test doctor command with warnings."""
        with (
            patch.object(doctor_module, "ProjectDoctor") as mock_doctor_class,
            patch.object(doctor_module, "load_config") as mock_load_config,
            patch.object(doctor_module, "Agent") as mock_agent_class,
        ):
            mock_doc = MagicMock()
            mock_doc.run_all_checks.return_value = {
                "checks": [
                    {"category": "PEP 621", "field": "name", "status": "pass", "message": "Present"},
                    {"category": "PEP 621", "field": "license", "status": "warn",
                     "message": "Recommended: License declaration"},
                ],
                "summary": {"passed": 1, "warned": 1, "failed": 0},
            }
            mock_doctor_class.return_value = mock_doc
            mock_load_config.return_value = {}

            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {
                "success": True,
                "selected_suggestion": "Add a license field",
                "selected_agent": "ConfigSpecialist",
                "reasoning": "Best practice",
            }
            mock_agent_class.return_value = mock_agent

            result = cli_runner.invoke(doctor, ["--project-root", str(temp_project_dir)])

            assert result.exit_code == 0
            assert "1" in result.output  # 1 warning
            assert "RECOMMENDATIONS" in result.output

    def test_doctor_no_ai(self, cli_runner, temp_project_dir):
        """Test doctor command with --no-ai flag skips AI analysis."""
        with patch.object(doctor_module, "ProjectDoctor") as mock_doctor_class:
            mock_doc = MagicMock()
            mock_doc.run_all_checks.return_value = {
                "checks": [
                    {"category": "PEP 621", "field": "name", "status": "pass", "message": "Present"},
                ],
                "summary": {"passed": 1, "warned": 0, "failed": 0},
            }
            mock_doctor_class.return_value = mock_doc

            result = cli_runner.invoke(
                doctor, ["--project-root", str(temp_project_dir), "--no-ai"]
            )

            assert result.exit_code == 0
            assert "RECOMMENDATIONS" not in result.output

    def test_doctor_ai_failure(self, cli_runner, temp_project_dir):
        """Test doctor command when AI analysis fails."""
        with (
            patch.object(doctor_module, "ProjectDoctor") as mock_doctor_class,
            patch.object(doctor_module, "load_config") as mock_load_config,
            patch.object(doctor_module, "Agent") as mock_agent_class,
        ):
            mock_doc = MagicMock()
            mock_doc.run_all_checks.return_value = {
                "checks": [],
                "summary": {"passed": 0, "warned": 0, "failed": 0},
            }
            mock_doctor_class.return_value = mock_doc
            mock_load_config.return_value = {}

            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {"success": False, "output": "LLM error"}
            mock_agent_class.return_value = mock_agent

            result = cli_runner.invoke(doctor, ["--project-root", str(temp_project_dir)])

            assert result.exit_code != 0 or "failed" in result.output.lower()


class TestBuildDoctorTask:
    """Test _build_doctor_task helper."""

    def test_all_pass(self):
        checks = [{"status": "pass", "category": "X", "field": "f", "message": "ok"}]
        summary = {"passed": 1, "warned": 0, "failed": 0}
        task = _build_doctor_task(checks, summary)
        assert "passed" in task.lower()

    def test_with_issues(self):
        checks = [
            {"status": "warn", "category": "PEP 621", "field": "license", "message": "Missing"},
            {"status": "fail", "category": "Hatch", "field": "packages", "message": "Not found"},
        ]
        summary = {"passed": 0, "warned": 1, "failed": 1}
        task = _build_doctor_task(checks, summary)
        assert "license" in task
        assert "packages" in task.lower()
        assert "0 passed" in task


class TestProjectDoctor:
    """Test ProjectDoctor analyzer directly."""

    def test_pep621_all_present(self, tmp_path):
        """Test PEP 621 check with all fields present."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"
version = "1.0.0"
description = "A test"
readme = "README.md"
license = "MIT"
requires-python = ">=3.10"
classifiers = ["Development Status :: 3 - Alpha"]

[project.urls]
Homepage = "https://example.com"
""")
        from hatch_agent.analyzers.doctor import ProjectDoctor

        doc = ProjectDoctor(tmp_path)
        results = doc.check_pep621_compliance()

        statuses = {r["field"]: r["status"] for r in results}
        assert statuses["name"] == "pass"
        assert statuses["version"] == "pass"
        assert statuses["description"] == "pass"

    def test_pep621_missing_required(self, tmp_path):
        """Test PEP 621 check with missing required fields."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\n")

        from hatch_agent.analyzers.doctor import ProjectDoctor

        doc = ProjectDoctor(tmp_path)
        results = doc.check_pep621_compliance()

        statuses = {r["field"]: r["status"] for r in results}
        assert statuses["name"] == "fail"
        assert statuses["version"] == "fail"

    def test_gitignore_present(self, tmp_path):
        """Test gitignore check with complete file."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("dist/\n*.egg-info\n__pycache__\n.venv\nbuild/\n")
        (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\nversion='1'\n")

        from hatch_agent.analyzers.doctor import ProjectDoctor

        doc = ProjectDoctor(tmp_path)
        results = doc.check_gitignore()

        assert results[0]["status"] == "pass"

    def test_gitignore_missing(self, tmp_path):
        """Test gitignore check when file is absent."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\nversion='1'\n")

        from hatch_agent.analyzers.doctor import ProjectDoctor

        doc = ProjectDoctor(tmp_path)
        results = doc.check_gitignore()

        assert results[0]["status"] == "warn"

    def test_run_all_checks(self, tmp_path):
        """Test run_all_checks aggregation."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "test"
version = "1.0.0"
""")

        from hatch_agent.analyzers.doctor import ProjectDoctor

        doc = ProjectDoctor(tmp_path)
        report = doc.run_all_checks()

        assert "checks" in report
        assert "summary" in report
        assert isinstance(report["checks"], list)
        assert report["summary"]["passed"] >= 0
