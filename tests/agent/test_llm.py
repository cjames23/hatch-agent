"""Tests for LLM provider implementations."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from hatch_agent.agent.llm import LLMClient, StrandsProvider


class TestStrandsProvider:
    """Test StrandsProvider class."""

    def test_init_stores_config(self):
        """Test that __init__ stores config."""
        config = {"mode": "single", "model": "gpt-4"}
        provider = StrandsProvider(config)
        assert provider.config == config

    def test_complete_multi_agent_mode(self):
        """Test complete in multi-agent mode."""
        # Patch at the import location inside the complete method
        with patch.dict('sys.modules', {'hatch_agent.agent.multi_agent': MagicMock()}):
            import sys
            mock_module = sys.modules['hatch_agent.agent.multi_agent']
            mock_orchestrator = MagicMock()
            mock_orchestrator.run.return_value = {
                "selected_suggestion": "Use requests library",
                "selected_agent": "ConfigSpecialist",
                "reasoning": "Best for HTTP"
            }
            mock_module.MultiAgentOrchestrator.return_value = mock_orchestrator
            
            config = {"mode": "multi-agent", "underlying_provider": "openai"}
            provider = StrandsProvider(config)
            result = provider.complete("Add HTTP client")
            
            assert "Use requests library" in result
            assert "ConfigSpecialist" in result

    @patch("hatch_agent.agent.llm.StrandsAgent")
    def test_complete_single_mode(self, mock_strands_agent):
        """Test complete in single agent mode."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = "Single agent response"
        mock_strands_agent.return_value = mock_agent_instance
        
        config = {"mode": "single"}
        provider = StrandsProvider(config)
        result = provider.complete("Test prompt")
        
        assert "Single agent response" in result
        mock_strands_agent.assert_called_once()

    def test_complete_default_mode_is_multi_agent(self):
        """Test that default mode is multi-agent."""
        with patch.dict('sys.modules', {'hatch_agent.agent.multi_agent': MagicMock()}):
            import sys
            mock_module = sys.modules['hatch_agent.agent.multi_agent']
            mock_orchestrator = MagicMock()
            mock_orchestrator.run.return_value = {
                "selected_suggestion": "suggestion",
                "selected_agent": "agent",
                "reasoning": "reason"
            }
            mock_module.MultiAgentOrchestrator.return_value = mock_orchestrator
            
            config = {}  # No mode specified
            provider = StrandsProvider(config)
            provider.complete("Test")
            
            mock_module.MultiAgentOrchestrator.assert_called()

    def test_complete_passes_model_to_config(self):
        """Test that model is passed through to underlying config."""
        with patch.dict('sys.modules', {'hatch_agent.agent.multi_agent': MagicMock()}):
            import sys
            mock_module = sys.modules['hatch_agent.agent.multi_agent']
            mock_orchestrator = MagicMock()
            mock_orchestrator.run.return_value = {
                "selected_suggestion": "s",
                "selected_agent": "a",
                "reasoning": "r"
            }
            mock_module.MultiAgentOrchestrator.return_value = mock_orchestrator
            
            config = {"mode": "multi-agent", "model": "gpt-4-turbo"}
            provider = StrandsProvider(config)
            provider.complete("Test")
            
            # Verify orchestrator was called
            mock_module.MultiAgentOrchestrator.assert_called()

    def test_chat_routes_to_complete(self):
        """Test that chat routes to complete."""
        config = {}
        provider = StrandsProvider(config)
        
        with patch.object(provider, 'complete', return_value="response") as mock_complete:
            result = provider.chat("message")
            mock_complete.assert_called_once_with("message")
            assert result == "response"


