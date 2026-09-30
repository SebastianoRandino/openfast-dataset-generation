import csv
import json
from copy import deepcopy
from pathlib import Path

import pytest

from openfast_dataset.campaign.models import ResolvedCase, ValidationError, Wind
from openfast_dataset.campaign.resolver import resolve_campaign
from openfast_dataset.config import load_campaign
from openfast_dataset.wind.manifest import write_manifest
from openfast_dataset.wind.models import WindRealization
from openfast_dataset.wind.planner import plan_winds
from openfast_dataset.wind.turbsim import render_turbsim_input

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "legacy_turbsim.inp"


def turbulent_case(**changes):
    case_id = changes.pop("case_id", "case_00001")
    split = changes.pop("split", "train")
    wind = {
        "kind": "turbulent",
        "speed_mps": 12.0,
        "reference_height_m": 150.0,
        "spectral_model": "IECKAI",
        "iec_wind_type": "NTM",
        "iec_turbulence_class": "B",
        "seed": 100001,
        "seed_index": 1,
        "generation_duration_s": 1000.0,
        "usable_duration_s": "ALL",
        "template_id": "legacy-iea15mw-turbsim-v2",
        "grid": {"num_y": 11, "num_z": 11, "width_m": 300.0, "height_m": 300.0},
        "metadata": {"dlc": "DLC11"},
        "turbsim": {"overrides": {"RandSeed2": "RanLux"}},
    }
    wind.update(changes.pop("wind", {}))
    scientific = {"wind": wind, "numerics": {"wind_dt_s": 0.1}}
    scientific.update(changes)
    return ResolvedCase(case_id, split, scientific)


def test_steady_and_external_wind_planning() -> None:
    steady = turbulent_case(wind={"kind": "steady", "speed_mps": 8.0})
    external = turbulent_case(wind={"kind": "external", "bts_path": "wind.bts", "reference_height_m": 150.0})
    plan = plan_winds([steady, external])
    assert {item.kind for item in plan.realizations} == {"steady", "external"}
    assert {item.content["kind"] for item in plan.realizations} == {"steady", "external"}


def test_identity_is_deterministic_and_excludes_case_metadata() -> None:
    first = turbulent_case()
    second = deepcopy(first)
    second = second.__class__("case_00002", "test", deepcopy(second.scientific), {"source": "other"})
    second.scientific["wind"]["metadata"]["dlc"] = "DLC16"
    second.scientific["controller"] = {"omega_pc": 0.1}
    second.scientific["waves"] = {"significant_height_m": 2.0}
    plan = plan_winds([first, second])
    assert len(plan.realizations) == 1
    assert plan.case_to_wind[first.case_id] == plan.case_to_wind[second.case_id]
    assert WindRealization.create("steady", {"speed_mps": 8}) == WindRealization.create("steady", {"speed_mps": 8})


@pytest.mark.parametrize(
    ("change", "expected_unique"),
    [
        ({"seed": 100002}, 2),
        ({"speed_mps": 14.0}, 2),
        ({"turbsim": {"overrides": {"TimeStep": 0.2}}}, 2),
        ({"grid": {"num_y": 13, "num_z": 11, "width_m": 300.0, "height_m": 300.0}}, 2),
        ({"spectral_model": "IECTM"}, 2),
        ({"iec_wind_type": "ETM"}, 2),
        ({"iec_turbulence_class": "C"}, 2),
    ],
)
def test_generation_parameter_changes_identity(change, expected_unique) -> None:
    first = turbulent_case()
    second = turbulent_case(wind=change)
    assert len(plan_winds([first, second]).realizations) == expected_unique


def test_legacy_campaign_has_derived_unique_wind_count() -> None:
    cases = resolve_campaign(load_campaign(ROOT / "configs/campaigns/legacy_compatible_doe.yaml"))
    plan = plan_winds(cases)
    scientific_combinations = {
        (
            case.scientific["wind"]["speed_mps"],
            case.scientific["wind"]["spectral_model"],
            case.scientific["wind"]["iec_wind_type"],
            case.scientific["wind"]["iec_turbulence_class"],
            case.scientific["wind"]["seed"],
            case.scientific["wind"]["generation_duration_s"],
            case.scientific["wind"]["usable_duration_s"],
            case.scientific["wind"]["reference_height_m"],
            case.scientific["wind"]["template_id"],
            tuple(sorted(case.scientific["wind"]["grid"].items())),
            tuple(sorted(case.scientific["wind"]["turbsim"].get("overrides", {}).items())),
            case.scientific["numerics"]["wind_dt_s"],
        )
        for case in cases
    }
    assert len(scientific_combinations) == len(plan.realizations) == 80


