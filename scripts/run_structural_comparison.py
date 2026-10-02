"""Run the validated six-case OpenFAST v5 structural comparison sequentially."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from openfast_dataset.campaign.resolver import resolve_campaign
from openfast_dataset.cases import prepare_openfast_case, run_openfast
from openfast_dataset.cases.execution import probe_openfast_version
from openfast_dataset.config import load_campaign
from openfast_dataset.paths import load_machine_paths, resolve_openfast_executable
from openfast_dataset.wind.execution import prepare_turbsim_realization, run_turbsim
from openfast_dataset.wind.planner import plan_winds


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--campaign", default="configs/campaigns/structural_comparison_v5.yaml"
    )
    parser.add_argument("--paths", default="configs/paths.yaml")
    parser.add_argument(
        "--output-root",
        default="outputs/structural-comparison-v5-production-dt001",
    )
    args = parser.parse_args()

    cases = resolve_campaign(load_campaign(args.campaign))
    expected_ids = [f"case_{index:05d}" for index in range(1, 7)]
    expected_models = ["elastodyn", "beamdyn"] * 3
    expected_speeds = [5.0, 5.0, 10.0, 10.0, 14.0, 14.0]
    if [case.case_id for case in cases] != expected_ids:
        parser.error("validated structural campaign must resolve to case_00001...case_00006")
    if [case.scientific["structural_model"] for case in cases] != expected_models:
        parser.error("validated structural campaign must alternate ElastoDyn/BeamDyn")
    if [case.scientific["wind"]["speed_mps"] for case in cases] != expected_speeds:
        parser.error("validated structural campaign must use paired 5/10/14 m/s conditions")

    paths = load_machine_paths(args.paths)
    executable = resolve_openfast_executable(paths, "5.0.0")
    if probe_openfast_version(executable) != "5.0.0":
        parser.error("structural comparison requires OpenFAST 5.0.0")

    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)

    wind_plan = plan_winds(cases)
    if len(wind_plan.realizations) != 3:
        parser.error("validated campaign must resolve to exactly three wind realizations")

    for wind in wind_plan.realizations:
        print(f"generating/reusing {wind.wind_id}", flush=True)
        run_turbsim(prepare_turbsim_realization(wind, paths, root))

    winds = {wind.wind_id: wind for wind in wind_plan.realizations}
    labels = ["LC1_ED", "LC1_BD", "LC2_ED", "LC2_BD", "LC3_ED", "LC3_BD"]
    report = []
    for label, case in zip(labels, cases):
        print(f"preparing {label} ({case.case_id})", flush=True)
        prepared = prepare_openfast_case(
            case, paths, winds[wind_plan.case_to_wind[case.case_id]], root
        )
        start = time.perf_counter()
        result = run_openfast(prepared, paths)
        wall = time.perf_counter() - start
        row = {
            "label": label,
            "case": case.case_id,
            "structural_model": case.scientific["structural_model"],
            "status": result.status,
            "return_code": result.return_code,
            "wall_clock_s": wall,
            "output": str(result.output_path),
        }
        report.append(row)
        (root / "production_run_summary.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        print(
            f"{label}: {result.status}, rc={result.return_code}, "
            f"wall={wall:.1f}s, output={result.output_path}",
            flush=True,
        )
        if result.return_code != 0:
            raise SystemExit(f"{label} failed; campaign stopped. Inspect its runtime log.")

    print("all six structural-comparison cases completed", flush=True)


if __name__ == "__main__":
    main()
