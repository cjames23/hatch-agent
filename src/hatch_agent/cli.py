"""Unified CLI entry point for hatch-agent.

Provides a single ``hatch-agent`` command with subcommands for all
AI-powered project management features.
"""

import click

from hatch_agent.commands.add_dependency import add_dep
from hatch_agent.commands.chat import chat
from hatch_agent.commands.config import generate_config
from hatch_agent.commands.doctor import doctor
from hatch_agent.commands.explain import explain
from hatch_agent.commands.fix import fix
from hatch_agent.commands.migrate import migrate
from hatch_agent.commands.multi_task import multi_task
from hatch_agent.commands.security import security
from hatch_agent.commands.sync import sync
from hatch_agent.commands.update_dependency import update_dep


@click.group()
def cli():
    """Hatch Agent - AI-powered assistance for Hatch projects."""


cli.add_command(multi_task, "task")
cli.add_command(chat, "chat")
cli.add_command(explain, "explain")
cli.add_command(add_dep, "add-dep")
cli.add_command(update_dep, "update-dep")
cli.add_command(generate_config, "config")
cli.add_command(sync, "sync")
cli.add_command(doctor, "doctor")
cli.add_command(fix, "fix")
cli.add_command(migrate, "migrate")
cli.add_command(security, "security")


if __name__ == "__main__":
    cli()
