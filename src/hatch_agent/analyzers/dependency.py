"""Utilities for managing dependencies in pyproject.toml."""

from pathlib import Path
from typing import Any

import tomli
import tomli_w
from hatch.cli.application import Application


class DependencyManager:
    """Manages dependencies in pyproject.toml and Hatch environments."""

    def __init__(self, project_root: Path | None = None, app: Application | None = None):
        """Initialize the dependency manager.

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

    def read_pyproject(self) -> dict[str, Any]:
        """Read the current pyproject.toml file."""
        if not self.pyproject_path.exists():
            raise FileNotFoundError(f"pyproject.toml not found at {self.pyproject_path}")

        with open(self.pyproject_path, "rb") as f:
            return tomli.load(f)

    def write_pyproject(self, config: dict[str, Any]) -> None:
        """Write the updated pyproject.toml file."""
        with open(self.pyproject_path, "wb") as f:
            tomli_w.dump(config, f)

    def add_dependency(
        self, package: str, version_spec: str | None = None, optional_group: str | None = None
    ) -> dict[str, Any]:
        """Add a dependency to pyproject.toml.

        Args:
            package: Package name (e.g., 'requests')
            version_spec: Optional version specification (e.g., '>=2.28.0')
            optional_group: Optional dependency group (e.g., 'dev', 'test')

        Returns:
            Dict with success status and details
        """
        try:
            config = self.read_pyproject()

            # Construct dependency string
            dep_string = f"{package}{version_spec}" if version_spec else package

            # Determine where to add the dependency
            if optional_group:
                # Add to optional dependencies
                if "project" not in config:
                    config["project"] = {}
                if "optional-dependencies" not in config["project"]:
                    config["project"]["optional-dependencies"] = {}
                if optional_group not in config["project"]["optional-dependencies"]:
                    config["project"]["optional-dependencies"][optional_group] = []

                deps_list = config["project"]["optional-dependencies"][optional_group]
                target = f"project.optional-dependencies.{optional_group}"
            else:
                # Add to main dependencies
                if "project" not in config:
                    config["project"] = {}
                if "dependencies" not in config["project"]:
                    config["project"]["dependencies"] = []

                deps_list = config["project"]["dependencies"]
                target = "project.dependencies"

            # Check if package already exists
            existing = self._find_existing_dependency(deps_list, package)
            if existing:
                return {
                    "success": False,
                    "error": f"Package '{package}' already exists as '{existing}'",
                    "action": "none",
                }

            # Add the dependency
            deps_list.append(dep_string)

            # Write back to file
            self.write_pyproject(config)

            return {
                "success": True,
                "package": package,
                "dependency_string": dep_string,
                "target": target,
                "action": "added",
            }
        except Exception as e:
            return {"success": False, "error": str(e), "action": "failed"}

    def _find_existing_dependency(self, deps_list: list[str], package: str) -> str | None:
        """Find if a package already exists in the dependencies list."""
        package_lower = package.lower()
        for dep in deps_list:
            # Extract package name (before any version specifier)
            dep_name = (
                dep.split("[")[0]
                .split(">=")[0]
                .split("==")[0]
                .split("~=")[0]
                .split(">")[0]
                .split("<")[0]
                .strip()
            )
            if dep_name.lower() == package_lower:
                return dep
        return None

    def sync_environment(self, env_name: str | None = None) -> dict[str, Any]:
        """Sync Hatch environment to install new dependencies using Hatch's API.

        Args:
            env_name: Optional specific environment name to sync

        Returns:
            Dict with success status and command output
        """
        try:
            app = self._get_app()

            # Determine which environment to sync
            if env_name is None:
                # Use the default environment or first available
                env_names = list(app.project.config.envs.keys())
                env_name = env_names[0] if env_names else "default"

            # Get the environment
            env = app.get_environment(env_name)

            # Remove the environment to force recreation with new dependencies
            if env.exists():
                env.remove()

            # Create the environment (this installs dependencies)
            env.create()

            return {
                "success": True,
                "environment": env_name,
                "action": "Environment recreated with new dependencies",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_current_dependencies(self) -> dict[str, Any]:
        """Get current dependencies from pyproject.toml."""
        try:
            config = self.read_pyproject()

            result = {"main": [], "optional": {}}

            # Get main dependencies
            if "project" in config and "dependencies" in config["project"]:
                result["main"] = config["project"]["dependencies"]

            # Get optional dependencies
            if "project" in config and "optional-dependencies" in config["project"]:
                result["optional"] = config["project"]["optional-dependencies"]

            return result
        except Exception as e:
            return {"error": str(e)}
