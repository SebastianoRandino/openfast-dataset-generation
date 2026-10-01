"""Materialize a separate pinned v5 deck; never reads or modifies the validated v4 deck.

Usage: python scripts/materialize_iea15mw_v5.py SOURCE_GIT_REPO NEW_DEST ROSCO_LIBRARY
SOURCE_GIT_REPO is a checkout of https://github.com/IEAWindSystems/IEA-15-240-RWT.
All source content is read from committed objects, ignoring working-tree changes.
"""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

REVISION = "86d51c8a1ee65be4f3686087a5c443c0b57e5cfb"
BASE = "OpenFAST/IEA-15-240-RWT"
SEMI = BASE + "-UMaineSemi"


def materialize(source: Path, destination: Path, rosco: Path) -> None:
    if destination.exists():
        raise ValueError("destination exists; choose a new directory (templates are immutable)")
    if not rosco.is_file():
        raise ValueError("ROSCO library does not exist")
    archive = subprocess.run(["git", "-C", str(source), "archive", REVISION, BASE, SEMI],
                             check=True, capture_output=True).stdout
    destination.mkdir(parents=True)
    # Pinned Git archive contains only regular files/directories with relative names.
    with tarfile.open(fileobj=io.BytesIO(archive)) as tree:
        for member in tree.getmembers():
            if member.isfile():
                path = destination / member.name
                if not path.resolve().is_relative_to(destination.resolve()):
                    raise ValueError("archive path escapes destination")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(tree.extractfile(member).read())

    def edit(relative: str, *, before=None, after=None, remove=()):
        path = destination / relative
        lines = path.read_text().splitlines()
        result = []
        found = set()
        for line in lines:
            parts = line.split()
            label = parts[1] if len(parts) > 1 else ""
            if before and label in before:
                result.extend(before[label]); found.add(label)
            if label not in remove:
                result.append(line)
            if after and label in after:
                result.extend(after[label]); found.add(label)
        expected = set(before or {}) | set(after or {})
        if found != expected:
            raise ValueError(f"unexpected pinned input layout in {relative}: {expected - found}")
        path.write_text("\n".join(result) + "\n")

    prefix = SEMI + "/IEA-15-240-RWT-UMaineSemi"
    edit(prefix + ".fst", before={"InterpOrder": ["1 ModCoupling - Legacy loose coupling"],
         "DT_UJac": ["1.0 RhoInf - Unused with loose coupling", "1e-4 ConvTol", "6 MaxConvIter"],
         "CompElast": ["1 NRotors"], "MHK": ["0 CompSoil"]},
         after={"MHK": ["False MirrorRotor"], "IceFile": ['"unused" SoilFile']})
    edit(prefix + "_ElastoDyn.dat", before={"TeetDOF": ["False PitchDOF - Pitch actuation disabled"],
         "PtfmRefzt": ["0 PtfmRefxt", "0 PtfmRefyt"]}, after={"TipMass(3)": [
         "0 PBrIner(1)", "0 PBrIner(2)", "0 PBrIner(3)",
         "0 BlPIner(1)", "0 BlPIner(2)", "0 BlPIner(3)"]})
    edit(prefix + "_ServoDyn.dat", after={"TPCOn": [
         "0 PitNeut(1)", "0 PitNeut(2)", "0 PitNeut(3)",
         "0 PitSpr(1)", "0 PitSpr(2)", "0 PitSpr(3)",
         "0 PitDamp(1)", "0 PitDamp(2)", "0 PitDamp(3)"]})
    edit(prefix + "_SeaState.dat", after={"WaveStMod": ["0 WvCrntMod - Simple superposition"]})
    edit(prefix + "_HydroDyn.dat", after={"AMMod": ["0 HstMod - Still-water hydrostatics"],
         "PtfmCOByt": ["0 NAddDOF - Six rigid-body modes only"]})
    edit(prefix + "_AeroDyn15.dat", remove=("Buoyancy",))

    blade = destination / (BASE + "/IEA-15-240-RWT_ElastoDyn_blade.dat")
    lines = blade.read_text().splitlines()
    # v5 removes PitchAxis from the ElastoDyn blade properties table.
    start = next(i for i, line in enumerate(lines) if "BlFract" in line)
    count = int(next(line.split()[0] for line in lines if "NBlInpSt" in line))
    for i in range(start, start + count + 2):
        parts = lines[i].split(); del parts[1]; lines[i] = "    ".join(parts)
    blade.write_text("\n".join(lines) + "\n")

    blade = destination / (BASE + "/IEA-15-240-RWT_AeroDyn15_blade.dat")
    lines = blade.read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if "BlSpn" in line)
    count = int(next(line.split()[0] for line in lines if "NumBlNds" in line))
    for i in range(start, start + count + 2):
        parts = lines[i].split()
        additions = ["t_c", "BlCpn", "BlCpt", "BlCan", "BlCat", "BlCam"] if i == start else (["(-)"] * 6 if i == start + 1 else ["0"] * 6)
        parts.insert(7, additions[0]); parts.extend(additions[1:]); lines[i] = "    ".join(parts)
    blade.write_text("\n".join(lines) + "\n")
    aero = destination / (prefix + "_AeroDyn15.dat")
    lines = aero.read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("TwrElev"))
    count = int(next(line.split()[0] for line in lines if "NumTwrNds" in line))
    lines[start] = "TwrElev TwrDiam TwrCd TwrTI TwrCb TwrCp TwrCa"
    lines[start + 1] = "(m) (m) (-) (-) (-) (-) (-)"
    for i in range(start + 2, start + 2 + count):
        lines[i] += " 0 0"
    aero.write_text("\n".join(lines) + "\n")
    servo = destination / (prefix + "_ServoDyn.dat")
    lines = servo.read_text().splitlines()
    for i, line in enumerate(lines):
        if " DLL_FileName " in line:
            lines[i] = '"../lib/libdiscon.so" DLL_FileName - Local bundled ROSCO dependency'
    servo.write_text("\n".join(lines) + "\n")
    library = destination / "OpenFAST/lib/libdiscon.so"
    library.parent.mkdir(); shutil.copyfile(rosco, library)
    manifest = {"template_id": "IEA15MW_VolturnUS_v5.0.0", "openfast_version": "5.0.0",
                "source_repository": "https://github.com/IEAWindSystems/IEA-15-240-RWT",
                "source_revision": REVISION,
                "files_sha256": {p.relative_to(destination).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sorted(destination.rglob("*")) if p.is_file()}}
    (destination / "template_provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    materialize(*(Path(arg).expanduser().resolve() for arg in sys.argv[1:]))
