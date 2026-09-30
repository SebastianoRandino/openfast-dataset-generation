import json
from pathlib import Path

import pytest

from openfast_dataset.campaign.models import ResolvedCase, ValidationError
from openfast_dataset.cases.preparation import OpenFASTPreparationError, patch_openfast_field, prepare_openfast_case
from openfast_dataset.paths import MachinePaths, resolve_openfast_template
from openfast_dataset.wind.models import WindRealization


def _template(root: Path) -> Path:
    (root / "main").mkdir(parents=True)
    (root / "common").mkdir()
    (root / "main" / "model.fst").write_text('10 TMax - time\n0.01 DT - dt\n0.1 DT_Out - output\n2 OutFileFmt - binary\n"../common/Inflow.dat" InflowFile - file\n"SeaState.dat" SeaStFile - sea\n"ServoDyn.dat" ServoFile - servo\n', encoding="utf-8")
    (root / "main" / "SeaState.dat").write_text('2 WaveMod\n1 WaveHs\n8 WaveTp\nDEFAULT WavePkShp\n0 WaveDir\n1 WaveSeed(1)\nRANLUX WaveSeed(2)\n10 WaveTMax\n0.25 WaveDT\n', encoding="utf-8")
    (root / "common" / "Inflow.dat").write_text('1 WindType - type\n8 HWindSpeed - steady\n"old.bts" FileName_BTS - bts\n', encoding="utf-8")
    (root / "main" / "ServoDyn.dat").write_bytes(b"DLL_DT preserved exactly\n")
    (root / "main" / "DISCON.IN").write_bytes(b"baseline DISCON preserved exactly\n")
    return root


def _case(*, kind="turbulent", case_id="case_00001") -> ResolvedCase:
    wind = {"kind": kind, "speed_mps": 12.0, "bts_path": None}
    if kind == "external": wind["bts_path"] = "external.bts"
    return ResolvedCase(case_id, "train", {"model": "test", "model_configuration": {"openfast_template_id": "test", "openfast_primary_fst": "main/model.fst"}, "platform": {"kind": "fixed", "initial_conditions": {}}, "numerics": {"integration_dt_s": 0.025, "output_dt_s": 0.1, "duration_s": 120.0}, "wind": wind, "waves": {"kind": "none"}, "controller": {"kind": "template"}, "actuation": {"enabled": False}, "overrides": {}})


def _paths(template: Path, output: Path) -> MachinePaths:
    return MachinePaths(Path("/bin/true"), {}, {"test": template}, output)


def test_resolution_and_turbulent_preparation_is_deterministic(tmp_path: Path) -> None:
    template = _template(tmp_path / "template")
    paths = _paths(template, tmp_path / "outputs")
    assert resolve_openfast_template("test", paths) == template.resolve()
    with pytest.raises(ValidationError, match="unknown OpenFAST"):
        resolve_openfast_template("missing", paths)
    realization = WindRealization.create("turbulent", {"seed": 1})
    bts = paths.output_root / "wind" / realization.wind_id / "wind.bts"; bts.parent.mkdir(parents=True); bts.write_bytes(b"BTS")
    prepared = prepare_openfast_case(_case(), paths, realization)
    assert not prepared.reused and prepared.fst_path.read_text().splitlines()[:3] == ["120.0   TMax   - time", "0.025   DT   - dt", "0.1   DT_Out   - output"]
    inflow = prepared.workspace / "common/Inflow.dat"
    assert '3   WindType' in inflow.read_text() and '"Wind/wind.bts"   FileName_BTS' in inflow.read_text()
    link = prepared.workspace / "common/Wind/wind.bts"
    assert link.is_symlink() and link.resolve() == bts.resolve()
    assert prepare_openfast_case(_case(), paths, realization).reused
    assert (template / "common/Inflow.dat").read_text().startswith("1 WindType")


