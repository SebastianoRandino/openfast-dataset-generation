from __future__ import annotations

"""Machine-local executable and template resolution."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .campaign.models import ValidationError
from .config import load_yaml


@dataclass(frozen=True)
class MachinePaths:
    turbsim_executable: Path
    turbsim_templates: dict[str, Path]
    openfast_templates: dict[str, Path] = field(default_factory=dict)
    output_root: Path = Path("outputs")
    openfast_executable: Path | None = None
    openfast_executables: dict[str, Path] = field(default_factory=dict)


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


def _directory(value: Any, description: str) -> Path:
    if not isinstance(value, (str, Path)) or not str(value):
        raise ValidationError(f"{description} is not configured")
    path = Path(value).expanduser()
    if not path.exists():
        raise ValidationError(f"{description} does not exist: {path}")
    if not path.is_dir():
        raise ValidationError(f"{description} is not a directory: {path}")
    return path.resolve()


def load_machine_paths(config_path: str | Path = "configs/paths.yaml") -> MachinePaths:
    """Load ignored local paths, accepting the former flat executable key."""
    raw = load_yaml(config_path)
    executables = raw.get("executables", {})
    templates = raw.get("templates", {})
    turbsim_value = executables.get("turbsim") if isinstance(executables, dict) else None
    openfast_value = executables.get("openfast") if isinstance(executables, dict) else None
    versioned = openfast_value if isinstance(openfast_value, dict) else {}
    if isinstance(openfast_value, dict):
        openfast_value = None
    turbsim_value = turbsim_value or raw.get("turbsim_executable")
    template_values = templates.get("turbsim", {}) if isinstance(templates, dict) else {}
    openfast_values = templates.get("openfast", {}) if isinstance(templates, dict) else {}
    if not isinstance(template_values, dict):
        raise ValidationError("templates.turbsim must be a mapping")
    if not isinstance(openfast_values, dict):
        raise ValidationError("templates.openfast must be a mapping")
    resolved = {
        str(template_id): _file(path, f"TurbSim template '{template_id}'")
        for template_id, path in template_values.items()
    }
    output = raw.get("outputs", {}).get("root") if isinstance(raw.get("outputs"), dict) else None
    return MachinePaths(
        turbsim_executable=_file(turbsim_value, "TurbSim executable", executable=True),
        turbsim_templates=resolved,
        openfast_templates={str(template_id): _directory(path, f"OpenFAST template '{template_id}'") for template_id, path in openfast_values.items()},
        output_root=Path(output or raw.get("output_directory", "outputs")).expanduser(),
        openfast_executable=_file(openfast_value, "OpenFAST executable", executable=True) if openfast_value else None,
        openfast_executables={str(version): _file(path, f"OpenFAST {version} executable", executable=True) for version, path in versioned.items()},
    )


def resolve_turbsim_template(template_id: str, paths: MachinePaths) -> Path:
    try:
        return paths.turbsim_templates[template_id]
    except KeyError:
        raise ValidationError(f"unknown TurbSim template ID: {template_id}") from None


def resolve_turbsim_executable(paths: MachinePaths) -> Path:
    return paths.turbsim_executable


def resolve_openfast_template(template_id: str, paths: MachinePaths) -> Path:
    try:
        return paths.openfast_templates[template_id]
    except KeyError:
        raise ValidationError(f"unknown OpenFAST template ID: {template_id}") from None


def resolve_openfast_executable(paths: MachinePaths, version: str | None = None) -> Path:
    if version is not None and paths.openfast_executables:
        if version not in paths.openfast_executables:
            raise ValidationError(f"OpenFAST {version} executable is not configured")
        return _file(paths.openfast_executables[version], f"OpenFAST {version} executable", executable=True)
    if paths.openfast_executable is None:
        raise ValidationError("OpenFAST executable is not configured")
    return _file(paths.openfast_executable, "OpenFAST executable", executable=True)
