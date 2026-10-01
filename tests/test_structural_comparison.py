import subprocess
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

from openfast_dataset.campaign.models import ValidationError, validate_resolved_scientific
from openfast_dataset.campaign.provenance import scientific_hash
from openfast_dataset.campaign.resolver import resolve_campaign
from openfast_dataset.cases.preparation import _field_value, prepare_openfast_case
from openfast_dataset.cases.structure import COMMON_ED_CHANNELS, ED_BLADE_CHANNELS
from openfast_dataset.config import load_campaign
from openfast_dataset.paths import MachinePaths
from openfast_dataset.waves.planner import plan_waves
from openfast_dataset.wind.planner import plan_winds
from openfast_dataset.wind.turbsim import render_turbsim_input

ROOT = Path(__file__).resolve().parents[1]


def test_beamdyn_format_adaptation_preserves_all_original_bytes(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "recipe", ROOT / "scripts/materialize_iea15mw_v5.py"
    )
    recipe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recipe)
    path = tmp_path / "blade.dat"
    original = (
        b"official header\n26 station_total\n1 damp_type\n"
        b"0.00299005 0.00218775 0.00084171 0.00218775 0.00299005 0.00084171\n"
        b" ---------------------- DISTRIBUTED PROPERTIES-----\n"
        b"0.000000\n6.7403759942007923e+09\n"
    )
    path.write_bytes(original)
    recipe.adapt_beamdyn_blade(path)
    adapted = path.read_bytes()
    start = adapted.index(b"------ Modal Damping")
    end = adapted.index(b" ---------------------- DISTRIBUTED PROPERTIES")
    assert adapted[:start] + adapted[end:] == original
    assert b"3 n_modes" in adapted and b"0.1 0.2 0.3 zeta" in adapted
    with pytest.raises(ValueError, match="layout"):
        recipe.adapt_beamdyn_blade(path)


def campaign():
    return resolve_campaign(load_campaign(ROOT / "configs/campaigns/structural_comparison_v5.yaml"))


def test_matrix_dependency_identity_and_pairwise_science():
    cases = campaign()
    winds, waves = plan_winds(cases), plan_waves(cases)
    assert len(cases) == 6
    assert len(winds.realizations) == len(waves.realizations) == 3
    # Existing full-duration BTS dependencies must survive the global-clock change.
    assert {wind.wind_id for wind in winds.realizations} == {
        "wind_8029c703c7171299", "wind_74fb16429b75d05e", "wind_b5a3cb79b3fb0007"
    }
    assert sorted(Counter(winds.case_to_wind.values()).values()) == [2, 2, 2]
    for index, (u, hs, tp) in enumerate(((5, 1, 6), (10, 2, 8), (14, 3, 10))):
        ed, bd = cases[2 * index : 2 * index + 2]
        assert winds.case_to_wind[ed.case_id] == winds.case_to_wind[bd.case_id]
        assert waves.case_to_wave[ed.case_id] == waves.case_to_wave[bd.case_id]
        left, right = deepcopy(ed.scientific), deepcopy(bd.scientific)
        assert left.pop("structural_model") == "elastodyn"
        assert right.pop("structural_model") == "beamdyn"
        assert left == right
        assert scientific_hash(ed.scientific) != scientific_hash(bd.scientific)
        assert left["wind"]["speed_mps"] == u
        assert left["waves"]["significant_height_m"] == hs
        assert left["waves"]["peak_period_s"] == tp
        assert left["wind"]["seed"] == 510001 + index
        assert left["waves"]["seed"] == 610001 + index
        assert left["waves"]["seed_2"] == "RANLUX"
        assert left["numerics"]["integration_dt_s"] == 0.01
        assert left["numerics"]["output_dt_s"] == 0.01
        assert left["numerics"]["beamdyn_dt_s"] == 0.01
        assert left["numerics"]["duration_s"] == 400.0
        assert left["numerics"]["wind_dt_s"] == 0.05
        assert left["numerics"]["wave_dt_s"] == 0.25
        assert left["controller"]["kind"] == "template"
        assert left["overrides"]["openfast"] == {"fst": {"ModCoupling": 3}}
        assert ed.split is bd.split is None
    for wind in winds.realizations:
        assert wind.content["generation_duration_s"] == 460
        assert wind.content["usable_duration_s"] == 400
        assert wind.content["dt_s"] == 0.05
        assert wind.content["grid"] == {
            "num_y": 31,
            "num_z": 31,
            "width_m": 300.0,
            "height_m": 300.0,
        }
        rendered = render_turbsim_input(
            wind,
            (ROOT / "tests/fixtures/legacy_turbsim.inp").read_text()
            + "\nTrue WrADFF\nFalse WrBLFF\n",
        )
        assert '"NTM"   IEC_WindType' in rendered
        assert '"B"   IECturbc' in rendered


