"""Project analysis helpers."""

from hatch_agent.analyzers.config import analyze_config
from hatch_agent.analyzers.dependencies import analyze_dependencies
from hatch_agent.analyzers.doctor import ProjectDoctor
from hatch_agent.analyzers.fix import BuildFixer
from hatch_agent.analyzers.migrate import ProjectMigrator
from hatch_agent.analyzers.project import analyze_project
from hatch_agent.analyzers.security import SecurityAuditor
from hatch_agent.analyzers.sync import DependencySync

__all__ = [
    "analyze_project",
    "analyze_dependencies",
    "analyze_config",
    "DependencySync",
    "ProjectDoctor",
    "BuildFixer",
    "ProjectMigrator",
    "SecurityAuditor",
]
