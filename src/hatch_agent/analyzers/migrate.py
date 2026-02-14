"""Migration utilities for converting projects to Hatch from other build systems."""

import configparser
import re
import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib as tomli
else:
    import tomli

import tomli_w


class ProjectMigrator:
    """Detects, parses, and migrates projects from other build systems to Hatch."""

    SUPPORTED_SYSTEMS = ("setuptools", "poetry", "flit", "pdm", "pipfile")

    def __init__(self, project_root: Path | None = None):
        """Initialize the project migrator.

        Args:
            project_root: Root directory of the project to migrate.
        """
        self.project_root = project_root or Path.cwd()
        self.pyproject_path = self.project_root / "pyproject.toml"

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect_build_system(self) -> dict[str, Any]:
        """Detect the current build system used by the project.

        Returns:
            Dict with 'system' (str) and 'files' (list of relevant file paths).
        """
        detected: dict[str, Any] = {"system": None, "files": []}

        setup_py = self.project_root / "setup.py"
        setup_cfg = self.project_root / "setup.cfg"
        pipfile = self.project_root / "Pipfile"

        # Check pyproject.toml first
        if self.pyproject_path.exists():
            try:
                with open(self.pyproject_path, "rb") as f:
                    config = tomli.load(f)

                tool = config.get("tool", {})
                build_system = config.get("build-system", {})
                backend = build_system.get("build-backend", "")

                if "poetry" in tool:
                    detected["system"] = "poetry"
                    detected["files"].append(str(self.pyproject_path))
                elif "flit" in tool:
                    detected["system"] = "flit"
                    detected["files"].append(str(self.pyproject_path))
                elif "pdm" in tool:
                    detected["system"] = "pdm"
                    detected["files"].append(str(self.pyproject_path))
                elif "hatchling" in backend:
                    detected["system"] = "hatch"
                    detected["files"].append(str(self.pyproject_path))
                elif "setuptools" in backend:
                    detected["system"] = "setuptools"
                    detected["files"].append(str(self.pyproject_path))
            except Exception:
                pass

        # Check for setup.py / setup.cfg (setuptools)
        if detected["system"] is None:
            if setup_py.exists():
                detected["system"] = "setuptools"
                detected["files"].append(str(setup_py))
            if setup_cfg.exists():
                detected["system"] = "setuptools"
                detected["files"].append(str(setup_cfg))

        # Check for Pipfile
        if detected["system"] is None and pipfile.exists():
            detected["system"] = "pipfile"
            detected["files"].append(str(pipfile))

        return detected

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    def parse_setup_py(self, path: Path | None = None) -> dict[str, Any]:
        """Read setup.py as text and extract metadata via static analysis.

        Does NOT execute the file. Returns raw text for AI to handle dynamic cases.

        Args:
            path: Path to setup.py (defaults to project_root/setup.py)

        Returns:
            Dict with 'raw_content' and any statically parseable fields.
        """
        path = path or self.project_root / "setup.py"
        if not path.exists():
            return {"raw_content": "", "error": "setup.py not found"}

        content = path.read_text(encoding="utf-8", errors="replace")
        result: dict[str, Any] = {"raw_content": content}

        # Try to extract common fields with regex
        for field in ("name", "version", "description", "author", "author_email", "url", "license"):
            match = re.search(rf'{field}\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                result[field] = match.group(1)

        # Try to extract install_requires list
        requires_match = re.search(r"install_requires\s*=\s*\[(.*?)\]", content, re.DOTALL)
        if requires_match:
            raw = requires_match.group(1)
            deps = re.findall(r'["\']([^"\']+)["\']', raw)
            result["install_requires"] = deps

        # Try to extract python_requires
        py_match = re.search(r'python_requires\s*=\s*["\']([^"\']+)["\']', content)
        if py_match:
            result["python_requires"] = py_match.group(1)

        return result

    def parse_setup_cfg(self, path: Path | None = None) -> dict[str, Any]:
        """Parse setup.cfg using configparser.

        Args:
            path: Path to setup.cfg (defaults to project_root/setup.cfg)

        Returns:
            Dict with extracted metadata and options.
        """
        path = path or self.project_root / "setup.cfg"
        if not path.exists():
            return {"error": "setup.cfg not found"}

        parser = configparser.ConfigParser()
        parser.read(str(path), encoding="utf-8")

        result: dict[str, Any] = {}

        # [metadata] section
        if parser.has_section("metadata"):
            for key in (
                "name",
                "version",
                "description",
                "long_description",
                "author",
                "author_email",
                "url",
                "license",
                "classifiers",
                "python_requires",
            ):
                if parser.has_option("metadata", key):
                    value = parser.get("metadata", key)
                    if key == "classifiers":
                        result[key] = [c.strip() for c in value.strip().splitlines() if c.strip()]
                    else:
                        result[key] = value

        # [options] section
        if parser.has_section("options"):
            if parser.has_option("options", "install_requires"):
                raw = parser.get("options", "install_requires")
                result["install_requires"] = [
                    d.strip() for d in raw.strip().splitlines() if d.strip()
                ]

            if parser.has_option("options", "packages"):
                result["packages"] = parser.get("options", "packages")

            if parser.has_option("options", "python_requires"):
                result["python_requires"] = parser.get("options", "python_requires")

        # [options.extras_require]
        if parser.has_section("options.extras_require"):
            extras: dict[str, list[str]] = {}
            for key in parser.options("options.extras_require"):
                raw = parser.get("options.extras_require", key)
                extras[key] = [d.strip() for d in raw.strip().splitlines() if d.strip()]
            if extras:
                result["extras_require"] = extras

        # [options.entry_points]
        if parser.has_section("options.entry_points"):
            entry_points: dict[str, list[str]] = {}
            for key in parser.options("options.entry_points"):
                raw = parser.get("options.entry_points", key)
                entry_points[key] = [e.strip() for e in raw.strip().splitlines() if e.strip()]
            if entry_points:
                result["entry_points"] = entry_points

        result["raw_content"] = path.read_text(encoding="utf-8", errors="replace")

        return result

    def parse_poetry_config(self, pyproject: dict[str, Any] | None = None) -> dict[str, Any]:
        """Parse [tool.poetry] section from pyproject.toml.

        Args:
            pyproject: Pre-loaded pyproject.toml dict. If None, loads from disk.

        Returns:
            Dict with extracted metadata mapped toward PEP 621 fields.
        """
        if pyproject is None:
            if not self.pyproject_path.exists():
                return {"error": "pyproject.toml not found"}
            with open(self.pyproject_path, "rb") as f:
                pyproject = tomli.load(f)

        poetry = pyproject.get("tool", {}).get("poetry", {})
        if not poetry:
            return {"error": "No [tool.poetry] section found"}

        result: dict[str, Any] = {}

        # Direct mappings
        for field in ("name", "version", "description", "license", "readme"):
            if field in poetry:
                result[field] = poetry[field]

        # Authors (Poetry uses "Name <email>" format)
        if "authors" in poetry:
            result["authors"] = poetry["authors"]

        # Python version
        python_dep = poetry.get("dependencies", {}).get("python", "")
        if python_dep:
            result["requires_python"] = python_dep

        # Dependencies (exclude python)
        deps = poetry.get("dependencies", {})
        result["dependencies"] = []
        for pkg, spec in deps.items():
            if pkg.lower() == "python":
                continue
            if isinstance(spec, str):
                # Convert Poetry version spec to PEP 440
                result["dependencies"].append(f"{pkg}{self._poetry_to_pep440(spec)}")
            elif isinstance(spec, dict):
                version = spec.get("version", "")
                result["dependencies"].append(f"{pkg}{self._poetry_to_pep440(version)}")

        # Dev dependencies / groups
        dev_deps = poetry.get("dev-dependencies", {})
        if dev_deps:
            result["optional_dependencies"] = {"dev": []}
            for pkg, spec in dev_deps.items():
                if isinstance(spec, str):
                    result["optional_dependencies"]["dev"].append(
                        f"{pkg}{self._poetry_to_pep440(spec)}"
                    )

        # Poetry groups (newer format)
        groups = poetry.get("group", {})
        if groups:
            if "optional_dependencies" not in result:
                result["optional_dependencies"] = {}
            for group_name, group_data in groups.items():
                group_deps = group_data.get("dependencies", {})
                result["optional_dependencies"][group_name] = []
                for pkg, spec in group_deps.items():
                    if isinstance(spec, str):
                        result["optional_dependencies"][group_name].append(
                            f"{pkg}{self._poetry_to_pep440(spec)}"
                        )

        # Scripts
        if "scripts" in poetry:
            result["scripts"] = poetry["scripts"]

        # URLs
        if "urls" in poetry:
            result["urls"] = poetry["urls"]
        elif "homepage" in poetry or "repository" in poetry:
            result["urls"] = {}
            if "homepage" in poetry:
                result["urls"]["Homepage"] = poetry["homepage"]
            if "repository" in poetry:
                result["urls"]["Source"] = poetry["repository"]

        result["raw_content"] = str(poetry)

        return result

    def parse_flit_config(self, pyproject: dict[str, Any] | None = None) -> dict[str, Any]:
        """Parse [tool.flit] section from pyproject.toml.

        Args:
            pyproject: Pre-loaded pyproject.toml dict. If None, loads from disk.

        Returns:
            Dict with extracted metadata.
        """
        if pyproject is None:
            if not self.pyproject_path.exists():
                return {"error": "pyproject.toml not found"}
            with open(self.pyproject_path, "rb") as f:
                pyproject = tomli.load(f)

        flit = pyproject.get("tool", {}).get("flit", {})
        if not flit:
            return {"error": "No [tool.flit] section found"}

        result: dict[str, Any] = {}
        metadata = flit.get("metadata", {})

        for field in ("module", "author", "author-email", "description-file"):
            if field in metadata:
                result[field.replace("-", "_")] = metadata[field]

        if "requires-python" in metadata:
            result["requires_python"] = metadata["requires-python"]

        if "requires" in metadata:
            result["dependencies"] = metadata["requires"]

        if "requires-extra" in metadata:
            result["optional_dependencies"] = metadata["requires-extra"]

        if "scripts" in flit:
            result["scripts"] = flit["scripts"]

        # Also capture project section if present (Flit can use PEP 621)
        if "project" in pyproject:
            result["project_section"] = pyproject["project"]

        result["raw_content"] = str(flit)

        return result

    def parse_pdm_config(self, pyproject: dict[str, Any] | None = None) -> dict[str, Any]:
        """Parse [tool.pdm] section from pyproject.toml.

        Args:
            pyproject: Pre-loaded pyproject.toml dict. If None, loads from disk.

        Returns:
            Dict with extracted metadata.
        """
        if pyproject is None:
            if not self.pyproject_path.exists():
                return {"error": "pyproject.toml not found"}
            with open(self.pyproject_path, "rb") as f:
                pyproject = tomli.load(f)

        result: dict[str, Any] = {}

        # PDM typically uses PEP 621 [project] section
        if "project" in pyproject:
            result["project_section"] = pyproject["project"]

        pdm = pyproject.get("tool", {}).get("pdm", {})
        if pdm:
            result["pdm_config"] = pdm

            # PDM dev dependencies
            dev_deps = pdm.get("dev-dependencies", {})
            if dev_deps:
                result["optional_dependencies"] = dev_deps

        result["raw_content"] = str(pdm)

        return result

    def parse_pipfile(self, path: Path | None = None) -> dict[str, Any]:
        """Parse Pipfile (TOML format).

        Args:
            path: Path to Pipfile (defaults to project_root/Pipfile)

        Returns:
            Dict with extracted dependencies.
        """
        path = path or self.project_root / "Pipfile"
        if not path.exists():
            return {"error": "Pipfile not found"}

        content = path.read_text(encoding="utf-8", errors="replace")
        result: dict[str, Any] = {"raw_content": content}

        try:
            data = tomli.loads(content)
        except Exception:
            return result

        # [packages]
        packages = data.get("packages", {})
        result["dependencies"] = []
        for pkg, spec in packages.items():
            if isinstance(spec, str) and spec != "*":
                result["dependencies"].append(f"{pkg}{spec}")
            elif isinstance(spec, dict):
                version = spec.get("version", "")
                if version and version != "*":
                    result["dependencies"].append(f"{pkg}{version}")
                else:
                    result["dependencies"].append(pkg)
            else:
                result["dependencies"].append(pkg)

        # [dev-packages]
        dev_packages = data.get("dev-packages", {})
        result["dev_dependencies"] = []
        for pkg, spec in dev_packages.items():
            if isinstance(spec, str) and spec != "*":
                result["dev_dependencies"].append(f"{pkg}{spec}")
            elif isinstance(spec, dict):
                version = spec.get("version", "")
                if version and version != "*":
                    result["dev_dependencies"].append(f"{pkg}{version}")
                else:
                    result["dev_dependencies"].append(pkg)
            else:
                result["dev_dependencies"].append(pkg)

        # [requires]
        requires = data.get("requires", {})
        if "python_version" in requires:
            result["python_requires"] = f">={requires['python_version']}"

        return result

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate_hatch_pyproject(self, parsed_data: dict[str, Any]) -> dict[str, Any]:
        """Build a Hatch-native pyproject.toml dict from parsed data.

        Args:
            parsed_data: Parsed metadata from one of the parse_* methods.

        Returns:
            A complete pyproject.toml dict ready to be written.
        """
        config: dict[str, Any] = {
            "build-system": {
                "requires": ["hatchling>=1.27"],
                "build-backend": "hatchling.build",
            },
            "project": {},
        }

        project = config["project"]

        # Map common fields
        for field in ("name", "version", "description", "readme", "license"):
            if field in parsed_data:
                project[field] = parsed_data[field]

        # requires-python
        requires_python = parsed_data.get("requires_python") or parsed_data.get("python_requires")
        if requires_python:
            project["requires-python"] = requires_python

        # Authors
        if "authors" in parsed_data:
            authors_raw = parsed_data["authors"]
            if isinstance(authors_raw, list):
                project["authors"] = []
                for a in authors_raw:
                    if isinstance(a, str):
                        # Parse "Name <email>" format
                        match = re.match(r"(.+?)\s*<(.+?)>", a)
                        if match:
                            project["authors"].append(
                                {"name": match.group(1).strip(), "email": match.group(2).strip()}
                            )
                        else:
                            project["authors"].append({"name": a})
                    elif isinstance(a, dict):
                        project["authors"].append(a)
        elif "author" in parsed_data:
            author_entry: dict[str, str] = {"name": parsed_data["author"]}
            if "author_email" in parsed_data:
                author_entry["email"] = parsed_data["author_email"]
            project["authors"] = [author_entry]

        # Dependencies
        if "dependencies" in parsed_data:
            project["dependencies"] = parsed_data["dependencies"]
        elif "install_requires" in parsed_data:
            project["dependencies"] = parsed_data["install_requires"]

        # Optional dependencies
        if "optional_dependencies" in parsed_data:
            project["optional-dependencies"] = parsed_data["optional_dependencies"]
        elif "extras_require" in parsed_data:
            project["optional-dependencies"] = parsed_data["extras_require"]

        # Handle Pipfile dev deps
        if "dev_dependencies" in parsed_data and parsed_data["dev_dependencies"]:
            if "optional-dependencies" not in project:
                project["optional-dependencies"] = {}
            project["optional-dependencies"]["dev"] = parsed_data["dev_dependencies"]

        # Classifiers
        if "classifiers" in parsed_data:
            project["classifiers"] = parsed_data["classifiers"]

        # Scripts
        if "scripts" in parsed_data:
            project["scripts"] = parsed_data["scripts"]

        # Entry points
        if "entry_points" in parsed_data:
            entry_points = parsed_data["entry_points"]
            if "console_scripts" in entry_points:
                project["scripts"] = {}
                for ep in entry_points["console_scripts"]:
                    if "=" in ep:
                        name, target = ep.split("=", 1)
                        project["scripts"][name.strip()] = target.strip()

        # URLs
        if "urls" in parsed_data:
            project["urls"] = parsed_data["urls"]
        elif "url" in parsed_data:
            project["urls"] = {"Homepage": parsed_data["url"]}

        # Add Hatch-specific config
        if project.get("name"):
            pkg_name = project["name"].replace("-", "_")
            config.setdefault("tool", {})
            config["tool"]["hatch"] = {
                "build": {
                    "targets": {
                        "wheel": {
                            "packages": [f"src/{pkg_name}"],
                        }
                    }
                }
            }

        # If project section was already PEP 621 (PDM/Flit), merge it
        if "project_section" in parsed_data:
            existing = parsed_data["project_section"]
            for key, value in existing.items():
                if key not in project:
                    project[key] = value

        return config

    def write_pyproject(self, config: dict[str, Any], path: Path | None = None) -> None:
        """Write a pyproject.toml dict to disk.

        Args:
            config: The pyproject.toml dict to write.
            path: Output path (defaults to project_root/pyproject.toml).
        """
        path = path or self.pyproject_path
        with open(path, "wb") as f:
            tomli_w.dump(config, f)

    def get_migration_diff(self, parsed_data: dict[str, Any], new_config: dict[str, Any]) -> str:
        """Generate a human-readable summary of the migration.

        Args:
            parsed_data: Original parsed data.
            new_config: The generated Hatch pyproject.toml dict.

        Returns:
            A formatted string describing the migration.
        """
        lines: list[str] = []
        project = new_config.get("project", {})

        lines.append("Migration Summary:")
        lines.append(f"  Name: {project.get('name', 'N/A')}")
        lines.append(f"  Version: {project.get('version', 'N/A')}")

        deps = project.get("dependencies", [])
        lines.append(f"  Dependencies: {len(deps)}")

        opt_deps = project.get("optional-dependencies", {})
        for group, group_deps in opt_deps.items():
            lines.append(f"  Optional ({group}): {len(group_deps)}")

        if project.get("scripts"):
            lines.append(f"  Scripts: {len(project['scripts'])}")

        if project.get("requires-python"):
            lines.append(f"  Python: {project['requires-python']}")

        lines.append("  Build backend: hatchling")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _poetry_to_pep440(spec: str) -> str:
        """Convert a Poetry version constraint to PEP 440 format.

        Handles common cases like ^, ~, *, and exact versions.
        """
        if not spec or spec == "*":
            return ""

        # Caret constraint: ^1.2.3 -> >=1.2.3,<2.0.0
        if spec.startswith("^"):
            version = spec[1:]
            parts = version.split(".")
            if len(parts) >= 1:
                major = int(parts[0])
                if major == 0 and len(parts) >= 2:
                    minor = int(parts[1])
                    return f">={version},<0.{minor + 1}.0"
                return f">={version},<{major + 1}.0.0"

        # Tilde constraint: ~1.2.3 -> >=1.2.3,<1.3.0
        if spec.startswith("~"):
            version = spec[1:]
            parts = version.split(".")
            if len(parts) >= 2:
                major = parts[0]
                minor = int(parts[1])
                return f">={version},<{major}.{minor + 1}.0"

        # Already PEP 440 compatible (>=, ==, etc.)
        if spec[0] in (">", "<", "=", "!"):
            return spec

        # Bare version -> ==version
        if re.match(r"^\d", spec):
            return f"=={spec}"

        return spec