def template(root):
    root.mkdir()
    (root / "model.fst").write_text(
        '3 ModCoupling\n6 MaxConvIter\n1e-4 ConvTol\n1 CompElast\n10 TMax\n.01 DT\n.1 DT_Out\n0 TStart\n2 OutFileFmt\n"ed.dat" EDFile\n"bd.dat" BDBldFile(1)\n"bd.dat" BDBldFile(2)\n"bd.dat" BDBldFile(3)\n"inflow.dat" InflowFile\n"sea.dat" SeaStFile\n"servo.dat" ServoFile\n"aero.dat" AeroFile\n'
    )
    (root / "ed.dat").write_text(
        "True FlapDOF1\nTrue FlapDOF2\nTrue EdgeDOF\n"
        + "".join(
            f"True {field}\n"
            for field in ("PtfmSgDOF", "PtfmSwDOF", "PtfmHvDOF", "PtfmRDOF", "PtfmPDOF", "PtfmYDOF")
        )
        + 'OutList\n"RotSpeed"\nEND\n'
    )
    (root / "bd.dat").write_text('"DEFAULT" DTBeam\n"blade.dat" BldFile\nOutList\n"RootFxr"\nEND\n')
    (root / "blade.dat").write_bytes(b"official structural properties stand-in\n")
    (root / "inflow.dat").write_text('1 WindType\n5 HWindSpeed\n"unused" FileName_BTS\n')
    (root / "sea.dat").write_text(
        "0 WaveMod\n1 WaveHs\n6 WaveTp\nDEFAULT WavePkShp\n0 WaveDir\n1 WaveSeed(1)\nRANLUX WaveSeed(2)\n400 WaveTMax\n.25 WaveDT\n"
    )
    (root / "servo.dat").write_bytes(
        b'baseline ROSCO\n"DEFAULT" DT\n"DEFAULT" DLL_DT\nOutList\n"GenPwr"\n"GenTq"\nEND\n'
    )
    (root / "DISCON.IN").write_bytes(b"unchanged controller tuning\n")
    (root / "libdiscon.so").write_bytes(b"unchanged ROSCO library\n")
    (root / "hydro.dat").write_bytes(b"unchanged hydrodynamics\n")
    (root / "mooring.dat").write_bytes(b"unchanged moorings\n")
    (root / "aero.dat").write_text('OutList\n"RtAeroFxh"\nEND\n')


