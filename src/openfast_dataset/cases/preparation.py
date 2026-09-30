"""Deterministic, non-executing OpenFAST case preparation."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openfast_dataset.campaign.models import ResolvedCase, ValidationError
from openfast_dataset.campaign.provenance import scientific_hash
from openfast_dataset.paths import MachinePaths, resolve_openfast_template
from openfast_dataset.wind.models import WindRealization
from openfast_dataset.waves.models import WaveRealization


class OpenFASTPreparationError(RuntimeError):
    """A deterministic case cannot safely be prepared."""


@dataclass(frozen=True)
class PreparedOpenFASTCase:
    case: ResolvedCase
    workspace: Path
    fst_path: Path
    metadata_path: Path
    reused: bool


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_checksum(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(_checksum(path).encode())
    return digest.hexdigest()


def _format(value: object) -> str:
    if isinstance(value, str) and not (value.startswith('"') and value.endswith('"')):
        return f'"{value}"'
    return str(value)


def patch_openfast_field(path: Path, field: str, value: object) -> None:
    """Replace precisely one OpenFAST ``value label`` record, preserving its tail."""
    lines = path.read_text(encoding="utf-8").splitlines()
    matches: list[int] = []
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped or stripped.startswith(("!", "#", "=")):
            continue
        parts = stripped.split(maxsplit=2)
        if len(parts) >= 2 and parts[1] == field:
            matches.append(index)
    if not matches:
        raise ValidationError(f"OpenFAST field {field!r} is not present in {path}")
    if len(matches) != 1:
        raise ValidationError(f"OpenFAST field {field!r} is ambiguous in {path}")
    index = matches[0]
    line = lines[index]
    indent = line[: len(line) - len(line.lstrip())]
    parts = line.lstrip().split(maxsplit=2)
    suffix = f"   {parts[2]}" if len(parts) == 3 else ""
    rendered = _format(value) if parts[0].startswith('"') else str(value)
    lines[index] = f"{indent}{rendered}   {field}{suffix}"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _field_value(path: Path, field: str) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.lstrip().split(maxsplit=2)
        if len(parts) >= 2 and parts[1] == field:
            return parts[0].strip('"')
    raise ValidationError(f"OpenFAST field {field!r} is not present in {path}")


def _primary_fst(case: ResolvedCase, template: Path) -> tuple[Path, Path]:
    configuration = case.scientific.get("model_configuration", {})
    relative = configuration.get("openfast_primary_fst")
    if not relative:
        raise ValidationError("model configuration is missing openfast_primary_fst")
    source = template / relative
    if not source.is_file():
        raise ValidationError(f"OpenFAST primary .fst does not exist: {source}")
    return source, Path(relative)


def _inflow_path(fst: Path) -> Path:
    value = _field_value(fst, "InflowFile")
    path = (fst.parent / value).resolve()
    if not path.is_file():
        raise ValidationError(f"InflowWind file referenced by {fst.name} does not exist: {value}")
    return path


def _referenced_file(fst: Path, field: str) -> Path:
    value = _field_value(fst, field)
    path = (fst.parent / value).resolve()
    if not path.is_file():
        raise ValidationError(f"file referenced by {field} in {fst.name} does not exist: {value}")
    return path


def _seastate_path(fst: Path) -> Path:
    return _referenced_file(fst, "SeaStFile")


def _patch_waves(fst: Path, workspace: Path, realization: WaveRealization) -> list[dict[str, str]]:
    """Map a planned dependency to SeaState v4.1.1 fields in a copied model."""
    sea = _seastate_path(fst)
    content, patched = realization.content, []
    values: list[tuple[str, object]] = []
    if realization.kind == "none":
        values = [("WaveMod", 0)]
    elif realization.kind == "regular":
        values = [("WaveMod", 1), ("WaveHs", content["wave_height_m"]), ("WaveTp", content["period_s"])]
    elif realization.kind == "irregular":
        peak_shape = 1.0 if content["spectrum"] in {"PIERSON-MOSKOWITZ", "PIERSON_MOSKOWITZ"} else content["peak_shape"]
        values = [("WaveMod", 2), ("WaveHs", content["significant_height_m"]), ("WaveTp", content["peak_period_s"]), ("WavePkShp", peak_shape), ("WaveSeed(1)", content["seed_1"]), ("WaveSeed(2)", content["seed_2"])]
    else:
        raise ValidationError(f"external SeaState waves are not implemented: {realization.kind}")
    if content.get("direction_deg") is not None and realization.kind != "none":
        values.append(("WaveDir", content["direction_deg"]))
    if realization.kind != "none":
        values.append(("WaveTMax", content["duration_s"]))
        if content.get("wave_dt_s") is not None:
            values.append(("WaveDT", content["wave_dt_s"]))
    for field, value in values:
        patch_openfast_field(sea, field, value)
        patched.append({"file": sea.relative_to(workspace.resolve()).as_posix(), "field": field})
    return patched


def _link_wind(source: Path, destination: Path) -> None:
    if not source.is_file() or source.stat().st_size == 0:
        raise ValidationError(f"required BTS file does not exist or is empty: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        destination.unlink()
    try:
        destination.symlink_to(source.resolve())
    except OSError as error:
        raise OpenFASTPreparationError(f"could not create BTS symlink {destination}: {error}") from error


def _wind_source(case: ResolvedCase, realization: WindRealization | None, root: Path) -> tuple[Path | None, str | None]:
    wind = case.scientific["wind"]
    if wind["kind"] == "steady":
        return None, None
    if wind["kind"] == "external":
        return Path(wind["bts_path"]).expanduser(), None
    if realization is None or realization.kind != "turbulent":
        raise ValidationError("turbulent OpenFAST preparation requires its WindRealization")
    return root / "wind" / realization.wind_id / "wind.bts", realization.wind_id


def prepare_openfast_case(case: ResolvedCase, paths: MachinePaths, realization: WindRealization | None = None, output_root: str | Path | None = None, *, wave_realization: WaveRealization | None = None, force: bool = False) -> PreparedOpenFASTCase:
    """Copy, patch and link one case; this function intentionally never runs OpenFAST."""
    configuration = case.scientific.get("model_configuration", {})
    template_id = configuration.get("openfast_template_id")
    if not template_id:
        raise ValidationError("model configuration is missing openfast_template_id")
    template = resolve_openfast_template(template_id, paths)
    source_fst, relative_fst = _primary_fst(case, template)
    root = Path(output_root) if output_root is not None else paths.output_root
    workspace = root / "cases" / case.case_id
    template_checksum = _tree_checksum(template)
    wind_source, wind_id = _wind_source(case, realization, root)
    if wind_source is not None and (not wind_source.is_file() or wind_source.stat().st_size == 0):
        raise ValidationError(f"required BTS file does not exist or is empty: {wind_source}")
    wind_checksum = _checksum(wind_source) if wind_source and wind_source.is_file() else None
    from openfast_dataset.waves.planner import plan_waves
    expected_wave = plan_waves([case]).realizations[0]
    if wave_realization is None:
        wave_realization = expected_wave
    if wave_realization.wave_id != expected_wave.wave_id:
        raise ValidationError("WaveRealization does not match the resolved case")
    identity = scientific_hash({"case": case.normalized(), "template_id": template_id, "template_checksum": template_checksum, "wind_id": wind_id, "wind_checksum": wind_checksum, "wave_id": wave_realization.wave_id})
    metadata_path = workspace / "case_metadata.json"
    if metadata_path.is_file() and not force:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("preparation_identity") == identity:
            return PreparedOpenFASTCase(case, workspace, workspace / relative_fst, metadata_path, True)
        raise OpenFASTPreparationError("existing case directory has inconsistent provenance; use force=True")
    if workspace.exists():
        if not force:
            raise OpenFASTPreparationError("existing case directory has no reusable provenance; use force=True")
        shutil.rmtree(workspace)
    shutil.copytree(template, workspace)
    fst = workspace / relative_fst
    patched: list[dict[str, str]] = []
    for field, value in (("DT", case.scientific["numerics"]["integration_dt_s"]), ("DT_Out", case.scientific["numerics"].get("output_dt_s") or "default"), ("TMax", case.scientific["numerics"]["duration_s"])):
        patch_openfast_field(fst, field, value); patched.append({"file": relative_fst.as_posix(), "field": field})
    inflow = _inflow_path(fst)
    wind = case.scientific["wind"]
    if wind["kind"] == "steady":
        for field, value in (("WindType", 1), ("HWindSpeed", wind["speed_mps"])):
            patch_openfast_field(inflow, field, value); patched.append({"file": inflow.relative_to(workspace.resolve()).as_posix(), "field": field})
    else:
        assert wind_source is not None
        local_bts = workspace / "Wind" / "wind.bts"
        _link_wind(wind_source, local_bts)
        for field, value in (("WindType", 3), ("FileName_BTS", "Wind/wind.bts")):
            patch_openfast_field(inflow, field, value); patched.append({"file": inflow.relative_to(workspace.resolve()).as_posix(), "field": field})
    controller = case.scientific["controller"]
    controller_dt = case.scientific["numerics"].get("controller_dt_s")
    if controller["kind"] == "rosco" and controller_dt is not None:
        servo = _referenced_file(fst, "ServoFile")
        patch_openfast_field(servo, "DLL_DT", controller_dt)
        patched.append({"file": servo.relative_to(workspace.resolve()).as_posix(), "field": "DLL_DT"})
    patched.extend(_patch_waves(fst, workspace, wave_realization))
    overrides = case.scientific.get("overrides", {}).get("openfast", {})
    if overrides:
        if not isinstance(overrides, dict):
            raise ValidationError("overrides.openfast must be a mapping")
        files = {"fst": fst, "inflowwind": inflow}
        for name, fields in overrides.items():
            if name not in files or not isinstance(fields, dict):
                raise ValidationError(f"unsupported OpenFAST override target: {name}")
            for field, value in fields.items():
                patch_openfast_field(files[name], field, value); patched.append({"file": files[name].relative_to(workspace.resolve()).as_posix(), "field": field})
    unresolved: dict[str, str] = {}
    if controller["kind"] != "none" and (controller.get("omega_pc") is not None or controller.get("zeta_pc") is not None or controller.get("overrides")):
        unresolved["controller"] = "ROSCO/controller parameter mapping requires the controller integration layer; copied template settings were preserved"
    if case.scientific["numerics"].get("actuator_dt_s") is not None:
        unresolved["actuator"] = "no actuator update field is represented by the current ROSCO/OpenFAST template"
    metadata = {"case_id": case.case_id, "campaign_provenance": case.provenance, "resolved_scientific_case": case.normalized(), "openfast_template_id": template_id, "template_path": str(template), "template_checksum_sha256": template_checksum, "primary_fst": relative_fst.as_posix(), "integration_dt_s": case.scientific["numerics"]["integration_dt_s"], "output_dt_s": case.scientific["numerics"].get("output_dt_s"), "duration_s": case.scientific["numerics"]["duration_s"], "clock_mapping": {"integration_dt_s": "OpenFAST .fst DT", "output_dt_s": "OpenFAST .fst DT_Out", "controller_dt_s": "ServoDyn DLL_DT for ROSCO Bladed-DLL", "actuator_dt_s": "unmapped by current controller architecture", "wind_dt_s": "TurbSim realization input, not patched here", "wave_dt_s": "SeaState WaveDT when explicitly configured; otherwise template policy"}, "wind_kind": wind["kind"], "wind_realization_id": wind_id, "wind_bts_checksum_sha256": wind_checksum, "wave_kind": wave_realization.kind, "wave_realization_id": wave_realization.wave_id, "wave_scientific_parameters": wave_realization.content, "seastate_file": _seastate_path(fst).relative_to(workspace.resolve()).as_posix(), "controller_configuration": controller, "unresolved": unresolved, "patched_fields": patched, "preparation_identity": identity, "status": "prepared" if not unresolved else "prepared_with_unresolved_dependencies"}
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return PreparedOpenFASTCase(case, workspace, fst, metadata_path, False)
