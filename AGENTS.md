# Agent Guidance

## Project objective
Build a general, reproducible framework for generating OpenFAST simulation campaigns and identification datasets. The primary current application is the IEA 15 MW + VolturnUS floating turbine, but the architecture must support other models and fixed or floating configurations. Do not tie the framework to one DoE.

## Core architecture

```text
CampaignSpecification
        |
        v
ResolvedCase
        |
        v
dependencies:
    WindRealization
    WaveRealization       [future/incomplete]
        |
        v
prepared OpenFAST case
        |
        v
simulation -> postprocessing -> versioned reduced dataset
```

## Scientific invariants
Do not silently change DoE points, seeds or seed derivation, splits, integration/output/controller/actuator/wind/wave timesteps, duration, TurbSim or wave settings, controller tuning, OpenFAST modules, output channels, template scientific values, platform initial conditions, or downstream naming/schema. Intentional scientific changes must be explicit and tested.

## Migration rule

```text
legacy behavior -> characterize -> regression test -> new implementation
-> numerical/configuration comparison -> only then remove duplication
```

Never clean up scientific values merely because they look suspicious.

## Configuration philosophy
Frequently varied scientific parameters belong in campaign/model YAML. Detailed validated OpenFAST/TurbSim baselines belong in templates. Machine-specific paths belong in ignored local configuration. Do not reproduce every OpenFAST input field in YAML.

Keep these time scales distinct: `integration_dt`, `output_dt`, `controller_dt`, `actuator_dt`, `wind_dt`, and `wave_dt`. Never silently assume they are equal.

## Dependency identity and metadata
Wind, wave, and other realizations represent physical/generated dependencies, not simulation cases. Different controllers or waves can consume the same wind realization. Only parameters that can change the generated wind field belong in its scientific hash. DLC labels, split, case ID, and descriptive tags must remain outside physical dependency hashes unless they genuinely alter generation.

For IEC TurbSim winds, keep these domain concepts distinct:

- `spectral_model` maps to TurbSim `TurbModel` (for example `IECKAI`).
- `iec_wind_type` maps to `IEC_WindType` (for example `NTM`, `ETM`, `1ETM`).
- `iec_turbulence_class` maps to `IECturbc` (for example `A`, `B`, `C`).

The renderer performs this final mapping; raw labels are not the campaign-domain design.

## Execution safety and generated files
Unit tests must not execute TurbSim, OpenFAST, HydroDyn, or ROSCO. External executable integration must be explicit and opt-in; never launch a full campaign in automated tests. Do not commit `.bts`, `.out`, `.outb`, large generated cases, logs, machine-specific paths, or secrets.

## Working with legacy code
Legacy scripts are scientific references until equivalence is demonstrated. Do not delete or rewrite them merely because the package implementation exists.

## Agent workflow
Before modifying code:

1. Read `AGENTS.md`.
2. Inspect `git status` and recent commits.
3. Preserve uncommitted user or agent work.
4. Read relevant migration/configuration documentation.
5. Run existing tests.

Before committing:

1. Inspect the full diff.
2. Run the full test suite in the project virtual environment.
3. Run `git diff --check`.
4. Check for generated/large files, machine-specific paths, secrets, and accidental scientific changes.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
pytest
```

Do not commit `.venv` and do not use a permanent `PYTHONPATH=src` workaround.
