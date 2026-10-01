# BeamDyn tight-coupling diagnostic, 2026-10-01

Historical diagnostic snapshot. The later corrected paired smoke and approved
production promotion are recorded in [structural comparison](structural_comparison_v5.md#corrected-timestep-validation-and-production-decision).
The recommendations and on-hold statements below describe this diagnostic's
state before that subsequent approval.

The iteration-budget diagnostics failed. No production configuration, timestep,
controller, template or structural property was changed. No 400 s simulation or
trajectory post-processing was performed. This report is additional diagnostic
documentation only; the numerical recommendation below has not been applied.

## Controlled LC1 experiment

Baseline: the accepted `outputs/structural-comparison-v5-migrated/cases/smoke_case_00002`
10 s BeamDyn case, OpenFAST 5.0.0, ModCoupling=3, DT=DT_Out=0.025 s,
DTBeam=0.01 s, ConvTol=1e-4, RhoInf=1, MaxConvIter=6.

Each diagnostic is an isolated copy of every baseline input, with only the
MaxConvIter record in the FST changed. SHA256 comparison covers all copied input
files, including waves, controller/library, initial-condition inputs, BeamDyn
geometry and properties, and the existing BTS. The BTS symlink retains its
absolute target and checksum
`69779c3955b8cc3e6ad1dcca7ff7815a2c823542f652f072790403fbb5ddfe04`.
Baseline inputs were checked again after each run and remain unchanged.
Executable SHA256:
`d2ec2e74a887acc338fdec8e80521bede637f859796d83c00a50511e6741c168`.

| MaxConvIter | Return code | Iteration-limit warnings | First / last affected step | Invalid-solution warnings | External wall time | Outcome |
|---|---:|---:|---|---:|---:|---|
| 6, existing baseline | 0 | 124 | 15 / 166 (0.375 / 4.150 s) | 124 | 84.980 s | Completed 10 s with warnings |
| 20 | 1 | 0 | None emitted; fatal at step 2, 0.050 s | 0 | 7.075 s | Aborted |
| 40 | 1 | 0 | None emitted; fatal at step 2, 0.050 s | 0 | 7.091 s | Aborted |

Counts refer specifically to `Failed to converge in ... iterations on step ...`
and `Solution will continue but may be invalid.` Neither diagnostic emitted
those messages before the fatal error. Zero warnings here is not a convergence
success. The additional 40 run was used because the 20 run still failed
numerically, through rotation-matrix convergence rather than an iteration-limit
warning. Both stderr streams are empty.

Both diagnostic logs report the same fatal path:

```text
FAST_Solution:FAST_UpdateStates:Solver_Step:FAST_CalcOutput:
BD_CalcOutput:ExtractRelativeRotation:BD_CrvExtractCrv:BD_CheckRotMat:
DBDSQR did not converge, INFO specifies how many superdiagonals of an
intermediate bidiagonal form B did not converge to zero 2,...,.
OpenFAST encountered an error at simulation time 5.00000E-02 of 10 seconds.
Simulation error level: FATAL ERROR
```

All other diagnostic warnings/notices, present in both runs:

- MoorDyn: invalid FX, FY and FZ output specifiers because object IDs are missing
  (three notices).
- AeroDyn: optional nodal output section absent/improperly formatted; skipped.
- Motion/load mesh mapping: close node-1 value 9.93843E-05 m (12 messages across
  AD/BD mappings).
- AeroDyn: rotor-averaged axial induction exceeds 0.5; time-varying tau1 limited.
- ElastoDyn: small-angle assumption violated due to large tower deflection;
  solution may be inaccurate, continuing warning suppressed thereafter.

Both initialize all three BeamDyn instances, wind, waves, HydroDyn, MoorDyn,
ServoDyn and ROSCO. Neither reaches the baseline's later Mach-number,
unsteady-aerodynamics or BladedInterface coupling warnings before aborting.

Raw logs and input-hash reports are preserved under ignored
`outputs/beamdyn-convergence-diagnostic/maxiter_20` and `maxiter_40`.
No response trajectories were read. Timing uses Python perf_counter around the
solver subprocess, including initialization.

## Source trace: effective BeamDyn step

Inspected the clean official v5.0.0 checkout, commit
`2895884d2be01862173c88d70f86b358d2f1a50a`. Links below refer to that release;
line numbers are from the local checkout used to build the executable.

1. [FAST_Subs.f90](https://github.com/OpenFAST/openfast/blob/v5.0.0/modules/openfast-library/src/FAST_Subs.f90#L455):
   initialization sets `dt_module = p_FAST%DT`, then calls BD_Init for each
   blade. MV_AddModule receives this returned interval plus the global DT.
2. [BeamDyn.f90](https://github.com/OpenFAST/openfast/blob/v5.0.0/modules/beamdyn/src/BeamDyn.f90#L119):
   BD_Init passes Interval to BD_ReadInput as its default. BD_ReadInput reads
   explicit DTBeam=0.01; SetParameters stores it in `p%dt` and computes the
   module's own integration coefficients (lines 921-922). BD_Init does not
   assign Interval back from `p%dt`. Thus the registered module interval remains
   0.025 s, while BeamDyn's private `p%dt` is 0.01 s.
3. [ModVar.f90](https://github.com/OpenFAST/openfast/blob/v5.0.0/modules/nwtc-library/src/ModVar.f90#L432):
   MV_AddModule checks registered ModDT against SolverDT. Equal values yield
   SubSteps=1. Otherwise it enforces ModDT <= SolverDT and an integer-divisor
   relationship. Here both registered values are 0.025, so the check passes.
4. [FAST_Solver.f90](https://github.com/OpenFAST/openfast/blob/v5.0.0/modules/openfast-library/src/FAST_Solver.f90#L68):
   FAST_SolverInit sets `p%h = p_FAST%DT`, and computes generalized-alpha
   BetaPrime/GammaPrime using this h. At lines 126-136, ED/BD/SD are selected as
   tight modules when ModCoupling is not loose; BD is excluded from Option 1.
   The initialization also explicitly announces disabled substepping for tight
   modules when registered SubSteps > 1 (lines 194-199). Here BD has SubSteps=1,
   so no such notice is needed.
5. [FAST_Subs.f90](https://github.com/OpenFAST/openfast/blob/v5.0.0/modules/openfast-library/src/FAST_Subs.f90#L5199):
   FAST_Solution_T calls FAST_UpdateStates_T, which calls FAST_SolverStep once
   for each global step. SolverStep computes next time as
   `t_initial + (n_t_global+1)*p%h` (line 1230).
6. [FAST_Solver.f90](https://github.com/OpenFAST/openfast/blob/v5.0.0/modules/openfast-library/src/FAST_Solver.f90#L1309):
   the solver packs the tight states, calls PredictNextState, and transfers
   predicted states via FAST_SetOP. The Newton loop calls FAST_GetOP for the
   tight-module derivatives; [FAST_Funcs.f90](https://github.com/OpenFAST/openfast/blob/v5.0.0/modules/openfast-library/src/FAST_Funcs.f90#L1109)
   dispatches the BD derivative request to BD_CalcContStateDeriv.
   UpdateStatePrediction applies the Newton corrections and FAST_SetOP writes
   the corrected states back into BD (Solver lines 1558-1583).
7. [PredictNextState / UpdateStatePrediction](https://github.com/OpenFAST/openfast/blob/v5.0.0/modules/openfast-library/src/FAST_Solver.f90#L2097)
   use h, h squared, BetaPrime and GammaPrime to advance displacement, velocity
   and acceleration. For this case h=0.025 s. The BD_UpdateStates substep loop
   in FAST_Funcs is the module-update path used for loosely coupled BD; it does
   not advance BD states in the selected tight path. Newton iterations and
   retries solve the same next time, not intermediate substeps.

Consequently:

- BeamDyn is **not integrated at 0.01 s** in this configuration.
- BeamDyn is **not subcycled** between global steps.
- DTBeam is parsed and retained; it is not overwritten with the global step.
  It sets BeamDyn's private coefficients, but those coefficients do not control
  the glue-code generalized-alpha state advance in tight coupling.
- The tight generalized-alpha solver advances BeamDyn states by **0.025 s**.
- The current configuration does **not** satisfy Lorenzo's requirement if
  "BeamDyn dt=0.01 s" means the actual time-integration increment.

## Documented compatibility versus this implementation

The [v5 solver documentation](https://github.com/OpenFAST/openfast/blob/v5.0.0/docs/source/user/glue-code/solver.rst)
requires module timesteps to equal or be integer sub-divisors of global DT.
The [glue-code overview](https://github.com/OpenFAST/openfast/blob/v5.0.0/docs/source/user/glue-code/overview.rst)
describes multirate stepping for divisor module steps.
Numerically, 0.025 / 0.01 = 2.5, so the requested input pair does not satisfy
that documented relationship if DTBeam is treated as a module coupling step.
However, the actual registered BD interval is 0.025 in this release, so
MV_AddModule validates 0.025 against 0.025. This is why these inputs initialize
without a divisor error; it is not evidence of 0.01 s subcycling. Choosing
DT=0.02 alone to make the ratio integral would still integrate tight BD at
0.02 s and would not satisfy the intended 0.01 s requirement.

## Recommendation, not applied

Increasing MaxConvIter alone is insufficient: both tested budgets abort at the
same early step. No tested numerical configuration yet establishes converged
BD timesteps. The adaptive solver retries with a rebuilt Jacobian after exhausting
the iteration budget (FAST_SolverStep lines 1429-1468); increasing that budget
can delay this recovery. That is a possible explanation, not a demonstrated
root cause of this fatal rotation error.

The minimum timestep change that actually satisfies the intended benchmark
while preserving ModCoupling=3 is **global DT=0.01 s for both ED and BD**, with
DTBeam=0.01 retained. Keep identical environments, initial conditions,
controller tuning and other physics. Use the same convergence policy for both
representations. First test an isolated paired smoke at the smaller global DT,
retaining MaxConvIter=6 to isolate the timestep effect; only then diagnose the
iteration budget if necessary. Select the smallest tested budget that completes
with no failed-convergence or fatal-state warnings. These experiments require
separate authorization; none were run here. Keep ConvTol and RhoInf unchanged
until evidence supports any further change.

Two consequences must be agreed before applying that recommendation:

- DT_Out=0.025 is not an integer multiple of DT=0.01 and v5 rejects it
  (FAST_Subs.f90 line 2158). For full-rate raw output, use DT_Out=0.01 in both
  cases; this explicitly changes the previous output specification.
- ServoDyn DT and DLL_DT are currently DEFAULT. A smaller global DT therefore
  changes their effective intervals, even with the same files and tuning. Make
  the new effective controller cadence explicit and identical in ED/BD. Keeping
  a 0.025 communication interval cannot simply be assumed on a 0.01 global
  grid. Do not silently claim that all effective clocks remain unchanged.

Production remains on hold. This report recommends the next isolated experiment,
not a validated production configuration.
