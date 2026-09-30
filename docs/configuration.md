# Campaign configuration

The framework keeps three layers separate: a validated OpenFAST template on disk,
a portable scientific campaign YAML, and explicit module overrides.  YAML does not
try to copy every OpenFAST field.  Future case preparation will patch only the
deliberate `overrides` entries using module-aware code.

`configs/paths.yaml` is local and ignored.  It contains executable, template, ROSCO,
and output paths.  `configs/models/` and `configs/campaigns/` are portable and
version controlled.  A campaign points at a model metadata file using `model:`.

`numerics` names independent clocks: `integration_dt_s`, `output_dt_s`,
`controller_dt_s`, `actuator_dt_s`, `wind_dt_s`, `wave_dt_s`, duration, and optional
discard time.  They are intentionally not aliases.

Campaigns are specifications; `resolve_campaign` expands `case_groups` and their
Cartesian or paired sweeps into deterministic `case_00001` records.  A resolved
case is scientific metadata, not a generated OpenFAST directory.  Generated files,
simulation outputs, and reduced datasets will remain separate future stages.

For a compact illustrative profile, see `configs/campaigns/example_floating_turbulent.yaml`.
It is explicitly not a validated default.  The legacy-compatible profile is a
regression reference, not a framework default.
