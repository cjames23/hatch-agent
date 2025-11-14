"""Commands to manage hatch-agent configuration."""
from typing import Optional
from ..config import get_config_path, DEFAULT_CONFIG, write_config


def generate_config(path: Optional[str] = None) -> None:
    """Generate a default config file and print where it was written."""
    p = path or get_config_path()
    success = write_config(DEFAULT_CONFIG.copy(), p)
    if success:
        print(f"Generated config at: {p}")
    else:
        print(f"Failed to write config at: {p}")

