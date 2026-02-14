"""CLI command for auditing dependency security using multi-agent analysis."""

from pathlib import Path

import click

from hatch_agent.agent.core import Agent
from hatch_agent.analyzers.security import SecurityAuditor
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
@click.option("--no-ai", is_flag=True, help="Show raw vulnerability data only, skip AI analysis")
@click.option(
    "--fix",
    "apply_fix",
    is_flag=True,
    help="Suggest and apply version bumps for vulnerable dependencies",
)
def security(
    project_root: Path | None,
    config: Path | None,
    show_all: bool,
    no_ai: bool,
    apply_fix: bool,
):
    """Audit dependencies for known security vulnerabilities.

    Checks all declared dependencies against the OSV.dev and PyPI vulnerability
    databases, then uses AI agents to analyze impact and suggest remediations.

    Examples:

      hatch-agent security

      hatch-agent security --no-ai

      hatch-agent security --fix
    """
    click.echo(click.style("🔒 Hatch Agent Security Audit", fg="cyan", bold=True))
    click.echo()

    auditor = SecurityAuditor(project_root)

    # Run audit
    click.echo("🔍 Checking dependencies against vulnerability databases...")
    report = auditor.run_audit()

    vulns = report["vulnerabilities"]
    summary = report["summary"]
    packages_checked = report["packages_checked"]

    click.echo(f"   Checked {packages_checked} package(s)")
    click.echo()

    if not vulns:
        click.echo(click.style("✅ No known vulnerabilities found!", fg="green", bold=True))
        return

    # Display vulnerability table
    click.echo(click.style("=" * 70, fg="red"))
    click.echo(click.style("VULNERABILITIES FOUND", fg="red", bold=True))
    click.echo(click.style("=" * 70, fg="red"))
    click.echo()

    for v in vulns:
        severity = v["severity"]
        sev_color = _severity_color(severity)

        click.echo(
            f"  {click.style(severity.upper(), fg=sev_color, bold=True)}  "
            f"{click.style(v['package'], fg='white', bold=True)} "
            f"({v['installed_version']})"
        )
        click.echo(f"    ID: {v['vuln_id']}")
        click.echo(f"    {v['summary']}")
        if v.get("fixed_in"):
            click.echo(f"    Fixed in: {click.style(v['fixed_in'], fg='green')}")
        if v.get("url"):
            click.echo(f"    URL: {click.style(v['url'], fg='blue')}")
        click.echo()

    # Summary line
    click.echo(click.style("─" * 50, fg="red"))
    parts = []
    for level in ("critical", "high", "medium", "low", "unknown"):
        count = summary.get(level, 0)
        if count > 0:
            parts.append(click.style(f"{count} {level}", fg=_severity_color(level)))
    click.echo(f"  Total: {' | '.join(parts)}")
    click.echo()

    # Suggest fixes
    if apply_fix:
        fixes = auditor.suggest_fixes(vulns)
        if fixes:
            click.echo(click.style("📝 Suggested version bumps:", fg="yellow", bold=True))
            for fix in fixes:
                click.echo(
                    f"  {fix['package']}: {fix['current_version']} → "
                    f"{click.style(fix['recommended_version'], fg='green')}"
                )
                click.echo(f"    Addresses: {fix['vuln_ids']}")
            click.echo()

    if no_ai:
        return

    # AI analysis
    task = _build_security_task(vulns, summary)

    cfg = load_config(config)
    provider = cfg.get("underlying_provider", "openai")
    provider_cfg = cfg.get("underlying_config", {})

    if cfg.get("model") and "model" not in provider_cfg:
        provider_cfg = dict(provider_cfg)
        provider_cfg["model"] = cfg.get("model")

    click.echo("🤖 Consulting AI agents for impact analysis and remediation...")
    click.echo()

    agent = Agent(
        name="security-auditor",
        use_multi_agent=True,
        provider_name=provider,
        provider_config=provider_cfg,
    )

    agent.prepare({"vulnerabilities": vulns, "summary": summary})

    result = agent.run_task(task)

    if not result.get("success"):
        click.echo(click.style("❌ AI analysis failed:", fg="red"))
        click.echo(result.get("output", "Unknown error"))
        raise click.Abort()

    click.echo(click.style("=" * 70, fg="cyan"))
    click.echo(click.style("SECURITY ANALYSIS & REMEDIATION", fg="cyan", bold=True))
    click.echo(click.style("=" * 70, fg="cyan"))
    click.echo()
    click.echo(result.get("selected_suggestion", "No analysis available"))
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


def _severity_color(severity: str) -> str:
    """Map severity to a click color."""
    return {
        "critical": "red",
        "high": "red",
        "medium": "yellow",
        "low": "green",
        "unknown": "white",
    }.get(severity.lower(), "white")


def _build_security_task(vulns: list[dict], summary: dict) -> str:
    """Build the task description for AI agents."""
    vuln_text = "\n".join(
        f"- [{v['severity'].upper()}] {v['package']} ({v['installed_version']}): "
        f"{v['vuln_id']} - {v['summary']}"
        + (f" (fixed in {v['fixed_in']})" if v.get("fixed_in") else "")
        for v in vulns
    )

    total = sum(summary.values())

    return f"""Analyze the following {total} security vulnerabilities found in project dependencies
and provide a prioritized remediation plan:

{vuln_text}

Please:
1. Assess the real-world impact of each vulnerability on a typical Hatch project
2. Prioritize which vulnerabilities to fix first based on severity and exploitability
3. Provide specific upgrade commands or pyproject.toml changes for each fix
4. Note any potential breaking changes from the suggested upgrades
5. Suggest any additional security hardening measures"""


if __name__ == "__main__":
    security()
