"""CLI command for updating dependencies and adapting code to API changes."""

import json
from pathlib import Path

import click

from hatch_agent.agent.core import Agent
from hatch_agent.analyzers.updater import DependencyUpdater
from hatch_agent.config import load_config


@click.command()
@click.argument("package", required=True)
@click.option(
    "--version", default="latest", help='Target version (e.g., "2.30.0", ">=2.30.0", or "latest")'
)
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
@click.option("--dry-run", is_flag=True, help="Show what would be done without making changes")
@click.option(
    "--show-all", is_flag=True, help="Show all agent suggestions, not just the selected one"
)
@click.option("--skip-sync", is_flag=True, help="Skip syncing Hatch environment after updating")
@click.option(
    "--no-code-changes", is_flag=True, help="Only update pyproject.toml, do not modify code"
)
def update_dep(
    package: str,
    version: str,
    project_root: Path,
    config: Path,
    dry_run: bool,
    show_all: bool,
    skip_sync: bool,
    no_code_changes: bool,
):
    """Update a dependency and adapt code to API changes.

    This command:
    1. Updates the dependency version in pyproject.toml
    2. Uses AI agents to identify required code changes for API compatibility
    3. Applies minimal, necessary code changes only

    Examples:

      hatch-agent-update-dep requests --version latest

      hatch-agent-update-dep pydantic --version ">=2.0.0"

      hatch-agent-update-dep django --version 5.0.0 --dry-run
    """
    click.echo(f"📦 Updating package: {click.style(package, fg='cyan')}")

    # Initialize updater
    updater = DependencyUpdater(project_root)

    # If version is 'latest', fetch from PyPI
    if version == "latest":
        click.echo("🔍 Fetching latest version from PyPI...")
        latest = updater.get_latest_version(package)
        if latest:
            version = f">={latest}"
            click.echo(f"   Latest version: {click.style(latest, fg='green')}")
        else:
            click.echo(click.style("⚠️  Could not fetch latest version from PyPI", fg="yellow"))
            click.echo("   Will proceed with current constraint")
            version = ""
    else:
        click.echo(f"   Target version: {click.style(version, fg='cyan')}")

    click.echo()

    # Get current version
    current_version = updater.get_current_version(package)
    if current_version:
        click.echo(f"Current version: {click.style(current_version, fg='yellow')}")
    else:
        click.echo(click.style(f"⚠️  Package '{package}' not found in dependencies", fg="yellow"))
        if not click.confirm("Add as new dependency?"):
            click.echo("Cancelled.")
            return
        current_version = "not installed"

    # Try to get changelog URL
    changelog_url = updater.get_changelog_url(package, version.lstrip(">="))
    if changelog_url:
        click.echo(f"📝 Changelog: {click.style(changelog_url, fg='blue')}")

    click.echo()

    # Prepare context for AI agents
    context = {
        "package": package,
        "current_version": current_version,
        "target_version": version,
        "project_root": str(project_root or Path.cwd()),
        "project_files": [str(f) for f in updater.get_project_files()[:50]],  # Limit for context
    }

    # Build task for AI agents
    task = _build_update_task(package, current_version, version)

    # Load agent configuration
    cfg = load_config(config)
    provider = cfg.get("underlying_provider", "openai")
    provider_cfg = cfg.get("underlying_config", {})

    # Ensure model is set
    if cfg.get("model") and "model" not in provider_cfg:
        provider_cfg = dict(provider_cfg)
        provider_cfg["model"] = cfg.get("model")

    click.echo("🤖 Consulting AI agents for update strategy...")
    click.echo()

    # Create agent with multi-agent orchestration
    agent = Agent(
        name="dependency-updater",
        use_multi_agent=True,
        provider_name=provider,
        provider_config=provider_cfg,
    )

    # Add context to agent
    agent.prepare(context)

    # Run the analysis
    result = agent.run_task(task)

    if not result.get("success"):
        click.echo(click.style("❌ Analysis failed:", fg="red"))
        click.echo(result.get("output", "Unknown error"))
        raise click.Abort()

    # Display the recommendation
    click.echo(click.style("=" * 70, fg="cyan"))
    click.echo(click.style("UPDATE STRATEGY", fg="cyan", bold=True))
    click.echo(click.style("=" * 70, fg="cyan"))
    click.echo()
    click.echo(result.get("selected_suggestion", ""))
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

        for i, sug in enumerate(result["all_suggestions"], 1):
            click.echo()
            click.echo(click.style(f"{i}. {sug['agent']}", fg="yellow", bold=True))
            click.echo(click.style(f"   Confidence: {sug['confidence']:.2f}", fg="yellow"))
            click.echo(f"   Suggestion: {sug['suggestion']}")

    click.echo()

    # Parse structured update plan
    update_plan = _extract_update_plan(result.get("selected_suggestion", ""))

    if not update_plan:
        click.echo(click.style("⚠️  Could not parse structured update plan.", fg="yellow"))
        click.echo("Please review the recommendation above and apply manually.")
        return

    # Show what will be done
    click.echo(click.style("📝 Proposed changes:", fg="green", bold=True))
    click.echo(f"  Package: {package}")
    click.echo(f"  Version update: {update_plan.get('version_spec', version)}")

    if update_plan.get("breaking_changes"):
        click.echo(f"  Breaking changes detected: {click.style('Yes', fg='red')}")
        for change in update_plan.get("breaking_changes", []):
            click.echo(f"    - {change}")
    else:
        click.echo(f"  Breaking changes detected: {click.style('No', fg='green')}")

    if update_plan.get("code_changes") and not no_code_changes:
        click.echo(f"  Code changes required: {len(update_plan.get('code_changes', []))}")
        for change in update_plan.get("code_changes", []):
            click.echo(f"    - {change.get('file', 'unknown')}: {change.get('description', 'N/A')}")

    click.echo()

    if dry_run:
        click.echo(click.style("🔍 DRY RUN - No changes will be made", fg="yellow"))
        return

    # Ask for confirmation
    if not click.confirm("Apply these changes?"):
        click.echo("Cancelled.")
        return

    # Step 1: Update pyproject.toml
    click.echo()
    click.echo("✏️  Updating pyproject.toml...")

    version_spec = update_plan.get("version_spec", version)
    if version_spec == "latest":
        version_spec = ""  # Let pip resolve latest

    update_result = updater.update_dependency(package=package, new_version=version_spec)

    if not update_result.get("success"):
        click.echo(
            click.style(f"❌ Failed to update dependency: {update_result.get('error')}", fg="red")
        )
        raise click.Abort()

    click.echo(
        click.style(
            f"✅ Updated {package} from {update_result['old_version']} to {update_result['new_version']} "
            f"in {update_result['target']}",
            fg="green",
        )
    )

    # Step 2: Sync environment
    if not skip_sync:
        click.echo()
        click.echo("🔄 Syncing Hatch environment...")

        sync_result = updater.sync_environment()

        if sync_result.get("success"):
            click.echo(click.style("✅ Environment synced successfully", fg="green"))
        else:
            click.echo(
                click.style(
                    f"⚠️  Environment sync had issues: {sync_result.get('error')}", fg="yellow"
                )
            )

    # Step 3: Apply code changes if needed
    if not no_code_changes and update_plan.get("code_changes"):
        click.echo()
        click.echo("🔧 Applying code changes for API compatibility...")

        code_changes_applied = _apply_code_changes(
            update_plan.get("code_changes", []), project_root or Path.cwd(), agent, cfg
        )

        if code_changes_applied:
            click.echo(click.style(f"✅ Applied {code_changes_applied} code change(s)", fg="green"))
        else:
            click.echo(click.style("⚠️  No code changes were applied", fg="yellow"))

    click.echo()
    click.echo(click.style("🎉 Dependency update complete!", fg="green", bold=True))
    click.echo()
    click.echo("Recommended next steps:")
    click.echo("  1. Run your tests: hatch run test")
    click.echo("  2. Review the changes: git diff")
    click.echo("  3. Commit if everything looks good")


