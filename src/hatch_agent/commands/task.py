"""One-shot task execution command - wrapper to multi_task for backwards compatibility."""

import click

from hatch_agent.commands.multi_task import multi_task


# This is a backwards-compatible wrapper
# The actual implementation is in multi_task.py
@click.command()
@click.argument("task", nargs=-1, required=True)
@click.option(
    "--config",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Path to agent configuration file",
)
@click.option("--name", default=None, help="Name for the agent instance")
def run_task(task: tuple, config: str, name: str):
    """Run a one-shot task (wrapper to multi_task for backwards compatibility).

    Use hatch-agent instead for the full multi-task command.
    """
    # Simply forward to multi_task
    from click.testing import CliRunner

    runner = CliRunner()

    args = list(task)
    if config:
        args.extend(["--config", config])
    if name:
        args.extend(["--name", name])

    result = runner.invoke(multi_task, args)
    click.echo(result.output, nl=False)
    return result.exit_code


if __name__ == "__main__":
    run_task()
