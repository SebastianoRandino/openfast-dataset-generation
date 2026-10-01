"""Prepare six cases or explicitly run a 10 s LC1 smoke pair; never run the full campaign."""

from __future__ import annotations

import argparse
import json
import time
from copy import deepcopy
from pathlib import Path

from openfast_dataset.campaign.models import ResolvedCase
from openfast_dataset.campaign.resolver import resolve_campaign
from openfast_dataset.cases import prepare_openfast_case, run_openfast
from openfast_dataset.cases.execution import probe_openfast_version
from openfast_dataset.config import load_campaign
from openfast_dataset.paths import load_machine_paths, resolve_openfast_executable
from openfast_dataset.waves.planner import plan_waves
from openfast_dataset.wind.execution import prepare_turbsim_realization, run_turbsim
from openfast_dataset.wind.planner import plan_winds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", default="configs/campaigns/structural_comparison_v5.yaml")
    parser.add_argument("--paths", default="configs/paths.yaml")
    parser.add_argument("--output-root", required=True)
    parser.add_argument(
        "--smoke", action="store_true", help="explicit opt-in: run LC1 ED/BD for 10 s"
    )
    args = parser.parse_args()
    cases = resolve_campaign(load_campaign(args.campaign))
    if len(cases) != 6 or len(plan_winds(cases).realizations) != 3:
        parser.error("expected six cases and three wind realizations")
    paths = load_machine_paths(args.paths)
    if probe_openfast_version(resolve_openfast_executable(paths, "5.0.0")) != "5.0.0":
        parser.error("this campaign requires a verified OpenFAST 5.0.0 executable")
    root = Path(args.output_root)
    wind_plan = plan_winds(cases)
    wave_plan = plan_waves(cases)
    root.mkdir(parents=True, exist_ok=True)
    (root / "campaign_manifest.json").write_text(
        json.dumps(
            {
                "cases": [case.normalized() for case in cases],
                "case_to_wind": wind_plan.case_to_wind,
                "case_to_wave": wave_plan.case_to_wave,
            },
            indent=2,
        )
        + "\n"
    )
    # Generate full-duration campaign winds even for smoke; reuse the same dependency.
    for wind in wind_plan.realizations:
        print(f"generating/reusing {wind.wind_id}", flush=True)
        run_turbsim(prepare_turbsim_realization(wind, paths, root))
    winds = {wind.wind_id: wind for wind in wind_plan.realizations}
    for case in cases:
        prepare_openfast_case(case, paths, winds[wind_plan.case_to_wind[case.case_id]], root)
    print("prepared six 400 s cases; no full-campaign simulations launched", flush=True)
    if args.smoke:
        reports = []
        for case in cases[:2]:
            science = deepcopy(case.scientific)
            science["numerics"]["duration_s"] = 10.0
            smoke = ResolvedCase(
                "smoke_" + case.case_id, None, science, {**case.provenance, "smoke_duration_s": 10}
            )
            prepared = prepare_openfast_case(
                smoke, paths, winds[wind_plan.case_to_wind[case.case_id]], root
            )
            start = time.perf_counter()
            try:
                result = run_openfast(prepared, paths)
            finally:
                report = {
                    "structural_model": science["structural_model"],
                    "wall_clock_s": time.perf_counter() - start,
                    "runtime": json.loads(
                        (prepared.workspace / "openfast_runtime.json").read_text()
                    ),
                }
                reports.append(report)
                (root / "smoke_report.json").write_text(json.dumps(reports, indent=2) + "\n")
            print(
                f"{science['structural_model']}: {result.status}, rc={result.return_code}, wall={report['wall_clock_s']:.3f}s",
                flush=True,
            )


if __name__ == "__main__":
    main()
