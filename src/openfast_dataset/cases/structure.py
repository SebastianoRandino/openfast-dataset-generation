"""Explicit v5 structural variants and raw-output selection in copied cases."""

from __future__ import annotations

import os
from pathlib import Path

from openfast_dataset.campaign.models import ValidationError, required_openfast_version

COMMON_ED_CHANNELS = (
    "GenSpeed",
    "RotSpeed",
    "Azimuth",
    "BldPitch1",
    "BldPitch2",
    "BldPitch3",
    "PtfmSurge",
    "PtfmSway",
    "PtfmHeave",
    "PtfmRoll",
    "PtfmPitch",
    "PtfmYaw",
    "TTDspFA",
    "TTDspSS",
    "YawBrFxp",
    "YawBrFyp",
    "YawBrFzp",
    "YawBrMxp",
    "YawBrMyp",
    "YawBrMzp",
)
ED_BLADE_CHANNELS = tuple(
    f"{quantity}{blade}"
    for blade in range(1, 4)
    for quantity in (
        "TipDxc",
        "TipDyc",
        "TipDzc",
        "TipDxb",
        "TipDyb",
        "RootFxb",
        "RootFyb",
        "RootFzb",
        "RootMxb",
        "RootMyb",
        "RootMzb",
    )
)
ED_CHANNELS = COMMON_ED_CHANNELS + ED_BLADE_CHANNELS
BD_CHANNELS = (
    "RootFxr",
    "RootFyr",
    "RootFzr",
    "RootMxr",
    "RootMyr",
    "RootMzr",
    "TipTDxr",
    "TipTDyr",
    "TipTDzr",
    "TipRDxr",
    "TipRDyr",
    "TipRDzr",
)


def patch_outlist(path: Path, channels: tuple[str, ...], *, clear_nodal: bool = False) -> None:
    """Select primary channels and optionally clear additional nodal output lists."""
    lines = path.read_text().splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip().startswith("OutList")]
    if not starts:
        raise ValidationError(f"missing OutList in {path.name}")
    for start in reversed(starts if clear_nodal else starts[:1]):
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("END")), None)
        if end is None:
            raise ValidationError(f"unterminated OutList in {path.name}")
        selected = channels if start == starts[0] else ()
        lines[start + 1 : end] = [f'"{channel}"' for channel in selected]
    path.write_text("\n".join(lines) + "\n")


def patch_structure(case, fst: Path, workspace: Path) -> list[dict[str, str]]:
    from .preparation import _referenced_file, patch_openfast_field

    scientific = case.scientific
    model = scientific.get("structural_model")
    profile = scientific.get("output_profile")
    if model is None and profile is None:
        return []
    if required_openfast_version(scientific["model_configuration"]) != "5.0.0":
        raise ValidationError("structural variants/output profile require OpenFAST 5.0.0")
    if model not in {"elastodyn", "beamdyn"}:
        raise ValidationError("structural_model must be elastodyn or beamdyn")
    patched = []

    def patch(path, field, value):
        patch_openfast_field(path, field, value)
        patched.append(
            {"file": path.resolve().relative_to(workspace.resolve()).as_posix(), "field": field}
        )

    ed = _referenced_file(fst, "EDFile")
    patch(fst, "CompElast", 2 if model == "beamdyn" else 1)
    for field in ("FlapDOF1", "FlapDOF2", "EdgeDOF"):
        patch(ed, field, model == "elastodyn")
    bd = None
    if model == "beamdyn":
        relative = scientific["model_configuration"].get("beamdyn_primary_file")
        if not relative:
            raise ValidationError("model metadata requires beamdyn_primary_file")
        bd = (workspace / relative).resolve()
        if not bd.is_relative_to(workspace.resolve()) or not bd.is_file():
            raise ValidationError("BeamDyn primary file must exist inside the copied template")
        _referenced_file(bd, "BldFile")
        for blade in range(1, 4):
            patch(fst, f"BDBldFile({blade})", os.path.relpath(bd, fst.parent))
        dt = scientific["numerics"].get("beamdyn_dt_s")
        if dt is None or dt <= 0:
            raise ValidationError("BeamDyn requires explicit positive numerics.beamdyn_dt_s")
        patch(bd, "DTBeam", dt)
    if profile is not None:
        if profile != "structural-comparison-v5":
            raise ValidationError("unsupported output_profile")
        patch(fst, "TStart", 0)
        for path, channels in (
            (ed, COMMON_ED_CHANNELS if model == "beamdyn" else ED_CHANNELS),
            (_referenced_file(fst, "AeroFile"), ("RtAeroMxh", "RtAeroFxh")),
        ):
            patch_outlist(path, channels, clear_nodal=True)
            patched.append(
                {"file": path.relative_to(workspace.resolve()).as_posix(), "field": "OutList"}
            )
        # ServoDyn's unchanged template OutList already supplies GenPwr/GenTq.
        if bd is not None:
            patch_outlist(bd, BD_CHANNELS, clear_nodal=True)
            patched.append(
                {"file": bd.relative_to(workspace.resolve()).as_posix(), "field": "OutList"}
            )
    return patched
