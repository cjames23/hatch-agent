"""Tests for config command."""

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from hatch_agent.commands.config import generate_config


class TestGenerateConfigCLI:
    """Test generate_config CLI command."""

    @pytest.fixture
    def cli_runner(self):
        """Create a Click CLI runner."""
        return CliRunner()

    @patch("hatch_agent.commands.config.write_config")
    def test_generate_config_default(self, mock_write, cli_runner, temp_project_dir):
        """Test generating default config."""
        mock_write.return_value = True
        config_file = temp_project_dir / "config.toml"

        result = cli_runner.invoke(generate_config, ["--path", str(config_file)])

        assert result.exit_code == 0
        assert "Configuration written" in result.output
        mock_write.assert_called_once()

    @patch("hatch_agent.commands.config.write_config")
    def test_generate_config_with_provider(self, mock_write, cli_runner, temp_project_dir):
        """Test generating config for specific provider."""
        mock_write.return_value = True
        config_file = temp_project_dir / "config.toml"

        result = cli_runner.invoke(
            generate_config, ["--provider", "openai", "--path", str(config_file)]
        )

        assert result.exit_code == 0
        assert "openai" in result.output.lower()

    @patch("hatch_agent.commands.config.write_config")
    def test_generate_config_anthropic(self, mock_write, cli_runner, temp_project_dir):
        """Test generating config for Anthropic."""
        mock_write.return_value = True
        config_file = temp_project_dir / "config.toml"

        result = cli_runner.invoke(
            generate_config, ["--provider", "anthropic", "--path", str(config_file)]
        )

        assert result.exit_code == 0
        mock_write.assert_called_once()

    @patch("hatch_agent.commands.config.write_config")
    def test_generate_config_write_failure(self, mock_write, cli_runner, temp_project_dir):
        """Test handling write failure."""
        mock_write.return_value = False
        config_file = temp_project_dir / "config.toml"

        result = cli_runner.invoke(generate_config, ["--path", str(config_file)])

        assert result.exit_code != 0 or "Failed" in result.output

    @patch("hatch_agent.commands.config.write_config")
    def test_generate_config_interactive(self, mock_write, cli_runner, temp_project_dir):
        """Test interactive config generation."""
        mock_write.return_value = True
        config_file = temp_project_dir / "config.toml"

        # Simulate interactive input: provider 1 (openai), no to customize model
        result = cli_runner.invoke(
            generate_config,
            ["--interactive", "--path", str(config_file)],
            input="1\ntest-api-key\nn\n",
        )

        assert result.exit_code == 0


class TestConfigCommand:
    """Test config command."""

    def test_show_config(self, mock_environment_config):
        """Test showing current configuration."""
        assert "name" in mock_environment_config
        assert "dependencies" in mock_environment_config


class TestConfigManagement:
    """Test configuration management."""

    def test_load_config_from_file(self, sample_pyproject_toml):
        """Test loading configuration from file."""
        assert sample_pyproject_toml.exists()


