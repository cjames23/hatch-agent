"""Interactive chat command implementation using multi-agent system."""

from pathlib import Path

import click

from hatch_agent.agent.core import Agent
from hatch_agent.config import load_config


@click.command()
@click.option(
    "--config",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to agent configuration file",
)
@click.option("--name", default="hatch-agent", help="Name for the agent instance")
@click.option(
    "--single-agent",
    is_flag=True,
    help="Use single agent mode instead of multi-agent (faster, less thorough)",
)
def chat(config: Path | None, name: str, single_agent: bool) -> None:
    """Start an interactive chat session with the AI agent.

    This provides a REPL interface where you can ask questions about
    your Hatch project and get AI-powered assistance.

    Examples:

      hatch-agent chat

      hatch-agent chat --single-agent  # Faster responses
    """
    # Load configuration
    cfg = load_config(str(config) if config else None)
    provider = cfg.get("underlying_provider", "openai")
    provider_cfg = cfg.get("underlying_config", {})

    # Ensure model is set
    if cfg.get("model") and "model" not in provider_cfg:
        provider_cfg = dict(provider_cfg)
        provider_cfg["model"] = cfg.get("model")

    # Create agent
    use_multi = not single_agent
    agent = Agent(
        name=name, use_multi_agent=use_multi, provider_name=provider, provider_config=provider_cfg
    )

    # Display welcome message
    mode_str = "multi-agent" if use_multi else "single-agent"
    click.echo(
        click.style(f"🤖 Hatch-Agent Interactive Chat ({mode_str} mode)", fg="cyan", bold=True)
    )
    click.echo(
        click.style(f"Provider: {provider} | Model: {cfg.get('model', 'default')}", fg="blue")
    )
    click.echo()
    click.echo("Type your questions or commands. Type 'exit' or 'quit' to end the session.")
    click.echo(click.style("─" * 70, fg="cyan"))
    click.echo()

    try:
        while True:
            # Get user input
            try:
                msg = click.prompt(click.style("You", fg="green", bold=True), prompt_suffix="> ")
            except click.Abort:
                break

            if not msg or msg.strip().lower() in {"exit", "quit", "q"}:
                click.echo(click.style("\n👋 Goodbye!", fg="cyan"))
                break

            # Show thinking indicator
            click.echo(click.style("🤔 Thinking...", fg="yellow"), nl=False)
            click.echo("\r" + " " * 20 + "\r", nl=False)  # Clear the line

            # Get response from agent
            if use_multi:
                # Use multi-agent task runner
                result = agent.run_task(msg)

                if result.get("success"):
                    click.echo(click.style("Agent", fg="cyan", bold=True) + "> ", nl=False)
                    click.echo(
                        result.get("selected_suggestion", result.get("output", "No response"))
                    )

                    # Show which agent answered
                    if result.get("selected_agent"):
                        click.echo(
                            click.style(
                                f"  [from {result.get('selected_agent')}]", fg="blue", dim=True
                            )
                        )
                else:
                    click.echo(
                        click.style("Error> ", fg="red") + result.get("output", "Unknown error")
                    )
            else:
                # Use simple chat
                try:
                    resp = agent.chat(msg)
                    click.echo(click.style("Agent", fg="cyan", bold=True) + f"> {resp}")
                except Exception as e:
                    click.echo(click.style(f"Error> {e}", fg="red"))

            click.echo()

    except (KeyboardInterrupt, EOFError):
        click.echo(click.style("\n\n👋 Interrupted. Goodbye!", fg="cyan"))


if __name__ == "__main__":
    chat()
