from copy import deepcopy
from pathlib import Path

import pytest

from openfast_dataset.campaign.models import ResolvedCase, ValidationError, Waves
from openfast_dataset.waves.planner import plan_waves


def _case(**changes) -> ResolvedCase:
    waves = {"kind": "irregular", "significant_height_m": 2.0, "peak_period_s": 8.0, "spectrum": "JONSWAP", "direction_deg": 0.0, "seed": -12, "peak_shape": "DEFAULT"}
    waves.update(changes.pop("waves", {}))
    return ResolvedCase(changes.pop("case_id", "case_00001"), None, {"waves": waves, "numerics": {"duration_s": 100.0, "wave_dt_s": 0.25}, **changes})


def test_wave_identity_deduplicates_only_wave_science() -> None:
    first = _case(controller={"omega_pc": 0.1}, wind={"seed": 1})
    second = _case(case_id="case_00002", controller={"omega_pc": 0.2}, wind={"seed": 2})
    plan = plan_waves([first, second])
    assert len(plan.realizations) == 1
    for field, value in (("seed", -13), ("significant_height_m", 3.0), ("peak_period_s", 9.0), ("direction_deg", 10.0), ("spectrum", "PIERSON-MOSKOWITZ"), ("peak_shape", 2.0)):
        changed = _case(case_id=field, waves={field: value})
        assert len(plan_waves([first, changed]).realizations) == 2


def test_none_regular_irregular_and_seed_policy() -> None:
    none = _case(waves={"kind": "none", "significant_height_m": None, "peak_period_s": None, "spectrum": None, "seed": None, "direction_deg": None})
    regular = _case(waves={"kind": "regular", "wave_height_m": 3.0, "period_s": 9.0, "significant_height_m": None, "peak_period_s": None, "spectrum": None, "seed": None})
    indexed = _case(waves={"seed": None, "seed_index": 7})
    plan = plan_waves([none, regular, indexed])
    assert [item.kind for item in plan.realizations] == ["irregular", "none", "regular"]
    assert plan.realizations[0].content["seed_1"] == -499999993
    assert plan.realizations[0].content["seed_2"] == "RANLUX"


def test_wave_validation_rejects_incompatible_values() -> None:
    with pytest.raises(ValidationError, match="must not define"):
        Waves(kind="none", significant_height_m=1).validate()
    with pytest.raises(ValidationError, match="must not define"):
        Waves(kind="regular", wave_height_m=1, period_s=2, significant_height_m=1).validate()
    with pytest.raises(ValidationError, match="require waves.seed"):
        Waves(kind="irregular", significant_height_m=1, peak_period_s=2, spectrum="JONSWAP").validate()
