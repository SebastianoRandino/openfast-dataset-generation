# OpenFAST Dataset Generation

Reproducible workflow for generating OpenFAST simulation datasets for wind-turbine system identification.

## Scope

This repository contains the data-generation side of the workflow:

1. Design of Experiments (DoE)
2. TurbSim wind generation
3. OpenFAST case preparation
4. OpenFAST execution
5. validation and diagnostics
6. post-processing toward reduced datasets

The identification algorithms themselves belong in a separate repository.

## Repository layout

- `configs/` — versioned simulation and DoE configuration; machine-specific paths are kept local.
- `src/openfast_dataset/` — reusable Python package.
- `scripts/` — thin entry points for individual workflow stages.
- `legacy/` — original research scripts kept temporarily as regression references during refactoring.
- `tests/` — tests that do not require running OpenFAST.
- `data/` — small manifests/DoE tables only.
- `outputs/` — generated simulations and large outputs; ignored by Git.

## WSL2 / Linux setup

OpenFAST and TurbSim are external executables and are not Python dependencies. Copy:

```bash
cp configs/paths.example.yaml configs/paths.yaml
```

and edit the local paths to your OpenFAST/TurbSim installations. `configs/paths.yaml` is intentionally ignored by Git.

Install the Python package in editable mode:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Refactoring status

The original scripts are preserved under `legacy/`. The new package is intentionally being migrated incrementally:

`legacy behavior -> regression test -> reusable module -> CLI -> validation -> remove legacy duplication`

Scientific behavior should not be changed silently during refactoring.

See `CODEX_REFACTOR_PROMPT.md` for the migration instructions.
