"""Key-aware TurbSim template rendering.  This module never executes TurbSim."""
from __future__ import annotations

from pathlib import Path

from openfast_dataset.campaign.models import ValidationError

from .models import WindRealization

LEGACY_FIELDS = ("RandSeed1", "RandSeed2", "NumGrid_Y", "NumGrid_Z", "TimeStep", "AnalysisTime", "UsableTime", "HubHt", "GridHeight", "GridWidth", "TurbModel", "IECturbc", "IEC_WindType", "RefHt", "URef", "PLExp", "HFlowAng")
REQUIRED_FIELDS = set(LEGACY_FIELDS) - {"RandSeed2", "PLExp", "HFlowAng"}


def _format(value: object) -> str:
    return f'"{value}"' if isinstance(value, str) and not (value.startswith("\"") and value.endswith("\"")) else str(value)


def render_turbsim_input(realization: WindRealization, template_text: str) -> str:
    if realization.kind != "turbulent":
        raise ValidationError("only turbulent wind realizations have TurbSim inputs")
    c, grid = realization.content, realization.content["grid"]
    overrides = c.get("turbsim_overrides", {})
    template_labels = {
        parts[1]
        for line in template_text.splitlines()
        if not line.lstrip().startswith(("!", "#"))
        and len(parts := line.lstrip().split(maxsplit=2)) >= 2
    }
    unknown = set(overrides) - template_labels
    if unknown:
        raise ValidationError(f"TurbSim overrides are not present in the template: {sorted(unknown)}")
    values = {
        "RandSeed1": c["seed"], "RandSeed2": "RanLux", "NumGrid_Y": grid["num_y"],
        "NumGrid_Z": grid["num_z"], "TimeStep": c["dt_s"],
        "AnalysisTime": c["generation_duration_s"], "UsableTime": c["usable_duration_s"],
        "HubHt": c["reference_height_m"], "GridHeight": grid["height_m"],
        "GridWidth": grid["width_m"], "TurbModel": c["spectral_model"],
        "IECturbc": c["iec_turbulence_class"], "IEC_WindType": c["iec_wind_type"],
        "RefHt": c["reference_height_m"], "URef": c["speed_mps"],
    }
    if c.get("shear_exponent") is not None: values["PLExp"] = c["shear_exponent"]
    if c.get("direction_deg") is not None: values["HFlowAng"] = c["direction_deg"]
    values.update(overrides)
    lines, found = [], set()
    for line in template_text.splitlines():
        stripped = line.lstrip()
        parts = stripped.split(maxsplit=2)
        if len(parts) >= 2 and parts[1] in values:
            label = parts[1]; indent = line[:len(line) - len(stripped)]
            suffix = f"   {parts[2]}" if len(parts) == 3 else ""
            lines.append(f"{indent}{_format(values[label])}   {label}{suffix}")
            found.add(label)
        else: lines.append(line)
    missing = REQUIRED_FIELDS - found
    if missing: raise ValidationError(f"TurbSim template is missing required labels: {sorted(missing)}")
    return "\n".join(lines) + "\n"


def render_turbsim_file(realization: WindRealization, template: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_turbsim_input(realization, template.read_text(encoding="utf-8")), encoding="utf-8")
    return destination
