"""Pytest configuration and shared fixtures for hatch-agent tests."""

import os
from unittest.mock import MagicMock, Mock

import pytest


@pytest.fixture
def mock_llm_response():
    """Mock LLM response to avoid API calls and costs."""
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "This is a mocked LLM response",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        },
    }


@pytest.fixture
def mock_openai_client(mock_llm_response):
    """Mock OpenAI client to avoid API calls."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = Mock(
        choices=[
            Mock(
                message=Mock(
                    role="assistant",
                    content="Mocked OpenAI response",
                ),
                finish_reason="stop",
            )
        ],
        usage=Mock(
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        ),
    )
    return mock_client


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client to avoid API calls."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = Mock(
        content=[Mock(text="Mocked Anthropic response")],
        stop_reason="end_turn",
        usage=Mock(
            input_tokens=10,
            output_tokens=20,
        ),
    )
    return mock_client


@pytest.fixture
def mock_google_client():
    """Mock Google AI client to avoid API calls."""
    mock_client = MagicMock()
    mock_response = Mock()
    mock_response.text = "Mocked Google AI response"
    mock_client.generate_content.return_value = mock_response
    return mock_client


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory for testing."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    return project_dir


@pytest.fixture
def sample_pyproject_toml(temp_project_dir):
    """Create a sample pyproject.toml file."""
    pyproject_path = temp_project_dir / "pyproject.toml"
    content = """
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "test-project"
version = "0.1.0"
description = "A test project"
dependencies = [
    "requests>=2.28.0",
    "click>=8.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "black>=22.0.0",
]

[tool.hatch.envs.default]
dependencies = [
    "pytest",
    "pytest-cov",
]
"""
    pyproject_path.write_text(content)
    return pyproject_path


@pytest.fixture
def sample_lockfile_content():
    """Sample lockfile content for testing."""
    return {
        "version": "1.0",
        "packages": {
            "requests": {
                "version": "2.28.1",
                "hashes": ["sha256:abc123"],
                "dependencies": ["urllib3", "certifi"],
            },
            "urllib3": {
                "version": "1.26.12",
                "hashes": ["sha256:def456"],
                "dependencies": [],
            },
            "certifi": {
                "version": "2022.9.24",
                "hashes": ["sha256:ghi789"],
                "dependencies": [],
            },
        },
    }


@pytest.fixture
def mock_environment_config():
    """Mock environment configuration."""
    return {
        "name": "default",
        "python": "3.10",
        "dependencies": ["pytest", "pytest-cov"],
        "features": [],
    }


@pytest.fixture
def mock_project_metadata():
    """Mock project metadata."""
    return {
        "name": "test-project",
        "version": "0.1.0",
        "description": "A test project",
        "dependencies": ["requests>=2.28.0", "click>=8.0.0"],
        "optional_dependencies": {
            "dev": ["pytest>=7.0.0", "black>=22.0.0"],
        },
    }


@pytest.fixture
def mock_dependency_info():
    """Mock dependency information."""
    return {
        "name": "requests",
        "version": "2.28.1",
        "latest_version": "2.31.0",
        "description": "HTTP library for Python",
        "homepage": "https://requests.readthedocs.io",
        "license": "Apache 2.0",
        "dependencies": ["urllib3>=1.26", "certifi>=2022"],
    }


@pytest.fixture(autouse=True)
def reset_environment():
    """Reset environment variables before each test."""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_llm_provider():
    """Generic mock LLM provider."""
    provider = MagicMock()
    provider.generate.return_value = "Mocked LLM generated text"
    provider.chat.return_value = "Mocked LLM chat response"
    provider.stream.return_value = iter(["Mocked ", "streaming ", "response"])
    return provider


@pytest.fixture
def mock_hatch_app():
    """Mock Hatch Application for testing."""
    app = MagicMock()
    app.project.config.envs = {"default": {}, "test": {}, "dev": {}}
    mock_env = MagicMock()
    mock_env.name = "default"
    mock_env.exists.return_value = True
    mock_env.dependencies = ["pytest", "requests"]
    mock_env.use_uv = False
    app.get_environment.return_value = mock_env
    app.env_active = "default"
    return app


@pytest.fixture
def mock_pypi_response():
    """Mock PyPI API response."""
    return {
        "info": {
            "version": "2.31.0",
            "name": "requests",
            "summary": "Python HTTP for Humans",
            "home_page": "https://requests.readthedocs.io",
            "license": "Apache 2.0",
            "project_urls": {
                "Changelog": "https://github.com/psf/requests/blob/main/HISTORY.md",
                "Documentation": "https://requests.readthedocs.io",
            },
        },
        "releases": {
            "2.28.0": [{"upload_time": "2022-06-29"}],
            "2.31.0": [{"upload_time": "2023-05-22"}],
        },
    }


@pytest.fixture
def mock_agent():
    """Mock Agent instance for testing commands."""
    agent = MagicMock()
    agent.run_task.return_value = {
        "success": True,
        "selected_suggestion": "Use pytest for testing",
        "selected_agent": "ConfigSpecialist",
        "reasoning": "Best practice for Python testing",
        "all_suggestions": [
            {
                "agent": "ConfigSpecialist",
                "suggestion": "Use pytest for testing",
                "reasoning": "Well-maintained",
                "confidence": 0.9,
            },
            {
                "agent": "WorkflowSpecialist",
                "suggestion": "Use unittest",
                "reasoning": "Built-in",
                "confidence": 0.7,
            },
        ],
    }
    agent.chat.return_value = "Mocked chat response"
    agent.prepare.return_value = None
    return agent


@pytest.fixture
def cli_runner():
    """Click CLI runner for testing commands."""
    from click.testing import CliRunner

    return CliRunner()
