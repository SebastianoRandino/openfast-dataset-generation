# Structural comparison production execution

Status: **all_six_successful**. Campaign commit `f366fca57981f3059a0be8e53dbac7feff4088c6`.

Runs were sequential in the approved LC1 ED/BD, LC2 ED/BD, LC3 ED/BD order.
Every input/dependency hash was verified before each run and rechecked after it.
All three ED/BD pairs passed the complete input-byte audit before execution.
Existing deterministic BTS files were reused without regeneration. No inputs changed.

| Case | Model | Return code | Reached s | Wall s | Samples | Failed convergence | Fatal errors |
|---|---|---:|---:|---:|---:|---:|---:|
| LC1_ED | elastodyn | 0 | 400.0 | 249.660 | 40001 | 0 | 0 |
| LC1_BD | beamdyn | 0 | 400.0 | 782.651 | 40001 | 0 | 0 |
| LC2_ED | elastodyn | 0 | 400.0 | 273.666 | 40001 | 0 | 0 |
| LC2_BD | beamdyn | 0 | 400.0 | 957.039 | 40001 | 0 | 0 |
| LC3_ED | elastodyn | 0 | 400.0 | 262.907 | 40001 | 0 | 0 |
| LC3_BD | beamdyn | 0 | 400.0 | 1237.216 | 40001 | 0 | 0 |

Each successful OUTB has a complete payload, 40001 samples, first time 0 s,
last time 400 s and spacing 0.01 s. Only binary headers and sizes were inspected.
No response trajectories were analyzed, compared, plotted, filtered, downsampled
or discarded; no reduced dataset was generated.

## Warning occurrences

| Case | Large deflection | Mach | Axial induction | UA disabled | Bladed interface | Mesh mapping | MoorDyn invalid | Nodal skipped | ROSCO estimator |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LC1_ED | 0 | 0 | 1 | 1 | 0 | 0 | 3 | 1 | 2 |
| LC1_BD | 0 | 1 | 1 | 1 | 1 | 12 | 3 | 1 | 2 |
| LC2_ED | 0 | 1 | 1 | 1 | 0 | 0 | 3 | 1 | 0 |
| LC2_BD | 0 | 1 | 1 | 1 | 1 | 12 | 3 | 1 | 0 |
| LC3_ED | 0 | 1 | 1 | 1 | 0 | 0 | 3 | 1 | 0 |
| LC3_BD | 0 | 1 | 1 | 1 | 1 | 12 | 3 | 1 | 0 |

MoorDyn FX/FY/FZ missing object IDs and skipped optional AeroDyn nodal outputs
are initialization notices. Close mesh-mapping nodes are reported during BD
step-zero initialization. Axial-induction, Mach, UA and BladedInterface messages
occur during stepping; repeat suppression does not demonstrate that a condition
disappeared. ROSCO warns when wind-estimator inputs leave normal-operation bounds
and switches to filtered hub-height wind speed. These warnings are faithfully
counted; physical validity is not established by solver convergence.

## Provenance

OpenFAST 5.0.0; executable SHA256 `d2ec2e74a887acc338fdec8e80521bede637f859796d83c00a50511e6741c168`.
The unchanged approved configuration uses ModCoupling=3, DT=DT_Out=DTBeam=0.01 s,
TMax=400 s, TStart=0, MaxConvIter=6, ConvTol=1e-4, DEFAULT ServoDyn DT/DLL_DT,
wind DT=0.05 s and WaveDT=0.25 s. Environment, seeds, initial conditions,
controllers, structural properties, damping, hydrodynamics and moorings are unchanged.

| Condition | Wind ID | BTS SHA256 | WaveSeed(1) | WaveSeed(2) |
|---|---|---|---:|---|
| LC1 | wind_8029c703c7171299 | 69779c3955b8cc3e6ad1dcca7ff7815a2c823542f652f072790403fbb5ddfe04 | 610001 | RANLUX |
| LC2 | wind_74fb16429b75d05e | 3a10d382ae6eee77fffc28b0403ee55a43f8cd94c71c1838c4270fba64db22a8 | 610002 | RANLUX |
| LC3 | wind_b5a3cb79b3fb0007 | f926a4c1a871d70f83c027dfa80cd8c76d778b668c7feff3d01fb4e0fc4c3612 | 610003 | RANLUX |

Summed solver subprocess wall time: **3763.138 s**.
Recorded execution-worker wall time, including checks: **3763.977 s**.
The latter spans the active worker segments and excludes the brief verification-parser
repair pause after LC1_ED. That run reported its Simulated Time in minutes; exact final
progress time and complete OUTB established 400 s. No solver retry occurred.

Important per-case input hashes, output checksums and warning counts are recorded in
[small execution provenance](structural_comparison_production_provenance.json).
The full input-hash audit and raw outputs/logs/controller debug files remain ignored
under outputs/structural-comparison-v5-production-dt001. They are not committed.

**All six runs reached 400 s with zero tight-coupling convergence failures,
zero invalid-solution warnings and no fatal numerical errors.**
No DBDSQR or BeamDyn rotation-matrix error occurred. Execution stopped after
the sixth run; no post-processing was started.

Validation after execution: **70 pytest tests passed**; Git diff checks passed.
No tracked Python source changed. Only this small report and its provenance are
included in the documentation commit; generated runtime artifacts remain ignored.
