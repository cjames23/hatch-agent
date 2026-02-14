"""CLI command for project health checking using multi-agent analysis."""

from pathlib import Path

import click

from hatch_agent.agent.core import Agent
from hatch_agent.analyzers.doctor import ProjectDoctor
from hatch_agent.config import load_config


@click.command()
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="Root directory of the Hatch project (defaults to current directory)",
)
@click.option(
    "--config",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to agent configuration file",
)
@click.option(
    "--show-all", is_flag=True, help="Show all agent suggestions, not just the selected one"
)
@click.option(
    "--no-ai", is_flag=True, help="Run checks only, skip AI analysis and recommendations"
)
def doctor(project_root: Path | None, config: Path | None, show_all: bool, no_ai: bool):
    """Check project health and get AI-powered recommendations.

    Runs a suite of checks on your Hatch project including PEP 621 compliance,
    Hatch configuration, dependency hygiene, Python version consistency,
    entry point resolution, and .gitignore completeness.

    Examples:

      hatch-agent doctor

      hatch-agent doctor --no-ai

      hatch-agent doctor --project-root /path/to/project --show-all
    """
    click.echo(click.style("🩺 Hatch Agent Doctor", fg="cyan", bold=True))
    click.echo()

    # Run all checks
    project_doctor = ProjectDoctor(project_root)
    report = project_doctor.run_all_checks()

    checks = report["checks"]
    summary = report["summary"]

    # Display results grouped by category
    current_category = None
    for item in checks:
        if item["category"] != current_category:
            current_category = item["category"]
            click.echo(click.style(f"── {current_category} ──", fg="cyan"))

        status = item["status"]
        if status == "pass":
            icon = click.style("✓", fg="green")
        elif status == "warn":
            icon = click.style("⚠", fg="yellow")
        else:
            icon = click.style("✗", fg="red")

        click.echo(f"  {icon} {item['field']}: {item['message']}")

    # Summary
    click.echo()
    click.echo(click.style("─" * 50, fg="cyan"))
    click.echo(
        f"  {click.style(str(summary['passed']), fg='green')} passed  "
        f"{click.style(str(summary['warned']), fg='yellow')} warnings  "
        f"{click.style(str(summary['failed']), fg='red')} failed"
    )
    click.echo()

    if no_ai:
        return

    # Build task for AI analysis
    task = _build_doctor_task(checks, summary)

    # Load agent configuration
    cfg = load_config(config)
    provider = cfg.get("underlying_provider", "openai")
    provider_cfg = cfg.get("underlying_config", {})

    if cfg.get("model") and "model" not in provider_cfg:
        provider_cfg = dict(provider_cfg)
        provider_cfg["model"] = cfg.get("model")

    click.echo("🤖 Consulting AI agents for recommendations...")
    click.echo()

    agent = Agent(
        name="project-doctor",
        use_multi_agent=True,
        provider_name=provider,
        provider_config=provider_cfg,
    )

    agent.prepare({"checks": checks, "summary": summary})

    result = agent.run_task(task)

    if not result.get("success"):
        click.echo(click.style("❌ AI analysis failed:", fg="red"))
        click.echo(result.get("output", "Unknown error"))
        raise click.Abort()

    # Display the selected suggestion
    click.echo(click.style("=" * 70, fg="cyan"))
    click.echo(click.style("RECOMMENDATIONS", fg="cyan", bold=True))
    click.echo(click.style("=" * 70, fg="cyan"))
    click.echo()
    click.echo(result.get("selected_suggestion", "No recommendations available"))
    click.echo()
    click.echo(click.style(f"Selected from: {result.get('selected_agent', 'N/A')}", fg="blue"))
    click.echo(click.style("Reasoning:", fg="blue"))
    click.echo(result.get("reasoning", "N/A"))

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


def _build_doctor_task(checks: list[dict], summary: dict) -> str:
    """Build the task description for AI agents based on check results."""
    issues = [c for c in checks if c["status"] != "pass"]

    if not issues:
        return (
            "All project health checks passed. Provide recommendations for "
            "maintaining best practices and any proactive improvements."
        )

    issues_text = "\n".join(
        f"- [{c['status'].upper()}] {c['category']} > {c['field']}: {c['message']}"
        for c in issues
    )

    return f"""Analyze the following Hatch project health check results and provide
actionable recommendations to improve project quality:

Summary: {summary['passed']} passed, {summary['warned']} warnings, {summary['failed']} failures

Issues found:
{issues_text}

Please:
1. Prioritize the most impactful issues to fix first
2. Provide specific steps to resolve each issue
3. Explain why each fix matters
4. Include relevant pyproject.toml snippets or Hatch commands
5. Suggest any additional best practices"""


if __name__ == "__main__":
    doctor()
