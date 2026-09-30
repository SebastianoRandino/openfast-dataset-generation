# Codex refactoring task

Refactor the research scripts in `legacy/` into `src/openfast_dataset/` while preserving validated scientific behavior.

## Main workflow
1. Generate the Design of Experiments.
2. Generate unique TurbSim turbulent wind fields.
3. Prepare OpenFAST cases from templates.
4. Configure environmental conditions and ROSCO.
5. Run OpenFAST cases in parallel.
6. Collect status and outputs.
7. Post-process simulations into reduced datasets.

Secondary workflows are controller/ROM wind-wave generation and free-decay validation.

## Rules
- Inspect all legacy code before changing scientific logic.
- Do not silently alter numerical values, distributions, seeds, units, schemas, OpenFAST settings, or dataset split semantics.
- Consolidate duplicated DoE generators only after documenting differences and adding regression tests.
- Remove hard-coded machine paths; use local config, environment variables, or CLI arguments.
- Keep Python dependencies separate from OpenFAST, TurbSim and ROSCO.
- Extract shared text patching, configuration, logging, deterministic seeds, paths and parallel execution.
- Keep controller-specific workflows separate except for genuinely shared utilities.
- Never commit generated `.bts`, `.outb`, case folders or logs.
- Keep CLI scripts thin; implementation belongs in the package.
- Before deleting legacy code, demonstrate equivalent intended behavior.

## First milestone
Compare all legacy DoE generators, document their differences, identify the intended CSV schema and split semantics, write regression tests, then implement one canonical generator.
