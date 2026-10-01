# Controlled LC1 smoke at global DT=0.01 s

Historical smoke snapshot. Subsequent approval promotes these validated clocks
to the [production campaign](structural_comparison_v5.md#corrected-timestep-validation-and-production-decision).
The Git status and unchanged-production statements below describe the smoke's
state before that promotion; further simulation execution remains on hold.

On 2026-10-01, exactly one ED/BD 10 s pair was run. Both completed normally
with no tight-coupling convergence failures or fatal numerical errors.
Production remains on hold pending review. No permanent campaign settings were
changed, no new numerical tuning was performed and no commit was made.

## Inputs and fairness

Fresh cases are preserved in ignored `outputs/lc1-dt001-smoke/LC1_ED` and
`LC1_BD`, copied from the accepted migrated smoke pair. The previous baseline
and MaxConvIter=20/40 diagnostics remain intact.

The only changed input records relative to each accepted baseline are FST
DT and DT_Out, from 0.025 to 0.01 s. SHA256 auditing verifies every other copied
input byte, including the official migrated BeamDyn geometry, sectional
matrices, damping, output selections, controller/library and initial conditions.
The baseline input hashes were rechecked after each run.

Common settings: OpenFAST 5.0.0, ModCoupling=3, DT=DT_Out=0.01 s, TMax=10 s,
MaxConvIter=6, ConvTol=1e-4, glue RhoInf=1. ED uses CompElast=1 and enabled
FlapDOF1/FlapDOF2/EdgeDOF; BD uses CompElast=2 and disables those ED blade DOFs.
BD DTBeam remains 0.01 s. No BeamDyn parameter or migration record changed.

LC1 remains URef=5 m/s, Hs=1 m, Tp=6 s. The exact existing BTS is reused,
without regeneration, SHA256:
`69779c3955b8cc3e6ad1dcca7ff7815a2c823542f652f072790403fbb5ddfe04`.
SeaState files/seeds, hydrodynamics, moorings, platform and controller files
are identical between ED and BD. Only FST, ElastoDyn primary and BeamDyn primary
files differ between the pair, for the accepted representation settings and
native output selection. The complete input-hash audit is stored in
`outputs/lc1-dt001-smoke/input_audit.json`.

The executable SHA256 remains
`d2ec2e74a887acc338fdec8e80521bede637f859796d83c00a50511e6741c168`;
its runtime banner reports OpenFAST-v5.0.0, GCC 13.3.0, double precision, no
OpenMP. ROSCO is 2.10.1 and MoorDyn is 2.3.8.

## Results

| Check | ED | BD |
|---|---:|---:|
| Return code | 0 | 0 |
| Simulated time reached | 10.0 s | 10.0 s |
| External wall time, including initialization | 8.918252 s | 28.771265 s |
| Binary samples | 1001 | 1001 |
| Binary first / last time | 0 / 10.0 s | 0 / 10.0 s |
| Binary time spacing | 0.01 s | 0.01 s |
| Complete binary payload | yes | yes |
| OUTB size | 221,531 bytes | 227,624 bytes |
| Failed-to-converge warnings | 0 | 0 |
| First / last affected timestep or time | none | none |
| Solution-will-continue-but-may-be-invalid warnings | 0 | 0 |
| DBDSQR error | absent | absent |
| BeamDyn rotation-matrix error | absent | absent |
| Fatal errors / stderr | none / empty | none / empty |

Both initialize ElastoDyn, InflowWind, SeaState, AeroDyn, HydroDyn, MoorDyn,
ServoDyn, the Bladed controller interface and ROSCO. BD additionally prints
Running BeamDyn three times and proceeds through all three blade instances.
Both output headers encode 1001 samples starting at zero with 0.01 s spacing,
and file sizes match the complete expected payload. No output response columns
were read, plotted, compared, filtered, downsampled or discarded.

## Effective integration and controller intervals

The [previous source trace](beamdyn_tight_coupling_diagnostic.md) applies to the
same clean v5.0.0 commit `2895884d2be01862173c88d70f86b358d2f1a50a`.
[FAST_SolverInit](https://github.com/OpenFAST/openfast/blob/v5.0.0/modules/openfast-library/src/FAST_Solver.f90#L68)
sets h from global DT, selects BD as a tight module and uses h in
PredictNextState/UpdateStatePrediction. For these audited FST inputs,
**h=0.01 s**, so BeamDyn tight states actually advance at 0.01 s without
subcycling. This conclusion follows from the active glue-code integration path,
not merely the written DTBeam field. Both runtime ElastoDyn summaries report
`Structural (s) 0.01000000`, consistent with that global increment.

ServoDyn DT and DLL_DT remain DEFAULT, byte-identical in the pair and to the
baseline. Effective ServoDyn and ROSCO DLL communication intervals are both
**0.01 s**. The source default chain is global DT -> ServoDyn DT -> DLL_DT:
[ServoDyn_IO.f90](https://github.com/OpenFAST/openfast/blob/v5.0.0/modules/servodyn/src/ServoDyn_IO.f90#L1055)
lines 1055 and 1379, then
[BladedInterface.f90](https://github.com/OpenFAST/openfast/blob/v5.0.0/modules/servodyn/src/BladedInterface.f90#L290)
sets the DLL interval and sends it to ROSCO in avrSWAP record 3 (line 904).
Each ServoDyn summary identifies record 3 as the communication interval but
does not print its numerical value. Runtime confirmation therefore additionally
uses only the ROSCO debug time column: each case has 1001 controller timestamps
from 0 to 10 s, every adjacent interval 0.01 s. No ROSCO response columns were
analyzed. BD's repeated same-time solver calls reuse the most recent DLL result,
as stated in its BladedInterface warning.

## Remaining warnings

| Warning / notice | ED count | BD count | Timing / persistence evidence |
|---|---:|---:|---|
| ElastoDyn large tower deflection / small-angle violation | 0 | 0 | absent |
| Axial induction >0.5, limiting tau1 | 1 | 1 | time-stepping; repeat suppressed, condition may persist |
| AeroDyn Mach >0.3, theory invalid | 0 | 1 | BD time-stepping; repeat suppressed, condition may persist |
| UA temporarily disabled for high AoA or low relative velocity | 0 | 1 | BD time-stepping; repeat suppressed, condition may persist |
| BladedInterface explicit-loose-coupling design / reuse until time advances | 0 | 1 | BD time-stepping; repeat suppressed; repeated calls handled throughout |
| Close mapping node, 9.93843E-05 m | 0 | 12 | BD step-zero initialization of AD/BD motion/load maps |
| MoorDyn FX/FY/FZ missing object IDs | 3 | 3 | initialization; corresponding output definitions remain invalid |
| Optional AeroDyn nodal output section skipped | 1 | 1 | initialization; optional nodal section stays skipped |

No separate ROSCO error was reported. Suppressed messages do not establish that
the underlying condition resolved; these logs do not locate their disappearance
or exact first/last affected physical time. The successful convergence smoke
does not clear the remaining aerodynamic-validity or interface warnings.

Raw full-rate outputs, summaries, logs and audits remain under the ignored
diagnostic root. Exactly two simulations were run. No 400 s production case or
trajectory post-processing was executed.

## Checks and Git

The complete pytest suite passes: **70 tests**. Git diff checks pass.
Full-repository Ruff reports **15 existing findings** in unchanged tracked files
(import ordering, nested-if style, exception-type style, __all__ ordering,
quoted annotation and unused imports). No application source was changed in
this smoke-only task. The previously targeted structural-comparison lint scope
passes; the repository-wide lint findings were left intact.

Git status contains only two untracked diagnostic documents:
`docs/beamdyn_tight_coupling_diagnostic.md` (previous diagnostic) and this report.
All generated evidence remains ignored. Production YAML is unchanged at
DT=DT_Out=0.025 s. No commit or push was performed; review is required before
any permanent production-setting change or further simulations.
