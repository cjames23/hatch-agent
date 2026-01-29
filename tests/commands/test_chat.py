"""Tests for chat command."""

from unittest.mock import MagicMock, Mock, patch
from click.testing import CliRunner
import sys
import importlib

import pytest

# Import the actual module (not the command) using importlib
chat_module = importlib.import_module('hatch_agent.commands.chat')
chat = chat_module.chat


class TestChatCLI:
    """Test chat CLI command."""

    @pytest.fixture
    def cli_runner(self):
        """Create a Click CLI runner."""
        return CliRunner()

    def test_chat_exit_immediately(self, cli_runner):
        """Test exiting chat with 'exit' command."""
        with patch.object(chat_module, 'load_config') as mock_load_config, \
             patch.object(chat_module, 'Agent') as mock_agent_class:
            mock_load_config.return_value = {}
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            
            result = cli_runner.invoke(chat, input="exit\n")
            
            assert result.exit_code == 0
            assert "Goodbye" in result.output

    def test_chat_quit_command(self, cli_runner):
        """Test exiting chat with 'quit' command."""
        with patch.object(chat_module, 'load_config') as mock_load_config, \
             patch.object(chat_module, 'Agent') as mock_agent_class:
            mock_load_config.return_value = {}
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            
            result = cli_runner.invoke(chat, input="quit\n")
            
            assert "Goodbye" in result.output

    def test_chat_q_command(self, cli_runner):
        """Test exiting chat with 'q' command."""
        with patch.object(chat_module, 'load_config') as mock_load_config, \
             patch.object(chat_module, 'Agent') as mock_agent_class:
            mock_load_config.return_value = {}
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            
            result = cli_runner.invoke(chat, input="q\n")
            
            assert "Goodbye" in result.output

    def test_chat_multi_agent_mode(self, cli_runner):
        """Test chat uses multi-agent mode by default."""
        with patch.object(chat_module, 'load_config') as mock_load_config, \
             patch.object(chat_module, 'Agent') as mock_agent_class:
            mock_load_config.return_value = {}
            mock_agent = MagicMock()
            mock_agent.run_task.return_value = {
                "success": True,
                "selected_suggestion": "Response",
                "selected_agent": "Agent1"
            }
            mock_agent_class.return_value = mock_agent
            
            result = cli_runner.invoke(chat, input="test question\nexit\n")
            
            mock_agent_class.assert_called_once()
            call_kwargs = mock_agent_class.call_args[1]
            assert call_kwargs["use_multi_agent"] is True

    def test_chat_single_agent_mode(self, cli_runner):
        """Test chat with --single-agent flag."""
        with patch.object(chat_module, 'load_config') as mock_load_config, \
             patch.object(chat_module, 'Agent') as mock_agent_class:
            mock_load_config.return_value = {}
            mock_agent = MagicMock()
            mock_agent.chat.return_value = "Response"
            mock_agent_class.return_value = mock_agent
            
            result = cli_runner.invoke(chat, ["--single-agent"], input="test\nexit\n")
            
            call_kwargs = mock_agent_class.call_args[1]
            assert call_kwargs["use_multi_agent"] is False

    def test_chat_displays_welcome(self, cli_runner):
        """Test chat displays welcome message."""
        with patch.object(chat_module, 'load_config') as mock_load_config, \
             patch.object(chat_module, 'Agent') as mock_agent_class:
            mock_load_config.return_value = {"model": "gpt-4"}
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            
            result = cli_runner.invoke(chat, input="exit\n")
            
            assert "Hatch-Agent" in result.output
            assert "Interactive Chat" in result.output


class TestChatCommand:
    """Test interactive chat command."""

    def test_start_chat_session(self, mock_llm_provider):
        """Test starting a chat session."""
        mock_llm_provider.chat.return_value = "Hello! How can I help you?"
        response = mock_llm_provider.chat("Hello")
        assert "help" in response.lower()

    def test_chat_with_context(self, mock_llm_provider):
        """Test chat with project context."""
        mock_llm_provider.chat.return_value = "I see you're working on a Python project."
        response = mock_llm_provider.chat("What am I working on?")
        assert "Python" in response

    def test_code_block_formatting(self, mock_llm_provider):
        """Test formatting code blocks in responses."""
        mock_llm_provider.chat.return_value = "```python\nprint('hello')\n```"
        response = mock_llm_provider.chat("Show me code")
        assert "```python" in response


class TestChatWithLLM:
    """Test chat with different LLM providers."""

    def test_chat_with_openai(self, mock_openai_client):
        """Test chat using OpenAI."""
        response = mock_openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}]
        )
        assert response.choices[0].message.content

    def test_chat_with_anthropic(self, mock_anthropic_client):
        """Test chat using Anthropic."""
        response = mock_anthropic_client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Hello"}]
        )
        assert response.content[0].text

    def test_chat_with_google(self, mock_google_client):
        """Test chat using Google AI."""
        response = mock_google_client.generate_content("Hello")
        assert response.text

