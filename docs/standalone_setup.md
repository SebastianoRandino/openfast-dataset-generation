# Self-contained Linux / WSL2 workflow

The repository includes both IEA 15 MW configurations: the **bottom-fixed
monopile** (SubDyn + HydroDyn, no moorings) and **floating VolturnUS / UMaineSemi**
(HydroDyn potential-flow data + MoorDyn). OpenFAST 5 inputs share the complete
rotor, airfoil, blade, tower and ROSCO performance data in `templates/iea15mw-v5/`.
The original custom floating v4 inputs are retained separately in
`templates/iea15mw-volturnus-v4/`. Generated BTS winds are intentionally generated
by TurbSim, rather than distributed with the models.

## Fresh clone

Run from the repository root on Linux x86_64 / WSL2 (bundled binaries were built
on Ubuntu 24.04). Install Python and system runtime libraries if needed:

```bash
sudo apt-get install python3-venv libgfortran5 liblapack3 libblas3
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python scripts/run_bundled_campaign.py configs/campaigns/bundled_fixed_smoke.yaml --output-root outputs/fixed-smoke --run
.venv/bin/python scripts/run_bundled_campaign.py configs/campaigns/bundled_floating_smoke.yaml --output-root outputs/floating-smoke --run
```

Both checks run for 5 s with steady 12 m/s wind and no waves. They demonstrate
startup and execution, not production accuracy or numerical convergence.
For the separate legacy v4 deck, use `bundled_floating_v4_smoke.yaml`.

`configs/paths.bundled.yaml` resolves every executable and template inside this
repository. No other project checkout or ignored `configs/paths.yaml` is needed.
Paths in this file are relative to the repository working directory.
The existing machine-specific path configuration remains available as an override.

## Generate data

Create a campaign YAML referencing either
`configs/models/iea15mw_monopile_v5.0.0.yaml` or
`configs/models/iea15mw_volturnus_v5.0.0.yaml`, following the existing
[configuration guide](configuration.md). For the copied custom v4 inputs use
`iea15mw_volturnus_v4.1.1_bundled.yaml`: the older frozen model checksum describes
the external tree including generated files, not this cleaned copy.

```bash
.venv/bin/python scripts/run_bundled_campaign.py YOUR_CAMPAIGN.yaml --output-root outputs/my-campaign --run
```

The runner resolves/deduplicates winds, generates required turbulent BTS files,
prepares each case and executes OpenFAST. Without `--run`, it only prepares cases;
`--run-winds` generates missing winds without executing OpenFAST. Simulation
outputs, wind files and runtime metadata stay in ignored `outputs/`.

`bundled_floating_turbulent_smoke.yaml` checks the complete TurbSim-to-OpenFAST
pipeline with a small 9x9 wind grid and regular waves. Its grid is for startup
verification only; choose and validate production settings explicitly.

## Solver sources and provenance

Working OpenFAST 4.1.1 / 5.0.0 and TurbSim binaries are in
`vendor/bin/linux-x86_64/`; ROSCO 2.10.1 is included in each model tree. System
shared libraries and Python packages remain installation prerequisites.
Native Windows/macOS executables are not included; use WSL2 for the bundled setup.

`vendor/manifest.json` records checksums, runtime dependencies and source commits.
`vendor/sources/` includes pinned OpenFAST and ROSCO source archives so rebuilding
does not require another checkout or network access:

```bash
sudo apt-get install cmake make gcc g++ gfortran liblapack-dev libblas-dev
.venv/bin/python scripts/build_bundled_solvers.py --jobs 2
```

The rebuild script requires Python 3.12+ for safe tar extraction. Rebuilding
changes executable checksums; record the new build provenance and repeat smoke
checks before treating that build as validated. Source/model licenses are in
`vendor/licenses/`. Model manifests record every distributed dependency.
The monopile follows the same v5 migration as the floating deck, plus SubDyn's
required zero rigid-body position (inactive for fixed bottom) and transition
piece ID 1 for the existing interface. Scientific source values are preserved.
