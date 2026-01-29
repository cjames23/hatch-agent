"""Tests for configuration system."""

from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import os

import pytest

from hatch_agent.config import (
    get_config_dir,
    get_config_path,
    load_config,
    write_config,
    _simple_toml_dumps,
    DEFAULT_CONFIG,
    PROVIDER_TEMPLATES,
)


class TestGetConfigDir:
    """Test get_config_dir function."""

    def test_with_xdg_config_home(self, monkeypatch):
        """Test get_config_dir when XDG_CONFIG_HOME is set."""
        monkeypatch.setenv("XDG_CONFIG_HOME", "/custom/config")
        result = get_config_dir()
        assert result == "/custom/config/hatch-agent"

    def test_without_xdg_config_home(self, monkeypatch):
        """Test get_config_dir when XDG_CONFIG_HOME is not set."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        result = get_config_dir()
        assert ".config/hatch-agent" in result
        assert os.path.expanduser("~") in result


class TestGetConfigPath:
    """Test get_config_path function."""

    def test_returns_toml_path(self, monkeypatch):
        """Test that get_config_path returns path ending in config.toml."""
        monkeypatch.setenv("XDG_CONFIG_HOME", "/test/config")
        result = get_config_path()
        assert result.endswith("config.toml")
        assert "hatch-agent" in result


class TestLoadConfig:
    """Test load_config function."""

    def test_load_config_success(self, temp_project_dir):
        """Test loading a valid TOML config file."""
        config_file = temp_project_dir / "config.toml"
        config_file.write_text("""
provider = "openai"
model = "gpt-4"

