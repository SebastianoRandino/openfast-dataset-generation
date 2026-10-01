"""Regression against byte-exact pinned official IEA BeamDyn input fixtures."""

import hashlib
import importlib.util
import io
import subprocess
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/iea15mw_beamdyn"


@pytest.fixture
def recipe():
    spec = importlib.util.spec_from_file_location(
        "v5_recipe", ROOT / "scripts/materialize_iea15mw_v5.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_primary_migration_only_removes_obsolete_records_and_restores_parser_order(
    tmp_path, recipe
):
    original = (FIXTURES / "IEA-15-240-RWT_BeamDyn.dat").read_bytes()
    assert (
        hashlib.sha256(original).hexdigest()
        == "26ffeb76c34a8dc176e83f19b4bd47cbf4d15b946c13e69e43d253f2dcc83428"
    )
    path = tmp_path / "primary.dat"
    path.write_bytes(original)
    recipe.adapt_beamdyn_primary(path)
    lines = original.splitlines(keepends=True)
    start = next(i for i, line in enumerate(lines) if b"PITCH ACTUATOR PARAMETERS" in line)
    assert path.read_bytes() == b"".join(lines[:start] + lines[start + 5 :])
    migrated = path.read_text().splitlines()
    assert not any(
        field in path.read_text()
        for field in ("PITCH ACTUATOR PARAMETERS", "UsePitchAct", "PitchJ", "PitchK", "PitchC")
    )
    cursor = next(
        i
        for i, line in enumerate(migrated)
        if len(line.split()) > 1 and line.split()[1] == "BldFile"
    )
    assert "OUTPUTS" in migrated[cursor + 1]
    # Consume records positionally, as BD_ReadPrimaryFile does in v5.0.0.
    records = [line.split() for line in migrated[cursor + 2 : cursor + 7]]
    assert [row[1] for row in records[:4]] + [records[4][0]] == [
        "SumPrint",
        "OutFmt",
        "NNodeOuts",
        "OutNd",
        "OutList",
    ]
    assert int(records[2][0]) == 0
    with pytest.raises(ValueError, match="section"):
        recipe.adapt_beamdyn_primary(path)


def test_official_blade_properties_and_active_damping_are_byte_identical(tmp_path, recipe):
    original = (FIXTURES / "IEA-15-240-RWT_BeamDyn_blade.dat").read_bytes()
    assert (
        hashlib.sha256(original).hexdigest()
        == "bbc76b78ba2a09fbe863663dbb807e9cdbe000af423441580874e694bce28608"
    )
    path = tmp_path / "blade.dat"
    path.write_bytes(original)
    recipe.adapt_beamdyn_blade(path)
    migrated = path.read_bytes()
    start = migrated.index(b"------ Modal Damping")
    end = migrated.index(b" ---------------------- DISTRIBUTED PROPERTIES")
    # Stronger than numerical equality: station locations and all matrix values
    # retain their original bytes, as do damp_type and the six active mu values.
    assert migrated[:start] + migrated[end:] == original
    assert b"1   damp_type" in migrated
    assert b"3 n_modes" in migrated and b"0.1 0.2 0.3 zeta" in migrated


def test_full_materialization_does_not_touch_source_or_frozen_v4(tmp_path, recipe, monkeypatch):
    source, frozen, target = tmp_path / "source", tmp_path / "frozen-v4", tmp_path / "new-v5"
    source.mkdir()
    frozen.mkdir()
    for name in ("IEA-15-240-RWT_BeamDyn.dat", "IEA-15-240-RWT_BeamDyn_blade.dat"):
        (source / name).write_bytes((FIXTURES / name).read_bytes())
        (frozen / name).write_bytes((FIXTURES / name).read_bytes())
    original = {p: p.read_bytes() for directory in (source, frozen) for p in directory.iterdir()}
    prefix = recipe.SEMI + "/IEA-15-240-RWT-UMaineSemi"
    files = {
        prefix + ".fst": b"1 InterpOrder\n1 DT_UJac\n1 CompElast\n0 MHK\nunused IceFile\n",
        prefix + "_ElastoDyn.dat": b"False TeetDOF\n0 PtfmRefzt\n0 TipMass(3)\n",
        prefix + "_ServoDyn.dat": b"0 TPCOn\nunused DLL_FileName \n",
        prefix + "_SeaState.dat": b"0 WaveStMod\n",
        prefix + "_HydroDyn.dat": b"0 AMMod\n0 PtfmCOByt\n",
        prefix
        + "_AeroDyn15.dat": b"False Buoyancy\n1 NumTwrNds\nTwrElev TwrDiam TwrCd TwrTI TwrCb\n(m) (m) (-) (-) (-)\n0 1 1 1 1\n",
        recipe.BASE
        + "/IEA-15-240-RWT_ElastoDyn_blade.dat": b"1 NBlInpSt\nBlFract PitchAxis StrcTwst BMassDen FlpStff EdgStff\n(-) (-) (deg) (kg/m) (Nm2) (Nm2)\n0 .25 0 1 1 1\n",
        recipe.BASE
        + "/IEA-15-240-RWT_AeroDyn15_blade.dat": b"1 NumBlNds\nBlSpn BlCrvAC BlSwpAC BlCrvAng BlTwist BlChord BlAFID BlCb BlCenBn BlCenBt\n(m) (m) (m) (deg) (deg) (m) (-) (-) (m) (m)\n0 0 0 0 0 1 1 0 0 0\n",
    }
    files.update(
        {recipe.BASE + "/" + p.name: data for p, data in original.items() if p.parent == source}
    )
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w") as tree:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tree.addfile(info, io.BytesIO(data))
    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kwargs: SimpleNamespace(stdout=archive.getvalue())
    )
    rosco = tmp_path / "rosco.so"
    rosco.write_bytes(b"fake-library-for-pure-unit-test")
    recipe.materialize(source, target, rosco)
    assert all(path.read_bytes() == data for path, data in original.items())
    assert "UsePitchAct" not in (target / recipe.BASE / "IEA-15-240-RWT_BeamDyn.dat").read_text()
    assert (target / "template_provenance.json").is_file()
