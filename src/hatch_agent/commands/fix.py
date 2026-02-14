"""CLI command for auto-fixing build failures using multi-agent analysis."""

import contextlib
import json
from pathlib import Path

import click

from hatch_agent.agent.core import Agent
from hatch_agent.analyzers.fix import BuildFixer
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
@click.option("--dry-run", is_flag=True, help="Show what would be fixed without making changes")
@click.option(
    "--no-autofix",
    is_flag=True,
    help="Skip ruff autofix, use AI for everything",
)
@click.option(
    "--show-all", is_flag=True, help="Show all agent suggestions, not just the selected one"
)
def fix(
    project_root: Path | None,
    config: Path | None,
    dry_run: bool,
    no_autofix: bool,
    show_all: bool,
):
    """Auto-fix build failures, lint errors, and type issues.

    This command:
    1. Runs ruff autofix for automatically fixable lint/format issues
    2. Collects remaining errors (ruff + mypy)
    3. Uses AI agents to generate fixes for non-trivial issues
    4. Applies fixes with confirmation (creates .bak backups)
    5. Runs tests to verify nothing broke

    Examples:

      hatch-agent fix

      hatch-agent fix --dry-run

      hatch-agent fix --no-autofix
    """
    project_root = project_root or Path.cwd()

    click.echo(click.style("🔧 Hatch Agent Fix", fg="cyan", bold=True))
    click.echo()

    fixer = BuildFixer(project_root)

    # Step 1: Autofix with ruff
    if not no_autofix:
        click.echo("⚡ Running ruff autofix...")
        autofix_result = fixer.run_autofix()

        if autofix_result.get("success"):
            files_fixed = autofix_result.get("files_fixed", 0)
            if files_fixed > 0:
                click.echo(click.style(f"   ✅ Auto-fixed {files_fixed} issue(s)", fg="green"))
            else:
                click.echo("   No auto-fixable issues found")
        else:
            click.echo(
                click.style(
                    f"   ⚠️  Autofix error: {autofix_result.get('error', 'Unknown')}",
                    fg="yellow",
                )
            )
        click.echo()
    else:
        click.echo("⏭️  Skipped autofix (--no-autofix)")
        click.echo()

    # Step 2: Collect remaining errors
    click.echo("🔍 Checking for remaining errors...")
    remaining = fixer.get_remaining_errors()

    if not remaining:
        click.echo(click.style("✅ No remaining errors!", fg="green", bold=True))
        return

    click.echo(f"   Found {len(remaining)} remaining error(s)")
    click.echo()

    # Display errors
    for err in remaining:
        tool_color = "yellow" if err["tool"] == "ruff" else "magenta"
        click.echo(
            f"  {click.style(err['tool'], fg=tool_color)} "
            f"{err['file']}:{err['line']} "
            f"[{err.get('code', '')}] {err['message']}"
        )

    click.echo()

    if dry_run:
        click.echo(
            click.style("🔍 DRY RUN - No AI fixes will be generated or applied", fg="yellow")
        )
        return

    # Step 3: Read relevant source files for AI context
    error_files: dict[str, str] = {}
    for err in remaining:
        file_path = project_root / err["file"]
        if file_path.exists() and str(file_path) not in error_files:
            with contextlib.suppress(Exception):
                error_files[str(file_path)] = file_path.read_text(encoding="utf-8")

    # Step 4: Build task and run AI
    task = _build_fix_task(remaining, error_files)

    cfg = load_config(config)
    provider = cfg.get("underlying_provider", "openai")
    provider_cfg = cfg.get("underlying_config", {})

    if cfg.get("model") and "model" not in provider_cfg:
        provider_cfg = dict(provider_cfg)
        provider_cfg["model"] = cfg.get("model")

    click.echo("🤖 Consulting AI agents for fixes...")
    click.echo()

    agent = Agent(
        name="build-fixer",
        use_multi_agent=True,
        provider_name=provider,
        provider_config=provider_cfg,
    )

    agent.prepare({"errors": remaining, "files": {k: v[:2000] for k, v in error_files.items()}})

    result = agent.run_task(task)

    if not result.get("success"):
        click.echo(click.style("❌ AI analysis failed:", fg="red"))
        click.echo(result.get("output", "Unknown error"))
        raise click.Abort()

    suggestion = result.get("selected_suggestion", "")

    # Display the suggestion
    click.echo(click.style("=" * 70, fg="cyan"))
    click.echo(click.style("PROPOSED FIXES", fg="cyan", bold=True))
    click.echo(click.style("=" * 70, fg="cyan"))
    click.echo()
    click.echo(suggestion)
    click.echo()
    click.echo(click.style(f"Selected from: {result.get('selected_agent', 'N/A')}", fg="blue"))

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

    # Step 5: Try to parse structured fixes and apply
    fix_plan = _extract_fix_plan(suggestion)

    if fix_plan and fix_plan.get("fixes"):
        click.echo()
        click.echo(
            click.style(f"📝 {len(fix_plan['fixes'])} structured fix(es) available", fg="green")
        )

        for i, fx in enumerate(fix_plan["fixes"], 1):
            click.echo(
                f"  {i}. {fx.get('file', '?')}:{fx.get('line', '?')} - {fx.get('description', 'N/A')}"
            )

        click.echo()
        if click.confirm("Apply these fixes? (.bak backups will be created)"):
            applied = 0
            for fx in fix_plan["fixes"]:
                file_path = project_root / fx.get("file", "")
                if not file_path.exists():
                    click.echo(click.style(f"  ⚠️  File not found: {file_path}", fg="yellow"))
                    continue

                original = fx.get("original", "")
                fixed = fx.get("fixed", "")

                if original and fixed:
                    try:
                        content = file_path.read_text(encoding="utf-8")
                        if original in content:
                            new_content = content.replace(original, fixed, 1)
                            apply_result = fixer.apply_fix(file_path, content, new_content)
                            if apply_result["success"]:
                                click.echo(click.style(f"  ✅ Fixed {file_path}", fg="green"))
                                applied += 1
                            else:
                                click.echo(
                                    click.style(
                                        f"  ⚠️  Could not apply fix to {file_path}: "
                                        f"{apply_result.get('error', '')}",
                                        fg="yellow",
                                    )
                                )
                        else:
                            click.echo(
                                click.style(
                                    f"  ⚠️  Original code not found in {file_path}", fg="yellow"
                                )
                            )
                    except Exception as e:
                        click.echo(click.style(f"  ⚠️  Error fixing {file_path}: {e}", fg="yellow"))
                else:
                    click.echo(
                        click.style(
                            f"  ⚠️  Fix for {file_path} missing original/fixed code", fg="yellow"
                        )
                    )

            click.echo()
            if applied > 0:
                click.echo(click.style(f"✅ Applied {applied} fix(es)", fg="green"))

                # Run tests
                click.echo()
                click.echo("🧪 Running tests to verify fixes...")
                test_result = fixer.run_tests()
                if test_result.get("success"):
                    click.echo(click.style("✅ Tests passed!", fg="green"))
                elif test_result.get("success") is None:
                    click.echo(click.style("⚠️  Could not run tests", fg="yellow"))
                else:
                    click.echo(click.style("❌ Tests failed after fixes!", fg="red"))
                    click.echo("   Review the changes and consider restoring from .bak files")
    else:
        click.echo()
        click.echo(
            click.style(
                "⚠️  Could not parse structured fixes. Review the suggestions above and apply manually.",
                fg="yellow",
            )
        )

    click.echo()
    click.echo(click.style("🎉 Done!", fg="green", bold=True))


