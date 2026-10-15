# Task: bottom-fixed Region-3 truth case for aerodynamic-map identification

## Scientific objective

Prepare one reproducible, high-fidelity **bottom-fixed IEA 15 MW** OpenFAST truth case for the first aerodynamic-map identification tests.

The first purpose is deliberately narrow: generate a controlled but realistic truth trajectory in Region 3 for testing recovery of a persistent `Cp(lambda,beta)` correction map under turbulent inflow. Do **not** add floating-platform dynamics in this task.

Read `AGENTS.md`, `README.md`, `docs/configuration.md`, and the existing v5 structural-comparison implementation before editing. Preserve all existing validated campaigns and their artifacts.

## Existing repository assets to reuse

Use the existing model metadata:

- `configs/models/iea15mw_monopile_v5.0.0.yaml`
- OpenFAST **v5.0.0**
- bundled IEA-15-240-RWT monopile template under `templates/iea15mw-v5/`
- existing ROSCO controller and model data from that template

There is already a validated 31 x 31 TurbSim NTM Region-3-type realization in the structural-comparison campaign:

- mean/reference wind speed: **14 m/s**
- TurbSim model: `IECKAI`
- `IEC_WindType = NTM`
- turbulence category/class: **B**
- reference height: **150 m**
- direction: **0 deg**
- shear exponent: **0.2**
- grid: **31 x 31**, **300 m x 300 m**
- TurbSim time step: **0.05 s**
- seed: **510003**
- generated duration: **460 s**
- usable duration: **400 s**
- template ID: `legacy-iea15mw-turbsim-v2`
- recorded wind ID: `wind_b5a3cb79b3fb0007`
- recorded BTS SHA256: `f926a4c1a871d70f83c027dfa80cd8c76d778b668c7feff3d01fb4e0fc4c3612`

Generated `.bts` files are intentionally not committed. Before regenerating this very large wind field, search the existing local `outputs/` tree for the recorded wind ID / checksum and reuse it if it is present and checksum-consistent. If it is absent, regenerate exactly the same deterministic realization using the existing wind lifecycle. Do not invent a new seed merely because the generated file is absent.

## New campaign

Add a new campaign configuration with a clear name, for example:

`configs/campaigns/cp_identification_bottom_fixed_region3.yaml`

This campaign must contain **one case only**.

### Turbine and structure

Use:

- model: `../models/iea15mw_monopile_v5.0.0.yaml`
- bottom-fixed monopile configuration
- `structural_model: elastodyn`
- preserve the official/validated ElastoDyn flexible blade, drivetrain, tower and substructure settings unless an explicit change is listed below
- keep `CompSub = 1` / SubDyn active
- do not enable BeamDyn in this first case

The reason for ElastoDyn is not that it is the highest possible structural fidelity; it is the chosen first truth model because it preserves a fully coupled aero-servo-elastic flexible turbine while remaining fast enough for repeated identification-development runs. BeamDyn can be added later as a harder structural-model-mismatch validation case without changing the wind realization.

### OpenFAST numerical clocks

Use the official monopile template integration step for this first truth case:

- OpenFAST integration step: **0.005 s**
- OpenFAST raw output step: **0.01 s**
- simulation duration: **400 s**

Do not make the OpenFAST integration step equal to the identification/controller step. The plant should remain integrated at high fidelity.

Use tight coupling if supported by the current validated v5 preparation path:

- `ModCoupling = 3`
- retain the existing validated convergence settings (`MaxConvIter = 6`, `ConvTol = 1e-4`) unless the 0.005-s ED case demonstrates that the template default is intentionally preferable; document any decision rather than silently changing it.

### Controller timing: critical requirement

The control signal must be a sampled-data signal with an explicit zero-order hold compatible with the later identification model.

Use:

- ROSCO communication/update interval: **0.05 s**
- `DLL_Ramp = False`

Thus the OpenFAST plant is integrated at 0.005 s, while ROSCO is updated every 0.05 s and its command is held between updates.

The current repository intentionally preserves template controller timing and does not yet expose it in campaign configuration. Implement this change cleanly instead of editing generated case files by hand.

Preferred implementation:

- extend the controller campaign configuration minimally, e.g. with explicit fields such as `controller.communication_dt_s` and `controller.ramp`, or another equally clear dedicated controller-timing representation;
- patch the copied ServoDyn file during case preparation;
- keep existing campaigns byte-for-byte/scientifically unchanged when those new fields are absent;
- add unit tests proving this backward compatibility and proving that the new case receives `DLL_DT = 0.05` and `DLL_Ramp = False`.

Do **not** interpret `numerics.actuator_dt_s` as controller timing: the repository documentation explicitly treats these clocks as independent.

### Wind

Use the existing 14 m/s Region-3 turbulent realization described above.

This first case should use exactly one deterministic turbulent realization, not a seed sweep. We first need a single truth trajectory for debugging the identification pipeline.

### Waves / hydrodynamics

For the **first** identification truth case, isolate the aerodynamic/servo/structural problem from stochastic wave forcing.

Use `waves: {kind: none}`.

However, do not casually destroy fixed-bottom structural physics. Keep SubDyn active. Configure SeaState/HydroDyn consistently with a no-wave case using the repository's normal case-preparation logic and the requirements of the monopile model. If a still-water HydroDyn contribution can remain active consistently, prefer that over removing physically relevant hydrodynamic added-mass/damping effects. If the framework currently maps `waves: none` to disabling those modules, document the exact resulting module switches before running.

