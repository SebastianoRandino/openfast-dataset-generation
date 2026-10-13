"""Verify distributed inputs and case preparation without executing real solvers."""

import hashlib
import json
from pathlib import Path

import pytest

from openfast_dataset.campaign.resolver import resolve_campaign
from openfast_dataset.cases import prepare_openfast_case
from openfast_dataset.cases.preparation import _field_value
from openfast_dataset.config import load_campaign
from openfast_dataset.paths import load_machine_paths

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "relative",
    [
        "vendor/manifest.json",
        "templates/iea15mw-v5/template_provenance.json",
        "templates/iea15mw-volturnus-v4/template_provenance.json",
    ],
)
def test_distributed_dependencies_match_manifest(relative):
    manifest = ROOT / relative
    base = ROOT if relative.startswith("vendor/") else manifest.parent
    for name, expected in json.loads(manifest.read_text())["files_sha256"].items():
        path = base / name
        assert path.is_file(), name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name


@pytest.mark.parametrize(
    "kind,hydro,sub,mooring",
    [
        ("fixed", "1", "1", "0"),
        ("floating", "1", "0", "3"),
        ("floating_v4", "1", "0", "3"),
    ],
)
def test_bundled_cases_prepare_with_local_active_dependencies(
    kind, hydro, sub, mooring, tmp_path, monkeypatch
):
    monkeypatch.chdir(ROOT)
    paths = load_machine_paths("configs/paths.bundled.yaml")
    for dependency in [
        paths.turbsim_executable,
        *paths.turbsim_templates.values(),
        *paths.openfast_templates.values(),
        *paths.openfast_executables.values(),
    ]:
        assert dependency.resolve().is_relative_to(ROOT)
    case = resolve_campaign(load_campaign(f"configs/campaigns/bundled_{kind}_smoke.yaml"))[0]
    prepared = prepare_openfast_case(case, paths, output_root=tmp_path)
    fst = prepared.fst_path
    assert _field_value(fst, "CompHydro") == hydro
    assert _field_value(fst, "CompSub") == sub
    assert _field_value(fst, "CompMooring") == mooring
    fields = ["EDFile", "InflowFile", "AeroFile", "ServoFile", "SeaStFile", "HydroFile"]
    if sub == "1":
        fields.append("SubFile")
    if mooring == "3":
        fields.append("MooringFile")
    for field in fields:
        dependency = (fst.parent / _field_value(fst, field)).resolve()
        assert dependency.is_file(), field
        assert dependency.is_relative_to(prepared.workspace.resolve()), field
    servo = fst.parent / _field_value(fst, "ServoFile")
    library = (servo.parent / _field_value(servo, "DLL_FileName")).resolve()
    assert library.is_file()
    assert library.is_relative_to(prepared.workspace.resolve())
