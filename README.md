# hatch-agent

An intelligent multi-agent AI assistant for managing Hatch projects using natural language.

## Overview

`hatch-agent` uses a sophisticated multi-agent approach powered by `strands-agents` to help you manage your Hatch Python projects. Instead of a single AI making decisions, it employs:

- **2 Specialist Agents**: Generate different approaches to your problem
  - ConfigurationSpecialist: Expert in pyproject.toml and dependencies
  - WorkflowSpecialist: Expert in testing, formatting, and CI/CD
- **1 Judge Agent**: Evaluates suggestions using a consistent scoring framework

This ensures you get well-reasoned, reliable recommendations.

## Installation

```bash
pip install hatch-agent
```

## Configuration

### Prerequisites

Before using `hatch-agent`, you need an active account with one of the supported LLM providers. This tool does not include any LLM services - you must bring your own API credentials and pay for usage according to your provider's pricing.

### Setting Up Credentials

Create a configuration file at `~/.config/hatch-agent/config.toml` or in your project root as `.hatch-agent.toml`.

#### OpenAI (Recommended)

1. **Get your API key**: Sign up at [platform.openai.com](https://platform.openai.com) and create an API key
2. **Set up billing**: Add a payment method in your OpenAI account settings
3. **Configure hatch-agent**:

```toml
mode = "multi-agent"
underlying_provider = "openai"
model = "gpt-4"  # or "gpt-3.5-turbo" for lower cost

[underlying_config]
api_key = "sk-..."  # Your OpenAI API key
```

**Alternative: Use environment variable**
```bash
export OPENAI_API_KEY="sk-..."
```

Then in config:
```toml
mode = "multi-agent"
underlying_provider = "openai"
model = "gpt-4"
# underlying_config.api_key will be read from environment
```

#### Anthropic (Claude)

1. **Get your API key**: Sign up at [console.anthropic.com](https://console.anthropic.com)
2. **Set up billing**: Add payment method and purchase credits
3. **Configure hatch-agent**:

```toml
mode = "multi-agent"
underlying_provider = "anthropic"
model = "claude-3-opus-20240229"  # or "claude-3-sonnet-20240229"

[underlying_config]
api_key = "sk-ant-..."  # Your Anthropic API key
```

**Alternative: Use environment variable**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

#### AWS Bedrock

1. **Set up AWS Account**: Ensure you have an AWS account with Bedrock access enabled
2. **Request model access**: In AWS Console, go to Bedrock and request access to desired models
3. **Create IAM credentials**: Create an IAM user with Bedrock permissions
4. **Configure hatch-agent**:

```toml
mode = "multi-agent"
underlying_provider = "bedrock"
model = "anthropic.claude-v2"  # or other Bedrock model

[underlying_config]
aws_access_key_id = "AKIA..."
aws_secret_access_key = "..."
region = "us-east-1"  # Your AWS region
```

**Alternative: Use AWS credentials file or environment**
```bash
# Configure AWS CLI or set environment variables
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_DEFAULT_REGION="us-east-1"
```

Then in config:
```toml
mode = "multi-agent"
underlying_provider = "bedrock"
model = "anthropic.claude-v2"
# Credentials will be read from environment/AWS config
```

#### Azure OpenAI

1. **Set up Azure OpenAI resource**: Create an Azure OpenAI service in Azure Portal
2. **Deploy a model**: Deploy a model like GPT-4 to get a deployment name
3. **Get credentials**: Find your API key and endpoint in Azure Portal
4. **Configure hatch-agent**:

```toml
mode = "multi-agent"
underlying_provider = "azure"
model = "gpt-4"

[underlying_config]
api_key = "..."  # Your Azure OpenAI key
api_base = "https://your-resource.openai.azure.com/"
api_version = "2024-02-15-preview"
deployment = "your-gpt4-deployment"  # Your deployment name
```

#### Google (Vertex AI / PaLM)

1. **Set up Google Cloud Project**: Enable Vertex AI API
2. **Set up authentication**: Create a service account and download credentials
3. **Configure hatch-agent**:

```toml
mode = "multi-agent"
underlying_provider = "google"
model = "gemini-pro"

[underlying_config]
project_id = "your-project-id"
location = "us-central1"
# Set GOOGLE_APPLICATION_CREDENTIALS env var to path of credentials JSON
```

**Set credentials**:
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

#### Cohere

1. **Get your API key**: Sign up at [cohere.com](https://cohere.com)
2. **Set up billing**: Add payment method
3. **Configure hatch-agent**:

```toml
mode = "multi-agent"
underlying_provider = "cohere"
model = "command"

[underlying_config]
api_key = "..."  # Your Cohere API key
```

### Configuration File Locations

`hatch-agent` looks for configuration files in this order:

1. `.hatch-agent.toml` in current directory
2. `~/.config/hatch-agent/config.toml` (Linux/macOS)
3. `~/Library/Application Support/hatch-agent/config.toml` (macOS)
4. `%APPDATA%\hatch-agent\config.toml` (Windows)

You can also specify a custom config file with `--config` flag.

### Cost Considerations

**You are responsible for all API costs incurred.** Here are approximate costs (as of 2025):

- **OpenAI GPT-4**: ~$0.03-0.06 per 1K tokens (input/output)
- **OpenAI GPT-3.5**: ~$0.001-0.002 per 1K tokens (much cheaper)
- **Anthropic Claude 3 Opus**: ~$0.015-0.075 per 1K tokens
- **Anthropic Claude 3 Sonnet**: ~$0.003-0.015 per 1K tokens (good balance)
- **AWS Bedrock**: Varies by model, similar to above
- **Azure OpenAI**: Same as OpenAI pricing plus Azure markup

**Tip**: Start with GPT-3.5-turbo or Claude 3 Sonnet for testing, then upgrade to GPT-4 or Claude 3 Opus for production use if needed.

### Security Best Practices

⚠️ **Never commit API keys to version control!**

- Use environment variables for sensitive credentials
- Add `.hatch-agent.toml` to your `.gitignore`
- Use different API keys for development and production
- Rotate keys regularly
- Set usage limits in your provider's dashboard

See `config.example.toml` for more provider examples and configuration options.

## Commands

### 1. Explain Build Failures

Get AI-powered analysis of why your build failed, including test failures, formatting issues, and type checking errors.

```bash
# Analyze build failures in current directory
hatch-agent-explain

# Specify project directory
hatch-agent-explain --project-root /path/to/project

# Show all agent suggestions
hatch-agent-explain --show-all
```

**What it does:**
- Runs your tests via `hatch run test`
- Checks code formatting
- Checks type hints
- Analyzes all failures with AI agents
- Provides actionable recommendations

### 2. Add Dependencies with Natural Language

Add dependencies to your project using plain English - the AI will determine the exact package, version, and location in pyproject.toml.

```bash
# Add a dependency
hatch-agent-add-dep add requests for http client

# Add to dev dependencies
hatch-agent-add-dep add pytest to dev dependencies

# Specify version
hatch-agent-add-dep I need pandas version 2.0 or higher

# Preview without making changes
hatch-agent-add-dep add numpy --dry-run

# Skip environment sync
hatch-agent-add-dep add flask --skip-sync
```

**What it does:**
- Parses your natural language request
- Determines the correct package name and version
- Identifies whether it should be main or optional dependency
- Modifies `pyproject.toml` correctly
- Syncs Hatch environment to install the package

### 3. General Tasks

Ask the AI agents any question about Hatch project management.

```bash
# Ask questions
hatch-agent How do I set up testing with pytest?

hatch-agent Configure my project for type checking

hatch-agent What's the best way to organize my Hatch environments?

# Show all agent suggestions
hatch-agent Setup CI/CD for my project --show-all
```

## Features

### Multi-Agent Architecture

Every command uses the multi-agent system:

1. **ConfigurationSpecialist** focuses on:
   - pyproject.toml structure
   - Dependency management
   - Build system configuration
   - PEP 621 compliance

2. **WorkflowSpecialist** focuses on:
   - Testing frameworks
   - Code quality tools
   - Development workflows
   - Automation scripts

3. **Judge** uses a consistent scoring framework:
   - Correctness (30 points)
   - Completeness (25 points)
   - Safety (20 points)
   - Best Practices (15 points)
   - Clarity (10 points)

This ensures similar inputs produce consistent, high-quality outputs.

### Detailed Prompts with Guardrails

All agents have comprehensive system prompts that:
- Define their expertise clearly
- Enforce structured output formats
- Ensure actionable recommendations
- Maintain consistency across similar inputs

### Automatic Execution

Commands like `add-dep` can automatically:
- Parse AI suggestions into executable actions
- Modify `pyproject.toml` safely
- Run Hatch commands to sync environments
- Provide rollback guidance if needed

## Example Workflows

### Debugging a Failed Build

```bash
# Run this when your build fails
hatch-agent-explain

# Output shows:
# ✓ Tests: FAILED
# ✓ Formatting: PASSED  
# ✓ Type checking: FAILED
#
# Then provides detailed analysis and fixes
```

### Adding Dependencies

```bash
# Natural language request
hatch-agent-add-dep add black and ruff to my dev dependencies

# AI determines:
# - Package names: black, ruff
# - Target: optional-dependencies.dev
# - Versions: latest compatible
#
# Then modifies pyproject.toml and syncs environment
```

## Supported LLM Providers

Through `strands-agents`, supports:
- OpenAI (GPT-3.5, GPT-4)
- Anthropic (Claude)
- AWS Bedrock
- Azure OpenAI
- Google (PaLM, Gemini)
- Cohere

## Development

```bash
# Clone the repository
git clone https://github.com/your-org/hatch-agent
cd hatch-agent

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest
```

## Architecture

```
hatch-agent/
├── src/hatch_agent/
│   ├── agent/
│   │   ├── core.py           # Main Agent class
│   │   ├── llm.py            # LLM client using strands-agents
│   │   └── multi_agent.py    # Multi-agent orchestration
│   ├── analyzers/
│   │   ├── build.py          # Build failure analysis
│   │   └── dependency.py     # Dependency management
│   └── commands/
│       ├── explain.py        # Build failure command
│       ├── add_dependency.py # Add dependency command
│       └── multi_task.py     # General task command
```

## License

MIT

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.
