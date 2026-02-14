"""Build fixer utilities for hatch-agent fix command."""

import shutil
from pathlib import Path
from typing import Any

from hatch.cli.application import Application


class BuildFixer:
    """Runs auto-fixes and collects remaining errors for AI-assisted fixing."""

    def __init__(self, project_root: Path | None = None, app: Application | None = None):
        """Initialize the build fixer.

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
            self.app = Application(self.project_root)
        return self.app

    def _find_env(self, app: Application) -> str | None:
        """Find a suitable environment to run commands in."""
        env_names = list(app.project.config.envs.keys())
        for name in ("lint", "format", "style", "default"):
            if name in env_names:
                return name
        return env_names[0] if env_names else None

    def run_autofix(self) -> dict[str, Any]:
        """Run ruff check --fix and ruff format in the Hatch environment.

        Returns:
            Dict with 'success', 'fix_output', 'format_output', and 'files_fixed'.
        """
        app = self._get_app()
        env_name = self._find_env(app)

        if not env_name:
            return {
                "success": False,
                "error": "No suitable Hatch environment found",
                "files_fixed": 0,
            }

        try:
            env = app.get_environment(env_name)
        except Exception as e:
            return {"success": False, "error": str(e), "files_fixed": 0}

        fix_output_lines: list[str] = []
        format_output_lines: list[str] = []

        # Run ruff check --fix
        try:
            for line in env.run_shell_command(["ruff", "check", "--fix", "."]):
                fix_output_lines.append(line)
        except Exception as e:
            fix_output_lines.append(f"ruff check --fix error: {e}")

        # Run ruff format
        try:
            for line in env.run_shell_command(["ruff", "format", "."]):
                format_output_lines.append(line)
        except Exception as e:
            format_output_lines.append(f"ruff format error: {e}")

        fix_output = "\n".join(fix_output_lines)
        format_output = "\n".join(format_output_lines)

        # Estimate files fixed from output
        files_fixed = fix_output.count("Fixed") + format_output.count("reformatted")

        return {
            "success": True,
            "fix_output": fix_output,
            "format_output": format_output,
            "files_fixed": files_fixed,
        }

    def get_remaining_errors(self) -> list[dict[str, str]]:
        """Run ruff check and mypy to collect remaining errors after autofix.

        Returns:
            List of dicts with 'file', 'line', 'code', 'message', 'tool'.
        """
        app = self._get_app()
        env_name = self._find_env(app)

        if not env_name:
            return []

        try:
            env = app.get_environment(env_name)
        except Exception:
            return []

        errors: list[dict[str, str]] = []

        # Collect ruff errors
        ruff_lines: list[str] = []
        try:
            for line in env.run_shell_command(["ruff", "check", "."]):
                ruff_lines.append(line)
        except Exception:
            pass

        for line in ruff_lines:
            parsed = self._parse_ruff_line(line)
            if parsed:
                errors.append(parsed)

        # Collect mypy errors
        mypy_lines: list[str] = []
        try:
            for line in env.run_shell_command(["mypy", "."]):
                mypy_lines.append(line)
        except Exception:
            pass

        for line in mypy_lines:
            parsed = self._parse_mypy_line(line)
            if parsed:
                errors.append(parsed)

        return errors

    def apply_fix(
        self,
        file_path: Path,
        original_content: str,
        fixed_content: str,
        create_backup: bool = True,
    ) -> dict[str, Any]:
        """Write a fix to disk with optional backup.

        Args:
            file_path: Absolute path to the file to fix.
            original_content: The original file content (for verification).
            fixed_content: The corrected file content to write.
            create_backup: Whether to create a .bak backup file.

        Returns:
            Dict with 'success' and optionally 'backup_path'.
        """
        try:
            # Verify the file still has the expected content
            current = file_path.read_text(encoding="utf-8")
            if current != original_content:
                return {
                    "success": False,
                    "error": "File has been modified since analysis; skipping to avoid conflicts",
                }

            backup_path = None
            if create_backup:
                backup_path = file_path.with_suffix(file_path.suffix + ".bak")
                shutil.copy2(file_path, backup_path)

            file_path.write_text(fixed_content, encoding="utf-8")

            return {
                "success": True,
                "backup_path": str(backup_path) if backup_path else None,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_tests(self) -> dict[str, Any]:
        """Run project tests to verify fixes did not break anything.

        Returns:
            Dict with 'success', 'exit_code', 'output'.
        """
        app = self._get_app()
        env_names = list(app.project.config.envs.keys())

        # Find test environment
        test_env = None
        for name in ("test", "tests", "default"):
            if name in env_names:
                test_env = name
                break
        if test_env is None and env_names:
            test_env = env_names[0]

        if test_env is None:
            return {"success": None, "error": "No test environment found"}

        try:
            env = app.get_environment(test_env)
            output_lines: list[str] = []

            try:
                for line in env.run_shell_command(["pytest"]):
                    output_lines.append(line)
                return {
                    "success": True,
                    "exit_code": 0,
                    "output": "\n".join(output_lines),
                }
            except Exception as e:
                return {
                    "success": False,
                    "exit_code": 1,
                    "output": "\n".join(output_lines) + f"\n{e}",
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_ruff_line(line: str) -> dict[str, str] | None:
        """Parse a ruff output line into structured error info.

        Expected format: path/to/file.py:10:5: E501 Line too long
        """
        parts = line.split(":", 3)
        if len(parts) < 4:
            return None

        file_path = parts[0].strip()
        line_no = parts[1].strip()

        # The rest is "col: CODE message"
        rest = parts[3].strip() if len(parts) > 3 else parts[2].strip()
        code_and_msg = rest.split(" ", 1)
        code = code_and_msg[0] if code_and_msg else ""
        message = code_and_msg[1] if len(code_and_msg) > 1 else rest

        if not file_path.endswith(".py"):
            return None

        return {
            "file": file_path,
            "line": line_no,
            "code": code,
            "message": message,
            "tool": "ruff",
        }

    @staticmethod
    def _parse_mypy_line(line: str) -> dict[str, str] | None:
        """Parse a mypy output line into structured error info.

        Expected format: path/to/file.py:10: error: Incompatible types [assignment]
        """
        parts = line.split(":", 2)
        if len(parts) < 3:
            return None

        file_path = parts[0].strip()
        line_no = parts[1].strip()
        rest = parts[2].strip()

        if not file_path.endswith(".py"):
            return None

        # Check if it's actually an error/warning line
        if not any(rest.startswith(kw) for kw in ("error:", "warning:", "note:")):
            return None

        # Extract error code if present [code]
        code = ""
        if "[" in rest and rest.endswith("]"):
            bracket_start = rest.rfind("[")
            code = rest[bracket_start + 1 : -1]
            rest = rest[:bracket_start].strip()

        return {
            "file": file_path,
            "line": line_no,
            "code": code,
            "message": rest,
            "tool": "mypy",
        }