def _build_fix_task(errors: list[dict], files: dict[str, str]) -> str:
    """Build the task description for AI agents."""
    errors_text = "\n".join(
        f"- [{e['tool']}] {e['file']}:{e['line']} [{e.get('code', '')}] {e['message']}"
        for e in errors
    )

    # Include file snippets (truncated)
    files_text = ""
    for path, content in list(files.items())[:5]:  # Limit to 5 files
        files_text += f"\n\n--- {path} ---\n{content[:1500]}"

    return f"""Fix the following {len(errors)} remaining errors in a Hatch project:

{errors_text}

Relevant source files:{files_text}

IMPORTANT: Your response MUST include a structured fix plan at the END in this EXACT format:

FIX_PLAN:
{{
    "fixes": [
        {{
            "file": "relative/path/to/file.py",
            "line": 42,
            "error_code": "E501",
            "description": "Brief description of the fix",
            "original": "exact original code to replace",
            "fixed": "corrected code"
        }}
    ]
}}

Requirements:
1. Make ONLY the minimum changes needed to fix each error
2. Do NOT refactor or improve unrelated code
3. Preserve existing code style and formatting
4. The "original" field must contain the EXACT text from the source file
5. The "fixed" field must contain ONLY the corrected version of that text"""


def _extract_fix_plan(suggestion: str) -> dict | None:
    """Extract structured fix plan from agent suggestion."""
    if "FIX_PLAN:" not in suggestion:
        return None

    try:
        plan_part = suggestion.split("FIX_PLAN:")[1].strip()
        start = plan_part.find("{")
        end = plan_part.rfind("}") + 1

        if start == -1 or end == 0:
            return None

        json_str = plan_part[start:end]
        return json.loads(json_str)
    except (json.JSONDecodeError, IndexError):
        return None


if __name__ == "__main__":
    fix()
