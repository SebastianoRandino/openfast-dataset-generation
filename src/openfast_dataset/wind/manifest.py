"""Small machine-readable wind plan manifest writers."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .planner import WindPlan


def write_manifest(plan: WindPlan, output: Path) -> tuple[Path, Path]:
    output.mkdir(parents=True, exist_ok=True)
    payload = {"winds": [{"wind_id": item.wind_id, "scientific_hash": item.scientific_hash, "kind": item.kind, "content": item.content, "source": {"turbulent": "generated_turbsim", "steady": "steady", "external": "external_bts"}[item.kind], "turbsim_input_path": str(item.directory / "turbsim.inp") if item.kind == "turbulent" else None, "expected_bts_path": str(item.directory / "wind.bts") if item.kind == "turbulent" else item.content.get("bts_path"), "generation_status": "planned" if item.kind == "turbulent" else "not_required"} for item in plan.realizations], "case_to_wind": plan.case_to_wind}
    json_path = output / "wind_manifest.json"; json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    csv_path = output / "case_to_wind.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["case_id", "wind_id"]); writer.writeheader(); writer.writerows({"case_id": key, "wind_id": value} for key, value in sorted(plan.case_to_wind.items()))
    return json_path, csv_path
