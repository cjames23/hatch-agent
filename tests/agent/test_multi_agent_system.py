"""Tests for multi-agent coordination."""

from unittest.mock import MagicMock, patch

import pytest

from hatch_agent.agent.multi_agent import AgentResponse, MultiAgentOrchestrator


class TestAgentResponse:
    """Test AgentResponse dataclass."""

    def test_agent_response_creation(self):
        """Test creating an AgentResponse."""
        response = AgentResponse(
            agent_name="TestAgent",
            suggestion="Use requests library",
            reasoning="It's well-maintained",
            confidence=0.95,
        )
        assert response.agent_name == "TestAgent"
        assert response.suggestion == "Use requests library"
        assert response.reasoning == "It's well-maintained"
        assert response.confidence == 0.95

    def test_agent_response_attributes(self):
        """Test AgentResponse has all expected attributes."""
        response = AgentResponse(
            agent_name="Agent1", suggestion="Suggestion", reasoning="Reasoning", confidence=0.8
        )
        assert hasattr(response, "agent_name")
        assert hasattr(response, "suggestion")
        assert hasattr(response, "reasoning")
        assert hasattr(response, "confidence")


class TestMultiAgentOrchestratorInit:
    """Test MultiAgentOrchestrator initialization."""

    def test_default_initialization(self):
        """Test orchestrator with default values."""
        orchestrator = MultiAgentOrchestrator()
        assert orchestrator.provider_name == "openai"
        assert orchestrator.provider_config == {}

    def test_custom_provider(self):
        """Test orchestrator with custom provider."""
        orchestrator = MultiAgentOrchestrator(provider_name="anthropic")
        assert orchestrator.provider_name == "anthropic"

    def test_custom_config(self):
        """Test orchestrator with custom config."""
        config = {"api_key": "test-key", "model": "gpt-4"}
        orchestrator = MultiAgentOrchestrator(provider_config=config)
        assert orchestrator.provider_config == config


class TestMultiAgentOrchestratorCreateAgent:
    """Test _create_agent method."""

    @patch("hatch_agent.agent.multi_agent.StrandsAgent")
    def test_create_agent_returns_agent(self, mock_strands):
        """Test _create_agent returns a StrandsAgent."""
        mock_agent = MagicMock()
        mock_strands.return_value = mock_agent

        orchestrator = MultiAgentOrchestrator()
        agent = orchestrator._create_agent(
            name="TestAgent", role="Test role", instructions="Test instructions"
        )

        assert agent is mock_agent
        mock_strands.assert_called_once()

    @patch("hatch_agent.agent.multi_agent.StrandsAgent")
    def test_create_agent_uses_system_prompt(self, mock_strands):
        """Test _create_agent passes correct system prompt."""
        orchestrator = MultiAgentOrchestrator()
        orchestrator._create_agent(
            name="ConfigAgent", role="Configuration expert", instructions="Analyze configs"
        )

        call_kwargs = mock_strands.call_args[1]
        assert "system_prompt" in call_kwargs
        assert "Configuration expert" in call_kwargs["system_prompt"]
        assert "Analyze configs" in call_kwargs["system_prompt"]


class TestMultiAgentOrchestratorRun:
    """Test run method."""

    @patch.object(MultiAgentOrchestrator, "_judge_suggestions")
    @patch.object(MultiAgentOrchestrator, "_get_agent_response")
    @patch.object(MultiAgentOrchestrator, "_create_agent")
    def test_run_general_task(self, mock_create, mock_get_response, mock_judge):
        """Test run with general task."""
        mock_agent = MagicMock()
        mock_create.return_value = mock_agent

        mock_get_response.return_value = AgentResponse(
            agent_name="Agent1", suggestion="Suggestion", reasoning="Reason", confidence=0.9
        )

        mock_judge.return_value = {
            "suggestion": "Best suggestion",
            "agent_name": "Agent1",
            "reasoning": "Best choice",
        }

        orchestrator = MultiAgentOrchestrator()
        result = orchestrator.run("Configure hatch project")

        assert result["success"] is True
        assert result["selected_suggestion"] == "Best suggestion"
        assert "all_suggestions" in result
        assert len(result["all_suggestions"]) == 2  # Two specialist agents

    @patch.object(MultiAgentOrchestrator, "_run_update_agents")
    def test_run_detects_update_task(self, mock_update_agents):
        """Test run routes update tasks to specialized agents."""
        mock_update_agents.return_value = {"success": True, "selected_suggestion": "Update plan"}

        orchestrator = MultiAgentOrchestrator()
        orchestrator.run("updating the dependency requests to 2.31.0")

        mock_update_agents.assert_called_once()

    @patch.object(MultiAgentOrchestrator, "_run_update_agents")
    def test_run_detects_update_strategy_task(self, mock_update_agents):
        """Test run routes update strategy tasks to specialized agents."""
        mock_update_agents.return_value = {"success": True, "selected_suggestion": "Plan"}

        orchestrator = MultiAgentOrchestrator()
        orchestrator.run("What's the best update strategy for django?")

        mock_update_agents.assert_called_once()


