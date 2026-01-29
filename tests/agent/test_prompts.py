"""Tests for agent prompts."""

import pytest

from hatch_agent.agent.prompts import default_prompt, system_prompt_factory


class TestDefaultPrompt:
    """Test default_prompt function."""

    def test_default_prompt_includes_task(self):
        """Test that default_prompt includes the task description."""
        task = "Analyze the pyproject.toml file"
        result = default_prompt(task)
        assert task in result

    def test_default_prompt_has_structure(self):
        """Test that default_prompt has expected structure."""
        task = "Run tests"
        result = default_prompt(task)
        assert "automated assistant" in result.lower()
        assert "task" in result.lower()
        assert "clarifying" in result.lower()

    def test_default_prompt_with_empty_task(self):
        """Test default_prompt with empty task description."""
        result = default_prompt("")
        assert isinstance(result, str)
        assert "automated assistant" in result.lower()

    def test_default_prompt_with_multiline_task(self):
        """Test default_prompt with multiline task."""
        task = "Step 1: Read the file\nStep 2: Analyze it\nStep 3: Report"
        result = default_prompt(task)
        assert "Step 1" in result
        assert "Step 3" in result


class TestSystemPromptFactory:
    """Test system_prompt_factory function."""

    def test_returns_callable(self):
        """Test that system_prompt_factory returns a callable."""
        factory = system_prompt_factory("Assistant")
        assert callable(factory)

    def test_factory_output_includes_role(self):
        """Test that the factory output includes the role name."""
        role = "HatchExpert"
        factory = system_prompt_factory(role)
        result = factory("Do the task")
        assert role in result

    def test_factory_output_includes_body(self):
        """Test that the factory output includes the body text."""
        body = "Analyze dependencies and suggest updates"
        factory = system_prompt_factory("Analyst")
        result = factory(body)
        assert body in result

    def test_factory_with_different_roles(self):
        """Test that different roles produce different prompts."""
        factory1 = system_prompt_factory("ConfigExpert")
        factory2 = system_prompt_factory("BuildExpert")
        
        body = "Same task"
        result1 = factory1(body)
        result2 = factory2(body)
        
        assert result1 != result2
        assert "ConfigExpert" in result1
        assert "BuildExpert" in result2

    def test_factory_preserves_formatting(self):
        """Test that factory preserves body formatting."""
        body = "Line 1\nLine 2\n\nLine 4"
        factory = system_prompt_factory("Test")
        result = factory(body)
        assert "Line 1" in result
        assert "Line 4" in result

