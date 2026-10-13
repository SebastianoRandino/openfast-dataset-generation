"""Rebuild Linux solvers from the included pinned source archives, without Git/network."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tarfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    work = root / "outputs" / "solver-build"
    binary = root / "vendor" / "bin" / "linux-x86_64"
    for version in ("5.0.0", "4.1.1"):
        source = work / f"openfast-{version}" / "source"
        source.mkdir(parents=True, exist_ok=True)
        with tarfile.open(root / "vendor" / "sources" / f"openfast-{version}.tar.gz") as archive:
            archive.extractall(source, filter="data")
        build = source.parent / "build"
        subprocess.run(
            [
                "cmake",
                "-S",
                str(source),
                "-B",
                str(build),
                "-DCMAKE_BUILD_TYPE=Release",
                "-DBUILD_TESTING=OFF",
                f"-DGIT_DESCRIBE=v{version}",
                "-DDOUBLE_PRECISION=ON",
                "-DOPENMP=OFF",
            ],
            check=True,
        )
        subprocess.run(
            [
                "cmake",
                "--build",
                str(build),
                "--target",
                "openfast",
                "turbsim",
                "--parallel",
                str(args.jobs),
            ],
            check=True,
        )
        shutil.copy2(build / "glue-codes/openfast/openfast", binary / f"openfast-{version}")
        if version == "4.1.1":
            shutil.copy2(build / "modules/turbsim/turbsim", binary / "turbsim")
    source = work / "rosco-2.10.1" / "source"
    source.mkdir(parents=True, exist_ok=True)
    with tarfile.open(root / "vendor/sources/rosco-2.10.1.tar.gz") as archive:
        archive.extractall(source, filter="data")
    build = source.parent / "build"
    subprocess.run(
        [
            "cmake",
            "-S",
            str(source / "rosco/controller"),
            "-B",
            str(build),
            "-DCMAKE_BUILD_TYPE=Release",
        ],
        check=True,
    )
    subprocess.run(["cmake", "--build", str(build), "--parallel", str(args.jobs)], check=True)
    library = next(build.rglob("libdiscon.so"))
    for destination in (
        "templates/iea15mw-v5/OpenFAST/lib/libdiscon.so",
        "templates/iea15mw-volturnus-v4/lib/libdiscon.so",
    ):
        shutil.copy2(library, root / destination)
    print(
        "Rebuilt solvers. Binary checksums differ from the distributed manifest; record them before committing."
    )


if __name__ == "__main__":
    main()
