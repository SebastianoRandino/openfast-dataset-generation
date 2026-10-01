# Campaign configuration

The framework keeps three layers separate: a validated OpenFAST template on disk,
a portable scientific campaign YAML, and explicit module overrides.  YAML does not
try to copy every OpenFAST field.  Future case preparation will patch only the
deliberate `overrides` entries using module-aware code.

`configs/paths.yaml` is local and ignored.  It contains executable, template, ROSCO,
and output paths.  `configs/models/` and `configs/campaigns/` are portable and
version controlled.  A campaign points at a model metadata file using `model:`.

OpenFAST template and executable versions are selected explicitly; see
[versioned templates and provenance](openfast_versions.md).

`numerics` names independent clocks: `integration_dt_s`, `output_dt_s`,
`actuator_dt_s`, `wind_dt_s`, `wave_dt_s`, duration, and optional discard time.
They are intentionally not aliases. Controller timing is deliberately absent: it
is part of the validated OpenFAST model template in the current implementation.
Platform kind and waves are also independent: a fixed-bottom model can use waves
and active hydrodynamics when its template/modules support them.

Campaigns are specifications; `resolve_campaign` expands `case_groups` and their
Cartesian or paired sweeps into deterministic `case_00001` records.  A resolved
case is scientific metadata, not a generated OpenFAST directory.  Generated files,
simulation outputs, and reduced datasets will remain separate future stages.

## TurbSim wind lifecycle

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
- `wind.template_id` is a portable logical reference. `configs/paths.yaml` resolves it through `templates.turbsim`; its absolute local path never contributes to a scientific hash.

For IEC turbulent winds, the domain keeps three distinct concepts explicit:
`wind.spectral_model` maps to TurbSim `TurbModel` (for example `IECKAI`),
`wind.iec_wind_type` maps to `IEC_WindType` (for example `NTM`, `ETM`, or
`1ETM`), and `wind.iec_turbulence_class` maps to `IECturbc` (for example
`A`, `B`, or `C`). The renderer performs this final label mapping. All three
values contribute to wind identity when they can change the generated field.

Step 3B supplies an explicit per-realization lifecycle:
`ResolvedCase -> WindRealization -> prepare_turbsim_realization -> run_turbsim -> wind.bts`.
Preparation resolves the ignored local template and executable, renders
`outputs/wind/wind_<scientific-hash>/turbsim.inp`, and writes initial metadata.
Execution is a separate opt-in subprocess in that directory. TurbSim's natural
`turbsim.bts` output is normalized to stable `wind.bts`; the log and checksummed
provenance remain alongside it. One BTS can therefore be shared by many OpenFAST
cases. A checksum-consistent existing BTS is reused; an inconsistent one requires
explicit `force=True` to rebuild.

Unit tests use fake executables only. Real TurbSim runs are deliberate integration
actions, never a test-suite side effect. Generated outputs remain ignored.

For a compact illustrative profile, see `configs/campaigns/example_floating_turbulent.yaml`.
It is explicitly not a validated default.  The legacy-compatible profile is a
regression reference, not a framework default.

## Controller policy

The current controller API is `controller: {kind: template}`. Case preparation
copies the selected OpenFAST model tree and preserves its ROSCO, ServoDyn, and
DISCON configuration byte-for-byte. Controller retuning, DISCON generation, and
controller-timestep changes are intentionally outside the current implementation;
they can be added later as a dedicated controller configuration layer.
