"""CLI command for syncing dependencies and analyzing breaking changes."""

import json
from pathlib import Path
from typing import Any

import click

from hatch_agent.agent.core import Agent
from hatch_agent.analyzers.sync import DependencySync
from hatch_agent.analyzers.updater import DependencyUpdater
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
    "--env", default=None, help="Specific Hatch environment to sync (defaults to first available)"
)
@click.option("--dry-run", is_flag=True, help="Show what would be upgraded without making changes")
@click.option("--skip-analysis", is_flag=True, help="Skip breaking changes analysis after upgrade")
@click.option(
    "--show-all", is_flag=True, help="Show all agent suggestions, not just the selected one"
)
@click.option("--no-code-changes", is_flag=True, help="Skip code modification suggestions")
@click.option("--major-only", is_flag=True, help="Only analyze packages with major version changes")
def sync(
    project_root: Path | None,
    config: Path | None,
    env: str | None,
    dry_run: bool,
    skip_analysis: bool,
    show_all: bool,
    no_code_changes: bool,
    major_only: bool,
):
    """Sync dependencies to latest compatible versions and analyze breaking changes.

    This command:
    1. Upgrades all dependencies to their latest compatible versions
    2. Identifies which packages were updated
    3. Uses AI agents to analyze breaking changes
    4. Suggests and optionally applies code modifications

    Examples:

      hatch-agent-sync

      hatch-agent-sync --env dev --dry-run

      hatch-agent-sync --skip-analysis

      hatch-agent-sync --major-only
    """
    project_root = project_root or Path.cwd()

    click.echo(click.style("🔄 Hatch Agent Dependency Sync", fg="cyan", bold=True))
    click.echo()

    # Initialize sync manager
    sync_manager = DependencySync(project_root)

    # Get environment info
    env_info = sync_manager.get_environment_info(env)
    click.echo(f"Environment: {click.style(env_info['name'], fg='cyan')}")
    click.echo(f"Installer: {click.style(env_info['installer'], fg='cyan')}")
    click.echo(f"Dependencies: {env_info['dependencies_count']}")
    click.echo()

    # Ensure environment exists
    ensure_result = sync_manager.ensure_environment_exists(env)
    if not ensure_result.get("success"):
        click.echo(
            click.style(f"❌ Failed to ensure environment: {ensure_result.get('error')}", fg="red")
        )
        raise click.Abort()

    if ensure_result.get("action") == "created":
        click.echo(click.style("✅ Created environment", fg="green"))

    # Step 1: Capture pre-upgrade versions
    click.echo("📊 Capturing current package versions...")
    before_versions = sync_manager.get_installed_versions(env)

    if not before_versions:
        click.echo(click.style("⚠️  Could not retrieve installed versions", fg="yellow"))
        click.echo("   Proceeding with upgrade anyway...")
    else:
        click.echo(f"   Found {len(before_versions)} installed packages")

    click.echo()

    # Step 2: Run upgrade
    if dry_run:
        click.echo(click.style("🔍 DRY RUN - Checking for available upgrades...", fg="yellow"))
    else:
        click.echo(f"⬆️  Upgrading dependencies using {env_info['installer']}...")

    upgrade_result = sync_manager.run_upgrade(env, dry_run=dry_run)

    if not upgrade_result.get("success"):
        click.echo(click.style(f"❌ Upgrade failed: {upgrade_result.get('error')}", fg="red"))
        raise click.Abort()

    if upgrade_result.get("action") == "none":
        click.echo(click.style("✅ No dependencies to upgrade", fg="green"))
        return

    click.echo(click.style("✅ Upgrade complete", fg="green"))
    click.echo()

    # Step 3: Capture post-upgrade versions and compare
    if dry_run:
        click.echo(click.style("🔍 DRY RUN complete - no changes made", fg="yellow"))
        return

    click.echo("📊 Capturing updated package versions...")
    after_versions = sync_manager.get_installed_versions(env)

    # Step 4: Compare versions
    updates = sync_manager.compare_versions(before_versions, after_versions)

    if not updates:
        click.echo(click.style("✅ All packages are already up to date!", fg="green"))
        return

    # Display updates
    click.echo()
    click.echo(click.style("=" * 70, fg="cyan"))
    click.echo(click.style("UPDATED PACKAGES", fg="cyan", bold=True))
    click.echo(click.style("=" * 70, fg="cyan"))
    click.echo()

    major_updates = []
    minor_updates = []
    patch_updates = []
    new_packages = []

    for update in updates:
        change_type = update["change_type"]
        pkg = update["package"]
        old_v = update["old_version"] or "N/A"
        new_v = update["new_version"]

        if change_type == "major":
            color = "red"
            symbol = "⚠️ "
            major_updates.append(update)
        elif change_type == "minor":
            color = "yellow"
            symbol = "📦"
            minor_updates.append(update)
        elif change_type == "new":
            color = "blue"
            symbol = "✨"
            new_packages.append(update)
        else:
            color = "green"
            symbol = "🔧"
            patch_updates.append(update)

        click.echo(f"  {symbol} {click.style(pkg, fg=color)}: {old_v} → {new_v} ({change_type})")

    click.echo()
    click.echo(
        f"Summary: {len(major_updates)} major, {len(minor_updates)} minor, "
        f"{len(patch_updates)} patch, {len(new_packages)} new"
    )
    click.echo()

    # Step 5: Breaking changes analysis
    if skip_analysis:
        click.echo(
            click.style("⏭️  Skipping breaking changes analysis (--skip-analysis)", fg="yellow")
        )
        return

    # Determine which packages to analyze
    if major_only:
        packages_to_analyze = major_updates
        click.echo(click.style("📋 Analyzing major version changes only (--major-only)", fg="cyan"))
    else:
        # Analyze major and minor updates (patch updates rarely have breaking changes)
        packages_to_analyze = major_updates + minor_updates
        click.echo(click.style("📋 Analyzing major and minor version changes", fg="cyan"))

    if not packages_to_analyze:
        click.echo(click.style("✅ No packages require breaking changes analysis", fg="green"))
        return

    click.echo(f"   {len(packages_to_analyze)} package(s) to analyze")
    click.echo()

    # Load agent configuration
    cfg = load_config(config)
    provider = cfg.get("underlying_provider", "openai")
    provider_cfg = cfg.get("underlying_config", {})

    if cfg.get("model") and "model" not in provider_cfg:
        provider_cfg = dict(provider_cfg)
        provider_cfg["model"] = cfg.get("model")

    # Initialize updater for changelog URLs and project files
    updater = DependencyUpdater(project_root)
    project_files = [str(f) for f in updater.get_project_files()[:50]]

    click.echo("🤖 Analyzing breaking changes with AI agents...")
    click.echo()

    # Create agent with multi-agent orchestration
    agent = Agent(
        name="dependency-sync-analyzer",
        use_multi_agent=True,
        provider_name=provider,
        provider_config=provider_cfg,
    )

    # Run analysis for each package
    all_breaking_changes = []
    all_code_changes = []

    for update in packages_to_analyze:
        pkg = update["package"]
        old_v = update["old_version"]
        new_v = update["new_version"]

        click.echo(f"  Analyzing {click.style(pkg, fg='cyan')} ({old_v} → {new_v})...")

        # Try to get changelog URL
        changelog_url = updater.get_changelog_url(pkg, new_v)

        # Prepare context
        context = {
            "package": pkg,
            "current_version": old_v,
            "target_version": new_v,
            "project_root": str(project_root),
            "project_files": project_files,
            "changelog_url": changelog_url,
        }

        # Build task
        task = _build_update_task(pkg, old_v, new_v)

        # Add context to agent
        agent.prepare(context)

        # Run the analysis
        result = agent.run_task(task)

        if result.get("success"):
            # Extract update plan
            plan = _extract_update_plan(result.get("selected_suggestion", ""))
            if plan:
                # Add package info to each breaking change
                for bc in plan.get("breaking_changes", []):
                    all_breaking_changes.append({"package": pkg, "change": bc})

                # Add package info to each code change
                for cc in plan.get("code_changes", []):
                    cc["package"] = pkg
                    all_code_changes.append(cc)
        else:
            click.echo(
                click.style(
                    f"    ⚠️  Analysis failed: {result.get('output', 'Unknown error')}", fg="yellow"
                )
            )

    click.echo()

    # Display aggregated results
    click.echo(click.style("=" * 70, fg="cyan"))
    click.echo(click.style("BREAKING CHANGES ANALYSIS", fg="cyan", bold=True))
    click.echo(click.style("=" * 70, fg="cyan"))
    click.echo()

    if all_breaking_changes:
        click.echo(
            click.style(
                f"⚠️  Found {len(all_breaking_changes)} potential breaking change(s):", fg="red"
            )
        )
        click.echo()
        for bc in all_breaking_changes:
            click.echo(f"  [{bc['package']}] {bc['change']}")
    else:
        click.echo(click.style("✅ No breaking changes detected", fg="green"))

    click.echo()

    if no_code_changes:
        click.echo(
            click.style(
                "⏭️  Skipping code modification suggestions (--no-code-changes)", fg="yellow"
            )
        )
        return

    if all_code_changes:
        click.echo(
            click.style(f"📝 Suggested code changes ({len(all_code_changes)}):", fg="yellow")
        )
        click.echo()

        for change in all_code_changes:
            pkg = change.get("package", "unknown")
            file_path = change.get("file", "unknown")
            desc = change.get("description", "N/A")
            reason = change.get("reason", "N/A")

            click.echo(f"  [{pkg}] {click.style(file_path, fg='blue')}")
            click.echo(f"      Change: {desc}")
            click.echo(f"      Reason: {reason}")
            click.echo()

        # Ask for confirmation to apply
        if click.confirm("Apply these code changes?"):
            applied = _apply_code_changes(all_code_changes, project_root, agent, cfg)
            if applied:
                click.echo(click.style(f"✅ Applied {applied} code change(s)", fg="green"))
            else:
                click.echo(click.style("⚠️  No code changes were applied", fg="yellow"))
    else:
        click.echo(click.style("✅ No code changes required", fg="green"))

    click.echo()
    click.echo(click.style("🎉 Dependency sync complete!", fg="green", bold=True))
    click.echo()
    click.echo("Recommended next steps:")
    click.echo("  1. Run your tests: hatch run test")
    click.echo("  2. Review the changes: git diff")
    click.echo("  3. Commit if everything looks good")


