"""CLI command for adding dependencies using natural language and multi-agent AI."""

import click
from pathlib import Path
import json

from hatch_agent.agent.core import Agent
from hatch_agent.config import load_config
from hatch_agent.analyzers.dependency import DependencyManager


@click.command()
@click.argument('description', nargs=-1, required=True)
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
    '--dry-run',
    is_flag=True,
    help='Show what would be done without making changes'
)
@click.option(
    '--show-all',
    is_flag=True,
    help='Show all agent suggestions, not just the selected one'
)
@click.option(
    '--skip-sync',
    is_flag=True,
    help='Skip syncing Hatch environment after adding dependency'
)
def add_dep(description: tuple, project_root: Path, config: Path, dry_run: bool, show_all: bool, skip_sync: bool):
    """Add a dependency to your Hatch project using natural language.

    Examples:

      hatch-agent add-dep add requests for http client

      hatch-agent add-dep add pytest to dev dependencies

      hatch-agent add-dep I need pandas version 2.0 or higher
    """
    # Join description words
    user_request = " ".join(description)

    click.echo(f"📦 Processing request: {click.style(user_request, fg='cyan')}")
    click.echo()

    # Get current dependencies for context
    dep_manager = DependencyManager(project_root)
    current_deps = dep_manager.get_current_dependencies()

    # Build context for agents
    context = {
        "project_root": str(project_root or Path.cwd()),
        "current_dependencies": current_deps,
        "user_request": user_request
    }

    # Construct task for agents
    task = _build_dependency_task(user_request, current_deps)

    # Load agent configuration
    cfg = load_config(config)
    provider = cfg.get("underlying_provider", "openai")
    provider_cfg = cfg.get("underlying_config", {})

    # Ensure model is set
    if cfg.get("model") and "model" not in provider_cfg:
        provider_cfg = dict(provider_cfg)
        provider_cfg["model"] = cfg.get("model")

    click.echo("🤖 Consulting AI agents to determine the best approach...")
    click.echo()

    # Create agent with multi-agent orchestration
    agent = Agent(
        name="dependency-manager",
        use_multi_agent=True,
        provider_name=provider,
        provider_config=provider_cfg
    )

    # Add context to agent
    agent.prepare(context)

    # Run the analysis
    result = agent.run_task(task)

    if not result.get("success"):
        click.echo(click.style("❌ Analysis failed:", fg="red"))
        click.echo(result.get("output", "Unknown error"))
        raise click.Abort()

    # Parse the suggestion to extract dependency details
    suggestion = result.get("selected_suggestion", "")

    click.echo(click.style("=" * 70, fg="cyan"))
    click.echo(click.style("RECOMMENDED ACTION", fg="cyan", bold=True))
    click.echo(click.style("=" * 70, fg="cyan"))
    click.echo()
    click.echo(suggestion)
    click.echo()
    click.echo(click.style(f"Selected from: {result.get('selected_agent', 'N/A')}", fg="blue"))

    # Show all suggestions if requested
    if show_all and "all_suggestions" in result:
        click.echo()
        click.echo(click.style("=" * 70, fg="yellow"))
        click.echo(click.style("ALL AGENT SUGGESTIONS", fg="yellow", bold=True))
        click.echo(click.style("=" * 70, fg="yellow"))

        for i, sug in enumerate(result["all_suggestions"], 1):
            click.echo()
            click.echo(click.style(f"{i}. {sug['agent']}", fg="yellow", bold=True))
            click.echo(click.style(f"   Confidence: {sug['confidence']:.2f}", fg="yellow"))
            click.echo(f"   Suggestion: {sug['suggestion']}")

    click.echo()

    # Try to parse structured action from the suggestion
    dependency_info = _extract_dependency_info(suggestion)

    if not dependency_info:
        click.echo(click.style("⚠️  Could not automatically execute the suggestion.", fg="yellow"))
        click.echo("Please review the recommendation above and apply manually.")
        return

    # Show what will be done
    click.echo(click.style("📝 Proposed changes:", fg="green", bold=True))
    click.echo(f"  Package: {dependency_info['package']}")
    if dependency_info.get('version'):
        click.echo(f"  Version: {dependency_info['version']}")
    if dependency_info.get('group'):
        click.echo(f"  Group: {dependency_info['group']}")
    click.echo()

    if dry_run:
        click.echo(click.style("🔍 DRY RUN - No changes will be made", fg="yellow"))
        return

    # Ask for confirmation
    if not click.confirm("Apply these changes?"):
        click.echo("Cancelled.")
        return

    # Add the dependency
    click.echo()
    click.echo("✏️  Modifying pyproject.toml...")

    add_result = dep_manager.add_dependency(
        package=dependency_info['package'],
        version_spec=dependency_info.get('version'),
        optional_group=dependency_info.get('group')
    )

    if not add_result.get("success"):
        click.echo(click.style(f"❌ Failed to add dependency: {add_result.get('error')}", fg="red"))
        raise click.Abort()

    click.echo(click.style(f"✅ Added '{add_result['dependency_string']}' to {add_result['target']}", fg="green"))

    # Sync environment
    if not skip_sync:
        click.echo()
        click.echo("🔄 Syncing Hatch environment...")

        sync_result = dep_manager.sync_environment()

        if sync_result.get("success"):
            click.echo(click.style("✅ Environment synced successfully", fg="green"))
        else:
            click.echo(click.style(f"⚠️  Environment sync had issues: {sync_result.get('error', 'Unknown error')}", fg="yellow"))
            click.echo("You may need to run 'hatch env create' manually.")
    else:
        click.echo()
        click.echo(click.style("⏭️  Skipped environment sync (--skip-sync flag)", fg="yellow"))
        click.echo("Run 'hatch env create' to install the new dependency.")

    click.echo()
    click.echo(click.style("🎉 Done!", fg="green", bold=True))


