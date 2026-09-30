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
`numerics` is the only source of simulation clocks: controller and actuator
configuration contains model/physical settings, never duplicate update steps.
Platform kind and waves are also independent: a fixed-bottom model can use waves
and active hydrodynamics when its template/modules support them.

Campaigns are specifications; `resolve_campaign` expands `case_groups` and their
Cartesian or paired sweeps into deterministic `case_00001` records.  A resolved
case is scientific metadata, not a generated OpenFAST directory.  Generated files,
simulation outputs, and reduced datasets will remain separate future stages.

## Step 3A wind planning

`resolve_campaign` produces `ResolvedCase` objects. The pure wind API converts
those cases into `WindRealization` objects, deduplicates them by their effective
wind-generation parameters, renders TurbSim input text from an explicitly supplied
template, and writes a JSON/CSV wind manifest. This stage does not discover machine
paths, execute TurbSim, or create BTS files.

Wind realization identity represents the physics and generation configuration that
determines the wind field, not the simulation case that consumes it. Campaign
metadata such as DLC labels, split, controller settings, wave settings, and case IDs
is excluded. For example, the same turbulent wind used by 3 controllers under 2 wave
conditions represents 6 simulation cases but only 1 wind realization.

The wind configuration keeps three concerns explicit:

- `wind.metadata` contains campaign labels and provenance that must not affect wind identity.
- `wind.turbsim.overrides` contains only deliberate TurbSim parameter overrides; these are part of wind identity and are validated against the concrete template during rendering.
- `wind.template_id` is a portable logical reference. Resolving it to a machine-specific template path belongs to a future preparation/execution layer; Step 3A accepts template text or a concrete path directly.

For a compact illustrative profile, see `configs/campaigns/example_floating_turbulent.yaml`.
It is explicitly not a validated default.  The legacy-compatible profile is a
regression reference, not a framework default.
