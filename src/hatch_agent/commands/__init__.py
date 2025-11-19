"""Command entry points for hatch-agent."""

from hatch_agent.commands.chat import chat
from hatch_agent.commands.task import run_task
from hatch_agent.commands.config import generate_config
from hatch_agent.commands.explain import explain
from hatch_agent.commands.add_dependency import add_dep
from hatch_agent.commands.update_dependency import update_dep
from hatch_agent.commands.multi_task import multi_task

__all__ = [
    "chat",
    "run_task",
    "generate_config",
    "explain",
    "add_dep",
    "update_dep",
    "multi_task"
]
