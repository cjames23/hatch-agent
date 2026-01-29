"""Utilities for analyzing Hatch build failures and project state."""

from pathlib import Path
from typing import Any

import tomli
from hatch.cli.application import Application


class BuildAnalyzer:
    """Analyzes Hatch build failures including tests, formatting, and type checking."""

    def __init__(self, project_root: Path | None = None, app: Application | None = None):
        """Initialize the build analyzer.

        Args:
            project_root: Root directory of the Hatch project (defaults to current directory)
            app: Hatch Application instance (will be created if not provided)
        """
        self.project_root = project_root or Path.cwd()
        self.pyproject_path = self.project_root / "pyproject.toml"
        self.app = app

    def _get_app(self) -> Application:
        """Get or create the Hatch application instance."""
        if self.app is None:
            from hatch.cli.application import Application

            self.app = Application(self.project_root)
        return self.app

    def analyze_build_failure(self) -> dict[str, Any]:
        """Analyze recent build failures.

        Returns:
            Dict containing analysis of test failures, formatting issues, and type errors
        """
        context = {
            "project_root": str(self.project_root),
            "pyproject_exists": self.pyproject_path.exists(),
        }

        app = self._get_app()

        # Run tests and capture output
        test_result = self._run_tests(app)
        context["test_result"] = test_result

        # Check formatting
        format_result = self._check_formatting(app)
        context["format_result"] = format_result

        # Check type hints
        type_result = self._check_types(app)
        context["type_result"] = type_result

        # Get environment info
        env_info = self._get_env_info(app)
        context["env_info"] = env_info

        return context

    def _run_tests(self, app: Application) -> dict[str, Any]:
        """Run tests using Hatch's environment system."""
        try:
            # Get the default or test environment
            env_name = self._find_test_env(app)
            if not env_name:
                return {
                    "success": None,
                    "error": "No test environment configured",
                    "command": "N/A",
                }

            env = app.get_environment(env_name)

            # Run the test command
            output_lines = []

            try:
                # Execute tests in the environment
                for line in env.run_shell_command(
                    ["pytest"] if env_name == "test" else ["hatch", "run", "test"]
                ):
                    output_lines.append(line)

                return {
                    "success": True,
                    "exit_code": 0,
                    "stdout": "\n".join(output_lines),
                    "stderr": "",
                    "command": f"hatch run {env_name}:test",
                }
            except Exception as e:
                return {
                    "success": False,
                    "exit_code": 1,
                    "stdout": "\n".join(output_lines),
                    "stderr": str(e),
                    "command": f"hatch run {env_name}:test",
                }

        except Exception as e:
            return {"success": False, "error": str(e), "command": "hatch run test"}

    def _check_formatting(self, app: Application) -> dict[str, Any]:
        """Check code formatting using Hatch environment."""
        # Try to find a lint or format environment
        env_name = self._find_format_env(app)

        if not env_name:
            return {
                "success": None,
                "error": "No formatting environment configured",
                "command": "N/A",
            }

        try:
            env = app.get_environment(env_name)
            output_lines = []

            try:
                for line in env.run_shell_command(["ruff", "check", "."]):
                    output_lines.append(line)

                return {
                    "success": True,
                    "exit_code": 0,
                    "stdout": "\n".join(output_lines),
                    "stderr": "",
                    "command": f"hatch run {env_name}:ruff check",
                }
            except Exception as e:
                return {
                    "success": False,
                    "exit_code": 1,
                    "stdout": "\n".join(output_lines),
                    "stderr": str(e),
                    "command": f"hatch run {env_name}:format",
                }
        except Exception as e:
            return {"success": None, "error": str(e), "command": "N/A"}

    def _check_types(self, app: Application) -> dict[str, Any]:
        """Check type hints using Hatch environment."""
        env_name = self._find_type_env(app)

        if not env_name:
            return {
                "success": None,
                "error": "No type checking environment configured",
                "command": "N/A",
            }

        try:
            env = app.get_environment(env_name)
            output_lines = []

            try:
                for line in env.run_shell_command(["mypy", "."]):
                    output_lines.append(line)

                return {
                    "success": True,
                    "exit_code": 0,
                    "stdout": "\n".join(output_lines),
                    "stderr": "",
                    "command": f"hatch run {env_name}:mypy",
                }
            except Exception as e:
                return {
                    "success": False,
                    "exit_code": 1,
                    "stdout": "\n".join(output_lines),
                    "stderr": str(e),
                    "command": f"hatch run {env_name}:type",
                }
        except Exception as e:
            return {"success": None, "error": str(e), "command": "N/A"}

    def _get_env_info(self, app: Application) -> dict[str, Any]:
        """Get Hatch environment information."""
        try:
            environments = list(app.project.config.envs.keys())

            return {"available": True, "environments": environments, "active_env": app.env_active}
        except Exception as e:
            return {"available": False, "error": str(e)}

    def _find_test_env(self, app: Application) -> str | None:
        """Find the test environment."""
        env_names = list(app.project.config.envs.keys())

        # Look for common test environment names
        for name in ["test", "tests", "default"]:
            if name in env_names:
                return name

        # Return first environment if available
        return env_names[0] if env_names else None

    def _find_format_env(self, app: Application) -> str | None:
        """Find the formatting/linting environment."""
        env_names = list(app.project.config.envs.keys())

        for name in ["lint", "format", "style", "default"]:
            if name in env_names:
                return name

        return env_names[0] if env_names else None

    def _find_type_env(self, app: Application) -> str | None:
        """Find the type checking environment."""
        env_names = list(app.project.config.envs.keys())

        for name in ["type", "types", "typing", "lint", "default"]:
            if name in env_names:
                return name

        return env_names[0] if env_names else None

    def get_project_config(self) -> dict[str, Any] | None:
        """Read and return the pyproject.toml configuration."""
        if not self.pyproject_path.exists():
            return None

        try:
            with open(self.pyproject_path, "rb") as f:
                return tomli.load(f)
        except Exception as e:
            return {"error": str(e)}
