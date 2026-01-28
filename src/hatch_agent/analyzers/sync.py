"""Utilities for syncing dependencies and tracking version changes."""

from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import json
import re

from hatch.cli.application import Application


class DependencySync:
    """Manages dependency upgrades using Hatch's EnvironmentInterface APIs.
    
    This class wraps Hatch's environment APIs to provide:
    - Installer detection (pip vs uv)
    - Version tracking (before/after upgrade)
    - Upgrade execution
    - Semver change classification
    """

    def __init__(self, project_root: Optional[Path] = None, app: Optional[Application] = None):
        """Initialize the dependency sync manager.

        Args:
            project_root: Root directory of the Hatch project (defaults to current directory)
            app: Hatch Application instance (will be created if not provided)
        """
        self.project_root = project_root or Path.cwd()
        self._app = app
        self._env_cache: Dict[str, Any] = {}

    def _get_app(self) -> Application:
        """Get or create the Hatch application instance."""
        if self._app is None:
            self._app = Application(self.project_root)
        return self._app

    def _get_environment(self, env_name: Optional[str] = None):
        """Get Hatch environment, leveraging existing env selection logic.
        
        Args:
            env_name: Specific environment name, or None for default
            
        Returns:
            Hatch environment instance
        """
        cache_key = env_name or "_default"
        if cache_key in self._env_cache:
            return self._env_cache[cache_key]
            
        app = self._get_app()
        if env_name is None:
            env_names = list(app.project.config.envs.keys())
            env_name = env_names[0] if env_names else "default"
        
        env = app.get_environment(env_name)
        self._env_cache[cache_key] = env
        return env

    def get_installer(self, env_name: Optional[str] = None) -> str:
        """Get configured installer using env.use_uv property.
        
        Args:
            env_name: Specific environment name, or None for default
            
        Returns:
            "uv" if uv is configured, otherwise "pip"
        """
        env = self._get_environment(env_name)
        return "uv" if getattr(env, 'use_uv', False) else "pip"

    def get_dependencies(self, env_name: Optional[str] = None) -> List[str]:
        """Get the list of dependencies for the environment.
        
        Args:
            env_name: Specific environment name, or None for default
            
        Returns:
            List of dependency strings from env.dependencies
        """
        env = self._get_environment(env_name)
        return list(env.dependencies)

    def get_installed_versions(self, env_name: Optional[str] = None) -> Dict[str, str]:
        """Get installed package versions using pip list in environment.
        
        Args:
            env_name: Specific environment name, or None for default
            
        Returns:
            Dict mapping lowercase package names to version strings
        """
        env = self._get_environment(env_name)
        
        try:
            # Build the pip list command using Hatch's command construction
            # construct_pip_install_command builds pip/uv command prefix
            if getattr(env, 'use_uv', False):
                # For uv: uv pip list --format json
                base_cmd = self._get_uv_command(env)
                command = base_cmd + ["pip", "list", "--format", "json"]
            else:
                # For pip: pip list --format json
                command = ["pip", "list", "--format", "json"]
            
            # Run command in environment context
            output_lines = []
            with env.command_context():
                result = env.platform.run_command(command, capture_output=True)
                if result.returncode == 0:
                    output_lines = result.stdout.decode('utf-8') if isinstance(result.stdout, bytes) else result.stdout
                else:
                    return {}
            
            packages = json.loads(output_lines)
            return {pkg["name"].lower(): pkg["version"] for pkg in packages}
            
        except Exception as e:
            # If we can't get versions, return empty dict
            return {}

    def _get_uv_command(self, env) -> List[str]:
        """Get the uv command prefix from environment."""
        if hasattr(env, 'uv_path') and env.uv_path:
            return [env.uv_path]
        return ["uv"]

    def run_upgrade(
        self, 
        env_name: Optional[str] = None, 
        dry_run: bool = False,
        packages: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run pip/uv upgrade using Hatch's construct_pip_install_command.
        
        Args:
            env_name: Specific environment name, or None for default
            dry_run: If True, only show what would be upgraded
            packages: Specific packages to upgrade, or None for all dependencies
            
        Returns:
            Dict with success status and output
        """
        env = self._get_environment(env_name)
        
        try:
            # Get dependencies to upgrade
            if packages:
                deps = packages
            else:
                deps = self.get_dependencies(env_name)
            
            if not deps:
                return {
                    "success": True,
                    "output": "No dependencies to upgrade",
                    "action": "none"
                }
            
            # Build upgrade command - Hatch handles pip vs uv automatically
            args = ["--upgrade"] + deps
            if dry_run:
                args.insert(0, "--dry-run")
            
            command = env.construct_pip_install_command(args)
            
            # Execute the upgrade
            with env.command_context():
                result = env.platform.run_command(command, capture_output=True)
                output = result.stdout.decode('utf-8') if isinstance(result.stdout, bytes) else str(result.stdout)
                
                if result.returncode != 0:
                    stderr = result.stderr.decode('utf-8') if isinstance(result.stderr, bytes) else str(result.stderr)
                    return {
                        "success": False,
                        "error": stderr or output,
                        "action": "failed"
                    }
            
            return {
                "success": True,
                "output": output,
                "action": "upgraded" if not dry_run else "dry_run"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "action": "failed"
            }

    def compare_versions(
        self, 
        before: Dict[str, str], 
        after: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """Compare versions and identify updates with semver change type.
        
        Args:
            before: Dict of package names to versions before upgrade
            after: Dict of package names to versions after upgrade
            
        Returns:
            List of dicts with package, old_version, new_version, change_type
        """
        updates = []
        for name, new_version in after.items():
            old_version = before.get(name)
            if old_version and old_version != new_version:
                updates.append({
                    "package": name,
                    "old_version": old_version,
                    "new_version": new_version,
                    "change_type": self._classify_version_change(old_version, new_version)
                })
        
        # Also check for newly installed packages
        for name in after:
            if name not in before:
                updates.append({
                    "package": name,
                    "old_version": None,
                    "new_version": after[name],
                    "change_type": "new"
                })
        
        return updates

    def _classify_version_change(self, old: str, new: str) -> str:
        """Classify version change as major/minor/patch based on semver.
        
        Args:
            old: Old version string (e.g., "1.2.3")
            new: New version string (e.g., "2.0.0")
            
        Returns:
            One of: "major", "minor", "patch", "unknown"
        """
        old_parts = self._parse_version(old)
        new_parts = self._parse_version(new)
        
        if old_parts is None or new_parts is None:
            return "unknown"
        
        old_major, old_minor, old_patch = old_parts
        new_major, new_minor, new_patch = new_parts
        
        if new_major != old_major:
            return "major"
        elif new_minor != old_minor:
            return "minor"
        elif new_patch != old_patch:
            return "patch"
        else:
            return "unknown"

    def _parse_version(self, version: str) -> Optional[Tuple[int, int, int]]:
        """Parse a version string into (major, minor, patch) tuple.
        
        Args:
            version: Version string (e.g., "1.2.3", "1.2.3.post1", "1.2")
            
        Returns:
            Tuple of (major, minor, patch) or None if parsing fails
        """
        # Match semver-like patterns
        match = re.match(r'^(\d+)(?:\.(\d+))?(?:\.(\d+))?', version)
        if match:
            major = int(match.group(1))
            minor = int(match.group(2)) if match.group(2) else 0
            patch = int(match.group(3)) if match.group(3) else 0
            return (major, minor, patch)
        return None

    def ensure_environment_exists(self, env_name: Optional[str] = None) -> Dict[str, Any]:
        """Ensure the environment exists, creating it if necessary.
        
        Args:
            env_name: Specific environment name, or None for default
            
        Returns:
            Dict with success status and environment info
        """
        env = self._get_environment(env_name)
        
        try:
            if not env.exists():
                env.create()
                return {
                    "success": True,
                    "action": "created",
                    "environment": env.name
                }
            return {
                "success": True,
                "action": "exists",
                "environment": env.name
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "action": "failed"
            }

    def get_environment_info(self, env_name: Optional[str] = None) -> Dict[str, Any]:
        """Get information about the environment.
        
        Args:
            env_name: Specific environment name, or None for default
            
        Returns:
            Dict with environment details
        """
        env = self._get_environment(env_name)
        
        return {
            "name": env.name,
            "installer": self.get_installer(env_name),
            "exists": env.exists(),
            "dependencies_count": len(self.get_dependencies(env_name)),
        }