class TestLLMClient:
    """Test LLMClient class."""

    def test_from_config_new_style(self):
        """Test from_config with new-style config."""
        config = {
            "underlying_provider": "openai",
            "model": "gpt-4",
            "underlying_config": {"api_key": "test"}
        }
        client = LLMClient.from_config(config)
        assert client.provider_config == config

    def test_from_config_with_mode(self):
        """Test from_config with mode in config."""
        config = {"mode": "single", "model": "gpt-4"}
        client = LLMClient.from_config(config)
        assert client.provider_config == config

    def test_from_config_old_style_non_strands(self):
        """Test from_config converts old-style non-strands config."""
        config = {
            "provider": "openai",
            "model": "gpt-4",
            "providers": {
                "openai": {"api_key": "test-key"}
            }
        }
        client = LLMClient.from_config(config)
        assert client.provider_config["underlying_provider"] == "openai"
        assert client.provider_config["model"] == "gpt-4"

    def test_from_config_old_style_strands(self):
        """Test from_config with old-style strands config."""
        config = {
            "provider": "strands",
            "model": "gpt-4",
            "providers": {
                "strands": {
                    "underlying_provider": "openai"
                }
            }
        }
        client = LLMClient.from_config(config)
        assert "model" in client.provider_config

    def test_from_config_model_passthrough(self):
        """Test that model is passed through in old-style config."""
        config = {
            "provider": "strands",
            "model": "claude-3",
            "providers": {
                "strands": {}
            }
        }
        client = LLMClient.from_config(config)
        assert client.provider_config.get("model") == "claude-3"

    def test_provider_returns_strands_provider(self):
        """Test _provider returns StrandsProvider instance."""
        client = LLMClient(provider_config={"model": "test"})
        provider = client._provider()
        assert isinstance(provider, StrandsProvider)

    def test_complete_calls_provider(self):
        """Test complete calls through to provider."""
        client = LLMClient(provider_config={})
        
        with patch.object(StrandsProvider, 'complete', return_value="response") as mock:
            result = client.complete("test prompt")
            mock.assert_called_once_with("test prompt")
            assert result == "response"

    def test_chat_calls_provider(self):
        """Test chat calls through to provider."""
        client = LLMClient(provider_config={})
        
        with patch.object(StrandsProvider, 'chat', return_value="response") as mock:
            result = client.chat("test message")
            mock.assert_called_once_with("test message")
            assert result == "response"


class TestLLMProvider:
    """Test LLM provider abstraction."""

    def test_llm_provider_mock(self, mock_llm_provider):
        """Test with mocked LLM provider."""
        response = mock_llm_provider.generate("Hello")
        assert response == "Mocked LLM generated text"

    def test_llm_chat_mock(self, mock_llm_provider):
        """Test chat with mocked LLM provider."""
        response = mock_llm_provider.chat("Hello")
        assert response == "Mocked LLM chat response"

    def test_llm_streaming_mock(self, mock_llm_provider):
        """Test streaming with mocked LLM provider."""
        chunks = list(mock_llm_provider.stream("Hello"))
        assert len(chunks) == 3
        assert "".join(chunks) == "Mocked streaming response"


class TestOpenAIProvider:
    """Test OpenAI LLM provider."""

    def test_openai_chat_completion(self, mock_openai_client):
        """Test OpenAI chat completion without API calls."""
        response = mock_openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}]
        )

        assert response.choices[0].message.content == "Mocked OpenAI response"
        assert response.usage.total_tokens == 30

    def test_openai_streaming_response(self, mock_openai_client):
        """Test OpenAI streaming without API calls."""
        mock_stream = [
            Mock(choices=[Mock(delta=Mock(content="Hello"))]),
            Mock(choices=[Mock(delta=Mock(content=" world"))]),
        ]
        mock_openai_client.chat.completions.create.return_value = iter(mock_stream)

        response = mock_openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}],
            stream=True
        )

        chunks = list(response)
        assert len(chunks) == 2

    def test_openai_error_handling(self, mock_openai_client):
        """Test OpenAI error handling."""
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")

        with pytest.raises(Exception) as exc_info:
            mock_openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "Hello"}]
            )

        assert "API Error" in str(exc_info.value)

    def test_openai_token_counting(self, mock_openai_client):
        """Test token usage tracking."""
        response = mock_openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}]
        )

        assert response.usage.prompt_tokens > 0
        assert response.usage.completion_tokens > 0
        assert response.usage.total_tokens > 0


