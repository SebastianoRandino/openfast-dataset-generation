# OpenFAST Dataset Generation

Reproducible OpenFAST/TurbSim campaign generator used for the IEA 15 MW + UMaine VolturnUS floating-wind-turbine studies.

The current validated reference is the **OpenFAST v5.0.0 structural comparison campaign** (ElastoDyn vs BeamDyn). The repository contains the campaign configuration, case-generation code, tests, provenance and the ED/BeamDyn comparison analysis. Large generated files (`.bts`, `.outb`, prepared cases and logs) are intentionally not committed.


## Self-contained bottom-fixed and floating setup

Complete IEA 15 MW bottom-fixed monopile and floating VolturnUS inputs are now
included under `templates/`, together with ROSCO, TurbSim, Linux/WSL2 OpenFAST
4.1.1 and 5.0.0 binaries, pinned solver source archives and license notices.
No separate model or solver checkout is needed. System runtime libraries and
Python packages remain prerequisites; see [standalone setup](docs/standalone_setup.md).

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python scripts/run_bundled_campaign.py configs/campaigns/bundled_fixed_smoke.yaml --output-root outputs/fixed-smoke --run
.venv/bin/python scripts/run_bundled_campaign.py configs/campaigns/bundled_floating_smoke.yaml --output-root outputs/floating-smoke --run
```

Use `configs/paths.bundled.yaml` for repository-local dependencies. The original
custom v4 floating template is retained separately. Smoke cases demonstrate
startup, not production accuracy. For turbulent wind generation and regular
waves, run `bundled_floating_turbulent_smoke.yaml` with the same runner.

## Reproducible workflow

The validated structural campaign follows this reproducible workflow:

```text
campaign YAML
   -> 3 deterministic TurbSim wind fields
   -> 6 OpenFAST cases (LC1/LC2/LC3 x ED/BD)
   -> sequential OpenFAST execution
   -> raw .outb files
   -> ED/BD post-processing
```

The validated production settings are documented in `docs/structural_comparison_v5.md`. The completed reference execution and its exact provenance are in `docs/structural_comparison_production_execution.md` and `docs/structural_comparison_production_provenance.json`.

## Requirements

Use Linux/WSL2 and Python >= 3.10. OpenFAST and TurbSim are external executables.

The validated structural campaign requires:
- OpenFAST **v5.0.0**;
- a TurbSim executable;
- the pinned IEA-15-240-RWT source deck used by the materialization script;
- the ROSCO shared library used by the IEA model.

Python setup:

```bash
git clone https://github.com/SebastianoRandino/openfast-dataset-generation.git
cd openfast-dataset-generation

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"

pytest
```

## 1. Select bundled or local paths

For the included dependencies, pass `--paths configs/paths.bundled.yaml` to the
preparation/execution scripts. To use another installation, configure local paths.
Machine-specific paths are never committed:

```bash
cp configs/paths.example.yaml configs/paths.yaml
```

Edit `configs/paths.yaml` so that it points to your TurbSim/OpenFAST executables and local templates. In particular the structural campaign uses the template ID `IEA15MW_VolturnUS_v5.0.0`.

Example structure:

```yaml
executables:
  turbsim: /absolute/path/to/turbsim
  openfast:
    5.0.0: /absolute/path/to/openfast

templates:
  turbsim:
    legacy-iea15mw-turbsim-v2: /absolute/path/to/TurbSim.inp
  openfast:
    IEA15MW_VolturnUS_v5.0.0: /absolute/path/to/materialized-v5-template

outputs:
  root: ./outputs
```

The loader verifies the OpenFAST version before running the v5 campaign.

## 2. Materialize the validated v5 IEA-15MW template

The complete v5-compatible model is included in `templates/iea15mw-v5/`.
The script below is an optional way to materialize the pinned floating baseline
from a separate IEA-15-240-RWT checkout:

```bash
python scripts/materialize_iea15mw_v5.py \
    /path/to/IEA-15-240-RWT \
    /path/to/materialized-v5-template \
    /path/to/libdiscon.so
```

The source Git revision and the BeamDyn migration are pinned inside the script. See `docs/openfast_versions.md` and `docs/structural_comparison_v5.md` for the exact provenance and rationale.

## 3. Prepare the structural comparison

To generate/reuse the three deterministic wind realizations and prepare all six 400 s OpenFAST cases without running them:

```bash
python scripts/prepare_structural_comparison.py \
    --paths configs/paths.yaml \
    --output-root outputs/structural-comparison-v5-production-dt001
