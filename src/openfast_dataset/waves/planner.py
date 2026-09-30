"""Pure dependency planning for OpenFAST SeaState waves."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openfast_dataset.campaign.models import ResolvedCase, ValidationError
from .models import WaveRealization


@dataclass(frozen=True)
class WavePlan:
    realizations: tuple[WaveRealization, ...]
    case_to_wave: dict[str, str]


def _seed(waves: dict[str, Any]) -> int:
    if waves.get("seed") is not None:
        return int(waves["seed"])
    index = waves.get("seed_index")
    if index is None:
        raise ValidationError("irregular waves require waves.seed or waves.seed_index")
    # Stable independent policy; seed_index is provenance, not an OpenFAST seed.
    return -500_000_000 + int(index)


def _content(case: ResolvedCase) -> tuple[str, dict[str, Any]]:
    waves, numerics = case.scientific["waves"], case.scientific["numerics"]
    kind = waves["kind"]
    common = {"direction_deg": waves.get("direction_deg"), "duration_s": numerics["duration_s"], "wave_dt_s": numerics.get("wave_dt_s")}
    if kind == "none":
        return kind, common
    if kind == "regular":
        return kind, {**common, "wave_height_m": waves["wave_height_m"], "period_s": waves["period_s"]}
    if kind == "irregular":
        spectrum = str(waves["spectrum"]).upper()
        if spectrum not in {"JONSWAP", "PIERSON-MOSKOWITZ", "PIERSON_MOSKOWITZ"}:
            raise ValidationError(f"unsupported irregular wave spectrum: {waves['spectrum']}")
        seed_2 = waves.get("seed_2")
        return kind, {**common, "significant_height_m": waves["significant_height_m"], "peak_period_s": waves["peak_period_s"], "spectrum": spectrum, "seed_1": _seed(waves), "seed_2": "RANLUX" if seed_2 is None else seed_2, "peak_shape": waves.get("peak_shape", "DEFAULT")}
    if kind == "external":
        return kind, {**common, "external_reference": waves["external_reference"]}
    raise ValidationError(f"unsupported wave kind: {kind}")


def plan_waves(cases: list[ResolvedCase]) -> WavePlan:
    by_id: dict[str, WaveRealization] = {}
    mapping: dict[str, str] = {}
    for case in cases:
        kind, content = _content(case)
        realization = WaveRealization.create(kind, content)
        by_id[realization.wave_id] = realization
        mapping[case.case_id] = realization.wave_id
    return WavePlan(tuple(by_id[key] for key in sorted(by_id)), mapping)
