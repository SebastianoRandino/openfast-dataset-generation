from __future__ import annotations

"""Machine-local executable and template resolution."""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .campaign.models import ValidationError
from .config import load_yaml


@dataclass(frozen=True)
class MachinePaths:
    turbsim_executable: Path
    turbsim_templates: dict[str, Path]
    output_root: Path = Path("outputs")


def _file(value: Any, description: str, *, executable: bool = False) -> Path:
    if not isinstance(value, (str, Path)) or not str(value):
        raise ValidationError(f"{description} is not configured")
    path = Path(value).expanduser()
    if not path.exists():
        raise ValidationError(f"{description} does not exist: {path}")
    if not path.is_file():
        raise ValidationError(f"{description} is not a file: {path}")
    if executable and not os.access(path, os.X_OK):
        raise ValidationError(f"{description} is not executable: {path}")
    return path.resolve()


def load_machine_paths(config_path: str | Path = "configs/paths.yaml") -> MachinePaths:
    """Load ignored local paths, accepting the former flat executable key."""
    raw = load_yaml(config_path)
    executables = raw.get("executables", {})
    templates = raw.get("templates", {})
    turbsim_value = executables.get("turbsim") if isinstance(executables, dict) else None
    turbsim_value = turbsim_value or raw.get("turbsim_executable")
    template_values = templates.get("turbsim", {}) if isinstance(templates, dict) else {}
    if not isinstance(template_values, dict):
        raise ValidationError("templates.turbsim must be a mapping")
    resolved = {
        str(template_id): _file(path, f"TurbSim template '{template_id}'")
        for template_id, path in template_values.items()
    }
    output = raw.get("outputs", {}).get("root") if isinstance(raw.get("outputs"), dict) else None
    return MachinePaths(
        turbsim_executable=_file(turbsim_value, "TurbSim executable", executable=True),
        turbsim_templates=resolved,
        output_root=Path(output or raw.get("output_directory", "outputs")).expanduser(),
    )


def resolve_turbsim_template(template_id: str, paths: MachinePaths) -> Path:
    try:
        return paths.turbsim_templates[template_id]
    except KeyError:
        raise ValidationError(f"unknown TurbSim template ID: {template_id}") from None


def resolve_turbsim_executable(paths: MachinePaths) -> Path:
    return paths.turbsim_executable
