"""Configuration helpers for hatch-agent.

The configuration is read from an XDG-compatible config location:
$XDG_CONFIG_HOME/hatch-agent/config.toml or ~/.config/hatch-agent/config.toml

The configuration is stored in TOML format and describes which provider
and model to use for LLM calls as well as provider-specific credentials.
"""
from typing import Dict, Any
import os

# Prefer stdlib tomllib (py3.11+) then tomli; tomli_w for writing when available
try:
    import tomllib as _toml_loader  # type: ignore
except Exception:
    try:
        import tomli as _toml_loader  # type: ignore
    except Exception:  # pragma: no cover - runtime will surface missing dependency
        _toml_loader = None

try:
    import tomli_w as _toml_writer  # type: ignore
except Exception:
    _toml_writer = None


DEFAULT_CONFIG = {
    "provider": "mock",
    "model": "gpt-sim-1",
    "providers": {
        "mock": {},
        "aws": {"region": "us-east-1", "access_key": "", "secret_key": ""},
        "openai": {"api_key": "", "organization": ""},
    },
}

# Provider-specific configuration templates for the config wizard
PROVIDER_TEMPLATES: Dict[str, Any] = {
    "openai": {
        "underlying_provider": "openai",
        "model": "gpt-4",
        "underlying_config": {
            "api_key": "",
        },
    },
    "anthropic": {
        "underlying_provider": "anthropic",
        "model": "claude-3-sonnet-20240229",
        "underlying_config": {
            "api_key": "",
        },
    },
    "bedrock": {
        "underlying_provider": "bedrock",
        "model": "anthropic.claude-3-sonnet-20240229-v1:0",
        "underlying_config": {
            "aws_access_key_id": "",
            "aws_secret_access_key": "",
            "region": "us-east-1",
        },
    },
    "azure": {
        "underlying_provider": "azure",
        "model": "gpt-4",
        "underlying_config": {
            "api_key": "",
            "api_base": "",
            "deployment": "",
        },
    },
    "google": {
        "underlying_provider": "google",
        "model": "gemini-pro",
        "underlying_config": {
            "project_id": "",
            "location": "us-central1",
        },
    },
    "cohere": {
        "underlying_provider": "cohere",
        "model": "command",
        "underlying_config": {
            "api_key": "",
        },
    },
}


def get_config_dir() -> str:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return os.path.join(xdg, "hatch-agent")
    return os.path.join(os.path.expanduser("~"), ".config", "hatch-agent")


def get_config_path() -> str:
    return os.path.join(get_config_dir(), "config.toml")


def load_config(path: str | None = None) -> Dict[str, Any]:
    path = path or get_config_path()
    try:
        with open(path, "rb") as f:
            if _toml_loader is None:
                raise RuntimeError("tomllib (stdlib) or tomli is required to read TOML config")
            return _toml_loader.load(f)
    except FileNotFoundError:
        return DEFAULT_CONFIG.copy()


def _simple_toml_dumps(obj: Dict[str, Any]) -> str:
    """A tiny TOML serializer sufficient for DEFAULT_CONFIG-like dicts.

    This is intentionally minimal and not a full TOML implementation.
    """
    lines = []

    def emit_section(prefix: str, mapping: Dict[str, Any]):
        for k, v in mapping.items():
            if isinstance(v, dict):
                # nested table
                section = f"[{prefix}.{k}]" if prefix else f"[{k}]"
                lines.append(section)
                for kk, vv in v.items():
                    if isinstance(vv, str):
                        lines.append(f"{kk} = \"{vv}\"")
                    elif isinstance(vv, bool):
                        lines.append(f"{kk} = {str(vv).lower()}")
                    else:
                        lines.append(f"{kk} = {vv}")
                lines.append("")
            else:
                if isinstance(v, str):
                    lines.append(f"{k} = \"{v}\"")
                elif isinstance(v, bool):
                    lines.append(f"{k} = {str(v).lower()}")
                elif isinstance(v, list):
                    items = ", ".join(f'\"{x}\"' for x in v)
                    lines.append(f"{k} = [{items}]")
                else:
                    lines.append(f"{k} = {v}")

    # top-level simple keys
    top = {k: v for k, v in obj.items() if not isinstance(v, dict)}
    emit_section("", top)
    # nested tables
    for k, v in obj.items():
        if isinstance(v, dict):
            lines.append(f"[{k}]")
            for kk, vv in v.items():
                if isinstance(vv, str):
                    lines.append(f"{kk} = \"{vv}\"")
                elif isinstance(vv, bool):
                    lines.append(f"{kk} = {str(vv).lower()}")
                else:
                    lines.append(f"{kk} = {vv}")
            lines.append("")

    return "\n".join(lines)


def write_config(config: Dict[str, Any], path: str | None = None) -> bool:
    path = path or get_config_path()
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    try:
        if _toml_writer is not None:
            with open(path, "wb") as f:
                f.write(_toml_writer.dumps(config).encode("utf-8"))
            return True
        # Fallback to simple serializer
        with open(path, "w", encoding="utf-8") as f:
            f.write(_simple_toml_dumps(config))
        return True
    except Exception:
        return False
