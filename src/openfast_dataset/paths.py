from __future__ import annotations

from pathlib import Path

from .config import load_yaml


def load_machine_paths(config_path: str | Path = "configs/paths.yaml") -> dict[str, Path]:
    """Load machine-specific paths without embedding them in source code."""
    raw = load_yaml(config_path)
    return {key: Path(value).expanduser() for key, value in raw.items()}