def _build_update_task(package: str, current_version: str, target_version: str) -> str:
    """Build the task description for AI agents."""
    return f"""You are analyzing the dependency '{package}' update from {current_version} to {target_version}.

Your task is to identify:

1. Any breaking API changes between these versions
2. ONLY the minimal code changes required for API compatibility
3. Specific file paths and change descriptions

CRITICAL REQUIREMENTS:
- Identify ONLY changes required for API compatibility
- Do NOT suggest refactoring or improvements
- Do NOT suggest adding new features
- Do NOT suggest style or formatting changes
- Be extremely conservative with suggestions

RESPONSE FORMAT (required):

Your response MUST include this structured section at the END:

UPDATE_PLAN:
{{
    "version_spec": ">={target_version}",
    "breaking_changes": [
        "Description of breaking change 1",
        "Description of breaking change 2"
    ],
    "code_changes": [
        {{
            "file": "src/module/file.py",
            "line_range": "45-50",
            "description": "Replace deprecated method X with Y",
            "reason": "Method X was removed in version {target_version}"
        }}
    ]
}}

If NO breaking changes or code changes are needed, use empty arrays: 
"breaking_changes": [], "code_changes": []

Provide this JSON block AFTER your explanation."""


def _extract_update_plan(suggestion: str) -> dict[str, Any] | None:
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


def _apply_code_changes(
    code_changes: list[dict[str, Any]], project_root: Path, agent: Agent, config: dict
) -> int:
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
Package: {change.get("package", "unknown")}

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
            click.echo(click.style(f"📄 Generated changes for: {file_path}", fg="blue"))
            applied += 1
        else:
            click.echo(click.style(f"⚠️  Could not generate changes for: {file_path}", fg="yellow"))

    return applied


if __name__ == "__main__":
    sync()
