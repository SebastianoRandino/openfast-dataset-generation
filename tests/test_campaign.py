from dataclasses import replace
from pathlib import Path

import pytest

from openfast_dataset.campaign.models import Actuation, Controller, ValidationError, Waves
from openfast_dataset.campaign.provenance import scientific_hash
from openfast_dataset.campaign.resolver import resolve_campaign
from openfast_dataset.config import load_campaign

ROOT = Path(__file__).parents[1]


def test_example_campaign_expands_deterministically() -> None:
    spec = load_campaign(ROOT / "configs/campaigns/example_floating_turbulent.yaml")
    first = resolve_campaign(spec)
    second = resolve_campaign(spec)
    assert [case.case_id for case in first] == [f"case_{i:05d}" for i in range(1, 7)]
    assert [case.scientific for case in first] == [case.scientific for case in second]
    assert {case.split for case in first} == {"train", "validation", "test"}
    assert "controller_dt_s" not in first[0].scientific["numerics"]
    assert "update_dt_s" not in first[0].scientific["actuation"]


def test_campaign_validation_messages() -> None:
    spec = load_campaign(ROOT / "configs/campaigns/example_floating_turbulent.yaml")
    bad = spec.__class__(**{**spec.__dict__, "wind": spec.wind.__class__(kind="external")})
    with pytest.raises(ValidationError, match="bts_path"):
        resolve_campaign(bad)


def test_hash_is_stable() -> None:
    one = {"b": 2, "a": [1]}
    assert scientific_hash(one) == scientific_hash({"a": [1], "b": 2})


def test_legacy_reference_preserves_campaign_population_and_labels() -> None:
    cases = resolve_campaign(load_campaign(ROOT / "configs/campaigns/legacy_compatible_doe.yaml"))
    assert len(cases) == 300
    assert [case.split for case in cases].count("train") == 180
    assert [case.split for case in cases].count("validation") == 60
    assert [case.split for case in cases].count("test") == 60
    assert {case.scientific["wind"]["metadata"]["dlc"] for case in cases} == {"DLC11", "DLC13", "DLC16"}
    assert {case.scientific["wind"]["seed_index"] for case in cases} == {1, 2, 3, 4, 5}


def test_paired_sweep_rejects_mismatched_dimensions() -> None:
    spec = load_campaign(ROOT / "configs/campaigns/example_floating_turbulent.yaml")
    bad_group = {"sweeps": [{"mode": "paired", "dimensions": {"wind.speed_mps": [8], "wind.seed_index": [1, 2]}}]}
    bad = spec.__class__(**{**spec.__dict__, "case_groups": [bad_group]})
    with pytest.raises(ValidationError, match="equal lengths"):
        resolve_campaign(bad)


def test_fixed_and_floating_platforms_can_both_have_waves() -> None:
    spec = load_campaign(ROOT / "configs/campaigns/example_floating_turbulent.yaml")
    assert resolve_campaign(spec)
    assert resolve_campaign(replace(spec, platform=replace(spec.platform, kind="fixed")))


def test_resolved_sweep_values_are_validated() -> None:
    spec = load_campaign(ROOT / "configs/campaigns/example_floating_turbulent.yaml")
    bad_wind = replace(spec, case_groups=[{"fixed": {"wind.speed_mps": -10}}])
    with pytest.raises(ValidationError, match=r"resolved case_00001: wind.speed_mps"):
        resolve_campaign(bad_wind)
    bad_controller = replace(spec, case_groups=[{"fixed": {"controller.kind": "rosco"}}])
    with pytest.raises(ValidationError, match=r"resolved case_00001: controller.kind"):
        resolve_campaign(bad_controller)


def test_structured_path_typo_is_rejected() -> None:
    spec = load_campaign(ROOT / "configs/campaigns/example_floating_turbulent.yaml")
    bad = replace(spec, case_groups=[{"fixed": {"controller.omeg_pc": 0.1}}])
    with pytest.raises(ValidationError, match="controller.omeg_pc"):
        resolve_campaign(bad)


def test_regular_and_irregular_wave_validation() -> None:
    Waves(kind="regular", wave_height_m=2.0, period_s=8.0).validate()
    Waves(kind="irregular", significant_height_m=2.0, peak_period_s=8.0, spectrum="JONSWAP", seed=1).validate()
    with pytest.raises(ValidationError, match="wave_height_m"):
        Waves(kind="regular", significant_height_m=2.0, peak_period_s=8.0).validate()
    with pytest.raises(ValidationError, match="spectrum"):
        Waves(kind="irregular", significant_height_m=2.0, peak_period_s=8.0).validate()


def test_template_controller_is_the_only_current_mode() -> None:
    Controller(kind="template").validate()
    with pytest.raises(ValidationError, match="template"):
        Controller(kind="rosco").validate()
    with pytest.raises(ValidationError, match="active actuation"):
        Actuation(enabled=True).validate()
