"""CLI command for explaining build failures using multi-agent analysis."""

import click
from pathlib import Path

from hatch_agent.agent.core import Agent
from hatch_agent.config import load_config
from hatch_agent.analyzers.build import BuildAnalyzer


@click.command()
@click.option(
    '--project-root',
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help='Root directory of the Hatch project (defaults to current directory)'
)
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
def explain(project_root: Path, config: Path, show_all: bool):
    """Explain why a Hatch build failed.

    This command analyzes test failures, formatting issues, and type checking
    errors, then uses multi-agent AI to provide explanations and suggestions.
    """
    click.echo("🔍 Analyzing build failures...")
    click.echo()

    # Analyze the build
    analyzer = BuildAnalyzer(project_root)
    build_context = analyzer.analyze_build_failure()

    # Show what was checked
    click.echo("Checked:")
    click.echo(f"  ✓ Tests: {_status_icon(build_context['test_result'])}")
    click.echo(f"  ✓ Formatting: {_status_icon(build_context['format_result'])}")
    click.echo(f"  ✓ Type checking: {_status_icon(build_context['type_result'])}")
    click.echo()

    # Construct task description for agents
    task = _build_explanation_task(build_context)

    # Load agent configuration
    cfg = load_config(config)
    provider = cfg.get("underlying_provider", "openai")
    provider_cfg = cfg.get("underlying_config", {})

    # Ensure model is set
    if cfg.get("model") and "model" not in provider_cfg:
        provider_cfg = dict(provider_cfg)
        provider_cfg["model"] = cfg.get("model")

    click.echo("🤖 Consulting AI agents for analysis...")
    click.echo()

    # Create agent with multi-agent orchestration
    agent = Agent(
        name="build-explainer",
        use_multi_agent=True,
        provider_name=provider,
        provider_config=provider_cfg
    )

    # Add build context to agent state
    agent.prepare(build_context)

    # Run the analysis
    result = agent.run_task(task)

    if not result.get("success"):
        click.echo(click.style("❌ Analysis failed:", fg="red"))
        click.echo(result.get("output", "Unknown error"))
        raise click.Abort()

    # Display the selected suggestion
    click.echo(click.style("=" * 70, fg="cyan"))
    click.echo(click.style("ANALYSIS & RECOMMENDATIONS", fg="cyan", bold=True))
    click.echo(click.style("=" * 70, fg="cyan"))
    click.echo()
    click.echo(result.get("selected_suggestion", "No suggestion available"))
    click.echo()
    click.echo(click.style(f"Selected from: {result.get('selected_agent', 'N/A')}", fg="blue"))
    click.echo(click.style("Reasoning:", fg="blue"))
    click.echo(result.get("reasoning", "N/A"))

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


def _status_icon(result: dict) -> str:
    """Get a status icon for a result."""
    if result.get("success") is True:
        return click.style("PASSED", fg="green")
    elif result.get("success") is False:
        return click.style("FAILED", fg="red")
    else:
        return click.style("SKIPPED", fg="yellow")


def _build_explanation_task(context: dict) -> str:
    """Build the task description for agents."""
    failures = []

    test_result = context.get("test_result", {})
    if test_result.get("success") is False:
        failures.append(f"Tests failed with exit code {test_result.get('exit_code')}:\n{test_result.get('stderr', test_result.get('stdout', ''))[:500]}")

    format_result = context.get("format_result", {})
    if format_result.get("success") is False:
        failures.append(f"Formatting issues:\n{format_result.get('stdout', format_result.get('stderr', ''))[:500]}")

    type_result = context.get("type_result", {})
    if type_result.get("success") is False:
        failures.append(f"Type checking errors:\n{type_result.get('stdout', type_result.get('stderr', ''))[:500]}")

    if not failures:
        return "All checks passed. Provide recommendations for maintaining code quality."

    failure_text = "\n\n".join(failures)

    return f"""Analyze the following Hatch build failures and provide a clear explanation with actionable recommendations:

{failure_text}

Please:
1. Identify the root cause of each failure
2. Explain what went wrong in clear terms
3. Provide step-by-step fixes
4. Suggest preventive measures for the future
5. Include any relevant Hatch commands to resolve issues"""


if __name__ == "__main__":
    explain()

