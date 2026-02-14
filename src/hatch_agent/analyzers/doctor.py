"""Project health checking utilities for hatch-agent doctor command."""

import ast
import re
import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib as tomli
else:
    import tomli


# Standard library module names (top-level) that should not be flagged as undeclared deps
_STDLIB_TOP_LEVEL = frozenset(
    {
        "abc",
        "aifc",
        "argparse",
        "array",
        "ast",
        "asynchat",
        "asyncio",
        "asyncore",
        "atexit",
        "audioop",
        "base64",
        "bdb",
        "binascii",
        "binhex",
        "bisect",
        "builtins",
        "bz2",
        "calendar",
        "cgi",
        "cgitb",
        "chunk",
        "cmath",
        "cmd",
        "code",
        "codecs",
        "codeop",
        "collections",
        "colorsys",
        "compileall",
        "concurrent",
        "configparser",
        "contextlib",
        "contextvars",
        "copy",
        "copyreg",
        "cProfile",
        "crypt",
        "csv",
        "ctypes",
        "curses",
        "dataclasses",
        "datetime",
        "dbm",
        "decimal",
        "difflib",
        "dis",
        "distutils",
        "doctest",
        "email",
        "encodings",
        "enum",
        "errno",
        "faulthandler",
        "fcntl",
        "filecmp",
        "fileinput",
        "fnmatch",
        "formatter",
        "fractions",
        "ftplib",
        "functools",
        "gc",
        "getopt",
        "getpass",
        "gettext",
        "glob",
        "grp",
        "gzip",
        "hashlib",
        "heapq",
        "hmac",
        "html",
        "http",
        "idlelib",
        "imaplib",
        "imghdr",
        "imp",
        "importlib",
        "inspect",
        "io",
        "ipaddress",
        "itertools",
        "json",
        "keyword",
        "lib2to3",
        "linecache",
        "locale",
        "logging",
        "lzma",
        "mailbox",
        "mailcap",
        "marshal",
        "math",
        "mimetypes",
        "mmap",
        "modulefinder",
        "multiprocessing",
        "netrc",
        "nis",
        "nntplib",
        "numbers",
        "operator",
        "optparse",
        "os",
        "ossaudiodev",
        "pathlib",
        "pdb",
        "pickle",
        "pickletools",
        "pipes",
        "pkgutil",
        "platform",
        "plistlib",
        "poplib",
        "posix",
        "posixpath",
        "pprint",
        "profile",
        "pstats",
        "pty",
        "pwd",
        "py_compile",
        "pyclbr",
        "pydoc",
        "queue",
        "quopri",
        "random",
        "re",
        "readline",
        "reprlib",
        "resource",
        "rlcompleter",
        "runpy",
        "sched",
        "secrets",
        "select",
        "selectors",
        "shelve",
        "shlex",
        "shutil",
        "signal",
        "site",
        "smtpd",
        "smtplib",
        "sndhdr",
        "socket",
        "socketserver",
        "spwd",
        "sqlite3",
        "sre_compile",
        "sre_constants",
        "sre_parse",
        "ssl",
        "stat",
        "statistics",
        "string",
        "stringprep",
        "struct",
        "subprocess",
        "sunau",
        "symtable",
        "sys",
        "sysconfig",
        "syslog",
        "tabnanny",
        "tarfile",
        "telnetlib",
        "tempfile",
        "termios",
        "test",
        "textwrap",
        "threading",
        "time",
        "timeit",
        "tkinter",
        "token",
        "tokenize",
        "tomllib",
        "trace",
        "traceback",
        "tracemalloc",
        "tty",
        "turtle",
        "turtledemo",
        "types",
        "typing",
        "unicodedata",
        "unittest",
        "urllib",
        "uu",
        "uuid",
        "venv",
        "warnings",
        "wave",
        "weakref",
        "webbrowser",
        "winreg",
        "winsound",
        "wsgiref",
        "xdrlib",
        "xml",
        "xmlrpc",
        "zipapp",
        "zipfile",
        "zipimport",
        "zlib",
        # Common aliases / special names
        "_thread",
        "__future__",
        "_io",
        "_collections_abc",
    }
)

