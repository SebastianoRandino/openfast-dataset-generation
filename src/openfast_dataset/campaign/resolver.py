"""Deterministic expansion of campaign sweeps without creating simulation files."""
from __future__ import annotations

from copy import deepcopy
from itertools import product
from typing import Any

from .models import ResolvedCase, ValidationError


def _set_path(data: dict[str, Any], path: str, value: Any) -> None:
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
        cases.append(ResolvedCase(f"case_{number:05d}", split, scientific, spec.provenance))
    return cases
