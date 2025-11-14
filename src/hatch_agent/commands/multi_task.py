"""Multi-agent task execution command using Click."""

import click
from pathlib import Path

from hatch_agent.agent.core import Agent
from hatch_agent.config import load_config


@click.command()
@click.argument('task', nargs=-1, required=True)
@click.option(
    '--config',
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
    default=None,
    help='Path to agent configuration file'
)
@click.option(
    '--show-all',
    is_flag=True,
    help='Show all agent suggestions, not just the selected one'
)
def multi_task(task: tuple, config: Path, show_all: bool):
    """Run a task using multi-agent orchestration.

    This command uses a multi-agent approach with:
    - 2 specialist agents that generate different suggestions
    - 1 judge agent that evaluates and selects the best suggestion

    Examples:

      hatch-agent multi-task How do I set up testing with pytest?

      hatch-agent multi-task Configure my project for type checking
    """
    # Join task words
    task_description = " ".join(task)

    click.echo(f"🤖 Task: {click.style(task_description, fg='cyan')}")
    click.echo()

    # Load agent configuration
    cfg = load_config(config)
    provider = cfg.get("underlying_provider", "openai")
    provider_cfg = cfg.get("underlying_config", {})

    # Ensure model is set
    if cfg.get("model") and "model" not in provider_cfg:
        provider_cfg = dict(provider_cfg)
        provider_cfg["model"] = cfg.get("model")

    click.echo("🤖 Consulting AI agents...")
    click.echo()

    # Create agent with multi-agent orchestration enabled
    agent = Agent(
        name="hatch-multi-agent",
        use_multi_agent=True,
        provider_name=provider,
        provider_config=provider_cfg
    )

    result = agent.run_task(task_description)

    if not result.get("success"):
        click.echo(click.style("❌ Task failed:", fg="red"))
        click.echo(result.get("output", "Unknown error"))
        raise click.Abort()

    # Format the multi-agent output
    click.echo(click.style("=" * 70, fg="cyan"))
    click.echo(click.style("SELECTED SUGGESTION", fg="cyan", bold=True))
    click.echo(click.style("=" * 70, fg="cyan"))
    click.echo()
    click.echo(result.get("selected_suggestion", result.get("output", "")))
    click.echo()
    click.echo(click.style(f"Selected Agent: {result.get('selected_agent', 'N/A')}", fg="blue"))
    click.echo(click.style(f"Reasoning: {result.get('reasoning', 'N/A')}", fg="blue"))

    # Show all suggestions if requested
    if show_all and "all_suggestions" in result:
        click.echo()
        click.echo(click.style("=" * 70, fg="yellow"))
        click.echo(click.style("ALL AGENT SUGGESTIONS", fg="yellow", bold=True))
        click.echo(click.style("=" * 70, fg="yellow"))

        for i, suggestion in enumerate(result["all_suggestions"], 1):
            click.echo()
            click.echo(click.style(f"{i}. {suggestion['agent']}", fg="yellow", bold=True))
            click.echo(click.style(f"   Confidence: {suggestion['confidence']:.2f}", fg="yellow"))
            click.echo(f"   Suggestion: {suggestion['suggestion']}")
            click.echo(f"   Reasoning: {suggestion['reasoning']}")


if __name__ == "__main__":
    multi_task()
