# First structural comparison campaign

**Status (2026-10-01): v5 format migration verified and both 10 s smoke runs
completed. BD convergence warnings require review before production use.
The six 400 s simulations have not been executed.**

`configs/campaigns/structural_comparison_v5.yaml` resolves in order to LC1 ED/BD,
LC2 ED/BD, LC3 ED/BD. Environments are (URef, Hs, Tp) = (5, 1, 6),
(10, 2, 8), (14, 3, 10), in m/s, m, s. There are six 400 s cases, three
deduplicated wind dependencies and three deterministic SeaState dependencies.
No splits or post-processing are defined. The possible later 100 s transient
discard appears only in provenance; all output starts at t=0.

All cases use OpenFAST 5.0.0, ModCoupling=3, DT=DT_Out=0.025 s. Floating DOFs,
initial conditions, hydrodynamics, moorings and ROSCO remain inherited. ServoDyn,
DISCON and the ROSCO library are copied without edits. The optional
`structural_model: elastodyn | beamdyn` affects case science/identity but never
wind or wave dependency identity. Unselected legacy cases receive no structural
patches or new scientific clock keys; frozen v4 inputs are untouched.

ED uses CompElast=1 with FlapDOF1, FlapDOF2, EdgeDOF enabled. BD uses CompElast=2,
the same official BeamDyn primary file for all three blades, DTBeam=0.01 s,
and those three ED blade modal DOFs disabled. All other structural values stay
inherited. The DTBeam input is kept distinct from the global solver clock.
With tight coupling, v5 integrates ED/BD states in the glue code at global
DT=0.025 s; DTBeam=0.01 is stored in BeamDyn but is not evidence of independent
0.01 s substeps. See v5 FAST_Solver.f90, its iModTC selection and generalized-alpha
state integration. This distinction must be considered before production use.

Wind uses IECKAI, NTM, category B, 31x31 points over 300x300 m, reference/hub
height 150 m, shear exponent 0.2, direction 0 degrees, DT=0.05 s. Explicit
RandSeed1 values are 510001/510002/510003 and RandSeed2=RanLux. AnalysisTime=460 s
and UsableTime=400 s include the 60 s grid advection margin at the lowest speed.
Each ED/BD pair links to the same generated `wind_<hash>/wind.bts`; no duplicate
wind generation is performed. The ignored local paths configuration resolves
the existing TurbSim template ID; its checksum is recorded at generation.

Waves use SeaState WaveMod=2, JONSWAP with DEFAULT peak shape, WaveDT=0.25 s,
WaveDir=0, WaveTMax=400 s and WaveSeed(1)=610001/610002/610003,
WaveSeed(2)=RANLUX. SeaState generates waves internally during initialization;
the framework records and shares the complete generating configuration, not
a separately fabricated wave time series. ED/BD SeaState files are identical.

## BeamDyn source search and adaptation

Before adapting the pinned deck, inspected:

