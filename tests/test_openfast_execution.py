from pathlib import Path

import pytest

from openfast_dataset.cases import OpenFASTPreparationError, prepare_openfast_case, run_openfast
from openfast_dataset.paths import MachinePaths, resolve_openfast_executable
from test_openfast_preparation import _case, _paths, _template


def _executable(path: Path, body: str) -> Path:
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def _prepared(tmp_path: Path, body: str):
    template = _template(tmp_path / "template")
    paths = _paths(template, tmp_path / "outputs")
    executable = _executable(tmp_path / "fake-openfast", body)
    paths = MachinePaths(paths.turbsim_executable, paths.turbsim_templates, paths.openfast_templates, paths.output_root, executable)
    return prepare_openfast_case(_case(kind="steady"), paths), paths


def test_executable_resolution_and_success_reuse(tmp_path: Path) -> None:
    prepared, paths = _prepared(tmp_path, 'echo stdout; echo stderr >&2; printf OUT > "${1%.fst}.outb"\n')
    assert resolve_openfast_executable(paths) == paths.openfast_executable.resolve()
    result = run_openfast(prepared, paths)
    assert result.status == "success" and result.output_path.read_bytes() == b"OUT"
    assert "stdout" in result.log_path.read_text() and "stderr" in result.log_path.read_text()
    assert run_openfast(prepared, paths).reused


def test_command_uses_primary_fst_and_its_directory(tmp_path: Path) -> None:
    prepared, paths = _prepared(tmp_path, 'pwd > cwd.txt; test "$1" = model.fst; printf OUT > "${1%.fst}.outb"\n')
    result = run_openfast(prepared, paths)
    assert (prepared.fst_path.parent / "cwd.txt").read_text().strip() == str(prepared.fst_path.parent.resolve())
    assert "model.fst" in result.log_path.read_text()


@pytest.mark.parametrize("body, message", [("exit 7\n", "return code 7"), ("exit 0\n", "did not create"), ('printf "" > "${1%.fst}.outb"\n', "did not create")])
def test_execution_failures(tmp_path: Path, body: str, message: str) -> None:
    prepared, paths = _prepared(tmp_path, body)
    with pytest.raises(OpenFASTPreparationError, match=message): run_openfast(prepared, paths)


def test_inconsistent_output_requires_force(tmp_path: Path) -> None:
    prepared, paths = _prepared(tmp_path, 'printf ONE > "${1%.fst}.outb"\n')
    result = run_openfast(prepared, paths)
    result.output_path.write_bytes(b"changed")
    with pytest.raises(OpenFASTPreparationError, match="inconsistent"): run_openfast(prepared, paths)
    assert run_openfast(prepared, paths, force=True).status == "success"


def test_missing_executable_fails(tmp_path: Path) -> None:
    prepared, paths = _prepared(tmp_path, 'printf OUT > "${1%.fst}.outb"\n')
    with pytest.raises(Exception, match="OpenFAST executable"):
        run_openfast(prepared, MachinePaths(paths.turbsim_executable, paths.turbsim_templates, paths.openfast_templates, paths.output_root))


def test_non_executable_file_is_rejected(tmp_path: Path) -> None:
    prepared, paths = _prepared(tmp_path, 'printf OUT > "${1%.fst}.outb"\n')
    blocked = tmp_path / "blocked-openfast"; blocked.write_text("not executable", encoding="utf-8"); blocked.chmod(0o644)
    with pytest.raises(Exception, match="not executable"):
        run_openfast(prepared, MachinePaths(paths.turbsim_executable, paths.turbsim_templates, paths.openfast_templates, paths.output_root, blocked))