@pytest.mark.parametrize("relative_output", [False, True])
def test_prepared_six_cases_and_allowed_file_differences(tmp_path, monkeypatch, relative_output):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "template"
    template(source)
    cases = campaign()
    for case in cases:
        case.scientific["model_configuration"].update(
            openfast_primary_fst="model.fst", beamdyn_primary_file="bd.dat"
        )
    winds = plan_winds(cases)
    paths = MachinePaths(
        Path("/bin/true"),
        {},
        {"IEA15MW_VolturnUS_v5.0.0": source},
        Path("outputs") if relative_output else tmp_path / "outputs",
    )
    lookup = {wind.wind_id: wind for wind in winds.realizations}
    for wind in winds.realizations:
        bts = paths.output_root / "wind" / wind.wind_id / "wind.bts"
        bts.parent.mkdir(parents=True)
        bts.write_bytes(b"fake wind")
    prepared = []
    for case in cases:
        result = prepare_openfast_case(case, paths, lookup[winds.case_to_wind[case.case_id]])
        prepared.append(result)
        fst, ed, bd = result.fst_path, result.workspace / "ed.dat", result.workspace / "bd.dat"
        beam = case.scientific["structural_model"] == "beamdyn"
        for key, value in {
            "CompElast": 2 if beam else 1,
            "ModCoupling": 3,
            "DT": 0.01,
            "DT_Out": 0.01,
            "MaxConvIter": 6,
            "ConvTol": 1e-4,
            "TMax": 400,
            "TStart": 0,
        }.items():
            assert float(_field_value(fst, key)) == value
        assert int(float(_field_value(fst, "TMax")) / float(_field_value(fst, "DT_Out"))) + 1 == 40001
        for key in ("DT", "DLL_DT"):
            assert _field_value(result.workspace / "servo.dat", key) == "DEFAULT"
        for key in ("FlapDOF1", "FlapDOF2", "EdgeDOF"):
            assert _field_value(ed, key) == str(not beam)
        for key in ("PtfmSgDOF", "PtfmSwDOF", "PtfmHvDOF", "PtfmRDOF", "PtfmPDOF", "PtfmYDOF"):
            assert _field_value(ed, key) == "True"
        if beam:
            for channel in COMMON_ED_CHANNELS:
                assert f'"{channel}"' in ed.read_text()
            for channel in ED_BLADE_CHANNELS:
                assert f'"{channel}"' not in ed.read_text()
            assert float(_field_value(bd, "DTBeam")) == 0.01
            for blade in range(1, 4):
                assert _field_value(fst, f"BDBldFile({blade})") == "bd.dat"
        for name in ("servo.dat", "DISCON.IN", "libdiscon.so", "blade.dat", "hydro.dat", "mooring.dat"):
            assert (result.workspace / name).read_bytes() == (source / name).read_bytes()
    for ed, bd in zip(prepared[::2], prepared[1::2]):
        assert (ed.workspace / "Wind/wind.bts").resolve() == (
            bd.workspace / "Wind/wind.bts"
        ).resolve()
        for name in ("sea.dat", "inflow.dat", "aero.dat", "servo.dat", "DISCON.IN", "libdiscon.so", "blade.dat", "hydro.dat", "mooring.dat"):
            assert (ed.workspace / name).read_bytes() == (bd.workspace / name).read_bytes()
        differences = {
            name
            for name in (
                "model.fst",
                "ed.dat",
                "bd.dat",
                "sea.dat",
                "inflow.dat",
                "aero.dat",
                "servo.dat",
                "DISCON.IN",
                "blade.dat",
            )
            if (ed.workspace / name).read_bytes() != (bd.workspace / name).read_bytes()
        }
        assert differences == {"model.fst", "ed.dat", "bd.dat"}
    assert _field_value(source / "bd.dat", "DTBeam") == "DEFAULT"


def test_legacy_variants_are_opt_in_and_invalid_selection_fails():
    legacy = load_campaign(ROOT / "configs/campaigns/legacy_compatible_doe.yaml")
    # Characterized from the pre-change models at commit 8c5c9c4.
    assert (
        scientific_hash(legacy.base_scientific())
        == "ea0a0c6809a939feb1d50f443b6c7242d23ea99aaab41767d45d0d9f24595e58"
    )
    for name in ("iea15mw_volturnus.yaml", "iea15mw_volturnus_v4.1.1.yaml"):
        # Existing model metadata remains unchanged; legacy science gains no new clocks/keys.
        from openfast_dataset.config import load_yaml

        assert "beamdyn_primary_file" not in load_yaml(ROOT / "configs/models" / name)
    spec = load_campaign(ROOT / "configs/campaigns/integration_v5_short.yaml")
    science = resolve_campaign(spec)[0].scientific
    assert "structural_model" not in science and "output_profile" not in science
    assert "beamdyn_dt_s" not in science["numerics"]
    case = campaign()[0]
    case.scientific["structural_model"] = "unknown"
    with pytest.raises(ValidationError, match="structural_model"):
        validate_resolved_scientific(case.scientific)


def test_generated_files_and_machine_config_are_ignored():
    names = [
        "outputs/structural-smoke/cases/tmp/model.fst",
        "test.bts",
        "test.outb",
        "test.log",
        "configs/paths.yaml",
    ]
    result = subprocess.run(
        ["git", "check-ignore", *names], cwd=ROOT, capture_output=True, text=True, check=True
    )
    assert result.stdout.splitlines() == names
