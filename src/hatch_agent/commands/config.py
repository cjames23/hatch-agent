"""Commands to manage hatch-agent configuration."""

from pathlib import Path

import click

from hatch_agent.config import DEFAULT_CONFIG, PROVIDER_TEMPLATES, get_config_path, write_config


@click.command()
@click.option(
    "--provider",
    type=click.Choice(["openai", "anthropic", "bedrock", "azure", "google", "cohere"]),
    help="LLM provider to use",
)
@click.option("--interactive", is_flag=True, help="Interactive configuration wizard")
@click.option(
    "--path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Custom path for config file",
)
def generate_config(provider: str | None, interactive: bool, path: Path | None) -> None:
    """Generate a hatch-agent configuration file.

    Examples:

      hatch-agent-generate-config --provider openai

      hatch-agent-generate-config --interactive
    """
    config_path = str(path) if path else get_config_path()

    if interactive:
        # Interactive wizard
        click.echo(click.style("🔧 Hatch-Agent Configuration Wizard", fg="cyan", bold=True))
        click.echo()

        # Choose provider
        click.echo("Available LLM providers:")
        click.echo("  1. OpenAI (GPT-3.5, GPT-4)")
        click.echo("  2. Anthropic (Claude)")
        click.echo("  3. AWS Bedrock")
        click.echo("  4. Azure OpenAI")
        click.echo("  5. Google (Gemini)")
        click.echo("  6. Cohere")
        click.echo()

        provider_choice = click.prompt(
            "Select provider", type=click.Choice(["1", "2", "3", "4", "5", "6"]), default="1"
        )

        provider_map = {
            "1": "openai",
            "2": "anthropic",
            "3": "bedrock",
            "4": "azure",
            "5": "google",
            "6": "cohere",
        }
        provider = provider_map[provider_choice]

        # Get template
        config = PROVIDER_TEMPLATES[provider].copy()

        # Prompt for credentials based on provider
        click.echo()
        click.echo(click.style(f"Configuring {provider}...", fg="yellow"))
        click.echo()

        if provider in ["openai", "anthropic", "cohere"]:
            api_key = click.prompt("API Key", hide_input=True, default="")
            config["underlying_config"]["api_key"] = api_key

        elif provider == "bedrock":
            aws_key = click.prompt("AWS Access Key ID", default="")
            aws_secret = click.prompt("AWS Secret Access Key", hide_input=True, default="")
            region = click.prompt("AWS Region", default="us-east-1")
            config["underlying_config"]["aws_access_key_id"] = aws_key
            config["underlying_config"]["aws_secret_access_key"] = aws_secret
            config["underlying_config"]["region"] = region

        elif provider == "azure":
            api_key = click.prompt("Azure OpenAI API Key", hide_input=True, default="")
            api_base = click.prompt(
                "API Base URL", default="https://your-resource.openai.azure.com/"
            )
            deployment = click.prompt("Deployment Name", default="")
            config["underlying_config"]["api_key"] = api_key
            config["underlying_config"]["api_base"] = api_base
            config["underlying_config"]["deployment"] = deployment

        elif provider == "google":
            project_id = click.prompt("Google Cloud Project ID", default="")
            location = click.prompt("Location", default="us-central1")
            config["underlying_config"]["project_id"] = project_id
            config["underlying_config"]["location"] = location
            click.echo()
            click.echo(
                click.style(
                    "ℹ️  Don't forget to set GOOGLE_APPLICATION_CREDENTIALS environment variable",
                    fg="yellow",
                )
            )

        # Ask about model
        if click.confirm("Customize model name?", default=False):
            model = click.prompt("Model name", default=config["model"])
            config["model"] = model

    elif provider:
        # Use template for specified provider
        config = PROVIDER_TEMPLATES[provider].copy()
        click.echo(f"Using template for {provider}")
        click.echo()
        click.echo(
            click.style("⚠️  Remember to add your credentials to the config file!", fg="yellow")
        )

    else:
        # Use default config
        config = DEFAULT_CONFIG.copy()
        click.echo("Using default configuration (OpenAI)")
        click.echo()
        click.echo(click.style("⚠️  Remember to add your API key to the config file!", fg="yellow"))

    # Write config
    success = write_config(config, config_path)

    if success:
        click.echo()
        click.echo(click.style(f"✅ Configuration written to: {config_path}", fg="green"))
        click.echo()
        click.echo("Next steps:")
        click.echo("  1. Edit the config file to add your credentials")
        click.echo("  2. Test with: hatch-agent How do I configure testing?")
    else:
        click.echo(click.style(f"❌ Failed to write config to: {config_path}", fg="red"))
        raise click.Abort()


if __name__ == "__main__":
    generate_config()