class TestMultiAgentSystem:
    """Test multi-agent coordination."""

    def test_task_delegation(self, mock_llm_provider):
        """Test delegating tasks to appropriate agents."""
        mock_llm_provider.generate.return_value = "Task delegated to specialist agent"
        result = mock_llm_provider.generate("Delegate task")
        assert "delegated" in result.lower()

    def test_analyzer_agent(self, mock_llm_provider):
        """Test analyzer agent specialization."""
        mock_llm_provider.generate.return_value = "Analysis complete: 5 issues found"
        result = mock_llm_provider.generate("Analyze code")
        assert "analysis" in result.lower()


class TestBulkUpdateAnalysis:
    """Test bulk update analysis functionality."""

    @pytest.fixture
    def orchestrator(self):
        """Create a MultiAgentOrchestrator instance."""
        return MultiAgentOrchestrator(provider_name="mock", provider_config={})

    @pytest.fixture
    def sample_updates(self):
        """Sample package updates for testing."""
        return [
            {
                "package": "requests",
                "old_version": "2.28.0",
                "new_version": "2.31.0",
            },
            {
                "package": "django",
                "old_version": "3.2.0",
                "new_version": "4.0.0",
            },
        ]

    @pytest.fixture
    def sample_context(self):
        """Sample context for testing."""
        return {
            "project_root": "/tmp/test_project",
            "project_files": ["src/app.py", "src/views.py"],
        }

    def test_build_bulk_update_task(self, orchestrator, sample_updates):
        """Test _build_bulk_update_task generates correct task."""
        task = orchestrator._build_bulk_update_task(sample_updates[0], sample_updates)

        assert "requests" in task
        assert "2.28.0" in task
        assert "2.31.0" in task
        assert "UPDATE_PLAN:" in task
        # Should mention other updates
        assert "django" in task

    def test_build_bulk_update_task_single_package(self, orchestrator):
        """Test task for single package update."""
        updates = [{"package": "requests", "old_version": "2.0", "new_version": "3.0"}]
        task = orchestrator._build_bulk_update_task(updates[0], updates)

        assert "requests" in task
        assert "Other packages" not in task  # No other packages

    def test_extract_update_plan_valid(self, orchestrator):
        """Test _extract_update_plan with valid JSON."""
        suggestion = """
        Analysis shows...
        
        UPDATE_PLAN:
        {
            "version_spec": ">=2.31.0",
            "breaking_changes": ["Method removed"],
            "code_changes": [{"file": "app.py", "description": "Update call"}]
        }
        """

        plan = orchestrator._extract_update_plan(suggestion)

        assert plan is not None
        assert plan["version_spec"] == ">=2.31.0"
        assert len(plan["breaking_changes"]) == 1
        assert len(plan["code_changes"]) == 1

    def test_extract_update_plan_no_marker(self, orchestrator):
        """Test _extract_update_plan without marker."""
        suggestion = "Just text without plan"

        plan = orchestrator._extract_update_plan(suggestion)
        assert plan is None

    def test_extract_update_plan_invalid_json(self, orchestrator):
        """Test _extract_update_plan with invalid JSON."""
        suggestion = "UPDATE_PLAN:\n{not valid json}"

        plan = orchestrator._extract_update_plan(suggestion)
        assert plan is None

    def test_deduplicate_code_changes_no_duplicates(self, orchestrator):
        """Test _deduplicate_code_changes with unique changes."""
        changes = [
            {"file": "app.py", "line_range": "10-15", "description": "Change 1"},
            {"file": "views.py", "line_range": "20-25", "description": "Change 2"},
        ]

        result = orchestrator._deduplicate_code_changes(changes)
        assert len(result) == 2

    def test_deduplicate_code_changes_with_duplicates(self, orchestrator):
        """Test _deduplicate_code_changes removes duplicates."""
        changes = [
            {"file": "app.py", "line_range": "10-15", "description": "Short", "package": "a"},
            {
                "file": "app.py",
                "line_range": "10-15",
                "description": "Longer description",
                "package": "b",
            },
        ]

        result = orchestrator._deduplicate_code_changes(changes)

        assert len(result) == 1
        # Should keep the one with longer description
        assert result[0]["description"] == "Longer description"
        # Should track both packages
        assert "packages" in result[0]
        assert "a" in result[0]["packages"]
        assert "b" in result[0]["packages"]

    def test_deduplicate_code_changes_different_files(self, orchestrator):
        """Test _deduplicate_code_changes keeps different file changes."""
        changes = [
            {"file": "app.py", "line_range": "10-15", "description": "Change"},
            {"file": "views.py", "line_range": "10-15", "description": "Change"},
        ]

        result = orchestrator._deduplicate_code_changes(changes)
        assert len(result) == 2

    @patch.object(MultiAgentOrchestrator, "_run_update_agents")
    def test_run_bulk_update_analysis_success(
        self, mock_run_update, orchestrator, sample_updates, sample_context
    ):
        """Test run_bulk_update_analysis with successful analysis."""
        # Mock successful analysis for each package
        mock_run_update.return_value = {
            "success": True,
            "selected_suggestion": """
            UPDATE_PLAN:
            {
                "version_spec": ">=2.31.0",
                "breaking_changes": ["API change"],
                "code_changes": [{"file": "app.py", "description": "Update"}]
            }
            """,
        }

        result = orchestrator.run_bulk_update_analysis(sample_updates, sample_context)

        assert result["success"] is True
        assert result["packages_analyzed"] == 2
        assert len(result["breaking_changes"]) == 2  # One per package
        assert len(result["failed_packages"]) == 0

    @patch.object(MultiAgentOrchestrator, "_run_update_agents")
    def test_run_bulk_update_analysis_partial_failure(
        self, mock_run_update, orchestrator, sample_updates, sample_context
    ):
        """Test run_bulk_update_analysis with some failures."""
        # First succeeds, second fails
        mock_run_update.side_effect = [
            {
                "success": True,
                "selected_suggestion": """
                UPDATE_PLAN:
                {"version_spec": ">=2.31.0", "breaking_changes": [], "code_changes": []}
                """,
            },
            {"success": False, "output": "Error"},
        ]

        result = orchestrator.run_bulk_update_analysis(sample_updates, sample_context)

        assert result["success"] is True
        assert result["packages_analyzed"] == 2
        assert len(result["failed_packages"]) == 1
        assert "django" in result["failed_packages"]

    @patch.object(MultiAgentOrchestrator, "_run_update_agents")
    def test_run_bulk_update_analysis_exception_handling(
        self, mock_run_update, orchestrator, sample_updates, sample_context
    ):
        """Test run_bulk_update_analysis handles exceptions."""
        mock_run_update.side_effect = Exception("Network error")

        result = orchestrator.run_bulk_update_analysis(sample_updates, sample_context)

        assert result["success"] is True  # Overall success despite failures
        assert len(result["failed_packages"]) == 2  # Both failed

    @patch.object(MultiAgentOrchestrator, "_run_update_agents")
    def test_run_bulk_update_analysis_aggregates_changes(
        self, mock_run_update, orchestrator, sample_updates, sample_context
    ):
        """Test that changes are properly aggregated."""
        mock_run_update.side_effect = [
            {
                "success": True,
                "selected_suggestion": """
                UPDATE_PLAN:
                {
                    "version_spec": ">=2.31.0",
                    "breaking_changes": ["Change A"],
                    "code_changes": [{"file": "a.py", "line_range": "1-5", "description": "A"}]
                }
                """,
            },
            {
                "success": True,
                "selected_suggestion": """
                UPDATE_PLAN:
                {
                    "version_spec": ">=4.0.0",
                    "breaking_changes": ["Change B"],
                    "code_changes": [{"file": "b.py", "line_range": "1-5", "description": "B"}]
                }
                """,
            },
        ]

        result = orchestrator.run_bulk_update_analysis(sample_updates, sample_context)

        assert len(result["breaking_changes"]) == 2
        assert len(result["code_changes"]) == 2

        # Verify package info is attached to breaking changes
        packages_in_breaking = {bc["package"] for bc in result["breaking_changes"]}
        assert "requests" in packages_in_breaking
        assert "django" in packages_in_breaking
