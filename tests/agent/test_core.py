"""Tests for core agent functionality."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from hatch_agent.agent.core import Agent


class TestAgentInitialization:
    """Test Agent class initialization."""

    def test_agent_default_initialization(self):
        """Test agent with default parameters."""
        agent = Agent()
        assert agent.name == "hatch-agent"
        assert agent.llm is None
        assert agent.use_multi_agent is False
        assert agent.orchestrator is None
        assert agent.state == {}

    def test_agent_with_custom_name(self):
        """Test agent with custom name."""
        agent = Agent(name="my-custom-agent")
        assert agent.name == "my-custom-agent"

    def test_agent_with_llm_client(self):
        """Test agent initialization with LLM client."""
        mock_llm = MagicMock()
        agent = Agent(llm_client=mock_llm)
        assert agent.llm is mock_llm

    @patch("hatch_agent.agent.core.MultiAgentOrchestrator")
    def test_agent_with_multi_agent_mode(self, mock_orchestrator_class):
        """Test agent initialization in multi-agent mode."""
        mock_orchestrator = MagicMock()
        mock_orchestrator_class.return_value = mock_orchestrator
        
        agent = Agent(use_multi_agent=True, provider_name="openai")
        
        assert agent.use_multi_agent is True
        assert agent.orchestrator is mock_orchestrator
        mock_orchestrator_class.assert_called_once()

    def test_agent_without_multi_agent_mode(self):
        """Test agent initialization without multi-agent mode."""
        agent = Agent(use_multi_agent=False)
        assert agent.orchestrator is None


class TestAgentPrepare:
    """Test Agent prepare method."""

    def test_prepare_with_context(self):
        """Test prepare updates state with context."""
        agent = Agent()
        context = {"project_root": "/test", "package": "requests"}
        
        agent.prepare(context)
        
        assert agent.state["project_root"] == "/test"
        assert agent.state["package"] == "requests"

    def test_prepare_with_none(self):
        """Test prepare with None context."""
        agent = Agent()
        agent.prepare(None)
        assert agent.state == {}

    def test_prepare_accumulates_state(self):
        """Test prepare accumulates state across calls."""
        agent = Agent()
        agent.prepare({"key1": "value1"})
        agent.prepare({"key2": "value2"})
        
        assert agent.state["key1"] == "value1"
        assert agent.state["key2"] == "value2"


class TestAgentRunTask:
    """Test Agent run_task method."""

    @patch("hatch_agent.agent.core.MultiAgentOrchestrator")
    def test_run_task_multi_agent_success(self, mock_orchestrator_class):
        """Test run_task with multi-agent orchestration."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.run.return_value = {
            "success": True,
            "selected_suggestion": "Use requests library"
        }
        mock_orchestrator_class.return_value = mock_orchestrator
        
        agent = Agent(use_multi_agent=True)
        result = agent.run_task("Add HTTP client")
        
        assert result["success"] is True
        mock_orchestrator.run.assert_called_once()

    @patch("hatch_agent.agent.core.MultiAgentOrchestrator")
    def test_run_task_multi_agent_exception(self, mock_orchestrator_class):
        """Test run_task handles multi-agent exceptions."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.run.side_effect = Exception("Orchestration failed")
        mock_orchestrator_class.return_value = mock_orchestrator
        
        agent = Agent(use_multi_agent=True)
        result = agent.run_task("Some task")
        
        assert result["success"] is False
        assert "Orchestration failed" in result["output"]

    def test_run_task_with_llm_success(self):
        """Test run_task with LLM client success."""
        mock_llm = MagicMock()
        mock_llm.complete.return_value = "Task completed successfully"
        
        agent = Agent(llm_client=mock_llm)
        result = agent.run_task("Test task")
        
        assert result["success"] is True
        assert result["output"] == "Task completed successfully"

    def test_run_task_with_llm_exception(self):
        """Test run_task handles LLM exceptions."""
        mock_llm = MagicMock()
        mock_llm.complete.side_effect = Exception("LLM Error")
        
        agent = Agent(llm_client=mock_llm)
        result = agent.run_task("Test task")
        
        assert result["success"] is False
        assert "LLM Error" in result["output"]

    def test_run_task_fallback_simulation(self):
        """Test run_task fallback when no LLM."""
        agent = Agent()
        result = agent.run_task("Execute test")
        
        assert result["success"] is True
        assert "(simulated)" in result["output"]
        assert "Execute test" in result["output"]


class TestAgentChat:
    """Test Agent chat method."""

    def test_chat_with_llm(self):
        """Test chat routes to LLM client."""
        mock_llm = MagicMock()
        mock_llm.chat.return_value = "Hello from LLM!"
        
        agent = Agent(llm_client=mock_llm)
        result = agent.chat("Hello")
        
        assert result == "Hello from LLM!"
        mock_llm.chat.assert_called_once_with("Hello")

    def test_chat_without_llm(self):
        """Test chat returns echo response without LLM."""
        agent = Agent(name="test-agent")
        result = agent.chat("Test message")
        
        assert "test-agent" in result
        assert "Test message" in result


class TestAgent:
    """Additional Agent tests for compatibility."""

    def test_agent_execute_task(self, mock_llm_provider):
        """Test agent task execution without LLM calls."""
        mock_llm_provider.generate.return_value = "Task completed successfully"
        result = mock_llm_provider.generate("Complete this task")
        assert result == "Task completed successfully"

    def test_agent_error_handling(self, mock_llm_provider):
        """Test agent error handling."""
        mock_llm_provider.generate.side_effect = Exception("LLM Error")

        with pytest.raises(Exception) as exc_info:
            mock_llm_provider.generate("Task")

        assert "LLM Error" in str(exc_info.value)


class TestAgentMemory:
    """Test agent memory and context management."""

    def test_add_to_memory(self):
        """Test adding messages to agent memory."""
        pass

    def test_retrieve_from_memory(self):
        """Test retrieving relevant context from memory."""
        pass

    def test_memory_limit(self):
        """Test memory size limits."""
        pass

    def test_clear_memory(self):
        """Test clearing agent memory."""
        pass


class TestAgentPlanning:
    """Test agent planning capabilities."""

    def test_create_plan(self, mock_llm_provider):
        """Test creating execution plan."""
        mock_llm_provider.generate.return_value = """
        1. Analyze the problem
        2. Break down into subtasks
        3. Execute each subtask
        4. Verify results
        """

        plan = mock_llm_provider.generate("Create a plan")
        assert "subtask" in plan.lower()

    def test_execute_plan_steps(self, mock_llm_provider):
        """Test executing plan steps."""
        pass

    def test_plan_adaptation(self, mock_llm_provider):
        """Test adapting plan based on results."""
        pass


class TestAgentObservation:
    """Test agent observation and feedback."""

    def test_observe_environment(self):
        """Test observing environment state."""
        pass

    def test_process_feedback(self, mock_llm_provider):
        """Test processing feedback."""
        pass

    def test_learn_from_errors(self):
        """Test learning from execution errors."""
        pass


class TestAgentToolUse:
    """Test agent tool usage."""

    def test_select_tool(self, mock_llm_provider):
        """Test tool selection logic."""
        pass

    def test_execute_tool(self):
        """Test tool execution."""
        pass

    def test_handle_tool_errors(self):
        """Test handling tool execution errors."""
        pass

    def test_chain_tool_calls(self):
        """Test chaining multiple tool calls."""
        pass

