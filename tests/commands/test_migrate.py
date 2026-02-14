"""Tests for migrate command."""

import importlib
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

migrate_module = importlib.import_module("hatch_agent.commands.migrate")
migrate = migrate_module.migrate
_extract_migration_plan = migrate_module._extract_migration_plan


class TestMigrateCLI:
    """Test migrate CLI command."""

    @pytest.fixture
    def cli_runner(self):
        return CliRunner()

    def test_migrate_auto_detect_setuptools(self, cli_runner, temp_project_dir):
        """Test migrate auto-detects setuptools."""
        # Create a setup.py
        (temp_project_dir / "setup.py").write_text(
            "from setuptools import setup\nsetup(name='test', version='1.0')\n"
        )

        with (
            patch.object(migrate_module, "ProjectMigrator") as mock_migrator_class,
            patch.object(migrate_module, "load_config") as mock_load_config,
            patch.object(migrate_module, "Agent") as mock_agent_class,
        ):
            mock_migrator = MagicMock()
            mock_migrator.detect_build_system.return_value = {
                "system": "setuptools",
                "files": [str(temp_project_dir / "setup.py")],
            }
            mock_migrator.parse_setup_py.return_value = {
                "name": "test", "version": "1.0", "raw_content": "...",
            }
            mock_migrator.parse_setup_cfg.return_value = {"error": "not found"}
            mock_migrator.generate_hatch_pyproject.return_value = {
                "build-system": {"requires": ["hatchling"], "build-backend": "hatchling.build"},
                "project": {"name": "test", "version": "1.0"},
            }
            mock_migrator.get_migration_diff.return_value = "Migration Summary:\n  Name: test"
            mock_migrator_class.return_value = mock_migrator

            mock_load_config.return_value = {}

            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {
                "success": True,
                "selected_suggestion": "Migration looks good",
                "selected_agent": "ConfigSpecialist",
                "reasoning": "Clean migration",
            }
            mock_agent_class.return_value = mock_agent

            result = cli_runner.invoke(
                migrate,
                ["--project-root", str(temp_project_dir), "--dry-run"],
            )

            assert result.exit_code == 0
            assert "setuptools" in result.output
            assert "DRY RUN" in result.output

    def test_migrate_already_hatch(self, cli_runner, temp_project_dir):
        """Test migrate when project already uses Hatch."""
        with patch.object(migrate_module, "ProjectMigrator") as mock_migrator_class:
            mock_migrator = MagicMock()
            mock_migrator.detect_build_system.return_value = {
                "system": "hatch",
                "files": [str(temp_project_dir / "pyproject.toml")],
            }
            mock_migrator_class.return_value = mock_migrator

            result = cli_runner.invoke(
                migrate, ["--project-root", str(temp_project_dir)]
            )

            assert result.exit_code == 0
            assert "already uses Hatch" in result.output

    def test_migrate_no_system_detected(self, cli_runner, temp_project_dir):
        """Test migrate when no build system detected."""
        with patch.object(migrate_module, "ProjectMigrator") as mock_migrator_class:
            mock_migrator = MagicMock()
            mock_migrator.detect_build_system.return_value = {
                "system": None,
                "files": [],
            }
            mock_migrator_class.return_value = mock_migrator

            result = cli_runner.invoke(
                migrate, ["--project-root", str(temp_project_dir)]
            )

            assert result.exit_code != 0 or "Could not detect" in result.output


class TestExtractMigrationPlan:
    """Test _extract_migration_plan helper."""

    def test_valid_plan(self):
        suggestion = """Here's the migration.

MIGRATION_PLAN:
{
    "pyproject": {"project": {"name": "test"}},
    "notes": ["Note 1"],
    "manual_steps": ["Remove setup.py"]
}"""
        plan = _extract_migration_plan(suggestion)
        assert plan is not None
        assert "pyproject" in plan
        assert plan["pyproject"]["project"]["name"] == "test"

    def test_no_plan(self):
        assert _extract_migration_plan("Just analysis, no plan") is None

    def test_invalid_json(self):
        assert _extract_migration_plan("MIGRATION_PLAN:\n{bad json}") is None


