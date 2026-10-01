from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .campaign.models import (
    Actuation, CampaignSpecification, Controller, Platform, TimeScales, Waves, Wind,
)


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML configuration file."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")
    return data


def load_campaign(path: str | Path) -> CampaignSpecification:
    """Load a portable campaign YAML and its referenced model metadata."""
    source = Path(path)
    data = load_yaml(source)
    model_ref = data.get("model")
    if not isinstance(model_ref, str):
        raise ValueError("campaign.model must reference a model YAML file")
    model_data = load_yaml(source.parent / model_ref)
    platform_data = data.get("platform", model_data.get("platform", {}))
    return CampaignSpecification(
        name=data.get("name", ""), model=model_data.get("identifier", ""),
        openfast_template_id=model_data.get("openfast_template_id"), openfast_primary_fst=model_data.get("openfast_primary_fst"),
        openfast_version=model_data.get("openfast_version"),
        structural_model=data.get("structural_model"), output_profile=data.get("output_profile"),
        beamdyn_primary_file=model_data.get("beamdyn_primary_file"),
        turbine=model_data.get("turbine", {}), platform=Platform(**platform_data),
        numerics=TimeScales(**data.get("numerics", {})), wind=Wind(**data.get("wind", {})),
        waves=Waves(**data.get("waves", {})), controller=Controller(**data.get("controller", {})),
        actuation=Actuation(**data.get("actuation", {})), modules=data.get("modules", {}),
        overrides=data.get("overrides", {}), sweeps=data.get("sweeps", []),
        case_groups=data.get("case_groups", []), cases=data.get("cases", []),
        splits=data.get("splits", {}), provenance=data.get("provenance", {}),
    )
