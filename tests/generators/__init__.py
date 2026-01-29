"""Tests for generators module initialization."""


class TestGeneratorsInit:
    """Test the generators module exports."""

    def test_generate_environment_importable(self):
        """Test that generate_environment is importable."""
        from hatch_agent.generators import generate_environment

        assert generate_environment is not None
        assert callable(generate_environment)

    def test_read_lockfile_importable(self):
        """Test that read_lockfile is importable."""
        from hatch_agent.generators import read_lockfile

        assert read_lockfile is not None
        assert callable(read_lockfile)

    def test_write_lockfile_importable(self):
        """Test that write_lockfile is importable."""
        from hatch_agent.generators import write_lockfile

        assert write_lockfile is not None
        assert callable(write_lockfile)

    def test_all_exports(self):
        """Test that __all__ contains expected exports."""
        from hatch_agent import generators

        assert hasattr(generators, "__all__")
        assert "generate_environment" in generators.__all__
        assert "read_lockfile" in generators.__all__
        assert "write_lockfile" in generators.__all__