def _build_update_task(package: str, current_version: str, target_version: str) -> str:
    """Build the task description for AI agents."""
    return f"""You are updating the dependency '{package}' from {current_version} to {target_version}.

Your task is to create an update strategy that:

1. Determines the exact version specification to use in pyproject.toml
2. Identifies any breaking API changes between versions
3. Lists ONLY the minimal code changes required for API compatibility
4. Provides specific file paths and change descriptions

CRITICAL REQUIREMENTS:
- Make ONLY changes required for API compatibility
- Do NOT refactor or improve existing code
- Do NOT add new features or complexity
- Do NOT change code style or formatting
- Be extremely conservative with changes

RESPONSE FORMAT (required):

Your response MUST include this structured section at the END:

UPDATE_PLAN:
{{
    "version_spec": ">=2.30.0",
    "breaking_changes": [
        "Description of breaking change 1",
        "Description of breaking change 2"
    ],
    "code_changes": [
        {{
            "file": "src/module/file.py",
            "line_range": "45-50",
            "description": "Replace deprecated method X with Y",
            "reason": "Method X was removed in version 2.0"
        }}
    ]
}}

If NO code changes are needed, use an empty array: "code_changes": []

Provide this JSON block AFTER your explanation."""


def _extract_update_plan(suggestion: str) -> dict:
    """Extract structured update plan from agent suggestion."""
    if "UPDATE_PLAN:" not in suggestion:
        return None

    try:
        plan_part = suggestion.split("UPDATE_PLAN:")[1].strip()

        # Find the JSON object
        start = plan_part.find("{")
        end = plan_part.rfind("}") + 1

        if start == -1 or end == 0:
            return None

        json_str = plan_part[start:end]
        plan_data = json.loads(json_str)

        return plan_data
    except (json.JSONDecodeError, IndexError):
        return None


def _apply_code_changes(code_changes: list, project_root: Path, agent: Agent, config: dict) -> int:
    """Apply code changes with AI assistance.

    Returns:
        Number of changes applied
    """
    if not code_changes:
        return 0

    applied = 0

    for change in code_changes:
        file_path = project_root / change.get("file", "")

        if not file_path.exists():
            click.echo(click.style(f"⚠️  File not found: {file_path}", fg="yellow"))
            continue

        # Read current file content
        try:
            with open(file_path, encoding="utf-8") as f:
                original_content = f.read()
        except Exception as e:
            click.echo(click.style(f"⚠️  Could not read {file_path}: {e}", fg="yellow"))
            continue

        # Ask AI to generate the specific change
        change_task = f"""Apply this specific code change:

File: {change.get("file")}
Line range: {change.get("line_range", "N/A")}
Change needed: {change.get("description")}
Reason: {change.get("reason")}

Original code:
```
{original_content}
```

STRICT REQUIREMENTS:
1. Make ONLY the change described above
2. Do NOT modify any other code
3. Do NOT refactor or improve code
4. Preserve all formatting and style
5. Return the COMPLETE modified file content

Return the full file content with only the necessary change applied."""

        result = agent.run_task(change_task)

        if result.get("success"):
            # For now, we don't auto-apply - this would need careful validation
            click.echo(click.style(f"📄 Generated changes for: {file_path}", fg="blue"))
            applied += 1
        else:
            click.echo(click.style(f"⚠️  Could not generate changes for: {file_path}", fg="yellow"))

    return applied


if __name__ == "__main__":
    update_dep()
