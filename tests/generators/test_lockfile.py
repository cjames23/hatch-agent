"""Tests for lockfile operations."""

import json
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest


class TestReadLockfile:
    """Test cases for read_lockfile function."""

    def test_read_lockfile_success(self, temp_project_dir, sample_lockfile_content):
        """Test reading a valid lockfile."""
        from hatch_agent.generators.lockfile import read_lockfile

        lockfile_path = temp_project_dir / "hatch.lock"
        lockfile_path.write_text(json.dumps(sample_lockfile_content))

        result = read_lockfile(str(lockfile_path))
        assert result == sample_lockfile_content
        assert "packages" in result
        assert "requests" in result["packages"]

    def test_read_lockfile_nonexistent_file(self, temp_project_dir):
        """Test reading a non-existent lockfile returns empty dict."""
        from hatch_agent.generators.lockfile import read_lockfile

        result = read_lockfile(str(temp_project_dir / "nonexistent.lock"))
        assert result == {}

    def test_read_lockfile_invalid_json(self, temp_project_dir):
        """Test reading an invalid JSON lockfile."""
        from hatch_agent.generators.lockfile import read_lockfile

        lockfile_path = temp_project_dir / "invalid.lock"
        lockfile_path.write_text("not valid json{")

        with pytest.raises(json.JSONDecodeError):
            read_lockfile(str(lockfile_path))

    def test_read_lockfile_empty_file(self, temp_project_dir):
        """Test reading an empty lockfile."""
        from hatch_agent.generators.lockfile import read_lockfile

        lockfile_path = temp_project_dir / "empty.lock"
        lockfile_path.write_text("")

        with pytest.raises(json.JSONDecodeError):
            read_lockfile(str(lockfile_path))

    def test_read_lockfile_with_path_object(self, temp_project_dir, sample_lockfile_content):
        """Test reading lockfile with Path object."""
        from hatch_agent.generators.lockfile import read_lockfile

        lockfile_path = temp_project_dir / "hatch.lock"
        lockfile_path.write_text(json.dumps(sample_lockfile_content))

        # Function expects string, so convert Path to string
        result = read_lockfile(str(lockfile_path))
        assert result == sample_lockfile_content


class TestWriteLockfile:
    """Test cases for write_lockfile function."""

    def test_write_lockfile_success(self, temp_project_dir, sample_lockfile_content):
        """Test writing a valid lockfile."""
        from hatch_agent.generators.lockfile import write_lockfile

        lockfile_path = temp_project_dir / "hatch.lock"
        result = write_lockfile(str(lockfile_path), sample_lockfile_content)

        assert result is True
        assert lockfile_path.exists()
        written_content = json.loads(lockfile_path.read_text())
        assert written_content == sample_lockfile_content

    def test_write_lockfile_parent_dirs_must_exist(self, temp_project_dir, sample_lockfile_content):
        """Test that write_lockfile requires parent directories to exist."""
        from hatch_agent.generators.lockfile import write_lockfile

        lockfile_path = temp_project_dir / "subdir" / "nested" / "hatch.lock"
        # Create parent directories first
        lockfile_path.parent.mkdir(parents=True)

        result = write_lockfile(str(lockfile_path), sample_lockfile_content)
        assert result is True
        assert lockfile_path.exists()

    def test_write_lockfile_overwrites_existing(self, temp_project_dir):
        """Test that write_lockfile overwrites existing file."""
        from hatch_agent.generators.lockfile import write_lockfile

        lockfile_path = temp_project_dir / "hatch.lock"
        old_content = {"version": "0.1"}
        new_content = {"version": "1.0", "packages": {}}

        lockfile_path.write_text(json.dumps(old_content))
        write_lockfile(str(lockfile_path), new_content)

        written_content = json.loads(lockfile_path.read_text())
        assert written_content == new_content
        assert written_content != old_content

    def test_write_lockfile_with_path_object(self, temp_project_dir, sample_lockfile_content):
        """Test writing lockfile with Path object converted to string."""
        from hatch_agent.generators.lockfile import write_lockfile

        lockfile_path = temp_project_dir / "hatch.lock"
        write_lockfile(str(lockfile_path), sample_lockfile_content)

        assert lockfile_path.exists()

    def test_write_lockfile_formatted_json(self, temp_project_dir, sample_lockfile_content):
        """Test that written JSON is properly formatted."""
        from hatch_agent.generators.lockfile import write_lockfile

        lockfile_path = temp_project_dir / "hatch.lock"
        write_lockfile(str(lockfile_path), sample_lockfile_content)

        content = lockfile_path.read_text()
        # Check that JSON is formatted (has newlines and indentation)
        assert "\n" in content
        # Should be valid JSON
        parsed = json.loads(content)
        assert parsed == sample_lockfile_content

    def test_write_lockfile_empty_dict(self, temp_project_dir):
        """Test writing an empty lockfile."""
        from hatch_agent.generators.lockfile import write_lockfile

        lockfile_path = temp_project_dir / "empty.lock"
        write_lockfile(str(lockfile_path), {})

        assert lockfile_path.exists()
        content = json.loads(lockfile_path.read_text())
        assert content == {}

    def test_write_lockfile_invalid_path(self):
        """Test writing to invalid path returns False."""
        from hatch_agent.generators.lockfile import write_lockfile

        result = write_lockfile("/invalid/path/that/does/not/exist/lock.json", {})
        assert result is False


class TestLockfileRoundTrip:
    """Test reading and writing lockfiles together."""

    def test_lockfile_round_trip(self, temp_project_dir, sample_lockfile_content):
        """Test that read/write preserves data."""
        from hatch_agent.generators.lockfile import read_lockfile, write_lockfile

        lockfile_path = temp_project_dir / "hatch.lock"

        # Write then read
        write_lockfile(str(lockfile_path), sample_lockfile_content)
        result = read_lockfile(str(lockfile_path))

        assert result == sample_lockfile_content

    def test_lockfile_modification(self, temp_project_dir, sample_lockfile_content):
        """Test modifying and re-writing a lockfile."""
        from hatch_agent.generators.lockfile import read_lockfile, write_lockfile

        lockfile_path = temp_project_dir / "hatch.lock"

        # Initial write
        write_lockfile(str(lockfile_path), sample_lockfile_content)

        # Read and modify
        content = read_lockfile(str(lockfile_path))
        content["packages"]["new-package"] = {
            "version": "1.0.0",
            "hashes": ["sha256:new123"],
            "dependencies": [],
        }

        # Write modified content
        write_lockfile(str(lockfile_path), content)

        # Read again and verify
        final_content = read_lockfile(str(lockfile_path))
        assert "new-package" in final_content["packages"]
        assert len(final_content["packages"]) == len(sample_lockfile_content["packages"]) + 1