def test_steady_overrides_and_inconsistent_force(tmp_path: Path) -> None:
    template = _template(tmp_path / "template"); paths = _paths(template, tmp_path / "outputs")
    case = _case(kind="steady"); case.scientific["overrides"] = {"openfast": {"fst": {"DT_Out": 0.2}}}
    prepared = prepare_openfast_case(case, paths)
    assert "12.0   HWindSpeed" in (prepared.workspace / "common/Inflow.dat").read_text()
    assert "0.2   DT_Out" in prepared.fst_path.read_text()
    (prepared.workspace / "case_metadata.json").write_text("{}")
    with pytest.raises(OpenFASTPreparationError): prepare_openfast_case(case, paths)
    assert not prepare_openfast_case(case, paths, force=True).reused


def test_structured_patch_rejects_missing_and_ambiguous_fields(tmp_path: Path) -> None:
    path = tmp_path / "input.dat"; path.write_text("1 A\n2 A\n")
    with pytest.raises(ValidationError, match="ambiguous"): patch_openfast_field(path, "A", 3)
    with pytest.raises(ValidationError, match="not present"): patch_openfast_field(path, "B", 3)


def test_missing_bts_and_unresolved_dependencies_are_explicit(tmp_path: Path) -> None:
    template = _template(tmp_path / "template"); paths = _paths(template, tmp_path / "outputs")
    realization = WindRealization.create("turbulent", {"seed": 1})
    with pytest.raises(ValidationError, match="BTS"):
        prepare_openfast_case(_case(), paths, realization)
    bts = paths.output_root / "wind" / realization.wind_id / "wind.bts"; bts.parent.mkdir(parents=True); bts.write_bytes(b"BTS")
    case = _case(); case.scientific["waves"] = {"kind": "irregular", "significant_height_m": 2, "peak_period_s": 8, "spectrum": "JONSWAP", "seed": 1}
    payload = json.loads(prepare_openfast_case(case, paths, realization).metadata_path.read_text())
    assert payload["unresolved"] == {}
    assert payload["controller"] == {"kind": "template", "policy": "preserved_from_openfast_template"}


def test_template_controller_files_are_byte_identical(tmp_path: Path) -> None:
    template = _template(tmp_path / "template"); paths = _paths(template, tmp_path / "outputs")
    prepared = prepare_openfast_case(_case(kind="steady"), paths)
    for name in ("ServoDyn.dat", "DISCON.IN"):
        assert (prepared.workspace / "main" / name).read_bytes() == (template / "main" / name).read_bytes()
    assert json.loads(prepared.metadata_path.read_text())["unresolved"] == {}


def test_disabled_actuation_timestep_does_not_make_a_case_unresolved(tmp_path: Path) -> None:
    template = _template(tmp_path / "template"); paths = _paths(template, tmp_path / "outputs")
    case = _case(kind="steady"); case.scientific["numerics"]["actuator_dt_s"] = 0.01
    assert prepare_openfast_case(case, paths).metadata_path.exists()


def test_seastate_regular_and_irregular_mapping(tmp_path: Path) -> None:
    template = _template(tmp_path / "template"); paths = _paths(template, tmp_path / "outputs")
    regular = _case(kind="steady"); regular.scientific["waves"] = {"kind": "regular", "wave_height_m": 3, "period_s": 9, "direction_deg": 15}
    prepared = prepare_openfast_case(regular, paths)
    text = (prepared.workspace / "main/SeaState.dat").read_text()
    assert "1   WaveMod" in text and "3   WaveHs" in text and "9   WaveTp" in text and "15   WaveDir" in text
    irregular = _case(kind="steady", case_id="case_00002"); irregular.scientific["waves"] = {"kind": "irregular", "significant_height_m": 4, "peak_period_s": 10, "spectrum": "JONSWAP", "direction_deg": -10, "seed": -4}
    prepared = prepare_openfast_case(irregular, paths)
    text = (prepared.workspace / "main/SeaState.dat").read_text()
    assert "2   WaveMod" in text and "-4   WaveSeed(1)" in text and "RANLUX   WaveSeed(2)" in text
    assert json.loads(prepared.metadata_path.read_text())["wave_realization_id"].startswith("wave_")
