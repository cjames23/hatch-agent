"""Tests for security command."""

import importlib
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

security_module = importlib.import_module("hatch_agent.commands.security")
security = security_module.security
_build_security_task = security_module._build_security_task
_severity_color = security_module._severity_color


class TestSecurityCLI:
    """Test security CLI command."""

    @pytest.fixture
    def cli_runner(self):
        return CliRunner()

    def test_security_no_vulns(self, cli_runner, temp_project_dir):
        """Test security command when no vulnerabilities found."""
        with patch.object(security_module, "SecurityAuditor") as mock_auditor_class:
            mock_auditor = MagicMock()
            mock_auditor.run_audit.return_value = {
                "vulnerabilities": [],
                "summary": {"critical": 0, "high": 0, "medium": 0, "low": 0, "unknown": 0},
                "packages_checked": 5,
            }
            mock_auditor_class.return_value = mock_auditor

            result = cli_runner.invoke(security, ["--project-root", str(temp_project_dir)])

            assert result.exit_code == 0
            assert "No known vulnerabilities" in result.output

    def test_security_with_vulns(self, cli_runner, temp_project_dir):
        """Test security command with vulnerabilities found."""
        with (
            patch.object(security_module, "SecurityAuditor") as mock_auditor_class,
            patch.object(security_module, "load_config") as mock_load_config,
            patch.object(security_module, "Agent") as mock_agent_class,
        ):
            mock_auditor = MagicMock()
            mock_auditor.run_audit.return_value = {
                "vulnerabilities": [
                    {
                        "package": "requests",
                        "installed_version": "2.25.0",
                        "vuln_id": "GHSA-1234",
                        "severity": "high",
                        "summary": "SSRF vulnerability",
                        "fixed_in": "2.31.0",
                        "url": "https://osv.dev/vulnerability/GHSA-1234",
                        "source": "osv",
                    }
                ],
                "summary": {"critical": 0, "high": 1, "medium": 0, "low": 0, "unknown": 0},
                "packages_checked": 5,
            }
            mock_auditor_class.return_value = mock_auditor
            mock_load_config.return_value = {}

            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {
                "success": True,
                "selected_suggestion": "Upgrade requests to 2.31.0",
                "selected_agent": "ConfigSpecialist",
                "reasoning": "Critical fix",
            }
            mock_agent_class.return_value = mock_agent

            result = cli_runner.invoke(security, ["--project-root", str(temp_project_dir)])

            assert result.exit_code == 0
            assert "VULNERABILITIES FOUND" in result.output
            assert "requests" in result.output
            assert "GHSA-1234" in result.output

    def test_security_no_ai(self, cli_runner, temp_project_dir):
        """Test security command with --no-ai flag."""
        with patch.object(security_module, "SecurityAuditor") as mock_auditor_class:
            mock_auditor = MagicMock()
            mock_auditor.run_audit.return_value = {
                "vulnerabilities": [
                    {
                        "package": "urllib3",
                        "installed_version": "1.26.0",
                        "vuln_id": "CVE-2023-1234",
                        "severity": "medium",
                        "summary": "Test vuln",
                        "fixed_in": "1.26.18",
                        "url": None,
                        "source": "osv",
                    }
                ],
                "summary": {"critical": 0, "high": 0, "medium": 1, "low": 0, "unknown": 0},
                "packages_checked": 3,
            }
            mock_auditor_class.return_value = mock_auditor

            result = cli_runner.invoke(
                security, ["--project-root", str(temp_project_dir), "--no-ai"]
            )

            assert result.exit_code == 0
            assert "SECURITY ANALYSIS" not in result.output
            assert "urllib3" in result.output

    def test_security_fix_flag(self, cli_runner, temp_project_dir):
        """Test security command with --fix flag shows suggestions."""
        with patch.object(security_module, "SecurityAuditor") as mock_auditor_class:
            mock_auditor = MagicMock()
            mock_auditor.run_audit.return_value = {
                "vulnerabilities": [
                    {
                        "package": "requests",
                        "installed_version": "2.25.0",
                        "vuln_id": "GHSA-1234",
                        "severity": "high",
                        "summary": "Vuln",
                        "fixed_in": "2.31.0",
                        "url": None,
                        "source": "osv",
                    }
                ],
                "summary": {"critical": 0, "high": 1, "medium": 0, "low": 0, "unknown": 0},
                "packages_checked": 1,
            }
            mock_auditor.suggest_fixes.return_value = [
                {
                    "package": "requests",
                    "current_version": "2.25.0",
                    "recommended_version": "2.31.0",
                    "vuln_ids": "GHSA-1234",
                }
            ]
            mock_auditor_class.return_value = mock_auditor

            result = cli_runner.invoke(
                security, ["--project-root", str(temp_project_dir), "--fix", "--no-ai"]
            )

            assert result.exit_code == 0
            assert "Suggested version bumps" in result.output
            assert "2.31.0" in result.output


