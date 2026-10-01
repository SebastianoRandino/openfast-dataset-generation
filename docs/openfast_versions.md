# Versioned OpenFAST templates

Campaign `model:` selects portable `openfast_template_id`, `openfast_primary_fst`
and `openfast_version`. Ignored paths.yaml resolves IDs and
`executables.openfast.<version>` to local paths. See paths.example.yaml.

| Model YAML | Template ID | Executable |
|---|---|---|
| iea15mw_volturnus.yaml (legacy) | iea15mw-volturnus-openfast-v1 | 4.1.1 |
| iea15mw_volturnus_v4.1.1.yaml | IEA15MW_VolturnUS_v4.1.1 | 4.1.1 |
| iea15mw_volturnus_v5.0.0.yaml | IEA15MW_VolturnUS_v5.0.0 | 5.0.0 |

Both v4 IDs resolve to the unchanged validated tree. Metadata pins its complete
tree SHA256: `66d918b488d291ecbd97f4c75b3de0db22abbece635ff2b34ee041e3ffe293b7`.
Preparation rejects modifications. Preserve the whole tree, including auxiliary
files, in backups; run cases only in copies. The existing checksum algorithm feeds
sorted relative POSIX filenames followed by each file's hexadecimal SHA256 into SHA256.

The legacy executable scalar remains supported. Known IDs infer the required
version even for older metadata. Conflicting declarations and v4/v5 primary-file
format mixups fail. Before launch, reuse, or force deletion, the runner probes
the selected executable with `-v`. A recognized mismatch fails; an unavailable
banner is recorded as `unavailable` and cannot establish compatibility. Version
mapping never falls back to another version. Reuse also checks executable SHA256.
Required version participates in scientific case identity.

## Separate v5 provenance

The repository maintains v5 as a pinned reproducible input recipe, without
vendoring hydrodynamic data, binaries or generated cases:

```bash
python scripts/materialize_iea15mw_v5.py SOURCE_GIT_REPO NEW_DEST ROSCO_LIBRARY
```

The source must contain official
[IEAWindSystems/IEA-15-240-RWT revision 86d51c8a1ee65be4f3686087a5c443c0b57e5cfb](https://github.com/IEAWindSystems/IEA-15-240-RWT/tree/86d51c8a1ee65be4f3686087a5c443c0b57e5cfb).
The recipe exports committed objects for `OpenFAST/IEA-15-240-RWT` and
`OpenFAST/IEA-15-240-RWT-UMaineSemi`, ignoring checkout edits. It refuses an
existing destination and never reads or converts the validated v4 tree. Supply
ROSCO 2.10.1; it bundles the library locally and replaces the upstream CI absolute
DLL path with a relative reference. No retuning occurs. Generated
template_provenance.json records source revision and all file/library checksums.
Use an ignored destination, then configure its template ID in local paths.yaml.

Format references: [v5.0.0 release](https://github.com/OpenFAST/openfast/releases/tag/v5.0.0),
[API specification](https://github.com/OpenFAST/openfast/blob/v5.0.0/docs/source/user/api_change.rst),
and [r-test dd5feaaaa500ba7283140107806300d551cff0a7](https://github.com/OpenFAST/r-test/tree/dd5feaaaa500ba7283140107806300d551cff0a7).
The MD_Shared farm inputs establish field order, not scientific settings: they
use shared moorings, different platform properties and disable standalone
ServoDyn/moorings.

Changes to the pinned official IEA source:

- FST: ModCoupling=1 (legacy loose coupling), inactive RhoInf=1, ConvTol=1e-4,
  MaxConvIter=6; NRotors=1, MirrorRotor=False, CompSoil=0, unused SoilFile.
- ElastoDyn: PitchDOF=False, zero lateral reference offsets and inactive pitch
  inertias; remove obsolete PitchAxis blade column. Retain mass/stiffness/modes.
- ServoDyn: zero inactive pitch neutral/spring/damping fields; relative DLL path.
  Preserve source DISCON, gains, module selection and timing.
- AeroDyn: remove Buoyancy; add zero t_c and hydrodynamic blade coefficients,
  zero TwrCp/TwrCa. New hydrodynamic coefficients are inactive for MHK=0.
- SeaState: WvCrntMod=0 (simple superposition).
- BeamDyn primary: remove only the v5-deleted pitch-actuator heading and
  UsePitchAct/PitchJ/PitchK/PitchC records. BeamDyn blade: retain damp_type=1,
  all six active damping coefficients and every sectional-property byte; add
  required inactive modal-damping records from the official v5 API example.
  See [structural comparison and paired smoke evidence](structural_comparison_v5.md).
- HydroDyn: NAddDOF=0 and HstMod=0, consistent with source WaveStMod=0;
  preserve WAMIT data, standalone moorings and damping.

This is an official-source baseline, not numerical equivalence to custom v4.
Retained source differences versus v4: TMax 10 vs 1000 s; initial pitch 1 vs 0
degrees; rotor speed 7.55 vs 7.5 rpm; platform surge/pitch 0/0 vs 22 m/5 degrees;
rounded OverHang/Twr2Shft; DLL_DT default vs 0.10 s. SeaState: WaveTMax 850 vs
1000 s, inherited water properties, NX 2 vs 4, X_HalfWidth 5 vs 150 m, one vs two
elevation probes, second-order kinematics enabled vs disabled, SeaStSum false vs
true. DISCON bytes are identical. The smoke case explicitly patches duration,
integration/output steps, steady wind and WaveMod=0 through existing preparation.

## Integration evidence (2026-10-01)

Opt-in runner: `python scripts/run_openfast_case.py configs/campaigns/integration_v5_short.yaml
--output-root outputs/integration-v5-2`. Exactly one case is required.
Unit tests never run real solvers.

- OpenFAST **5.0.0**, GCC 13.3.0, double precision, no OpenMP; return code **0**.
- TMax **5 s**; banner simulated time and final binary time sample both **5.0 s**.
- Initialized ElastoDyn, InflowWind, SeaState, AeroDyn, HydroDyn, MoorDyn **2.3.8**,
  ServoDyn and ROSCO **2.10.1**.
- Warnings: SeaState adjusts WvHiCOff to 0.62832 rad/s based on WaveDT; MoorDyn
  bare FX/FY/FZ specifiers lack object IDs; AeroDyn limits tau1 for induction above
  0.5; AeroDyn Mach above 0.3 (theory invalid). No fatal errors; stderr empty.
- Output: `outputs/integration-v5-2/cases/case_00001/OpenFAST/IEA-15-240-RWT-UMaineSemi/IEA-15-240-RWT-UMaineSemi.outb`,
  **125373 bytes**. Runtime JSON and log remain in the ignored case workspace.
- ROSCO library SHA256: `696e433c75b27469503b5dee285b713d0b9102d3d767951753d317a25d69cdff`.

An earlier recipe attempt failed HydroDyn initialization (return code 1) because
NAddDOF was missing. The final recipe includes it and succeeds. This startup
check establishes input compatibility, not production validation or equivalence.
