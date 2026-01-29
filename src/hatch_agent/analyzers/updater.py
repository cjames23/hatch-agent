"""Utilities for updating dependencies and analyzing API changes."""

import re
from pathlib import Path
from typing import Any

import tomli
import tomli_w
from hatch.cli.application import Application


class DependencyUpdater:
    """Manages dependency updates and tracks version changes."""

    def __init__(self, project_root: Path | None = None, app: Application | None = None):
        """Initialize the dependency updater.

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

    def get_latest_version(self, package: str) -> str | None:
        """Get the latest version of a package from PyPI.

        Args:
            package: Package name

        Returns:
            Latest version string or None if not found
        """
        try:
            import requests

            # Query PyPI JSON API
            response = requests.get(
                f"https://pypi.org/pypi/{package}/json",
                timeout=10,
                headers={"User-Agent": "hatch-agent"},
            )

            if response.status_code == 200:
                data = response.json()
                return data["info"]["version"]
            else:
                return None
        except Exception:
            # If PyPI is unreachable or package not found, return None
            return None

    def get_changelog_url(self, package: str, version: str | None = None) -> str | None:
        """Try to find the changelog or release notes URL for a package.

        Args:
            package: Package name
            version: Specific version (if None, gets latest)

        Returns:
            URL to changelog if available, None otherwise
        """
        try:
            import requests

            response = requests.get(
                f"https://pypi.org/pypi/{package}/json",
                timeout=10,
                headers={"User-Agent": "hatch-agent"},
            )

            if response.status_code != 200:
                return None

            data = response.json()
            info = data.get("info", {})

            # Try to find changelog in project URLs
            project_urls = info.get("project_urls", {})

            # Common changelog URL keys
            changelog_keys = [
                "Changelog",
                "CHANGELOG",
                "Change Log",
                "Changes",
                "Release Notes",
                "Releases",
                "What's New",
            ]

            for key in changelog_keys:
                if key in project_urls:
                    return project_urls[key]

            # Try to construct GitHub releases URL if project is on GitHub
            home_page = info.get("home_page") or project_urls.get("Homepage", "")
            if "github.com" in home_page:
                # Convert repo URL to releases URL
                if home_page.endswith("/"):
                    home_page = home_page[:-1]
                if version:
                    return f"{home_page}/releases/tag/v{version}"
                else:
                    return f"{home_page}/releases"

            return None
        except Exception:
            return None

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

    def get_current_version(self, package: str) -> str | None:
        """Get the current version constraint for a package.

        Args:
            package: Package name

        Returns:
            Current version constraint or None if not found
        """
        config = self.read_pyproject()

        # Check main dependencies
        if "project" in config and "dependencies" in config["project"]:
            for dep in config["project"]["dependencies"]:
                if self._matches_package(dep, package):
                    return self._extract_version(dep)

        # Check optional dependencies
        if "project" in config and "optional-dependencies" in config["project"]:
            for _group, deps in config["project"]["optional-dependencies"].items():
                for dep in deps:
                    if self._matches_package(dep, package):
                        return self._extract_version(dep)

        return None

    def update_dependency(
        self, package: str, new_version: str, optional_group: str | None = None
    ) -> dict[str, Any]:
        """Update a dependency to a new version.

        Args:
            package: Package name (e.g., 'requests')
            new_version: New version specification (e.g., '>=2.30.0')
            optional_group: Optional dependency group if in optional dependencies

        Returns:
            Dict with success status, old version, and new version
        """
        try:
            config = self.read_pyproject()
            old_version = None
            updated = False
            target_location = None

            # Try to update in main dependencies
            if "project" in config and "dependencies" in config["project"]:
                for i, dep in enumerate(config["project"]["dependencies"]):
                    if self._matches_package(dep, package):
                        old_version = self._extract_version(dep)
                        config["project"]["dependencies"][i] = f"{package}{new_version}"
                        updated = True
                        target_location = "project.dependencies"
                        break

            # Try to update in optional dependencies
            if not updated and "project" in config and "optional-dependencies" in config["project"]:
                for group, deps in config["project"]["optional-dependencies"].items():
                    if optional_group and group != optional_group:
                        continue
                    for i, dep in enumerate(deps):
                        if self._matches_package(dep, package):
                            old_version = self._extract_version(dep)
                            config["project"]["optional-dependencies"][group][i] = (
                                f"{package}{new_version}"
                            )
                            updated = True
                            target_location = f"project.optional-dependencies.{group}"
                            break
                    if updated:
                        break

            if not updated:
                return {
                    "success": False,
                    "error": f"Package '{package}' not found in dependencies",
                    "action": "none",
                }

            # Write back to file
            self.write_pyproject(config)

            return {
                "success": True,
                "package": package,
                "old_version": old_version or "unspecified",
                "new_version": new_version,
                "target": target_location,
                "action": "updated",
            }
        except Exception as e:
            return {"success": False, "error": str(e), "action": "failed"}

    def _matches_package(self, dep_string: str, package: str) -> bool:
        """Check if a dependency string matches a package name."""
        dep_name = self._extract_package_name(dep_string)
        return dep_name.lower() == package.lower()

    def _extract_package_name(self, dep_string: str) -> str:
        """Extract the package name from a dependency string."""
        # Remove extras and version specifiers
        name = dep_string.split("[")[0]
        name = re.split(r"[><=~!]", name)[0]
        return name.strip()

    def _extract_version(self, dep_string: str) -> str | None:
        """Extract the version specification from a dependency string."""
        # Find version specifier
        match = re.search(r"([><=~!]+[^,;\s]+)", dep_string)
        if match:
            return match.group(1)
        return None

    def get_installed_version(self, package: str) -> str | None:
        """Get the currently installed version of a package.

        Args:
            package: Package name

        Returns:
            Installed version or None
        """
        try:
            app = self._get_app()
            env_names = list(app.project.config.envs.keys())

            if not env_names:
                return None

            env = app.get_environment(env_names[0])

            # Run pip show to get version
            output_lines = []
            try:
                for line in env.run_shell_command(["pip", "show", package]):
                    output_lines.append(line)

                # Parse version from output
                output = "\n".join(output_lines)
                for line in output.split("\n"):
                    if line.startswith("Version:"):
                        return line.split(":", 1)[1].strip()
            except Exception:
                return None

            return None
        except Exception:
            return None

    def get_project_files(self, extensions: list[str] | None = None) -> list[Path]:
        """Get all project source files.

        Args:
            extensions: File extensions to include

        Returns:
            List of source file paths
        """
        if extensions is None:
            extensions = [".py"]
        files = []

        # Common source directories
        src_dirs = [
            self.project_root / "src",
            self.project_root / "lib",
            self.project_root,
        ]

        for src_dir in src_dirs:
            if src_dir.exists():
                for ext in extensions:
                    files.extend(src_dir.rglob(f"*{ext}"))

        # Filter out common non-source directories
        exclude_patterns = [
            "__pycache__",
            ".git",
            ".hatch",
            "dist",
            "build",
            ".eggs",
            ".tox",
            "venv",
            ".venv",
        ]
        files = [f for f in files if not any(pattern in f.parts for pattern in exclude_patterns)]

        return files

    def sync_environment(self, env_name: str | None = None) -> dict[str, Any]:
        """Sync Hatch environment after updating dependencies.

        Args:
            env_name: Optional specific environment name to sync

        Returns:
            Dict with success status
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
                "action": "Environment recreated with updated dependencies",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
