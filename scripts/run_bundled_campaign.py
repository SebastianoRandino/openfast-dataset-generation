"""Prepare a campaign using repository-local dependencies; execution is opt-in."""

from __future__ import annotations

import argparse
from pathlib import Path

from openfast_dataset.campaign.resolver import resolve_campaign
from openfast_dataset.cases import prepare_openfast_case, run_openfast
from openfast_dataset.config import load_campaign
from openfast_dataset.paths import load_machine_paths
from openfast_dataset.wind.execution import prepare_turbsim_realization, run_turbsim
from openfast_dataset.wind.planner import plan_winds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign")
    parser.add_argument("--paths", default="configs/paths.bundled.yaml")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--run-winds", action="store_true", help="execute TurbSim if needed")
    parser.add_argument("--run", action="store_true", help="execute winds and all OpenFAST cases")
    args = parser.parse_args()
    paths = load_machine_paths(args.paths)
    cases = resolve_campaign(load_campaign(args.campaign))
    winds = plan_winds(cases)
    by_id = {wind.wind_id: wind for wind in winds.realizations}
    root = Path(args.output_root)
    for wind in winds.realizations:
        if wind.kind != "turbulent":
            continue
        if args.run or args.run_winds:
            run_turbsim(prepare_turbsim_realization(wind, paths, root))
        elif not (root / "wind" / wind.wind_id / "wind.bts").is_file():
            parser.error("missing turbulent wind: use --run-winds or --run to generate it")
    for case in cases:
        wind = by_id.get(winds.case_to_wind.get(case.case_id))
        prepared = prepare_openfast_case(case, paths, wind, root)
        if args.run:
            result = run_openfast(prepared, paths)
            print(f"{case.case_id}: {result.status} output={result.output_path}", flush=True)
        else:
            print(f"{case.case_id}: prepared {prepared.fst_path}", flush=True)


if __name__ == "__main__":
    main()
