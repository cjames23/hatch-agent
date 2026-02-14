"""CLI command for migrating projects to Hatch from other build systems."""

import json
import shutil
from pathlib import Path

import click
import tomli_w

from hatch_agent.agent.core import Agent
from hatch_agent.analyzers.migrate import ProjectMigrator
from hatch_agent.config import load_config


@click.command()
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="Root directory of the project to migrate (defaults to current directory)",
)
@click.option(
    "--config",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to agent configuration file",
)
@click.option(
    "--from",
    "source_system",
    type=click.Choice(["auto", "setuptools", "poetry", "flit", "pdm", "pipfile"]),
    default="auto",
    help="Source build system to migrate from (auto-detect by default)",
)
@click.option("--dry-run", is_flag=True, help="Show what would change without writing files")
@click.option(
    "--show-all", is_flag=True, help="Show all agent suggestions, not just the selected one"
)
def migrate(
    project_root: Path | None,
    config: Path | None,
    source_system: str,
    dry_run: bool,
    show_all: bool,
):
    """Migrate a project from another build system to Hatch.

    Detects and parses configuration from setuptools (setup.py/setup.cfg),
    Poetry, Flit, PDM, or Pipfile and generates a Hatch-native pyproject.toml.

    Examples:

      hatch-agent migrate

      hatch-agent migrate --from poetry --dry-run

      hatch-agent migrate --from setuptools
    """
    project_root = project_root or Path.cwd()

    click.echo(click.style("🔄 Hatch Agent Migration", fg="cyan", bold=True))
    click.echo()

    migrator = ProjectMigrator(project_root)

    # Step 1: Detect build system
    if source_system == "auto":
        click.echo("🔍 Detecting current build system...")
        detection = migrator.detect_build_system()
        detected = detection["system"]

        if detected is None:
            click.echo(
                click.style("❌ Could not detect a build system in this project", fg="red")
            )
            click.echo("   Use --from to specify the source build system")
            raise click.Abort()

        if detected == "hatch":
            click.echo(click.style("✅ Project already uses Hatch!", fg="green"))
            return

        source_system = detected
        click.echo(f"   Detected: {click.style(source_system, fg='cyan')}")
        click.echo(f"   Files: {', '.join(detection['files'])}")
    else:
        click.echo(f"Source: {click.style(source_system, fg='cyan')}")

    click.echo()

    # Step 2: Parse existing configuration
    click.echo("📖 Parsing existing configuration...")
    parsed_data = _parse_source(migrator, source_system)

    if "error" in parsed_data and not parsed_data.get("raw_content"):
        click.echo(click.style(f"❌ Parse error: {parsed_data['error']}", fg="red"))
        raise click.Abort()

    click.echo("   Done")
    click.echo()

    # Step 3: Generate base Hatch config
    base_config = migrator.generate_hatch_pyproject(parsed_data)

    # Step 4: Use AI to refine the migration
    task = _build_migration_task(source_system, parsed_data, base_config)

    cfg = load_config(config)
    provider = cfg.get("underlying_provider", "openai")
    provider_cfg = cfg.get("underlying_config", {})

    if cfg.get("model") and "model" not in provider_cfg:
        provider_cfg = dict(provider_cfg)
        provider_cfg["model"] = cfg.get("model")

    click.echo("🤖 Consulting AI agents for migration refinement...")
    click.echo()

    agent = Agent(
        name="project-migrator",
        use_multi_agent=True,
        provider_name=provider,
        provider_config=provider_cfg,
    )

    agent.prepare({
        "source_system": source_system,
        "parsed_data": {k: v for k, v in parsed_data.items() if k != "raw_content"},
        "base_config": base_config,
    })

    result = agent.run_task(task)

    if not result.get("success"):
        click.echo(click.style("❌ AI analysis failed:", fg="red"))
        click.echo(result.get("output", "Unknown error"))
        click.echo()
        click.echo("Falling back to auto-generated configuration...")
        final_config = base_config
    else:
        # Try to extract refined config from AI response
        suggestion = result.get("selected_suggestion", "")
        refined = _extract_migration_plan(suggestion)

        if refined and "pyproject" in refined:
            final_config = refined["pyproject"]
            click.echo(click.style("✅ AI-refined configuration generated", fg="green"))
        else:
            final_config = base_config
            click.echo("Using auto-generated configuration (AI refinement not parseable)")

        click.echo()
        click.echo(click.style("=" * 70, fg="cyan"))
        click.echo(click.style("MIGRATION ANALYSIS", fg="cyan", bold=True))
        click.echo(click.style("=" * 70, fg="cyan"))
        click.echo()
        click.echo(suggestion)
        click.echo()

        if show_all and "all_suggestions" in result:
            click.echo(click.style("=" * 70, fg="yellow"))
            click.echo(click.style("ALL AGENT SUGGESTIONS", fg="yellow", bold=True))
            click.echo(click.style("=" * 70, fg="yellow"))

            for i, sug in enumerate(result["all_suggestions"], 1):
                click.echo()
                click.echo(click.style(f"{i}. {sug['agent']}", fg="yellow", bold=True))
                click.echo(f"   Suggestion: {sug['suggestion']}")

    # Step 5: Show migration diff
    click.echo()
    diff = migrator.get_migration_diff(parsed_data, final_config)
    click.echo(click.style("📋 " + diff, fg="cyan"))
    click.echo()

    # Step 6: Show generated TOML
    click.echo(click.style("Generated pyproject.toml:", fg="green", bold=True))
    click.echo()

    # Serialize to TOML string for preview
    import io
    buf = io.BytesIO()
    tomli_w.dump(final_config, buf)
    toml_preview = buf.getvalue().decode("utf-8")
    click.echo(toml_preview)
    click.echo()

    if dry_run:
        click.echo(click.style("🔍 DRY RUN - No files will be written", fg="yellow"))
        return

    # Step 7: Confirm and write
    if not click.confirm("Write this pyproject.toml? (existing file will be backed up)"):
        click.echo("Cancelled.")
        return

    # Backup existing pyproject.toml if it exists
    pyproject_path = project_root / "pyproject.toml"
    if pyproject_path.exists():
        backup_path = project_root / "pyproject.toml.bak"
        shutil.copy2(pyproject_path, backup_path)
        click.echo(f"   Backed up existing file to {backup_path}")

    migrator.write_pyproject(final_config)
    click.echo(click.style("✅ pyproject.toml written!", fg="green"))
    click.echo()
    click.echo("Next steps:")
    click.echo("  1. Review the generated pyproject.toml")
    click.echo("  2. Run: hatch env create")
    click.echo("  3. Run: hatch run test")
    click.echo("  4. Remove old build files (setup.py, setup.cfg, Pipfile) once verified")


