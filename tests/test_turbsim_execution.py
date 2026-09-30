import json
from pathlib import Path

import pytest
from test_wind import FIXTURE, turbulent_case

from openfast_dataset.campaign.models import ValidationError
from openfast_dataset.paths import MachinePaths, load_machine_paths, resolve_turbsim_template
from openfast_dataset.wind.execution import (
    TurbSimExecutionError,
    prepare_turbsim_realization,
    run_turbsim,
)
from openfast_dataset.wind.planner import plan_winds


def _script(path: Path, body: str) -> Path:
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def _paths(tmp_path: Path, script_body: str = 'echo stdout; echo stderr >&2; printf BTS > turbsim.bts\n') -> MachinePaths:
    tmp_path.mkdir(parents=True, exist_ok=True)
    template = tmp_path / "template.inp"
    template.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    return MachinePaths(_script(tmp_path / "fake-turbsim", script_body), {"legacy-iea15mw-turbsim-v2": template})


def _realization():
    return plan_winds([turbulent_case()]).realizations[0]


def test_template_resolution_and_unknown_template(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    assert resolve_turbsim_template("legacy-iea15mw-turbsim-v2", paths).is_file()
    with pytest.raises(ValidationError, match="unknown TurbSim template"):
        resolve_turbsim_template("missing", paths)


def test_machine_paths_reject_missing_template_and_executable(tmp_path: Path) -> None:
    config = tmp_path / "paths.yaml"
    config.write_text("executables:\n  turbsim: /missing\ntemplates:\n  turbsim:\n    x: /missing-template\n")
    with pytest.raises(ValidationError, match="TurbSim template 'x' does not exist"):
        load_machine_paths(config)
    template = tmp_path / "template.inp"
    template.write_text("template")
    config.write_text(f"executables:\n  turbsim: /missing\ntemplates:\n  turbsim:\n    x: {template}\n")
    with pytest.raises(ValidationError, match="TurbSim executable does not exist"):
        load_machine_paths(config)
    executable = _script(tmp_path / "not-executable", "exit 0\n")
    executable.chmod(0o644)
    config.write_text(f"executables:\n  turbsim: {executable}\ntemplates:\n  turbsim: {{}}\n")
    with pytest.raises(ValidationError, match="not executable"):
        load_machine_paths(config)


def test_prepare_is_deterministic_and_paths_do_not_change_identity(tmp_path: Path) -> None:
    realization = _realization()
    first = prepare_turbsim_realization(realization, _paths(tmp_path / "one"), tmp_path / "outputs")
    second = prepare_turbsim_realization(realization, _paths(tmp_path / "two"), tmp_path / "outputs")
    assert first.workspace == second.workspace
    assert first.input_checksum == second.input_checksum
    assert first.realization.scientific_hash == realization.scientific_hash
    assert first.input_path.name == "turbsim.inp"


def test_successful_execution_logs_and_records_provenance(tmp_path: Path) -> None:
    prepared = prepare_turbsim_realization(_realization(), _paths(tmp_path), tmp_path / "outputs")
    result = run_turbsim(prepared)
    metadata = json.loads(prepared.metadata_path.read_text(encoding="utf-8"))
    assert result.status == "succeeded" and not result.reused
    assert prepared.output_path.read_bytes() == b"BTS"
    assert "stdout" in prepared.log_path.read_text() and "stderr" in prepared.log_path.read_text()
    assert metadata["status"] == "succeeded"
    assert metadata["input_checksum_sha256"] == prepared.input_checksum
    assert metadata["bts_checksum_sha256"]


def test_nonzero_and_missing_output_fail_clearly(tmp_path: Path) -> None:
    failed = prepare_turbsim_realization(_realization(), _paths(tmp_path / "failed", "echo bad >&2; exit 7\n"), tmp_path / "outputs")
    with pytest.raises(TurbSimExecutionError, match="return code 7"):
        run_turbsim(failed)
    absent = prepare_turbsim_realization(_realization(), _paths(tmp_path / "absent", "echo no-output\n"), tmp_path / "outputs2")
    with pytest.raises(TurbSimExecutionError, match="did not create wind.bts"):
        run_turbsim(absent)


def test_reuse_inconsistency_and_force_rebuild(tmp_path: Path) -> None:
    prepared = prepare_turbsim_realization(_realization(), _paths(tmp_path), tmp_path / "outputs")
    run_turbsim(prepared)
    assert run_turbsim(prepare_turbsim_realization(_realization(), _paths(tmp_path), tmp_path / "outputs")).reused
    metadata = json.loads(prepared.metadata_path.read_text())
    metadata["input_checksum_sha256"] = "wrong"
    prepared.metadata_path.write_text(json.dumps(metadata))
    with pytest.raises(TurbSimExecutionError, match="inconsistent"):
        run_turbsim(prepared)
    assert run_turbsim(prepared, force=True).status == "succeeded"