[providers]
[providers.openai]
api_key = "test-key"
""")
        result = load_config(str(config_file))
        assert result["provider"] == "openai"
        assert result["model"] == "gpt-4"

    def test_load_config_file_not_found(self, temp_project_dir):
        """Test load_config returns DEFAULT_CONFIG when file not found."""
        result = load_config(str(temp_project_dir / "nonexistent.toml"))
        assert result == DEFAULT_CONFIG

    def test_load_config_default_path(self, monkeypatch, temp_project_dir):
        """Test load_config uses default path when none provided."""
        config_dir = temp_project_dir / "config"
        config_dir.mkdir()
        config_file = config_dir / "hatch-agent" / "config.toml"
        config_file.parent.mkdir(parents=True)
        config_file.write_text('provider = "test"')
        
        monkeypatch.setenv("XDG_CONFIG_HOME", str(config_dir))
        result = load_config()
        assert result["provider"] == "test"


class TestWriteConfig:
    """Test write_config function."""

    def test_write_config_success(self, temp_project_dir):
        """Test writing config to file."""
        config_file = temp_project_dir / "subdir" / "config.toml"
        config = {"provider": "openai", "model": "gpt-4"}
        
        result = write_config(config, str(config_file))
        
        assert result is True
        assert config_file.exists()

    def test_write_config_creates_directory(self, temp_project_dir):
        """Test that write_config creates parent directories."""
        deep_path = temp_project_dir / "a" / "b" / "c" / "config.toml"
        config = {"test": "value"}
        
        result = write_config(config, str(deep_path))
        
        assert result is True
        assert deep_path.exists()

    def test_write_config_failure(self, temp_project_dir):
        """Test write_config returns False on failure."""
        # Try to write to a path that will fail (directory instead of file)
        with patch("builtins.open", side_effect=PermissionError("No permission")):
            with patch("os.makedirs"):  # Don't fail on makedirs
                result = write_config({}, str(temp_project_dir / "test.toml"))
        
        assert result is False


class TestSimpleTomlDumps:
    """Test _simple_toml_dumps function."""

    def test_string_values(self):
        """Test serializing string values."""
        config = {"name": "test-project"}
        result = _simple_toml_dumps(config)
        assert 'name = "test-project"' in result

    def test_boolean_values(self):
        """Test serializing boolean values."""
        config = {"enabled": True, "disabled": False}
        result = _simple_toml_dumps(config)
        assert "enabled = true" in result
        assert "disabled = false" in result

    def test_integer_values(self):
        """Test serializing integer values."""
        config = {"count": 42}
        result = _simple_toml_dumps(config)
        assert "count = 42" in result

    def test_list_values(self):
        """Test serializing list values."""
        config = {"items": ["a", "b", "c"]}
        result = _simple_toml_dumps(config)
        assert "items = [" in result
        assert '"a"' in result

    def test_nested_dict(self):
        """Test serializing nested dictionaries."""
        config = {
            "top": "value",
            "nested": {
                "key1": "val1",
                "key2": "val2"
            }
        }
        result = _simple_toml_dumps(config)
        assert "[nested]" in result
        assert 'key1 = "val1"' in result

    def test_deeply_nested_dict(self):
        """Test serializing deeply nested structure."""
        config = {
            "providers": {
                "openai": {
                    "api_key": "secret"
                }
            }
        }
        result = _simple_toml_dumps(config)
        assert "[providers]" in result


class TestDefaultConfig:
    """Test DEFAULT_CONFIG constant."""

    def test_default_config_has_provider(self):
        """Test DEFAULT_CONFIG has provider key."""
        assert "provider" in DEFAULT_CONFIG

    def test_default_config_has_model(self):
        """Test DEFAULT_CONFIG has model key."""
        assert "model" in DEFAULT_CONFIG

    def test_default_config_has_providers(self):
        """Test DEFAULT_CONFIG has providers dict."""
        assert "providers" in DEFAULT_CONFIG
        assert isinstance(DEFAULT_CONFIG["providers"], dict)


class TestProviderTemplates:
    """Test PROVIDER_TEMPLATES constant."""

    def test_has_openai_template(self):
        """Test PROVIDER_TEMPLATES has openai."""
        assert "openai" in PROVIDER_TEMPLATES
        assert "underlying_provider" in PROVIDER_TEMPLATES["openai"]

    def test_has_anthropic_template(self):
        """Test PROVIDER_TEMPLATES has anthropic."""
        assert "anthropic" in PROVIDER_TEMPLATES

    def test_has_bedrock_template(self):
        """Test PROVIDER_TEMPLATES has bedrock."""
        assert "bedrock" in PROVIDER_TEMPLATES

    def test_has_azure_template(self):
        """Test PROVIDER_TEMPLATES has azure."""
        assert "azure" in PROVIDER_TEMPLATES

    def test_has_google_template(self):
        """Test PROVIDER_TEMPLATES has google."""
        assert "google" in PROVIDER_TEMPLATES

    def test_has_cohere_template(self):
        """Test PROVIDER_TEMPLATES has cohere."""
        assert "cohere" in PROVIDER_TEMPLATES

    def test_all_templates_have_model(self):
        """Test all templates have model key."""
        for provider, template in PROVIDER_TEMPLATES.items():
            assert "model" in template, f"{provider} missing model"

    def test_all_templates_have_underlying_config(self):
        """Test all templates have underlying_config."""
        for provider, template in PROVIDER_TEMPLATES.items():
            assert "underlying_config" in template, f"{provider} missing underlying_config"


class TestSimpleTomlDumpsExtended:
    """Extended tests for _simple_toml_dumps edge cases."""

    def test_nested_dict_with_boolean(self):
        """Test nested dict with boolean values."""
        config = {
            "section": {
                "enabled": True,
                "disabled": False
            }
        }
        result = _simple_toml_dumps(config)
        assert "[section]" in result
        assert "enabled = true" in result
        assert "disabled = false" in result

    def test_nested_dict_with_integer(self):
        """Test nested dict with integer values."""
        config = {
            "settings": {
                "timeout": 30,
                "retries": 3
            }
        }
        result = _simple_toml_dumps(config)
        assert "[settings]" in result
        assert "timeout = 30" in result
        assert "retries = 3" in result

    def test_empty_dict(self):
        """Test serializing empty dict."""
        config = {}
        result = _simple_toml_dumps(config)
        assert result == ""

    def test_mixed_top_level(self):
        """Test mixed top-level values."""
        config = {
            "name": "project",
            "count": 5,
            "enabled": True,
            "tags": ["a", "b"]
        }
        result = _simple_toml_dumps(config)
        assert 'name = "project"' in result
        assert "count = 5" in result
        assert "enabled = true" in result
        assert "tags = [" in result


class TestWriteConfigFallback:
    """Test write_config fallback path."""

    def test_write_config_with_fallback(self, temp_project_dir):
        """Test write_config uses fallback when tomli_w not available."""
        import hatch_agent.config as config_module
        
        # Temporarily set the writer to None to trigger fallback
        original_writer = config_module._toml_writer
        config_module._toml_writer = None
        
        try:
            config_file = temp_project_dir / "fallback.toml"
            config = {"provider": "test", "model": "gpt-4"}
            
            result = write_config(config, str(config_file))
            
            assert result is True
            assert config_file.exists()
            content = config_file.read_text()
            assert 'provider = "test"' in content
        finally:
            config_module._toml_writer = original_writer