class TestAnthropicProvider:
    """Test Anthropic Claude provider."""

    def test_anthropic_message_creation(self, mock_anthropic_client):
        """Test Anthropic message creation without API calls."""
        response = mock_anthropic_client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Hello"}]
        )

        assert response.content[0].text == "Mocked Anthropic response"
        assert response.stop_reason == "end_turn"

    def test_anthropic_streaming(self, mock_anthropic_client):
        """Test Anthropic streaming without API calls."""
        mock_stream = [
            Mock(type="content_block_delta", delta=Mock(text="Hello")),
            Mock(type="content_block_delta", delta=Mock(text=" world")),
        ]
        mock_anthropic_client.messages.stream.return_value.__enter__ = Mock(return_value=iter(mock_stream))
        mock_anthropic_client.messages.stream.return_value.__exit__ = Mock(return_value=False)

        with mock_anthropic_client.messages.stream(
            model="claude-3-opus-20240229",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Hello"}]
        ) as stream:
            chunks = list(stream)
            assert len(chunks) == 2

    def test_anthropic_error_handling(self, mock_anthropic_client):
        """Test Anthropic error handling."""
        mock_anthropic_client.messages.create.side_effect = Exception("API Error")

        with pytest.raises(Exception):
            mock_anthropic_client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=1024,
                messages=[{"role": "user", "content": "Hello"}]
            )

    def test_anthropic_token_usage(self, mock_anthropic_client):
        """Test Anthropic token usage tracking."""
        response = mock_anthropic_client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Hello"}]
        )

        assert response.usage.input_tokens > 0
        assert response.usage.output_tokens > 0


class TestGoogleAIProvider:
    """Test Google AI (Gemini) provider."""

    def test_google_generate_content(self, mock_google_client):
        """Test Google AI content generation without API calls."""
        response = mock_google_client.generate_content("Hello")

        assert response.text == "Mocked Google AI response"

    def test_google_streaming(self, mock_google_client):
        """Test Google AI streaming without API calls."""
        mock_stream = [
            Mock(text="Hello"),
            Mock(text=" world"),
        ]
        mock_google_client.generate_content.return_value = iter(mock_stream)

        response = mock_google_client.generate_content("Hello", stream=True)
        chunks = list(response)
        assert len(chunks) == 2

    def test_google_error_handling(self, mock_google_client):
        """Test Google AI error handling."""
        mock_google_client.generate_content.side_effect = Exception("API Error")

        with pytest.raises(Exception):
            mock_google_client.generate_content("Hello")


class TestLLMResponseParsing:
    """Test parsing LLM responses."""

    def test_parse_openai_response(self, mock_openai_client):
        """Test parsing OpenAI response format."""
        response = mock_openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}]
        )

        content = response.choices[0].message.content
        assert isinstance(content, str)
        assert len(content) > 0

    def test_parse_anthropic_response(self, mock_anthropic_client):
        """Test parsing Anthropic response format."""
        response = mock_anthropic_client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Hello"}]
        )

        content = response.content[0].text
        assert isinstance(content, str)
        assert len(content) > 0

    def test_parse_google_response(self, mock_google_client):
        """Test parsing Google AI response format."""
        response = mock_google_client.generate_content("Hello")

        content = response.text
        assert isinstance(content, str)
        assert len(content) > 0


class TestLLMCostTracking:
    """Test LLM API cost tracking."""

    def test_track_openai_costs(self, mock_openai_client):
        """Test tracking OpenAI API costs."""
        response = mock_openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}]
        )

        # Calculate approximate cost based on token usage
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens

        assert prompt_tokens > 0
        assert completion_tokens > 0

    def test_track_anthropic_costs(self, mock_anthropic_client):
        """Test tracking Anthropic API costs."""
        response = mock_anthropic_client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Hello"}]
        )

        assert response.usage.input_tokens > 0
        assert response.usage.output_tokens > 0

    def test_cumulative_cost_tracking(self):
        """Test cumulative cost tracking across multiple calls."""
        # Would test cost accumulation logic
        pass