A second validation case with the existing LC3 irregular waves (`Hs = 3 m`, `Tp = 10 s`, seed 610003) can be added later; do not add it to this first one-case campaign.

## Aerodynamic fidelity

Preserve the official v5 AeroDyn physics unless a reproducibility issue requires otherwise. In particular, do not simplify the truth to the same static `Cp` model used by the identification ROM.

The current template already includes high-fidelity effects such as:

- AeroDyn blade-element aerodynamics;
- dynamic BEM/inflow (`DBEMT_Mod = 2` in the bundled v5 monopile template);
- unsteady airfoil aerodynamics (`UA_Mod = 3`);
- tip and hub losses;
- tangential induction;
- tower potential-flow influence and tower shadow;
- tower aerodynamic loading.

These effects are intentional model mismatch relative to the reduced identification model.

## Output profile for identification truth

Do not reuse the structural-comparison output profile blindly. Add a dedicated output profile for this campaign, e.g. `cp-identification-bottom-fixed`, while preserving the old profile unchanged.

At minimum retain/export the channels required to reconstruct and validate the reduced rotor problem:

### Rotor / controller

- `RotSpeed`
- `GenSpeed`
- `Azimuth`
- `BldPitch1`, `BldPitch2`, `BldPitch3`
- `GenTq`
- `GenPwr`

### Aerodynamic truth / diagnostics

- `RtAeroMxh`
- `RtAeroFxh`

Also inspect the OpenFAST 5 / AeroDyn output-channel definitions and, if valid in this exact model/version, include the rotor-integrated channels useful for aerodynamic truth such as rotor aerodynamic power, `Cp`, `Ct`, and rotor-average axial inflow. Do not guess channel names: verify them before adding them and add unit tests around the selected output profile.

Do not use hub-point wind speed as a synonym for REWS.

### Structural diagnostics

Keep a compact set of channels sufficient to quantify the high-fidelity dynamics omitted by the rotor-only ROM, including at least:

- `TTDspFA`, `TTDspSS`
- representative blade-tip deflections
- optionally nacelle/tower-top acceleration if a valid channel is available

Do not dump every available OpenFAST channel.

## Rotor-effective wind truth

The later identification framework needs an oracle-wind reference for the first debugging case.

Prefer an actual rotor-effective/rotor-averaged inflow quantity consistent with the aerodynamic model. If OpenFAST/AeroDyn provides a well-defined rotor-average axial inflow channel for this version, save it and document its definition.

If it does not, add a separate deterministic post-processing step that computes an oracle rotor-effective wind from the same BTS field with an explicitly documented spatial averaging operator. Do not silently substitute `Wind1VelX` at hub height.

This oracle signal is for validation only; later latent-wind experiments must not feed it to the estimator.

## Controller-aligned identification dataset

Keep the raw OpenFAST output at 0.01 s.

After a successful run, add a small deterministic extraction step that produces a reduced identification dataset sampled exactly on the **0.05-s controller-update grid**. Preserve causal indexing:

`measurement at t_k -> controller update u_k -> plant evolution -> measurement at t_{k+1}`.

The extractor should save enough provenance to map every reduced sample back to the raw OpenFAST time index. Do not low-pass/filter or interpolate unless explicitly required and documented.

Later we may test a 0.1-s EKF/identification observation interval by taking every second controller update while still respecting the two distinct 0.05-s held controls inside each 0.1-s model interval. Do not change the truth-controller interval to 0.1 s for that future test.

## Transient handling

Simulate the full **400 s** usable wind realization and retain all raw samples.

For identification/analysis metadata, mark the first **100 s** as transient/warm-up and use the nominal analysis interval:

- raw truth: 0--400 s
- default identification window: **100--400 s**

Do not delete the first 100 s from the raw result.

## Preparation / execution policy

Implement and validate the campaign first. Do not launch multiple campaigns.

Recommended sequence:

1. resolve the new YAML and inspect the resolved scientific metadata;
2. locate/reuse the existing LC3 BTS by recorded ID/checksum, or regenerate it exactly if absent;
3. prepare the single OpenFAST case without running it;
4. audit the copied case files and print/report the effective values of:
   - OpenFAST `DT`, `DT_Out`, `TMax`, `ModCoupling`, `CompElast`, `CompSub`, `CompSeaSt`, `CompHydro`;
   - ServoDyn `DLL_DT`, `DLL_Ramp`;
   - InflowWind BTS path;
   - structural model and all requested output channels;
5. run the repository test suite, `ruff check .`, and `git diff --check`;
6. only then execute the **single** 400-s case when explicitly requested;
7. verify solver return code, final simulated time, raw time spacing, warnings and output-channel inventory;
8. create the controller-aligned reduced dataset only after the raw simulation has passed those checks.

Never commit generated `.bts`, `.outb`, prepared cases or logs.

## Expected deliverables from Codex

At the end of implementation, report:

1. exact tracked files added/modified;
2. final campaign YAML;
3. whether the existing LC3 BTS was found locally and reused, including checksum verification;
4. exact effective OpenFAST module switches and timesteps;
5. exact effective `DLL_DT` and `DLL_Ramp`;
6. exact selected output channels and units;
7. tests executed and results;
8. the command to prepare the case;
9. the command to run only this case;
10. after execution, the output path, warning summary, final time and sample counts;
11. the path/schema of the controller-aligned 0.05-s identification dataset.

Do not change any existing validated structural-comparison scientific setting or artifact while implementing this new campaign.