def test_invalid_turbulent_requirements_raise_validation_error() -> None:
    missing_seed = turbulent_case(wind={"seed": None})
    with pytest.raises(ValidationError, match="wind.seed"):
        plan_winds([missing_seed])
    missing_template = turbulent_case(wind={"template_id": None})
    with pytest.raises(ValidationError, match="template_id"):
        plan_winds([missing_template])


@pytest.mark.parametrize("field", ["generation_duration_s", "usable_duration_s"])
def test_invalid_numeric_wind_configuration_is_validation_error(field) -> None:
    wind = Wind(kind="turbulent", speed_mps=12.0, spectral_model="IECKAI", iec_wind_type="NTM", iec_turbulence_class="B", seed=100001, **{field: "not-a-number"})
    with pytest.raises(ValidationError, match=field):
        wind.validate()


def test_renderer_matches_legacy_scientific_values_and_preserves_unrelated_text() -> None:
    rendered = render_turbsim_input(plan_winds([turbulent_case()]).realizations[0], FIXTURE.read_text(encoding="utf-8"))
    values = {line.split()[1]: line.split()[0] for line in rendered.splitlines() if len(line.split()) >= 2 and not line.startswith("!")}
    assert values == {
        "RandSeed1": "100001", "RandSeed2": '"RanLux"', "NumGrid_Y": "11", "NumGrid_Z": "11",
        "TimeStep": "0.1", "AnalysisTime": "1000.0", "UsableTime": '"ALL"', "HubHt": "150.0",
        "GridHeight": "300.0", "GridWidth": "300.0", "TurbModel": '"IECKAI"', "IECturbc": '"B"',
        "IEC_WindType": '"NTM"', "RefHt": "150.0", "URef": "12.0",
    }
    assert "! unrelated template line must remain unchanged" in rendered


def test_unknown_explicit_turbsim_override_fails() -> None:
    case = turbulent_case(wind={"turbsim": {"overrides": {"NotATurbSimField": 1}}})
    with pytest.raises(ValidationError, match="not present in the template"):
        render_turbsim_input(plan_winds([case]).realizations[0], FIXTURE.read_text(encoding="utf-8"))


def test_renderer_expected_failures_use_validation_error() -> None:
    steady = plan_winds([turbulent_case(wind={"kind": "steady", "speed_mps": 8.0})]).realizations[0]
    with pytest.raises(ValidationError, match="only turbulent"):
        render_turbsim_input(steady, FIXTURE.read_text(encoding="utf-8"))
    incomplete = FIXTURE.read_text(encoding="utf-8").replace("URef", "MissingURef")
    with pytest.raises(ValidationError, match="missing required labels"):
        render_turbsim_input(plan_winds([turbulent_case()]).realizations[0], incomplete)

def test_manifest_json_and_csv_contents(tmp_path: Path) -> None:
    plan = plan_winds([turbulent_case(), turbulent_case(case_id="case_00002", wind={"seed": 100002})])
    json_path, csv_path = write_manifest(plan, tmp_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(payload["winds"]) == 2
    assert payload["case_to_wind"] == plan.case_to_wind
    with csv_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert rows == [
        {"case_id": "case_00001", "wind_id": plan.case_to_wind["case_00001"]},
        {"case_id": "case_00002", "wind_id": plan.case_to_wind["case_00002"]},
    ]


def test_controller_rom_wind_is_representable() -> None:
    case = turbulent_case(wind={
        "speed_mps": 10.0,
        "iec_turbulence_class": "B",
        "seed": 110101,
        "reference_height_m": 150.0,
        "generation_duration_s": 1000.0,
        "grid": {"num_y": 11, "num_z": 11, "width_m": 300.0, "height_m": 300.0},
        "turbsim": {"overrides": {"TimeStep": 0.1}},
    })
    realization = plan_winds([case]).realizations[0]
    assert realization.content["grid"] == {"num_y": 11, "num_z": 11, "width_m": 300.0, "height_m": 300.0}
    assert realization.content["reference_height_m"] == 150.0
    assert realization.content["dt_s"] == 0.1
    assert realization.content["generation_duration_s"] == 1000.0
    assert realization.content["seed"] == 110101