def _build_dependency_task(user_request: str, current_deps: dict) -> str:
    """Build the task description for agents."""
    deps_summary = {
        "main_count": len(current_deps.get("main", [])),
        "optional_groups": list(current_deps.get("optional", {}).keys())
    }

    return f"""User wants to add a dependency with this request: "{user_request}"

Current project state:
- Main dependencies: {deps_summary['main_count']} packages
- Optional dependency groups: {deps_summary['optional_groups']}

Your task:
1. Determine the exact package name to add
2. Determine the appropriate version specification (if any)
3. Determine if this should be a main dependency or optional dependency (and which group)
4. Provide the complete modification plan

IMPORTANT: Your response MUST include a structured action in this EXACT format:

ACTION:
{{
    "package": "package-name",
    "version": ">=1.0.0",  // optional, omit if not needed
    "group": "dev"  // optional, omit for main dependencies
}}

Provide this JSON block at the END of your suggestion, after your explanation.

Example response format:
"Based on your request, I recommend adding the 'requests' package...
[explanation]

ACTION:
{{
    "package": "requests",
    "version": ">=2.28.0"
}}"

Be precise with package names and version specifications."""


def _extract_dependency_info(suggestion: str) -> dict:
    """Extract structured dependency information from agent suggestion."""
    # Look for ACTION: JSON block
    if "ACTION:" not in suggestion:
        return None

    # Extract the JSON portion
    try:
        action_part = suggestion.split("ACTION:")[1].strip()

        # Find the JSON object
        start = action_part.find("{")
        end = action_part.rfind("}") + 1

        if start == -1 or end == 0:
            return None

        json_str = action_part[start:end]
        action_data = json.loads(json_str)

        # Validate required fields
        if "package" not in action_data:
            return None

        return action_data
    except (json.JSONDecodeError, IndexError):
        return None


if __name__ == "__main__":
    add_dep()