def _parse_source(migrator: ProjectMigrator, source_system: str) -> dict:
    """Parse the source build system configuration."""
    if source_system == "setuptools":
        setup_py = migrator.parse_setup_py()
        setup_cfg = migrator.parse_setup_cfg()
        # Merge, preferring setup.cfg over setup.py
        merged = {**setup_py, **setup_cfg}
        if "error" in setup_cfg:
            merged.pop("error", None)
        return merged
    elif source_system == "poetry":
        return migrator.parse_poetry_config()
    elif source_system == "flit":
        return migrator.parse_flit_config()
    elif source_system == "pdm":
        return migrator.parse_pdm_config()
    elif source_system == "pipfile":
        return migrator.parse_pipfile()
    else:
        return {"error": f"Unsupported build system: {source_system}"}


def _build_migration_task(
    source_system: str, parsed_data: dict, base_config: dict
) -> str:
    """Build the task description for AI agents."""
    # Remove raw content to keep prompt size reasonable
    clean_data = {k: v for k, v in parsed_data.items()
                  if k != "raw_content" and not str(v).startswith("Error")}

    return f"""Migrate a Python project from {source_system} to Hatch.

Source build system: {source_system}

Parsed configuration:
{json.dumps(clean_data, indent=2, default=str)[:3000]}

Auto-generated Hatch configuration:
{json.dumps(base_config, indent=2, default=str)[:2000]}

Please:
1. Review the auto-generated Hatch pyproject.toml for correctness
2. Identify any missing fields or incorrect mappings
3. Suggest improvements to the Hatch configuration
4. Note any {source_system}-specific features that cannot be directly migrated
5. Recommend Hatch environments and scripts that would replace existing workflows

If you can improve the configuration, include a MIGRATION_PLAN: section at the END
with this format:

MIGRATION_PLAN:
{{
    "pyproject": {{ ... complete pyproject.toml as JSON ... }},
    "notes": ["note 1", "note 2"],
    "manual_steps": ["step 1", "step 2"]
}}

Only include the MIGRATION_PLAN if you have specific improvements over the base config."""


def _extract_migration_plan(suggestion: str) -> dict | None:
    """Extract structured migration plan from agent suggestion."""
    if "MIGRATION_PLAN:" not in suggestion:
        return None

    try:
        plan_part = suggestion.split("MIGRATION_PLAN:")[1].strip()
        start = plan_part.find("{")
        end = plan_part.rfind("}") + 1

        if start == -1 or end == 0:
            return None

        json_str = plan_part[start:end]
        return json.loads(json_str)
    except (json.JSONDecodeError, IndexError):
        return None


if __name__ == "__main__":
    migrate()
