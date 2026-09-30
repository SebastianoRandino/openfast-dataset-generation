"""Resolve reusable wind requirements from resolved campaign cases."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openfast_dataset.campaign.models import ResolvedCase, ValidationError

from .models import WindRealization


@dataclass(frozen=True)
class WindPlan:
    realizations: tuple[WindRealization, ...]
    case_to_wind: dict[str, str]


def _required(value: Any, name: str) -> Any:
    if value is None:
        raise ValidationError(f"turbulent wind requires {name} for TurbSim planning")
    return value


def _positive(value: Any, name: str) -> Any:
    value = _required(value, name)
    try:
        if float(value) <= 0:
            raise ValueError
    except (TypeError, ValueError):
        raise ValidationError(f"{name} must be a positive number for TurbSim planning") from None
    return value


def _content(case: ResolvedCase) -> tuple[str, dict[str, Any]]:
    wind = case.scientific["wind"]
    kind = wind["kind"]
    if kind == "steady":
        return kind, {key: wind.get(key) for key in ("speed_mps", "reference_height_m", "direction_deg", "shear_exponent")}
    if kind == "external":
        return kind, {"bts_path": wind["bts_path"], "reference_height_m": wind.get("reference_height_m")}
    grid = wind.get("grid", {})
    duration = _positive(wind.get("generation_duration_s"), "wind.generation_duration_s")
    turbsim = wind.get("turbsim", {})
    if not isinstance(turbsim, dict):
        raise ValidationError("wind.turbsim must be a mapping for TurbSim planning")
    overrides = turbsim.get("overrides", {})
    if not isinstance(overrides, dict):
        raise ValidationError("wind.turbsim.overrides must be a mapping for TurbSim planning")
    dt = overrides.get("TimeStep", case.scientific["numerics"].get("wind_dt_s"))
    content = {
        "speed_mps": _positive(wind.get("speed_mps"), "wind.speed_mps"),
        "spectral_model": _required(wind.get("spectral_model"), "wind.spectral_model"),
        "iec_wind_type": _required(wind.get("iec_wind_type"), "wind.iec_wind_type"),
        "iec_turbulence_class": _required(wind.get("iec_turbulence_class"), "wind.iec_turbulence_class"),
        "seed": _required(wind.get("seed"), "wind.seed (actual TurbSim RandSeed1)"),
        "dt_s": _positive(dt, "wind dt"), "generation_duration_s": duration,
        "usable_duration_s": wind.get("usable_duration_s", "ALL"),
        "reference_height_m": _positive(wind.get("reference_height_m"), "wind.reference_height_m"),
        "direction_deg": wind.get("direction_deg"), "shear_exponent": wind.get("shear_exponent"),
        "grid": {key: _positive(grid.get(key), f"wind.grid.{key}") for key in ("num_y", "num_z", "width_m", "height_m")},
        "template_id": _required(wind.get("template_id"), "wind.template_id"),
        "turbsim_overrides": dict(sorted(overrides.items())),
    }
    return kind, content


def plan_winds(cases: list[ResolvedCase]) -> WindPlan:
    """Deduplicate by wind science only; controller and waves never enter the key."""
    by_id: dict[str, WindRealization] = {}
    mapping: dict[str, str] = {}
    for case in cases:
        kind, content = _content(case)
        realization = WindRealization.create(kind, content)
        by_id[realization.wind_id] = realization
        mapping[case.case_id] = realization.wind_id
    return WindPlan(tuple(by_id[key] for key in sorted(by_id)), mapping)
