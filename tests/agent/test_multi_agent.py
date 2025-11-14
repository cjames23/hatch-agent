"""Tests for the multi-agent orchestration system."""

import pytest
from hatch_agent.agent.multi_agent import MultiAgentOrchestrator, AgentResponse, MockAgent


def test_mock_agent_specialist():
    """Test that MockAgent generates specialist responses."""
    agent = MockAgent("TestAgent", "Test Specialist", "Test instructions")
    response = agent.run("Test task")

    assert isinstance(response, dict)
    assert "suggestion" in response
    assert "reasoning" in response
    assert "confidence" in response
    assert "TestAgent" in response["suggestion"]


def test_mock_agent_judge():
    """Test that MockAgent generates judge responses."""
    agent = MockAgent("Judge", "Judge role", "Judge instructions")
    response = agent.run("Evaluate suggestions")

    assert isinstance(response, dict)
    assert "selected_agent" in response
    assert "suggestion" in response
    assert "reasoning" in response


def test_orchestrator_initialization():
    """Test that the orchestrator initializes correctly."""
    orchestrator = MultiAgentOrchestrator(provider_name="mock")

    assert orchestrator.provider_name == "mock"
    assert orchestrator.provider_config == {}
    # Should fall back to mock agents when strands-agents not available
    assert orchestrator.StrandsAgent is None or orchestrator._strands_available


def test_orchestrator_run_basic():
    """Test basic orchestrator run with mock provider."""
    orchestrator = MultiAgentOrchestrator(provider_name="mock")

    result = orchestrator.run("How do I add a new dependency to my Hatch project?")

    assert result["success"] is True
    assert "selected_suggestion" in result
    assert "selected_agent" in result
    assert "reasoning" in result
    assert "all_suggestions" in result
    assert len(result["all_suggestions"]) == 2


def test_orchestrator_with_context():
    """Test orchestrator with project context."""
    orchestrator = MultiAgentOrchestrator(provider_name="mock")

    context = {
        "project_name": "test-project",
        "dependencies": ["requests", "pytest"]
    }

    result = orchestrator.run(
        "Suggest how to organize my test suite",
        context=context
    )

    assert result["success"] is True
    assert "selected_suggestion" in result


def test_agent_response_dataclass():
    """Test AgentResponse dataclass."""
    response = AgentResponse(
        agent_name="TestAgent",
        suggestion="Do this",
        reasoning="Because reasons",
        confidence=0.85
    )

    assert response.agent_name == "TestAgent"
    assert response.suggestion == "Do this"
    assert response.reasoning == "Because reasons"
    assert response.confidence == 0.85


def test_orchestrator_parse_agent_response_json():
    """Test parsing agent response from JSON string."""
    orchestrator = MultiAgentOrchestrator(provider_name="mock")

    json_response = '{"suggestion": "Test suggestion", "reasoning": "Test reason", "confidence": 0.9}'
    parsed = orchestrator._parse_agent_response("Agent1", json_response)

    assert parsed.agent_name == "Agent1"
    assert parsed.suggestion == "Test suggestion"
    assert parsed.reasoning == "Test reason"
    assert parsed.confidence == 0.9


def test_orchestrator_parse_agent_response_dict():
    """Test parsing agent response from dict."""
    orchestrator = MultiAgentOrchestrator(provider_name="mock")

    dict_response = {
        "suggestion": "Test suggestion",
        "reasoning": "Test reason",
        "confidence": 0.8
    }
    parsed = orchestrator._parse_agent_response("Agent2", dict_response)

    assert parsed.agent_name == "Agent2"
    assert parsed.suggestion == "Test suggestion"
    assert parsed.reasoning == "Test reason"
    assert parsed.confidence == 0.8


def test_orchestrator_parse_judge_decision():
    """Test parsing judge decision."""
    orchestrator = MultiAgentOrchestrator(provider_name="mock")

    suggestions = [
        AgentResponse("Agent1", "Suggestion 1", "Reason 1", 0.7),
        AgentResponse("Agent2", "Suggestion 2", "Reason 2", 0.8)
    ]

    judge_response = {
        "selected_agent": "Agent2",
        "suggestion": "Selected suggestion",
        "reasoning": "This is better"
    }

    decision = orchestrator._parse_judge_decision(judge_response, suggestions)

    assert decision["agent_name"] == "Agent2"
    assert decision["suggestion"] == "Selected suggestion"
    assert decision["reasoning"] == "This is better"


def test_orchestrator_build_prompt():
    """Test prompt building."""
    orchestrator = MultiAgentOrchestrator(provider_name="mock")

    task = "Test task"
    context = {"key": "value"}

    prompt = orchestrator._build_prompt(task, context)

    assert "Test task" in prompt
    assert "key" in prompt
    assert "value" in prompt
    assert "suggestion" in prompt
    assert "reasoning" in prompt
    assert "confidence" in prompt


def test_orchestrator_build_judge_prompt():
    """Test judge prompt building."""
    orchestrator = MultiAgentOrchestrator(provider_name="mock")

    task = "Test task"
    suggestions = [
        AgentResponse("Agent1", "Suggestion 1", "Reason 1", 0.7),
        AgentResponse("Agent2", "Suggestion 2", "Reason 2", 0.8)
    ]
    context = {"key": "value"}

    prompt = orchestrator._build_judge_prompt(task, suggestions, context)

    assert "Test task" in prompt
    assert "Agent1" in prompt
    assert "Agent2" in prompt
    assert "Suggestion 1" in prompt
    assert "Suggestion 2" in prompt
    assert "selected_agent" in prompt

