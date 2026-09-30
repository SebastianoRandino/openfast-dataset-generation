"""Deterministic expansion of campaign sweeps without creating simulation files."""
from __future__ import annotations

from copy import deepcopy
from itertools import product
from typing import Any

from .models import ResolvedCase, ValidationError, validate_resolved_scientific

_FREE_FORM_PREFIXES = {
    "turbine", "platform.initial_conditions", "wind.grid", "wind.metadata",
    "wind.turbsim", "wind.turbsim.overrides",
    "waves.parameters", "controller.overrides", "modules", "overrides",
}
_STRUCTURED_PATHS = {
    "platform": {"kind", "hydrodynamics_template", "mooring_template", "initial_conditions"},
    "numerics": {"integration_dt_s", "duration_s", "output_dt_s", "controller_dt_s", "actuator_dt_s", "wind_dt_s", "wave_dt_s", "discard_transient_s"},
    "wind": {"kind", "speed_mps", "reference_height_m", "direction_deg", "shear_exponent", "spectral_model", "iec_wind_type", "iec_turbulence_class", "seed_index", "seed", "bts_path", "generation_duration_s", "usable_duration_s", "template_id", "grid", "metadata", "turbsim"},
    "waves": {"kind", "wave_height_m", "period_s", "significant_height_m", "peak_period_s", "spectrum", "direction_deg", "seed", "seed_index", "seed_2", "peak_shape", "external_reference", "parameters"},
    "controller": {"kind", "template", "omega_pc", "zeta_pc", "overrides"},
    "actuation": {"enabled", "delay_s", "rate_limit", "minimum", "maximum", "model"},
}


def _validate_path(path: str) -> None:
    if any(path == prefix or path.startswith(f"{prefix}.") for prefix in _FREE_FORM_PREFIXES):
        return
    root, *rest = path.split(".")
    if root not in _STRUCTURED_PATHS or len(rest) != 1 or rest[0] not in _STRUCTURED_PATHS[root]:
        raise ValidationError(f"unsupported structured sweep/override path: {path}")


def _set_path(data: dict[str, Any], path: str, value: Any) -> None:
    _validate_path(path)
    parts = path.split(".")
    target = data
    for part in parts[:-1]:
        if part not in target or not isinstance(target[part], dict):
            target[part] = {}
        target = target[part]
    target[parts[-1]] = value


def _apply(data: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(data)
    for path, value in values.items():
        _set_path(result, path, value)
    return result


def _expand_sweep(sweep: dict[str, Any]) -> list[dict[str, Any]]:
    dimensions = sweep.get("dimensions", {})
    if not isinstance(dimensions, dict) or not dimensions:
        raise ValidationError("sweep.dimensions must be a non-empty mapping")
    mode = sweep.get("mode", "cartesian")
    names, values = list(dimensions), list(dimensions.values())
    if not all(isinstance(item, list) and item for item in values):
        raise ValidationError("every sweep dimension must be a non-empty list")
    if mode == "cartesian":
        return [dict(zip(names, row)) for row in product(*values)]
    if mode == "paired":
        lengths = {len(item) for item in values}
        if len(lengths) != 1:
            raise ValidationError("paired sweep dimensions must have equal lengths")
        return [dict(zip(names, row)) for row in zip(*values)]
    raise ValidationError("sweep.mode must be cartesian or paired")


def _groups(spec: Any) -> list[dict[str, Any]]:
    groups = spec.case_groups or [{"sweeps": spec.sweeps}]
    result: list[dict[str, Any]] = []
    for group in groups:
        fixed = group.get("fixed", {})
        sweeps = group.get("sweeps", [])
        rows = [{}]
        for sweep in sweeps:
            rows = [{**left, **right} for left in rows for right in _expand_sweep(sweep)]
        if not sweeps:
            rows = [{}]
        result.extend([{**fixed, **row, "__split": group.get("split")} for row in rows])
    for item in spec.cases:
        values = item.get("values", item)
        result.append({**values, "__split": item.get("split")})
    return result


def resolve_campaign(spec: Any) -> list[ResolvedCase]:
    """Resolve groups in YAML order; sweep dimensions retain mapping/list order."""
    spec.validate()
    cases: list[ResolvedCase] = []
    for number, values in enumerate(_groups(spec), start=1):
        split = values.pop("__split", None)
        if split is not None and split not in {"train", "validation", "test"}:
            raise ValidationError(f"case split must be train, validation, or test, got {split!r}")
        scientific = _apply(spec.base_scientific(), values)
        try:
            validate_resolved_scientific(scientific)
        except ValidationError as error:
            raise ValidationError(f"resolved case_{number:05d}: {error}") from error
        cases.append(ResolvedCase(f"case_{number:05d}", split, scientific, spec.provenance))
    return cases
