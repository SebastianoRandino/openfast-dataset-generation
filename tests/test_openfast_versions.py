import json
from dataclasses import replace
from pathlib import Path

import pytest
from test_openfast_execution import _executable
from test_openfast_preparation import _case, _paths, _template

from openfast_dataset.campaign.models import ValidationError, required_openfast_version
from openfast_dataset.campaign.resolver import resolve_campaign
from openfast_dataset.cases import OpenFASTPreparationError, prepare_openfast_case, run_openfast
from openfast_dataset.cases.preparation import _tree_checksum
from openfast_dataset.config import load_campaign
from openfast_dataset.paths import load_machine_paths, resolve_openfast_executable


def test_model_selection():
    campaign = load_campaign("configs/campaigns/integration_v5_short.yaml")
    configuration = resolve_campaign(campaign)[0].scientific["model_configuration"]
    assert configuration["openfast_template_id"] == "IEA15MW_VolturnUS_v5.0.0"
    assert required_openfast_version(configuration) == "5.0.0"
    import yaml
    model = yaml.safe_load(Path("configs/models/iea15mw_volturnus_v4.1.1.yaml").read_text())
    campaign = replace(campaign, model=model["identifier"], openfast_version=model["openfast_version"],
                       openfast_template_id=model["openfast_template_id"])
    assert required_openfast_version(resolve_campaign(campaign)[0].scientific["model_configuration"]) == "4.1.1"


def test_local_version_mapping_and_legacy_scalar(tmp_path):
    executable = _executable(tmp_path / "openfast", "exit 0\n")
    config = tmp_path / "paths.yaml"
    config.write_text(f'executables:\n  turbsim: {executable}\n  openfast:\n    4.1.1: {executable}\n    5.0.0: {executable}\n')
    paths = load_machine_paths(config)
    assert resolve_openfast_executable(paths, "5.0.0") == executable
    with pytest.raises(ValidationError, match="not configured"):
        resolve_openfast_executable(paths, "4.2.0")
    config.write_text(f'executables:\n  turbsim: {executable}\n  openfast: {executable}\n')
    assert resolve_openfast_executable(load_machine_paths(config), "4.1.1") == executable


@pytest.mark.parametrize("expected,detected", [("4.1.1", "5.0.0"), ("5.0.0", "4.1.1")])
def test_mismatch_rejected_before_simulation_or_force(tmp_path, expected, detected):
    template = _template(tmp_path / "template")
    if expected == "5.0.0":
        with (template / "main/model.fst").open("a") as stream:
            stream.write("1 ModCoupling\n")
    case = _case(kind="steady")
    case.scientific["model_configuration"]["openfast_version"] = expected
    executable = _executable(tmp_path / "openfast", f'if [ "$1" = "-v" ]; then echo OpenFAST-v{detected}; exit 0; fi\ntouch SIMULATION_LAUNCHED\n')
    paths = replace(_paths(template, tmp_path / "outputs"), openfast_executables={expected: executable})
    prepared = prepare_openfast_case(case, paths)
    existing = prepared.fst_path.with_suffix(".outb"); existing.write_bytes(b"preserve")
    with pytest.raises(OpenFASTPreparationError, match="version mismatch"):
        run_openfast(prepared, paths, force=True)
    assert existing.read_bytes() == b"preserve"
    assert not (prepared.fst_path.parent / "SIMULATION_LAUNCHED").exists()


@pytest.mark.parametrize("banner", ["OpenFAST-v4.1.1", "unknown wrapper"])
def test_matching_or_unavailable_version_is_recorded(tmp_path, banner):
    template = _template(tmp_path / "template")
    case = _case(kind="steady")
    case.scientific["model_configuration"]["openfast_version"] = "4.1.1"
    executable = _executable(tmp_path / "openfast", f'if [ "$1" = "-v" ]; then echo "{banner}"; exit 0; fi\nprintf OUT > "${{1%.fst}}.outb"\n')
    paths = replace(_paths(template, tmp_path / "outputs"), openfast_executable=executable)
    prepared = prepare_openfast_case(case, paths)
    run_openfast(prepared, paths)
    runtime = json.loads((prepared.workspace / "openfast_runtime.json").read_text())
    assert runtime["version_check"] == ("matched" if "4.1.1" in banner else "unavailable")
    assert run_openfast(prepared, paths).reused
    executable.write_text(executable.read_text() + "# changed binary\n")
    with pytest.raises(OpenFASTPreparationError, match="inconsistent"):
        run_openfast(prepared, paths)


def test_legacy_id_infers_version_and_conflicting_declaration_fails():
    assert required_openfast_version({"openfast_template_id": "iea15mw-volturnus-openfast-v1"}) == "4.1.1"
    with pytest.raises(ValidationError, match="conflicts"):
        required_openfast_version({"openfast_template_id": "IEA15MW_VolturnUS_v5.0.0", "openfast_version": "4.1.1"})


def test_template_format_and_frozen_checksum(tmp_path):
    template = _template(tmp_path / "template")
    paths = _paths(template, tmp_path / "outputs")
    case = _case(kind="steady")
    case.scientific["model_configuration"]["openfast_version"] = "5.0.0"
    with pytest.raises(ValidationError, match="template format"):
        prepare_openfast_case(case, paths)
    case.scientific["model_configuration"]["openfast_version"] = "4.1.1"
    case.scientific["turbine"] = {"template_checksum": _tree_checksum(template)}
    prepare_openfast_case(case, paths)
    (template / "main/ServoDyn.dat").write_text("altered")
    with pytest.raises(ValidationError, match="frozen"):
        prepare_openfast_case(case, paths)
