"""Security auditing utilities for hatch-agent security command."""

import re
import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib as tomli
else:
    import tomli

import requests as http_requests


class SecurityAuditor:
    """Audits project dependencies for known security vulnerabilities."""

    OSV_API_URL = "https://api.osv.dev/v1/query"
    PYPI_API_URL = "https://pypi.org/pypi/{package}/json"

    def __init__(self, project_root: Path | None = None):
        """Initialize the security auditor.

        Args:
            project_root: Root directory of the Hatch project (defaults to current directory)
        """
        self.project_root = project_root or Path.cwd()
        self.pyproject_path = self.project_root / "pyproject.toml"

    def get_all_dependencies(self) -> list[dict[str, str]]:
        """Get all declared dependencies with their version specs.

        Returns:
            List of dicts with 'name' and 'version_spec' keys.
        """
        if not self.pyproject_path.exists():
            return []

        with open(self.pyproject_path, "rb") as f:
            config = tomli.load(f)

        project = config.get("project", {})
        deps: list[dict[str, str]] = []

        # Main dependencies
        for dep in project.get("dependencies", []):
            parsed = self._parse_dep_string(dep)
            if parsed:
                deps.append(parsed)

        # Optional dependencies
        for group, group_deps in project.get("optional-dependencies", {}).items():
            for dep in group_deps:
                parsed = self._parse_dep_string(dep)
                if parsed:
                    parsed["group"] = group
                    deps.append(parsed)

        return deps

    def query_osv(self, package: str, version: str | None = None) -> list[dict[str, Any]]:
        """Query the OSV.dev API for vulnerabilities.

        Args:
            package: PyPI package name
            version: Specific version to check (optional)

        Returns:
            List of vulnerability records from OSV.
        """
        payload: dict[str, Any] = {
            "package": {"name": package, "ecosystem": "PyPI"},
        }
        if version:
            payload["version"] = version

        try:
            response = http_requests.post(
                self.OSV_API_URL,
                json=payload,
                timeout=15,
                headers={"User-Agent": "hatch-agent"},
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("vulns", [])
            return []
        except Exception:
            return []

    def query_pypi_advisory(self, package: str) -> list[dict[str, Any]]:
        """Query the PyPI JSON API for vulnerability advisories.

        Args:
            package: PyPI package name

        Returns:
            List of vulnerability dicts from PyPI's vulnerabilities field.
        """
        try:
            response = http_requests.get(
                self.PYPI_API_URL.format(package=package),
                timeout=10,
                headers={"User-Agent": "hatch-agent"},
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("vulnerabilities", [])
            return []
        except Exception:
            return []

    def run_audit(self) -> dict[str, Any]:
        """Run a full security audit on all project dependencies.

        Returns:
            Dict with 'vulnerabilities' list and 'summary' counts.
        """
        deps = self.get_all_dependencies()

        if not deps:
            return {
                "vulnerabilities": [],
                "summary": {"critical": 0, "high": 0, "medium": 0, "low": 0, "unknown": 0},
                "packages_checked": 0,
            }

        vulnerabilities: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for dep in deps:
            package = dep["name"]
            version = dep.get("installed_version") or re.sub(
                r"^[>=<~!]+", "", dep.get("version_spec", "")
            )

            # Query OSV
            osv_vulns = self.query_osv(package, version if version else None)
            for vuln in osv_vulns:
                vuln_id = vuln.get("id", "")
                if vuln_id in seen_ids:
                    continue
                seen_ids.add(vuln_id)

                severity = self._extract_severity(vuln)
                fixed_in = self._extract_fixed_version(vuln, package)

                vulnerabilities.append(
                    {
                        "package": package,
                        "installed_version": version or "unknown",
                        "vuln_id": vuln_id,
                        "severity": severity,
                        "summary": vuln.get("summary", vuln.get("details", "No description")[:200]),
                        "fixed_in": fixed_in,
                        "url": f"https://osv.dev/vulnerability/{vuln_id}" if vuln_id else None,
                        "source": "osv",
                    }
                )

            # Query PyPI advisories
            pypi_vulns = self.query_pypi_advisory(package)
            for vuln in pypi_vulns:
                vuln_id = vuln.get("id", "")
                if vuln_id in seen_ids:
                    continue
                seen_ids.add(vuln_id)

                vulnerabilities.append(
                    {
                        "package": package,
                        "installed_version": version or "unknown",
                        "vuln_id": vuln_id,
                        "severity": vuln.get("severity", "unknown").lower(),
                        "summary": vuln.get("summary", vuln.get("details", "No description")[:200]),
                        "fixed_in": ", ".join(vuln.get("fixed_in", [])),
                        "url": vuln.get("link", None),
                        "source": "pypi",
                    }
                )

        # Build summary
        summary = {"critical": 0, "high": 0, "medium": 0, "low": 0, "unknown": 0}
        for v in vulnerabilities:
            sev = v.get("severity", "unknown").lower()
            if sev in summary:
                summary[sev] += 1
            else:
                summary["unknown"] += 1

        return {
            "vulnerabilities": vulnerabilities,
            "summary": summary,
            "packages_checked": len(deps),
        }

    def suggest_fixes(self, vulnerabilities: list[dict[str, Any]]) -> list[dict[str, str]]:
        """Suggest version bumps to fix vulnerabilities.

        Args:
            vulnerabilities: List of vulnerability dicts from run_audit().

        Returns:
            List of {package, current_version, recommended_version, vuln_ids} dicts.
        """
        # Group by package
        by_package: dict[str, dict[str, Any]] = {}
        for v in vulnerabilities:
            pkg = v["package"]
            if pkg not in by_package:
                by_package[pkg] = {
                    "package": pkg,
                    "current_version": v["installed_version"],
                    "vuln_ids": [],
                    "fixed_versions": [],
                }
            by_package[pkg]["vuln_ids"].append(v["vuln_id"])
            if v.get("fixed_in"):
                by_package[pkg]["fixed_versions"].append(v["fixed_in"])

        suggestions = []
        for pkg, info in by_package.items():
            recommended = None
            if info["fixed_versions"]:
                # Use the highest fixed_in version available
                recommended = max(info["fixed_versions"], default=None)

            suggestions.append(
                {
                    "package": pkg,
                    "current_version": info["current_version"],
                    "recommended_version": recommended or "latest",
                    "vuln_ids": ", ".join(info["vuln_ids"]),
                }
            )

        return suggestions

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_dep_string(dep: str) -> dict[str, str] | None:
        """Parse a PEP 508 dependency string into name and version spec."""
        # Remove environment markers (everything after ';')
        dep = dep.split(";")[0].strip()
        if not dep:
            return None

        # Split name from version specifier
        match = re.match(r"^([A-Za-z0-9_][A-Za-z0-9._-]*)(.*)$", dep)
        if not match:
            return None

        name = match.group(1).strip()
        version_spec = match.group(2).strip()

        # Remove extras like [extra1,extra2]
        name = re.split(r"\[", name)[0]

        return {"name": name, "version_spec": version_spec}

    @staticmethod
    def _extract_severity(vuln: dict[str, Any]) -> str:
        """Extract severity level from an OSV vulnerability record."""
        # Try database_specific severity
        db_specific = vuln.get("database_specific", {})
        severity = db_specific.get("severity")
        if severity:
            return severity.lower()

        # Try severity array
        severity_list = vuln.get("severity", [])
        if isinstance(severity_list, list):
            for s in severity_list:
                if isinstance(s, dict) and s.get("type") == "CVSS_V3":
                    score_str = s.get("score", "")
                    try:
                        score = float(score_str) if score_str else 0.0
                    except (ValueError, TypeError):
                        # CVSS vector string, not a numeric score
                        continue
                    if score >= 9.0:
                        return "critical"
                    elif score >= 7.0:
                        return "high"
                    elif score >= 4.0:
                        return "medium"
                    else:
                        return "low"

        return "unknown"

    @staticmethod
    def _extract_fixed_version(vuln: dict[str, Any], package: str) -> str | None:
        """Extract the fixed version from an OSV vulnerability record."""
        affected = vuln.get("affected", [])
        for entry in affected:
            pkg = entry.get("package", {})
            if pkg.get("name", "").lower() == package.lower():
                ranges = entry.get("ranges", [])
                for r in ranges:
                    events = r.get("events", [])
                    for event in events:
                        if "fixed" in event:
                            return event["fixed"]
        return None