```

This is safe by default: it prepares the production cases but does not launch the six full simulations.

For the short LC1 ED/BD smoke test:

```bash
python scripts/prepare_structural_comparison.py \
    --paths configs/paths.yaml \
    --output-root outputs/structural-comparison-v5-smoke \
    --smoke
```

## 4. Run the six validated production cases

After preparation, run:

```bash
python scripts/run_structural_comparison.py \
    --paths configs/paths.yaml \
    --output-root outputs/structural-comparison-v5-production-dt001
```

The runner executes LC1_ED, LC1_BD, LC2_ED, LC2_BD, LC3_ED and LC3_BD sequentially and stops on the first failed OpenFAST run. Existing valid wind/case artifacts are reused by the underlying execution layer.

Validated numerical settings are defined by `configs/campaigns/structural_comparison_v5.yaml`; do not edit generated OpenFAST files by hand.

The reference production campaign has 40,001 samples per case at 0.01 s over 0-400 s.

## 5. Post-process ED vs BeamDyn

After all six outputs are present:

```bash
python analysis/structural_comparison/analyze.py \
    --raw-dir outputs/structural-comparison-v5-production-dt001 \
    --output-dir analysis/structural_comparison
```

The analysis keeps raw files read-only, uses the 100-400 s analysis window, validates the production checksums/time vectors, applies the documented ED/BD channel mapping and produces statistics, PSD summaries and figures.

The channel/frame/unit mapping is documented in `analysis/structural_comparison/channel_mapping.md`. The reference results are summarized in `analysis/structural_comparison/report.md`.

## Validated campaign at a glance

The six cases are:
- LC1: URef = 5 m/s, Hs = 1.0 m, Tp = 6.0 s, ED and BD;
- LC2: URef = 10 m/s, Hs = 2.0 m, Tp = 8.0 s, ED and BD;
- LC3: URef = 14 m/s, Hs = 3.0 m, Tp = 10.0 s, ED and BD.

Common production settings include OpenFAST v5.0.0, ModCoupling=3, DT=DT_Out=0.01 s, TMax=400 s, MaxConvIter=6, ConvTol=1e-4, BeamDyn DTBeam=0.01 s, TurbSim DT=0.05 s and WaveDT=0.25 s. ROSCO/ServoDyn remain inherited from the validated template.

## Repository layout

```text
configs/
  campaigns/       scientific campaign definitions
  models/          model/version metadata
docs/              technical decisions, validation and provenance
scripts/           executable workflow entry points
src/openfast_dataset/
                   reusable campaign/wind/wave/OpenFAST implementation
analysis/
  structural_comparison/
                   reproducible ED/BD analysis and reference results
tests/             unit/regression tests (do not run OpenFAST)
templates/          complete fixed/floating OpenFAST inputs and TurbSim baseline
vendor/             versioned Linux solvers, source archives, licenses and hashes
outputs/            generated data; ignored by Git
```

## Important reproducibility rules

Do not commit generated `.bts`, `.outb`, prepared case directories, logs, machine-specific `configs/paths.yaml`, or ad hoc local binaries. The deliberately distributed solvers in `vendor/`
and ROSCO libraries in `templates/` have pinned sources, licenses and checksums. Do not silently change seeds, time steps, controller settings, template values or output channels. Scientific changes belong in versioned campaign/model configuration and should be tested.

## Documentation

Start with:
- `docs/structural_comparison_v5.md` — structural campaign definition and BeamDyn setup;
- `docs/structural_comparison_production_execution.md` — validated 6 x 400 s execution;
- `docs/structural_comparison_production_provenance.json` — machine-readable provenance;
- `docs/openfast_versions.md` — v4/v5 template/version handling;
- `docs/configuration.md` — general campaign configuration;
- `analysis/structural_comparison/report.md` — ED/BD results;
- `analysis/structural_comparison/channel_mapping.md` — channel equivalence and unit conversions.

Historical diagnostic notes are retained under `docs/` because they explain why the validated global time step is 0.01 s and document the BeamDyn tight-coupling investigation.