class TestGenerateConfigInteractive:
    """Test generate_config with interactive mode for different providers."""

    @pytest.fixture
    def cli_runner(self):
        return CliRunner()

    @patch("hatch_agent.commands.config.write_config")
    def test_interactive_anthropic(self, mock_write, cli_runner, temp_project_dir):
        """Test interactive config for Anthropic."""
        mock_write.return_value = True
        config_file = temp_project_dir / "config.toml"

        # Select anthropic (2), provide API key, no to customize model
        result = cli_runner.invoke(
            generate_config,
            ["--interactive", "--path", str(config_file)],
            input="2\ntest-api-key\nn\n",
        )

        assert result.exit_code == 0
        mock_write.assert_called_once()

    @patch("hatch_agent.commands.config.write_config")
    def test_interactive_bedrock(self, mock_write, cli_runner, temp_project_dir):
        """Test interactive config for AWS Bedrock."""
        mock_write.return_value = True
        config_file = temp_project_dir / "config.toml"

        # Select bedrock (3), provide AWS credentials, no to customize model
        result = cli_runner.invoke(
            generate_config,
            ["--interactive", "--path", str(config_file)],
            input="3\naws-key-id\naws-secret\nus-west-2\nn\n",
        )

        assert result.exit_code == 0

    @patch("hatch_agent.commands.config.write_config")
    def test_interactive_azure(self, mock_write, cli_runner, temp_project_dir):
        """Test interactive config for Azure OpenAI."""
        mock_write.return_value = True
        config_file = temp_project_dir / "config.toml"

        # Select azure (4), provide Azure credentials, no to customize model
        result = cli_runner.invoke(
            generate_config,
            ["--interactive", "--path", str(config_file)],
            input="4\nazure-key\nhttps://test.openai.azure.com/\nmy-deployment\nn\n",
        )

        assert result.exit_code == 0

    @patch("hatch_agent.commands.config.write_config")
    def test_interactive_google(self, mock_write, cli_runner, temp_project_dir):
        """Test interactive config for Google Cloud."""
        mock_write.return_value = True
        config_file = temp_project_dir / "config.toml"

        # Select google (5), provide GCP details, no to customize model
        result = cli_runner.invoke(
            generate_config,
            ["--interactive", "--path", str(config_file)],
            input="5\nmy-project-id\nus-central1\nn\n",
        )

        assert result.exit_code == 0

    @patch("hatch_agent.commands.config.write_config")
    def test_interactive_cohere(self, mock_write, cli_runner, temp_project_dir):
        """Test interactive config for Cohere."""
        mock_write.return_value = True
        config_file = temp_project_dir / "config.toml"

        # Select cohere (6), provide API key, no to customize model
        result = cli_runner.invoke(
            generate_config,
            ["--interactive", "--path", str(config_file)],
            input="6\ncohere-api-key\nn\n",
        )

        assert result.exit_code == 0

    @patch("hatch_agent.commands.config.write_config")
    def test_interactive_custom_model(self, mock_write, cli_runner, temp_project_dir):
        """Test interactive config with custom model name."""
        mock_write.return_value = True
        config_file = temp_project_dir / "config.toml"

        # Select openai (1), provide API key, yes to customize model, enter custom model
        result = cli_runner.invoke(
            generate_config,
            ["--interactive", "--path", str(config_file)],
            input="1\ntest-api-key\ny\ngpt-4-turbo\n",
        )

        assert result.exit_code == 0

    @patch("hatch_agent.commands.config.write_config")
    def test_generate_config_bedrock_provider(self, mock_write, cli_runner, temp_project_dir):
        """Test generating config for bedrock provider (non-interactive)."""
        mock_write.return_value = True
        config_file = temp_project_dir / "config.toml"

        result = cli_runner.invoke(
            generate_config, ["--provider", "bedrock", "--path", str(config_file)]
        )

        assert result.exit_code == 0
        assert "bedrock" in result.output.lower() or "template" in result.output.lower()

    @patch("hatch_agent.commands.config.write_config")
    def test_generate_config_azure_provider(self, mock_write, cli_runner, temp_project_dir):
        """Test generating config for azure provider (non-interactive)."""
        mock_write.return_value = True
        config_file = temp_project_dir / "config.toml"

        result = cli_runner.invoke(
            generate_config, ["--provider", "azure", "--path", str(config_file)]
        )

        assert result.exit_code == 0

    @patch("hatch_agent.commands.config.write_config")
    def test_generate_config_google_provider(self, mock_write, cli_runner, temp_project_dir):
        """Test generating config for google provider (non-interactive)."""
        mock_write.return_value = True
        config_file = temp_project_dir / "config.toml"

        result = cli_runner.invoke(
            generate_config, ["--provider", "google", "--path", str(config_file)]
        )

        assert result.exit_code == 0
