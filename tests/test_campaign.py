from pathlib import Path

import pytest

from openfast_dataset.campaign.models import ValidationError
from openfast_dataset.campaign.provenance import scientific_hash
from openfast_dataset.campaign.resolver import resolve_campaign
from openfast_dataset.config import load_campaign


ROOT = Path(__file__).parents[1]


def test_example_campaign_expands_deterministically() -> None:
    spec = load_campaign(ROOT / "configs/campaigns/example_floating_turbulent.yaml")
    first = resolve_campaign(spec)
    second = resolve_campaign(spec)
    assert [case.case_id for case in first] == [f"case_{i:05d}" for i in range(1, 11)]
    assert [case.scientific for case in first] == [case.scientific for case in second]
    assert {case.split for case in first} == {"train", "validation", "test"}
    assert first[0].scientific["numerics"]["controller_dt_s"] != first[0].scientific["actuation"]["update_dt_s"]


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
    assert {case.scientific["wind"]["overrides"]["dlc"] for case in cases} == {"DLC11", "DLC13", "DLC16"}
    assert {case.scientific["wind"]["seed_index"] for case in cases} == {1, 2, 3, 4, 5}


def test_paired_sweep_rejects_mismatched_dimensions() -> None:
    spec = load_campaign(ROOT / "configs/campaigns/example_floating_turbulent.yaml")
    bad_group = {"sweeps": [{"mode": "paired", "dimensions": {"wind.speed_mps": [8], "wind.seed_index": [1, 2]}}]}
    bad = spec.__class__(**{**spec.__dict__, "case_groups": [bad_group]})
    with pytest.raises(ValidationError, match="equal lengths"):
        resolve_campaign(bad)
