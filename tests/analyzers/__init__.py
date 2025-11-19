"""Tests for analyzers module initialization."""

import pytest


class TestAnalyzersInit:
    """Test the analyzers module."""

    def test_analyzers_module_importable(self):
        """Test that analyzers module can be imported."""
        import hatch_agent.analyzers
        assert hatch_agent.analyzers is not None

