"""Command entry points for hatch-agent."""

from hatch_agent.commands.add_dependency import add_dep
from hatch_agent.commands.chat import chat
from hatch_agent.commands.config import generate_config
from hatch_agent.commands.doctor import doctor
from hatch_agent.commands.explain import explain
from hatch_agent.commands.fix import fix
from hatch_agent.commands.migrate import migrate
from hatch_agent.commands.multi_task import multi_task
from hatch_agent.commands.update_dependency import update_dep

# Note: sync and security are intentionally not re-exported here to avoid
# shadowing their module names. Import them directly:
# from hatch_agent.commands.sync import sync
# from hatch_agent.commands.security import security

__all__ = [
    "chat",
    "generate_config",
    "doctor",
    "explain",
    "fix",
    "migrate",
    "add_dep",
    "update_dep",
    "multi_task",
]
