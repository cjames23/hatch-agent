"""Tests for commands module initialization."""


class TestCommandsInit:
    """Test the commands module."""

    def test_commands_module_importable(self):
        """Test that commands module can be imported."""
        import hatch_agent.commands

        assert hatch_agent.commands is not None
