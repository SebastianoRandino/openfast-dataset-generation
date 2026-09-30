# Incremental migration plan

This plan intentionally stops before implementation choices that could alter scientific behavior.

1. **Freeze references.** Select the authoritative legacy DoE profile(s), template revision, executable versions, and small representative successful cases. Store checksums and curated golden CSV/input/output summaries under version control; keep large outputs out of Git.
2. **Characterize legacy behavior.** Add regression tests for each DoE generator independently: exact CSV bytes or normalized rows, column order, case IDs, splits, and seeds. Add parser tests for TurbSim/OpenFAST label patching and folder naming.
3. **Migrate configuration loading only.** Extend ignored machine-path configuration and versioned scientific profile files without changing values. Validate paths and template labels before execution.
4. **Migrate DoE one profile at a time.** For each approved profile: legacy behavior -> regression test -> package implementation -> numerical/table comparison -> retain the legacy script until equivalent. Do not consolidate profiles during this step.
5. **Migrate campaign wind preparation.** Resolve cases into scientifically unique wind realizations, keeping campaign metadata separate from `wind.turbsim.overrides`. Add a pure TurbSim input renderer, wind manifest writers, and golden rendered-input tests. Then add execution plumbing, comparing a few generated input files and seeds before any campaign.
6. **Migrate case preparation and ROSCO.** Test copied-tree layout, symlink/path behavior, exact patched InflowWind/SeaState/ROSCO fields, and DISCON generation for a small baseline. Compare input files and selected DISCON values numerically.
7. **Migrate OpenFAST runner/status collection.** Add a dry-run case-preparation mode first, then an opt-in one-case integration comparison. Do not run a full campaign in tests.
8. **Migrate diagnostics and free decay separately.** Reproduce free-decay rendered inputs and selected response metrics before migrating plotting. Keep plots presentation-only unless used as a regression artifact.
9. **Migrate controller/ROM pipeline separately.** Reproduce controller TurbSim manifest, HydroDyn/SeaState inputs, wave-load schemas, rotor-mask output, and combined disturbance signal ordering. Confirm the wave table before declaring it scientific.
10. **Remove duplication only after evidence.** Once each replacement has golden tests and numerical comparison against the approved reference, deprecate—not delete—the matching legacy entry point. Remove duplicated shared code only after all callers use the tested utility.

At every stage follow: **legacy behavior -> regression test -> new implementation -> numerical comparison -> remove legacy duplication**. Any mismatch in values, schema, units, seeds, names, channels, or template settings is a stop condition requiring human review.