class TestBuildSecurityTask:
    """Test _build_security_task helper."""

    def test_builds_task_with_vulns(self):
        vulns = [
            {
                "package": "requests",
                "installed_version": "2.25.0",
                "vuln_id": "GHSA-1234",
                "severity": "high",
                "summary": "SSRF vuln",
                "fixed_in": "2.31.0",
            }
        ]
        summary = {"critical": 0, "high": 1, "medium": 0, "low": 0, "unknown": 0}
        task = _build_security_task(vulns, summary)

        assert "requests" in task
        assert "GHSA-1234" in task
        assert "1 security" in task or "remediation" in task.lower()


class TestSeverityColor:
    def test_critical(self):
        assert _severity_color("critical") == "red"

    def test_low(self):
        assert _severity_color("low") == "green"

    def test_unknown(self):
        assert _severity_color("unknown") == "white"


class TestSecurityAuditor:
    """Test SecurityAuditor analyzer directly."""

    def test_get_all_dependencies(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"
version = "1.0"
dependencies = ["requests>=2.28.0", "click>=8.0"]

[project.optional-dependencies]
dev = ["pytest>=7.0"]
""")
        from hatch_agent.analyzers.security import SecurityAuditor

        auditor = SecurityAuditor(tmp_path)
        deps = auditor.get_all_dependencies()

        names = [d["name"] for d in deps]
        assert "requests" in names
        assert "click" in names
        assert "pytest" in names

    def test_get_all_dependencies_no_file(self, tmp_path):
        from hatch_agent.analyzers.security import SecurityAuditor

        auditor = SecurityAuditor(tmp_path)
        deps = auditor.get_all_dependencies()
        assert deps == []

    def test_suggest_fixes(self):
        from hatch_agent.analyzers.security import SecurityAuditor

        auditor = SecurityAuditor()
        vulns = [
            {
                "package": "requests",
                "installed_version": "2.25.0",
                "vuln_id": "GHSA-1",
                "fixed_in": "2.31.0",
            },
            {
                "package": "requests",
                "installed_version": "2.25.0",
                "vuln_id": "GHSA-2",
                "fixed_in": "2.32.0",
            },
        ]
        fixes = auditor.suggest_fixes(vulns)

        assert len(fixes) == 1
        assert fixes[0]["package"] == "requests"
        assert fixes[0]["recommended_version"] == "2.32.0"

    def test_parse_dep_string(self):
        from hatch_agent.analyzers.security import SecurityAuditor

        result = SecurityAuditor._parse_dep_string("requests>=2.28.0")
        assert result["name"] == "requests"
        assert result["version_spec"] == ">=2.28.0"

    def test_parse_dep_string_with_marker(self):
        from hatch_agent.analyzers.security import SecurityAuditor

        result = SecurityAuditor._parse_dep_string('tomli>=2.0; python_version < "3.11"')
        assert result["name"] == "tomli"