class TestProjectMigrator:
    """Test ProjectMigrator analyzer directly."""

    def test_detect_setuptools_setup_py(self, tmp_path):
        (tmp_path / "setup.py").write_text("from setuptools import setup\nsetup()")

        from hatch_agent.analyzers.migrate import ProjectMigrator

        migrator = ProjectMigrator(tmp_path)
        result = migrator.detect_build_system()

        assert result["system"] == "setuptools"

    def test_detect_poetry(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("""
[tool.poetry]
name = "test"
version = "1.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
""")
        from hatch_agent.analyzers.migrate import ProjectMigrator

        migrator = ProjectMigrator(tmp_path)
        result = migrator.detect_build_system()

        assert result["system"] == "poetry"

    def test_detect_hatch(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("""
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
""")
        from hatch_agent.analyzers.migrate import ProjectMigrator

        migrator = ProjectMigrator(tmp_path)
        result = migrator.detect_build_system()

        assert result["system"] == "hatch"

    def test_detect_pipfile(self, tmp_path):
        (tmp_path / "Pipfile").write_text("""
[packages]
requests = "*"

[dev-packages]
pytest = "*"

[requires]
python_version = "3.10"
""")
        from hatch_agent.analyzers.migrate import ProjectMigrator

        migrator = ProjectMigrator(tmp_path)
        result = migrator.detect_build_system()

        assert result["system"] == "pipfile"

    def test_detect_nothing(self, tmp_path):
        from hatch_agent.analyzers.migrate import ProjectMigrator

        migrator = ProjectMigrator(tmp_path)
        result = migrator.detect_build_system()

        assert result["system"] is None

    def test_parse_setup_py(self, tmp_path):
        (tmp_path / "setup.py").write_text("""
from setuptools import setup

setup(
    name="my-package",
    version="1.2.3",
    description="A test package",
    install_requires=[
        "requests>=2.28.0",
        "click>=8.0",
    ],
    python_requires=">=3.10",
)
""")
        from hatch_agent.analyzers.migrate import ProjectMigrator

        migrator = ProjectMigrator(tmp_path)
        result = migrator.parse_setup_py()

        assert result["name"] == "my-package"
        assert result["version"] == "1.2.3"
        assert "requests>=2.28.0" in result["install_requires"]
        assert result["python_requires"] == ">=3.10"

    def test_parse_setup_cfg(self, tmp_path):
        (tmp_path / "setup.cfg").write_text("""
[metadata]
name = my-package
version = 1.0.0
description = A test package

[options]
install_requires =
    requests>=2.28.0
    click>=8.0

python_requires = >=3.10

[options.extras_require]
dev =
    pytest>=7.0
""")
        from hatch_agent.analyzers.migrate import ProjectMigrator

        migrator = ProjectMigrator(tmp_path)
        result = migrator.parse_setup_cfg()

        assert result["name"] == "my-package"
        assert "requests>=2.28.0" in result["install_requires"]
        assert "dev" in result["extras_require"]

    def test_parse_poetry(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("""
[tool.poetry]
name = "my-package"
version = "1.0.0"
description = "A Poetry project"
authors = ["Test User <test@example.com>"]

[tool.poetry.dependencies]
python = "^3.10"
requests = "^2.28.0"

[tool.poetry.dev-dependencies]
pytest = "^7.0"
""")
        from hatch_agent.analyzers.migrate import ProjectMigrator

        migrator = ProjectMigrator(tmp_path)
        result = migrator.parse_poetry_config()

        assert result["name"] == "my-package"
        assert len(result["dependencies"]) == 1  # requests, not python
        assert "dev" in result["optional_dependencies"]

    def test_parse_pipfile(self, tmp_path):
        (tmp_path / "Pipfile").write_text("""
[packages]
requests = ">=2.28.0"
click = "*"

[dev-packages]
pytest = ">=7.0"

[requires]
python_version = "3.10"
""")
        from hatch_agent.analyzers.migrate import ProjectMigrator

        migrator = ProjectMigrator(tmp_path)
        result = migrator.parse_pipfile()

        assert "requests>=2.28.0" in result["dependencies"]
        assert "click" in result["dependencies"]
        assert result["python_requires"] == ">=3.10"

    def test_generate_hatch_pyproject(self):
        from hatch_agent.analyzers.migrate import ProjectMigrator

        migrator = ProjectMigrator()
        parsed = {
            "name": "my-package",
            "version": "1.0.0",
            "description": "A test",
            "install_requires": ["requests>=2.28.0"],
            "python_requires": ">=3.10",
        }
        config = migrator.generate_hatch_pyproject(parsed)

        assert config["build-system"]["build-backend"] == "hatchling.build"
        assert config["project"]["name"] == "my-package"
        assert config["project"]["dependencies"] == ["requests>=2.28.0"]
        assert config["project"]["requires-python"] == ">=3.10"

    def test_poetry_to_pep440(self):
        from hatch_agent.analyzers.migrate import ProjectMigrator

        assert ProjectMigrator._poetry_to_pep440("^1.2.3") == ">=1.2.3,<2.0.0"
        assert ProjectMigrator._poetry_to_pep440("~1.2.3") == ">=1.2.3,<1.3.0"
        assert ProjectMigrator._poetry_to_pep440("*") == ""
        assert ProjectMigrator._poetry_to_pep440(">=2.0") == ">=2.0"
        assert ProjectMigrator._poetry_to_pep440("1.2.3") == "==1.2.3"

    def test_migration_diff(self):
        from hatch_agent.analyzers.migrate import ProjectMigrator

        migrator = ProjectMigrator()
        config = {
            "project": {
                "name": "test",
                "version": "1.0",
                "dependencies": ["a", "b"],
                "requires-python": ">=3.10",
            }
        }
        diff = migrator.get_migration_diff({}, config)

        assert "test" in diff
        assert "1.0" in diff
        assert "2" in diff  # 2 deps
