"""Single-case OpenFAST execution; preparation remains separate and pure."""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openfast_dataset.paths import MachinePaths, resolve_openfast_executable
from .preparation import OpenFASTPreparationError, PreparedOpenFASTCase


@dataclass(frozen=True)
class OpenFASTRunResult:
    prepared: PreparedOpenFASTCase
    status: str
    return_code: int | None
    output_path: Path
    log_path: Path
    reused: bool


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _field(path: Path, label: str) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.lstrip().split(maxsplit=2)
        if len(parts) >= 2 and parts[1] == label:
            return parts[0].strip('"')
    raise OpenFASTPreparationError(f"OpenFAST primary file is missing {label}")


def _output_path(prepared: PreparedOpenFASTCase) -> Path:
    fmt = int(_field(prepared.fst_path, "OutFileFmt"))
    if fmt not in {2, 3, 4, 5}:
        raise OpenFASTPreparationError(f"template output format {fmt} has no binary .outb primary artifact")
    return prepared.fst_path.with_suffix(".outb")


def _runtime_path(prepared: PreparedOpenFASTCase) -> Path:
    return prepared.workspace / "openfast_runtime.json"


def _preparation_identity(prepared: PreparedOpenFASTCase) -> str:
    return json.loads(prepared.metadata_path.read_text(encoding="utf-8"))["preparation_identity"]


def _write_runtime(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_openfast(prepared: PreparedOpenFASTCase, paths: MachinePaths, *, force: bool = False) -> OpenFASTRunResult:
    """Run one prepared case in the primary FST directory and validate its .outb."""
    executable = resolve_openfast_executable(paths)
    output, log, runtime = _output_path(prepared), prepared.workspace / "openfast.log", _runtime_path(prepared)
    identity = _preparation_identity(prepared)
    if runtime.is_file() and output.is_file() and output.stat().st_size > 0 and not force:
        prior = json.loads(runtime.read_text(encoding="utf-8"))
        if prior.get("status") == "success" and prior.get("preparation_identity") == identity and prior.get("output_checksum_sha256") == _checksum(output):
            return OpenFASTRunResult(prepared, "reused", prior.get("return_code", 0), output, log, True)
        raise OpenFASTPreparationError("existing OpenFAST output provenance is inconsistent; use force=True")
    if output.exists() and not force:
        raise OpenFASTPreparationError("existing OpenFAST output has no reusable provenance; use force=True")
    if force:
        for path in (output, log):
            if path.exists() or path.is_symlink(): path.unlink()
    _write_runtime(runtime, {"status": "running", "preparation_identity": identity, "openfast_executable": str(executable), "openfast_executable_checksum_sha256": _checksum(executable), "primary_output_filename": output.name, "log_filename": log.name})
    completed = subprocess.run([str(executable), prepared.fst_path.name], cwd=prepared.fst_path.parent, text=True, capture_output=True, check=False)
    log.write_text(f"# command: {executable} {prepared.fst_path.name}\n# return_code: {completed.returncode}\n\n--- stdout ---\n{completed.stdout}\n--- stderr ---\n{completed.stderr}", encoding="utf-8")
    base = {"preparation_identity": identity, "openfast_executable": str(executable), "openfast_executable_checksum_sha256": _checksum(executable), "primary_output_filename": output.name, "log_filename": log.name, "return_code": completed.returncode}
    if completed.returncode != 0:
        _write_runtime(runtime, {**base, "status": "failed"})
        raise OpenFASTPreparationError(f"OpenFAST failed with return code {completed.returncode}; see {log}")
    if not output.is_file() or output.stat().st_size == 0:
        _write_runtime(runtime, {**base, "status": "failed_missing_output"})
        raise OpenFASTPreparationError(f"OpenFAST returned success but did not create non-empty {output.name}")
    _write_runtime(runtime, {**base, "status": "success", "output_checksum_sha256": _checksum(output)})
    return OpenFASTRunResult(prepared, "success", completed.returncode, output, log, False)