- [OpenFAST v5.0.0](https://github.com/OpenFAST/openfast/tree/v5.0.0): no IEA-15MW BeamDyn deck in its tree.
- [Official r-test revision dd5feaaaa500ba7283140107806300d551cff0a7](https://github.com/OpenFAST/r-test/tree/dd5feaaaa500ba7283140107806300d551cff0a7):
  contains IEA-15MW FAST.Farm MD_Shared ED inputs but no IEA-15MW BeamDyn inputs.
- Official IEA master `e4993d63de10f165389534461dd544006750fe60` and develop
  `4c9719c054b05dd27539977f1ee4fb1e36dcdb98`: the BeamDyn blade inputs still
  lack the v5 modal-damping section. Official-source web search found no suitable
  directly compatible alternative. This records the search scope, not proof
  that no compatible file exists anywhere.

Therefore retain [pinned IEA revision 86d51c8a1ee65be4f3686087a5c443c0b57e5cfb](https://github.com/IEAWindSystems/IEA-15-240-RWT/tree/86d51c8a1ee65be4f3686087a5c443c0b57e5cfb):

| File under OpenFAST/IEA-15-240-RWT | Official source SHA256 |
|---|---|
| IEA-15-240-RWT_BeamDyn.dat | 26ffeb76c34a8dc176e83f19b4bd47cbf4d15b946c13e69e43d253f2dcc83428 |
| IEA-15-240-RWT_BeamDyn_blade.dat | bbc76b78ba2a09fbe863663dbb807e9cdbe000af423441580874e694bce28608 |

The [v5 API change specification](https://github.com/OpenFAST/openfast/blob/v5.0.0/docs/source/user/api_change.rst)
and r-test `glue-codes/openfast/5MW_Baseline/NRELOffshrBsline5MW_BeamDyn_Blade.dat`
establish the new section layout. v5 `modules/beamdyn/src/BeamDyn_IO.f90`
reads n_modes/zeta unconditionally, including when damp_type=1.
The materialization recipe adds only the required inactive header, n_modes=3,
and inactive zeta=0.1/0.2/0.3 values copied directly from the official v5 API example. It preserves damp_type=1 and the six
original stiffness-proportional damping coefficients. No geometry, mass matrix,
stiffness matrix, station, twist or interpolation property is reconstructed.
The primary migration removes exactly the obsolete PITCH ACTUATOR PARAMETERS
heading and UsePitchAct/PitchJ/PitchK/PitchC records, as specified under
Removed in OpenFAST 5.0.0. All other primary-file bytes, including the reference
line, geometry, quadrature, element order and original output definitions, remain
unchanged by materialization. Its ordering is verified against the official
r-test primary example and v5 BeamDyn_IO.f90:
BldFile -> OUTPUTS -> SumPrint -> OutFmt -> NNodeOuts -> OutNd -> OutList.
Case preparation subsequently applies only the previously agreed DTBeam and
native output profile. Each materialized template is a new immutable destination; the previous
v5 and frozen v4 templates remain intact. Generated manifests record all hashes.

## Raw output selection

The opt-in `output_profile: structural-comparison-v5` selects the same common
ED/AeroDyn channels in all six cases, with native blade-response channels in
the active structural module. ED blade channels are invalid when BD is active
(v5 ElastoDyn.f90 SetOutParam, BD4Blades branch), so that portion of the ED
OutList is present only for ED. The representation-specific output selection
is necessary to record comparable blade quantities without invalid channels.
Optional nodal OutLists in ED/BD/AeroDyn are cleared by this profile to retain
the compact requested set and avoid unsupported ED nodal outputs in BD runs.
This changes output selection only, not structural properties or solver states.
ServoDyn's template OutList remains unchanged and includes GenPwr and GenTq.
Channels were checked against the v5 module output definitions in ElastoDyn_IO,
BeamDyn_IO and AeroDyn. No samples or response magnitudes are analyzed here.

| Quantity | Channels |
|---|---|
| Generator/rotor speed, control context | GenSpeed, RotSpeed, Azimuth, BldPitch1/2/3 |
| Generator power/torque | template ServoDyn GenPwr, GenTq |
| Aerodynamic rotor torque/thrust | RtAeroMxh, RtAeroFxh (hub axes) |
| Platform six rigid-body responses | PtfmSurge/Sway/Heave/Roll/Pitch/Yaw |
| Tower-top response and yaw-bearing loads | TTDspFA/SS, YawBrFxp/Fyp/Fzp, YawBrMxp/Myp/Mzp |
| Blade-tip translations, all blades | ED TipDxb/TipDyb1/2/3 plus TipDxc/TipDyc/TipDzc1/2/3; BD blade-instance TipTDxr/yr/zr |
| Blade-root force/moment, all blades | ED RootFxb/Fyb/Fzb and RootMxb/Myb/Mzb1/2/3; BD blade-instance RootFxr/Fyr/Fzr and RootMxr/Myr/Mzr |
| Additional BD rotational response | B1/B2/B3TipRDxr/yr/zr |

ED `b` is the pitched blade frame and `c` the coned frame; BD `r` follows root-motion
orientation and is documented as the IEC blade `b` frame when coupled to FAST.
ED RootFxb/RootMxb etc. correspond to BD RootFxr/RootMxr etc.; ED TipDxb/TipDyb
correspond to BD TipTDxr/TipTDyr. These are candidate corresponding quantities, not established
numerical equivalences. Blade reference geometry, prebend, sign, origin and
coordinate conventions must be reconciled in the later analysis. BD tip
rotations use Wiener-Milenkovic parameters and have no direct ED modal counterpart.
ED root loads are in kN/kN-m; BD root loads are in N/N-m. Unit conversion and
sign/origin reconciliation belong to later analysis and are not performed now.
Native ED blade channels are selected only for ED, and native BD channels only
for BD. All common output selections are identical within each pair.

## Deliberate preparation and smoke

Materialize a fresh v5 template with `scripts/materialize_iea15mw_v5.py`, then
resolve its template ID in ignored `configs/paths.yaml`. From the repository:

```bash
.venv/bin/python scripts/prepare_structural_comparison.py --output-root outputs/structural-comparison-v5
# Explicit opt-in, only after unit tests pass:
.venv/bin/python scripts/prepare_structural_comparison.py --output-root outputs/structural-comparison-v5 --smoke
```

The command generates/reuses three full-duration BTS dependencies and prepares
six 400 s workspaces. `--smoke` prepares separate `smoke_case_00001/00002`
workspaces with TMax=10 s and identical 10 s wave generation settings, reusing
the campaign LC1 BTS. It then executes the ED/BD pair sequentially, stopping on
the first solver failure. It cannot launch the six-run campaign. Raw outputs,
logs, runtime JSON, templates and BTS remain under ignored outputs/.
The full six-run execution requires subsequent explicit approval.

## Migrated smoke evidence (2026-10-01)

Solver: **OpenFAST-v5.0.0**, GCC 13.3.0, 64-bit, double precision, no OpenMP.
Executable SHA256:
`d2ec2e74a887acc338fdec8e80521bede637f859796d83c00a50511e6741c168`.
ROSCO **2.10.1**, MoorDyn **2.3.8**. The existing TurbSim build identifies
itself as from OpenFAST **4.1.1**; both structural solver runs use **5.0.0**.

The same LC1 realization and scientific settings as the original attempt were
used: ModCoupling=3, DT=DT_Out=0.025 s, DTBeam=0.01 s, TMax=10 s, unchanged
ROSCO/platform/hydrodynamics/moorings/initial conditions. Resolved scientific
metadata matches the earlier smoke pair exactly. The shared LC1 BTS SHA256 is
`69779c3955b8cc3e6ad1dcca7ff7815a2c823542f652f072790403fbb5ddfe04`.
SeaState inputs and seeds match between ED/BD. No wind was regenerated.

| Check | ED | BD |
|---|---|---|
| Return code | 0 | 0 |
| Time reached | 10.0 s | 10.0 s |
| External wall time (Python perf_counter) | 5.745 s | 84.980 s |
| Raw OUTB bytes | 90,731 | 93,224 |
| Header verification | 401 samples, 0 to 10 s, 0.025 s interval | same |
| Termination | normal | normal |
| Fatal/parser errors | none | none |

Measured external wall-time ratio BD/ED: approximately **14.79**. These short
startup timings are not a production runtime forecast. OpenFAST's own BD
Total Real Time banner reports 1.5495 minutes; external elapsed timing is
recorded independently, and the two clocks differ in this run.

Both cases initialize ElastoDyn, InflowWind, SeaState, AeroDyn, HydroDyn,
MoorDyn, ServoDyn and ROSCO. BD additionally prints **Running BeamDyn** three
times and initializes all three blade instances. Initialization proceeds past
the former NNodeOuts failure into wave generation, hydrodynamics, moorings and
controller startup. The retained official QuasiStaticInit=True is unchanged.
Native BD header channels include B1/B2/B3RootFxr/Fyr/Fzr, RootMxr/Myr/Mzr,
TipTDxr/yr/zr and TipRDxr/yr/zr. Complete payload size was checked using headers
only; no response trajectories were analyzed.

Warnings and notices:

- Both: MoorDyn's inherited bare FX/FY/FZ output specifiers lack object IDs;
  three Invalid channels remain in the raw outputs. Template moorings were
  preserved.
- Both: AeroDyn skips its absent/improperly formatted optional nodal-output
  section; the requested primary channels are present.
- Both: rotor-averaged axial induction exceeds 0.5 and limits time-varying tau1.
- BD: motion/load mesh mapping reports a close value for node 1
  (9.93843E-05 m).
- BD: BladedInterface is designed for explicit loose coupling and reuses the
  last DLL values on subsequent calls until time advances.
- BD: Mach number exceeds 0.3; the aerodynamic theory is outside its stated
  validity range.
- BD: repeated failure to converge within the inherited MaxConvIter=6 and
  ConvTol=1e-4, reported at steps from 15 through 166, with the explicit solver
  warning that the continuing solution may be invalid.
- BD: unsteady aerodynamics temporarily turns off due to high angle of attack
  or low relative velocity.

Neither run has a fatal error; stderr is empty. The smoke demonstrates
input compatibility, initialization and completion, **not numerical validation**.
No iteration limit, tolerance, timestep, controller or other scientific setting
was altered to address these warnings. Full-campaign execution remains pending
explicit review and approval.

Exact BeamDyn inputs:

| Stage | Primary SHA256 | Blade-property SHA256 |
|---|---|---|
| Official pinned source | 26ffeb76c34a8dc176e83f19b4bd47cbf4d15b946c13e69e43d253f2dcc83428 | bbc76b78ba2a09fbe863663dbb807e9cdbe000af423441580874e694bce28608 |
| Materialized v5 format | 72725a0fe77eec8d502b3bc8780a0d8c1b43edb46cf966015888bda6d6d9f7a9 | 4e995189100a7b192d5418b5cbdc675934069759f430e4b4adc0c29096770380 |
| Prepared BD smoke | a29f3c8f3803be0438d789e6e91d527e18e5331a7f571771856848fedf00af1d | 4e995189100a7b192d5418b5cbdc675934069759f430e4b4adc0c29096770380 |

Repository/revision/source paths are specified above. The local template is the
new immutable `outputs/templates/v5-structural-migrated` destination. Generated
template_provenance.json records source revision, explicit format migration
records and all materialized hashes. All three blade references use
`OpenFAST/IEA-15-240-RWT/IEA-15-240-RWT_BeamDyn.dat`, which reads
`IEA-15-240-RWT_BeamDyn_blade.dat` from the same directory.

Generated artifacts are under ignored
`outputs/structural-comparison-v5-migrated/cases/smoke_case_00001/00002`.
Names below use the model stem `IEA-15-240-RWT-UMaineSemi`:

| File suffix / artifact | ED bytes | BD bytes |
|---|---:|---:|
| .outb | 90,731 | 93,224 |
| .ED.sum | 18,541 | 5,017 |
| .HD.sum | 1,620,549 | 1,620,549 |
| .SrvD.sum | 14,268 | 14,268 |
| .MD.out | 178,628 | 178,628 |
| .RO.dbg | 270,470 | 270,470 |
| openfast.log | 40,891 | 66,623 |
| openfast_runtime.json | 653 | 653 |
| case_metadata.json | 7,716 | 8,298 |

Full-duration winds (reused, three unique realizations):

| Condition | Wind realization | BTS bytes |
|---|---|---:|
| LC1 | wind_8029c703c7171299 | 53,047,366 |
| LC2 | wind_74fb16429b75d05e | 49,587,766 |
| LC3 | wind_b5a3cb79b3fb0007 | 48,601,780 |

The six production workspaces are prepared with TMax=400 s but contain no
OpenFAST runtime execution records. Within each pair, only FST, ElastoDyn and
BeamDyn primary files differ, for the agreed structural settings and necessary
native output selection. All ServoDyn/DISCON/library copies remain byte-identical
to the template. The actual frozen v4 tree's before/after checksum is unchanged:
`66d918b488d291ecbd97f4c75b3de0db22abbece635ff2b34ee041e3ffe293b7`.

Validation: **70 pytest tests passed**. New regressions use byte-exact official
fixtures with pinned hashes, verify positional NNodeOuts parsing and preserve
all original bytes outside the explicitly migrated records. A complete
materialization unit test checks source/v4 preservation without real solvers.
Ruff and git diff --check pass. Generated outputs, BTS, logs, local template
paths and local executable paths remain ignored and excluded from the commit.
The implementation is committed/pushed only after recording this completed
smoke evidence; final Git status and commit SHA are reported in chat.
