# Explicit channel equivalence and exclusions

The complete, ordered headers of all six production OUTBs are recorded in
`channel_inventory.csv` (including three duplicate `Invalid` entries per run).
`channel_map.csv` is the executable allowlist: 41 comparisons, with exact native
names, asserted header units, target units and multiplicative conversions.
No sign is inferred from correlation, and no data-dependent sign flip is used.

## Shared modules: 23 channels

These names retain the same module and output definition in both configurations:

- ServoDyn: `GenPwr` (kW), `GenTq` (kN-m).
- ElastoDyn drivetrain/control: `RotSpeed`, `GenSpeed` (rpm),
  `BldPitch1`, `BldPitch2`, `BldPitch3` (deg).
- AeroDyn: `RtAeroFxh` (N, rotor aerodynamic thrust along hub x),
  `RtAeroMxh` (N-m, aerodynamic torque about hub x).
- ElastoDyn platform: `PtfmSurge`, `PtfmSway`, `PtfmHeave` (m),
  `PtfmRoll`, `PtfmPitch`, `PtfmYaw` (deg).
- ElastoDyn tower/yaw bearing: `TTDspFA`, `TTDspSS` (m),
  `YawBrFxp`, `YawBrFyp`, `YawBrFzp` (kN),
  `YawBrMxp`, `YawBrMyp`, `YawBrMzp` (kN-m).

Both members of each pair use the same definitions, origins and signs. These
are module-reported quantities; tower-top motion is the native ED tower motion
output, not a reconstructed inertial nacelle trajectory. No conversion is
needed for these statistics. Plot display converts GenPwr to MW, aerodynamic
thrust to kN and aerodynamic torque to kN-m, and scales PSD density by the square
of the display factor. CSV statistics retain the allowlist engineering units.

## Blade channels: 18 matches

For each blade i = 1, 2, 3:

| ED | BD | Meaning and target unit | BD conversion |
|---|---|---|---|
| TipDxbi | BiTipTDxr | x tip translation relative to undeformed blade, pitched root frame, m | 1 |
| TipDybi | BiTipTDyr | y tip translation relative to undeformed blade, pitched root frame, m | 1 |
| RootFxbi | BiRootFxr | root x force, kN | N × 0.001 |
| RootFybi | BiRootFyr | root y force, kN | N × 0.001 |
| RootMxbi | BiRootMxr | root x bending moment (edgewise direction), kN-m | N-m × 0.001 |
| RootMybi | BiRootMyr | root y bending moment (flapwise direction), kN-m | N-m × 0.001 |

The x/y bending labels refer to the pitched root axes, not principal structural
axes rotated by local structural twist. The compared blade-tip coordinates
are displacements, not absolute tip positions. BD includes native prebend and
ED uses its own undeformed reference, so their zero geometries need not coincide.
This comparison measures deformation from each model's own reference geometry;
it does not identify a pure discretization error or compare absolute clearance.

### Source-level checks performed before numerical blade comparison

Definitions were checked against the official OpenFAST v5.0.0 source checkout,
commit `2895884d2be01862173c88d70f86b358d2f1a50a`:

- `modules/elastodyn/src/ElastoDyn.f90`, blade tip motions around lines 853–864:
  ED subtracts the undeformed tip and projects onto j1/j2 for TipDxb/TipDyb.
  Root loads around 1151–1160 project the integrated root force and moment onto
  the same j1/j2 axes. Loads are converted by 0.001 around lines 835–838.
- The same file, lines 1619–1627, builds BladeRootMotion orientation using
  j1, j2, j3 with the internal ED-to-inertial coordinate permutation. Lines
  6264–6266 define j1/j2 as the pitched blade axes.
- `modules/openfast-library/src/FAST_Mapping.f90`, lines 882–889, transfers ED
  BladeRootMotion to BD RootMotion. Thus BD r is the same pitched root frame.
- `modules/beamdyn/src/BeamDyn_IO.f90`, Calc_WriteOutput around 1695–1706,
  projects ReactionForce and ReactionMoment using RootMotion orientation;
  units are N and N-m. Lines 1717–1728 subtract the moving undeformed tip
  and project the translational deflection in this same root frame.
- `modules/openfast-library/src/FAST_Mapping.f90`, Custom_BD_to_SrvD around
  3539–3545, rotates BD RootMxr/RootMyr back to unpitched c coordinates without
  changing sign. Custom_ED_to_SrvD uses ED RootMxc/RootMyc directly.
  Together with the ED j1/j2 rotation this establishes the same moment sign,
  rather than requiring a reaction-action flip. BD ReactionForce is also mapped
  to ED BladeRootLoads (same file around 1038–1050), and ED adds these forces
  and moments with a coordinate permutation and no sign reversal (ElastoDyn
  around 7678–7679), establishing the root force sign.

Sources are available in the [OpenFAST v5.0.0 tree](https://github.com/OpenFAST/openfast/tree/v5.0.0/modules).
No independent source checkout is required to reproduce the established mapping.

## Excluded / deferred channels

- ED `TipDxc1–3`, `TipDyc1–3` are in the unpitched c frame; they are not directly
  paired with BD r components. The b-frame tip pair already provides the
  requested deflection comparison without redundant transformed statistics.
- ED `TipDzc1–3`, `RootFzb1–3`, `RootMzb1–3` and BD `BiTipTDzr`, `BiRootFzr`,
  `BiRootMzr`: axial/torsional channels are deferred. This stage's reviewed
  root-load mapping covers x/y only; axial deformation/reference and torsional
  model equivalence are not established here. No numerical comparison is made.
- BD `BiTipRDxr`, `BiTipRDyr`, `BiTipRDzr` are dimensionless Wiener–Milenkovic
  rotation parameters, not degrees or ED translation channels. No corresponding
  ED rotational outputs exist in these OUTBs.
- Three `Invalid` MoorDyn outputs per run are explicitly excluded. Native
  hydrodynamic, wave, mooring, wind, azimuth and convergence diagnostics remain
  in the inventory but are outside this response-comparison scope.

Missing or ambiguous names, unexpected units, nonfinite matched data, unequal
time vectors, or production checksum mismatches stop analysis rather than
silently changing the allowlist. Statistics select t >= 100 s after decoding;
all original data remain intact.
