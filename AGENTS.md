# Development and scientific invariants

This repository generates reproducible OpenFAST simulation campaigns and reduced analysis products. The current validated reference is the IEA 15 MW + VolturnUS OpenFAST v5 structural comparison.

## Scientific invariants

Do not silently change DoE/campaign points, seeds, integration/output/wind/wave/BeamDyn time steps, duration, TurbSim or wave settings, controller settings, OpenFAST modules, output channels, template values, platform initial conditions, or downstream schemas. Intentional scientific changes must be explicit, documented and tested.

Frequently varied scientific parameters belong in campaign/model YAML. Detailed validated OpenFAST/TurbSim baselines belong in templates. Machine-specific paths belong in ignored local configuration.

Wind and wave realizations are physical/generated dependencies rather than simulation-case metadata. Parameters that do not change the generated field must not alter dependency identity.

## Execution safety

Unit tests must not execute TurbSim, OpenFAST, HydroDyn or ROSCO. External executable integration is explicit and opt-in. Never launch a full campaign as a test-suite side effect.

Do not commit generated `.bts`, `.out`, `.outb`, prepared case trees, logs, local binaries, machine-specific paths or secrets.

## Development check

Before committing code changes:

```bash
source .venv/bin/activate
pytest
ruff check .
git diff --check
git status
```

Inspect the full diff and confirm that no scientific setting changed unintentionally.
