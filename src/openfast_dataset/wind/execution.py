"""Explicit preparation and execution of one TurbSim wind realization."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openfast_dataset.campaign.models import ValidationError
from openfast_dataset.paths import (
    MachinePaths,
    resolve_turbsim_executable,
    resolve_turbsim_template,
)

from .models import WindRealization
from .turbsim import render_turbsim_input


class TurbSimExecutionError(RuntimeError):
    """TurbSim could not produce the expected reusable BTS artifact."""


@dataclass(frozen=True)
class PreparedTurbSimRun:
    realization: WindRealization
    workspace: Path
    input_path: Path
    log_path: Path
    metadata_path: Path
    output_path: Path
    executable: Path
    template_path: Path
    input_checksum: str
    template_checksum: str


@dataclass(frozen=True)
class TurbSimRunResult:
    prepared: PreparedTurbSimRun
    status: str
    return_code: int | None
    reused: bool


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _metadata(prepared: PreparedTurbSimRun, **extra: Any) -> dict[str, Any]:
    return {
        "wind_realization_id": prepared.realization.wind_id,
        "scientific_hash": prepared.realization.scientific_hash,
        "wind_scientific_parameters": prepared.realization.content,
        "template_id": prepared.realization.content["template_id"],
        "template_checksum_sha256": prepared.template_checksum,
        "turbsim_executable": str(prepared.executable),
        "input_filename": prepared.input_path.name,
        "input_checksum_sha256": prepared.input_checksum,
        "output_bts_filename": prepared.output_path.name,
        **extra,
    }


def _write_metadata(prepared: PreparedTurbSimRun, **extra: Any) -> None:
    prepared.metadata_path.write_text(
        json.dumps(_metadata(prepared, **extra), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def prepare_turbsim_realization(
    realization: WindRealization, paths_config: MachinePaths, output_root: str | Path | None = None,
    *, force: bool = False,
) -> PreparedTurbSimRun:
    """Render deterministic input and initial provenance; never execute TurbSim."""
    if realization.kind != "turbulent":
        raise ValidationError("only turbulent wind realizations can be prepared for TurbSim")
    template = resolve_turbsim_template(realization.content["template_id"], paths_config)
    executable = resolve_turbsim_executable(paths_config)
    root = Path(output_root) if output_root is not None else paths_config.output_root
    workspace = root / "wind" / realization.wind_id
    workspace.mkdir(parents=True, exist_ok=True)
    input_path = workspace / "turbsim.inp"
    rendered = render_turbsim_input(realization, template.read_text(encoding="utf-8"))
    if input_path.exists() and input_path.read_text(encoding="utf-8") != rendered:
        output = workspace / "wind.bts"
        if output.exists() and output.stat().st_size > 0 and not force:
            raise TurbSimExecutionError("existing BTS has inconsistent rendered TurbSim input; use force=True")
    input_path.write_text(rendered, encoding="utf-8")
    prepared = PreparedTurbSimRun(
        realization, workspace, input_path, workspace / "turbsim.log", workspace / "metadata.json",
        workspace / "wind.bts", executable, template, _checksum(input_path), _checksum(template),
    )
    if not _valid_bts(prepared.output_path):
        _write_metadata(prepared, status="prepared", return_code=None, execution_timestamp=None)
    return prepared


def _valid_bts(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def run_turbsim(prepared: PreparedTurbSimRun, *, force: bool = False) -> TurbSimRunResult:
    """Run TurbSim and normalize its lowercase input RootName output to wind.bts."""
    existing: dict[str, Any] = {}
    if prepared.metadata_path.exists():
        existing = json.loads(prepared.metadata_path.read_text(encoding="utf-8"))
    if _valid_bts(prepared.output_path):
        if existing.get("input_checksum_sha256") == prepared.input_checksum and not force:
            _write_metadata(prepared, status="reused", return_code=existing.get("return_code", 0),
                            execution_timestamp=existing.get("execution_timestamp"),
                            bts_checksum_sha256=_checksum(prepared.output_path))
            return TurbSimRunResult(prepared, "reused", existing.get("return_code", 0), True)
        if not force:
            raise TurbSimExecutionError("existing BTS provenance is inconsistent; use force=True to rebuild")
        prepared.output_path.unlink()
    started = datetime.now(timezone.utc).isoformat()
    completed = subprocess.run(
        [str(prepared.executable), prepared.input_path.name], cwd=prepared.workspace,
        text=True, capture_output=True, check=False,
    )
    prepared.log_path.write_text(
        f"# command: {prepared.executable} {prepared.input_path.name}\n"
        f"# started: {started}\n# return_code: {completed.returncode}\n\n"
        f"--- stdout ---\n{completed.stdout}\n--- stderr ---\n{completed.stderr}", encoding="utf-8"
    )
    finished = datetime.now(timezone.utc).isoformat()
    if completed.returncode != 0:
        _write_metadata(prepared, status="failed", return_code=completed.returncode,
                        execution_timestamp=started, execution_finished_timestamp=finished)
        raise TurbSimExecutionError(f"TurbSim failed with return code {completed.returncode}; see {prepared.log_path}")
    native_output = prepared.workspace / f"{prepared.input_path.stem}.bts"
    if native_output != prepared.output_path and _valid_bts(native_output):
        shutil.move(str(native_output), str(prepared.output_path))
    if not _valid_bts(prepared.output_path):
        _write_metadata(prepared, status="failed_missing_bts", return_code=completed.returncode,
                        execution_timestamp=started, execution_finished_timestamp=finished)
        raise TurbSimExecutionError(f"TurbSim returned success but did not create {prepared.output_path.name}")
    _write_metadata(prepared, status="succeeded", return_code=completed.returncode,
                    execution_timestamp=started, execution_finished_timestamp=finished,
                    bts_checksum_sha256=_checksum(prepared.output_path))
    return TurbSimRunResult(prepared, "succeeded", completed.returncode, False)
