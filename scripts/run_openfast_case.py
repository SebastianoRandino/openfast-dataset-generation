"""Explicit opt-in single-case integration; never launches a campaign."""
import argparse

from openfast_dataset.campaign.resolver import resolve_campaign
from openfast_dataset.cases import prepare_openfast_case, run_openfast
from openfast_dataset.config import load_campaign
from openfast_dataset.paths import load_machine_paths

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("campaign")
parser.add_argument("--paths", default="configs/paths.yaml")
parser.add_argument("--output-root", required=True)
args = parser.parse_args()
cases = resolve_campaign(load_campaign(args.campaign))
if len(cases) != 1:
    parser.error("integration requires exactly one resolved case")
paths = load_machine_paths(args.paths)
prepared = prepare_openfast_case(cases[0], paths, output_root=args.output_root)
result = run_openfast(prepared, paths)
print(f"status={result.status} return_code={result.return_code} output={result.output_path}")