# Common mapping of PyPI package names to their importable top-level module names
_PACKAGE_IMPORT_MAP: dict[str, set[str]] = {
    "pillow": {"PIL"},
    "scikit-learn": {"sklearn"},
    "pyyaml": {"yaml"},
    "python-dateutil": {"dateutil"},
    "beautifulsoup4": {"bs4"},
    "opencv-python": {"cv2"},
    "attrs": {"attr", "attrs"},
    "tomli-w": {"tomli_w"},
    "strands-agents": {"strands"},
    "pytest-cov": {"pytest_cov"},
}


class ProjectDoctor:
    """Analyzes a Hatch project for health issues and misconfigurations."""

    def __init__(self, project_root: Path | None = None):
        """Initialize the project doctor.

        Args:
            project_root: Root directory of the Hatch project (defaults to current directory)
        """
        self.project_root = project_root or Path.cwd()
        self.pyproject_path = self.project_root / "pyproject.toml"

    def _load_pyproject(self) -> dict[str, Any] | None:
        """Load and return the pyproject.toml contents, or None if missing."""
        if not self.pyproject_path.exists():
            return None
        with open(self.pyproject_path, "rb") as f:
            return tomli.load(f)

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def check_pep621_compliance(self) -> list[dict[str, str]]:
        """Verify required and recommended PEP 621 fields in [project].

        Returns:
            List of {field, status, message} dicts.
            status is one of: "pass", "warn", "fail".
        """
        results: list[dict[str, str]] = []
        config = self._load_pyproject()

        if config is None:
            return [{"field": "pyproject.toml", "status": "fail", "message": "File not found"}]

        project = config.get("project", {})

        # Required fields
        required_fields = ["name", "version"]
        for field in required_fields:
            if field in project:
                results.append({"field": field, "status": "pass", "message": "Present"})
            else:
                results.append(
                    {
                        "field": field,
                        "status": "fail",
                        "message": f"Required field '{field}' missing",
                    }
                )

        # Recommended fields
        recommended_fields = {
            "description": "Helps users understand the project on PyPI",
            "readme": "README file for PyPI listing",
            "license": "License declaration for legal clarity",
            "requires-python": "Specifies supported Python versions",
            "classifiers": "PyPI classifiers help discoverability",
            "urls": "Project URLs (Homepage, Source, Tracker)",
        }

        # 'urls' can appear as project.urls
        for field, reason in recommended_fields.items():
            if field in project:
                results.append({"field": field, "status": "pass", "message": "Present"})
            else:
                results.append(
                    {"field": field, "status": "warn", "message": f"Recommended: {reason}"}
                )

        return results

    def check_hatch_config(self) -> list[dict[str, str]]:
        """Verify Hatch-specific configuration is well-formed.

        Returns:
            List of {field, status, message} dicts.
        """
        results: list[dict[str, str]] = []
        config = self._load_pyproject()

        if config is None:
            return [{"field": "pyproject.toml", "status": "fail", "message": "File not found"}]

        # Check build-system
        build_system = config.get("build-system", {})
        build_backend = build_system.get("build-backend", "")
        if "hatchling" in build_backend:
            results.append(
                {"field": "build-system", "status": "pass", "message": "Uses hatchling backend"}
            )
        else:
            results.append(
                {
                    "field": "build-system",
                    "status": "warn",
                    "message": f"Build backend is '{build_backend}', not hatchling",
                }
            )

        hatch = config.get("tool", {}).get("hatch", {})

        # Check build targets
        build_targets = hatch.get("build", {}).get("targets", {})
        wheel_config = build_targets.get("wheel", {})
        if wheel_config.get("packages"):
            packages = wheel_config["packages"]
            for pkg_path in packages:
                full_path = self.project_root / pkg_path
                if full_path.exists():
                    results.append(
                        {
                            "field": f"build.targets.wheel.packages ({pkg_path})",
                            "status": "pass",
                            "message": "Package directory exists",
                        }
                    )
                else:
                    results.append(
                        {
                            "field": f"build.targets.wheel.packages ({pkg_path})",
                            "status": "fail",
                            "message": f"Package directory '{pkg_path}' does not exist",
                        }
                    )
        else:
            results.append(
                {
                    "field": "build.targets.wheel.packages",
                    "status": "warn",
                    "message": "No explicit packages configured (hatchling will auto-detect)",
                }
            )

        # Check environments
        envs = hatch.get("envs", {})
        if envs:
            results.append(
                {
                    "field": "envs",
                    "status": "pass",
                    "message": f"{len(envs)} environment(s) configured",
                }
            )
        else:
            results.append(
                {
                    "field": "envs",
                    "status": "warn",
                    "message": "No environments configured in [tool.hatch.envs]",
                }
            )

        return results

    def check_dependency_hygiene(self) -> list[dict[str, str]]:
        """Compare declared dependencies against actual imports in source files.

        Returns:
            List of {field, status, message} dicts.
        """
        results: list[dict[str, str]] = []
        config = self._load_pyproject()

        if config is None:
            return [{"field": "pyproject.toml", "status": "fail", "message": "File not found"}]

        # Get declared dependencies
        project = config.get("project", {})
        declared_deps = project.get("dependencies", [])
        declared_packages = set()
        for dep in declared_deps:
            pkg_name = re.split(r"[><=~!\[;]", dep)[0].strip().lower()
            declared_packages.add(pkg_name)

        # Get actual imports from source files
        imported_modules = self._collect_imports()

        # Build reverse map: import name -> package name
        import_to_package: dict[str, str] = {}
        for pkg in declared_packages:
            # Default: package name with hyphens replaced by underscores
            import_name = pkg.replace("-", "_")
            import_to_package[import_name] = pkg
            # Also add from the known map
            if pkg in _PACKAGE_IMPORT_MAP:
                for alias in _PACKAGE_IMPORT_MAP[pkg]:
                    import_to_package[alias.lower()] = pkg

        # Check for imports that are not declared
        used_packages: set[str] = set()
        for mod in imported_modules:
            mod_lower = mod.lower()
            if mod_lower in _STDLIB_TOP_LEVEL or mod.startswith("_"):
                continue
            if mod_lower in import_to_package:
                used_packages.add(import_to_package[mod_lower])
            elif mod_lower in declared_packages or mod_lower.replace("_", "-") in declared_packages:
                used_packages.add(mod_lower)
            else:
                # Might be an undeclared dependency
                results.append(
                    {
                        "field": f"import '{mod}'",
                        "status": "warn",
                        "message": "Imported but not found in [project.dependencies]",
                    }
                )

        # Check for declared but unused dependencies
        unused = declared_packages - used_packages
        # Filter out common false positives (runtime-only deps, etc.)
        for pkg in sorted(unused):
            results.append(
                {
                    "field": f"dependency '{pkg}'",
                    "status": "warn",
                    "message": "Declared but not imported in source files (may be a runtime/CLI dep)",
                }
            )

        if not results:
            results.append(
                {
                    "field": "dependencies",
                    "status": "pass",
                    "message": "All declared dependencies appear to be used",
                }
            )

        return results

    def check_python_version_consistency(self) -> list[dict[str, str]]:
        """Check that requires-python, classifiers, and matrix are consistent.

        Returns:
            List of {field, status, message} dicts.
        """
        results: list[dict[str, str]] = []
        config = self._load_pyproject()

        if config is None:
            return [{"field": "pyproject.toml", "status": "fail", "message": "File not found"}]

        project = config.get("project", {})
        requires_python = project.get("requires-python", "")
        classifiers = project.get("classifiers", [])

        # Extract Python versions from classifiers
        classifier_versions: set[str] = set()
        for c in classifiers:
            match = re.match(r"Programming Language :: Python :: (\d+\.\d+)", c)
            if match:
                classifier_versions.add(match.group(1))

        # Extract Python versions from hatch matrix
        hatch = config.get("tool", {}).get("hatch", {})
        matrix_versions: set[str] = set()
        for _env_name, env_config in hatch.get("envs", {}).items():
            if isinstance(env_config, dict):
                # Check for inline matrix
                matrix = env_config.get("matrix", [])
                if isinstance(matrix, list):
                    for entry in matrix:
                        if isinstance(entry, dict) and "python" in entry:
                            for v in entry["python"]:
                                matrix_versions.add(str(v))

        if requires_python:
            results.append(
                {
                    "field": "requires-python",
                    "status": "pass",
                    "message": f"Set to '{requires_python}'",
                }
            )
        else:
            results.append(
                {
                    "field": "requires-python",
                    "status": "warn",
                    "message": "Not set -- recommended to specify supported Python versions",
                }
            )

        if classifier_versions and matrix_versions:
            if classifier_versions != matrix_versions:
                results.append(
                    {
                        "field": "python-versions",
                        "status": "warn",
                        "message": f"Classifier versions {sorted(classifier_versions)} "
                        f"differ from matrix versions {sorted(matrix_versions)}",
                    }
                )
            else:
                results.append(
                    {
                        "field": "python-versions",
                        "status": "pass",
                        "message": "Classifier and matrix versions are consistent",
                    }
                )
        elif classifier_versions:
            results.append(
                {
                    "field": "python-versions",
                    "status": "pass",
                    "message": f"Classifiers declare Python {sorted(classifier_versions)}",
                }
            )
        elif matrix_versions:
            results.append(
                {
                    "field": "python-versions",
                    "status": "pass",
                    "message": f"Matrix tests Python {sorted(matrix_versions)}",
                }
            )

        return results

    def check_entry_points(self) -> list[dict[str, str]]:
        """Verify that project.scripts and project.entry-points resolve to real modules.

        Returns:
            List of {field, status, message} dicts.
        """
        results: list[dict[str, str]] = []
        config = self._load_pyproject()

        if config is None:
            return [{"field": "pyproject.toml", "status": "fail", "message": "File not found"}]

        project = config.get("project", {})

        # Check [project.scripts]
        scripts = project.get("scripts", {})
        for name, target in scripts.items():
            check = self._check_entry_point_target(target)
            if check["resolvable"]:
                results.append(
                    {
                        "field": f"script '{name}'",
                        "status": "pass",
                        "message": f"Module '{check['module']}' exists",
                    }
                )
            else:
                results.append(
                    {
                        "field": f"script '{name}'",
                        "status": "fail",
                        "message": f"Module '{check['module']}' not found on disk",
                    }
                )

        # Check [project.entry-points]
        entry_points = project.get("entry-points", {})
        for group, entries in entry_points.items():
            if isinstance(entries, dict):
                for ep_name, target in entries.items():
                    check = self._check_entry_point_target(target)
                    if check["resolvable"]:
                        results.append(
                            {
                                "field": f"entry-point '{group}.{ep_name}'",
                                "status": "pass",
                                "message": f"Module '{check['module']}' exists",
                            }
                        )
                    else:
                        results.append(
                            {
                                "field": f"entry-point '{group}.{ep_name}'",
                                "status": "fail",
                                "message": f"Module '{check['module']}' not found on disk",
                            }
                        )

        if not scripts and not entry_points:
            results.append(
                {
                    "field": "entry-points",
                    "status": "pass",
                    "message": "No scripts or entry-points declared (nothing to check)",
                }
            )

        return results

    def check_gitignore(self) -> list[dict[str, str]]:
        """Verify .gitignore contains common Python/Hatch entries.

        Returns:
            List of {field, status, message} dicts.
        """
        results: list[dict[str, str]] = []
        gitignore_path = self.project_root / ".gitignore"

        if not gitignore_path.exists():
            return [
                {"field": ".gitignore", "status": "warn", "message": "No .gitignore file found"}
            ]

        content = gitignore_path.read_text(encoding="utf-8", errors="replace")

        recommended_entries = [
            "dist/",
            "*.egg-info",
            "__pycache__",
            ".venv",
            "build/",
        ]

        missing = []
        for entry in recommended_entries:
            # Check if the entry (or a close variant) is present
            if entry not in content and entry.rstrip("/") not in content:
                missing.append(entry)

        if missing:
            results.append(
                {
                    "field": ".gitignore",
                    "status": "warn",
                    "message": f"Missing recommended entries: {', '.join(missing)}",
                }
            )
        else:
            results.append(
                {
                    "field": ".gitignore",
                    "status": "pass",
                    "message": "Contains all recommended Python/Hatch entries",
                }
            )

        return results

    def run_all_checks(self) -> dict[str, Any]:
        """Run all health checks and return aggregated results.

        Returns:
            Dict with 'checks' list and 'summary' counts.
        """
        all_checks: list[dict[str, Any]] = []

        check_methods = [
            ("PEP 621 Compliance", self.check_pep621_compliance),
            ("Hatch Configuration", self.check_hatch_config),
            ("Dependency Hygiene", self.check_dependency_hygiene),
            ("Python Version Consistency", self.check_python_version_consistency),
            ("Entry Points", self.check_entry_points),
            (".gitignore", self.check_gitignore),
        ]

        passed = 0
        warned = 0
        failed = 0

        for category, method in check_methods:
            try:
                items = method()
            except Exception as e:
                items = [{"field": category, "status": "fail", "message": f"Check error: {e}"}]

            for item in items:
                item["category"] = category
                all_checks.append(item)
                if item["status"] == "pass":
                    passed += 1
                elif item["status"] == "warn":
                    warned += 1
                else:
                    failed += 1

        return {
            "checks": all_checks,
            "summary": {"passed": passed, "warned": warned, "failed": failed},
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _collect_imports(self) -> set[str]:
        """Walk source files and collect top-level import names."""
        imports: set[str] = set()

        # Find source files
        src_dirs = [
            self.project_root / "src",
            self.project_root / "lib",
        ]

        py_files: list[Path] = []
        for src_dir in src_dirs:
            if src_dir.exists():
                py_files.extend(src_dir.rglob("*.py"))

        # Also check project root (but not recursively to avoid venv etc.)
        for f in self.project_root.glob("*.py"):
            py_files.append(f)

        exclude_patterns = {"__pycache__", ".git", ".hatch", "dist", "build", ".venv", "venv"}

        for py_file in py_files:
            if any(part in exclude_patterns for part in py_file.parts):
                continue
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source, filename=str(py_file))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            top_level = alias.name.split(".")[0]
                            imports.add(top_level)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        top_level = node.module.split(".")[0]
                        imports.add(top_level)
            except (SyntaxError, UnicodeDecodeError):
                continue

        return imports

    def _check_entry_point_target(self, target: str) -> dict[str, Any]:
        """Check if a module:attribute entry-point target resolves on disk.

        Args:
            target: Entry-point string like 'mypackage.module:func'

        Returns:
            Dict with 'resolvable' bool and 'module' str.
        """
        # Split module:attribute
        module_path = target.split(":")[0]
        parts = module_path.split(".")

        # Try to find the module file in common source locations
        search_dirs = [
            self.project_root / "src",
            self.project_root,
        ]

        for base in search_dirs:
            # Try as a package (directory with __init__.py)
            pkg_path = base / "/".join(parts) / "__init__.py"
            if pkg_path.exists():
                return {"resolvable": True, "module": module_path}

            # Try as a module file
            mod_path = base / "/".join(parts[:-1]) / f"{parts[-1]}.py" if len(parts) > 1 else None
            if mod_path and mod_path.exists():
                return {"resolvable": True, "module": module_path}

            # Single-file module at root
            if len(parts) == 1:
                single = base / f"{parts[0]}.py"
                if single.exists():
                    return {"resolvable": True, "module": module_path}

        return {"resolvable": False, "module": module_path}
