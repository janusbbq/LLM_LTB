"""Turn a study's records into cross-scenario CSVs + a Markdown report (Step 2.7).

Deterministic and LLM-free. Reads ``<study_dir>/study_results.csv`` +
``run_memory/*.json`` and writes, into the same folder:

    results_long.csv        one row per (run, variable, device, slot)
    objective_summary.csv   objective + delta-vs-baseline per scenario
    run_status_summary.csv   counts by solver status
    summary.md              the human-readable report

Run it with:  python -m agent.tools.write_report generated/study_<ts>/
"""

from __future__ import annotations

import csv
import os
import sys
from typing import Any, Dict, List, Optional

from agent.analysis.aggregate import aggregate_long, load_study
from agent.analysis.rank import (
    dispatch_delta,
    failed_runs,
    lmp_ranking,
    most_loaded_lines,
    objective_summary,
    run_status_summary,
)


def _fmt(value: Any, nd: int = 4) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, float):
        return f"{value:.{nd}f}"
    return str(value)


def _write_csv(path: str, rows: List[Dict[str, Any]], columns: List[str]) -> None:
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _md_table(rows: List[Dict[str, Any]], columns: List[str], headers: List[str]) -> str:
    if not rows:
        return "_(none)_\n"
    out = ["| " + " | ".join(headers) + " |",
           "| " + " | ".join("---" for _ in headers) + " |"]
    for r in rows:
        out.append("| " + " | ".join(_fmt(r.get(c)) for c in columns) + " |")
    return "\n".join(out) + "\n"


def write_report(study_dir: str, output_dir: Optional[str] = None) -> Dict[str, str]:
    """Aggregate + rank + write the CSVs and summary.md. Returns output paths."""
    output_dir = output_dir or study_dir
    os.makedirs(output_dir, exist_ok=True)

    runs = load_study(study_dir)
    obj = objective_summary(runs)
    lmp = lmp_ranking(runs)
    lines = most_loaded_lines(runs)
    disp = dispatch_delta(runs)
    status = run_status_summary(runs)
    failed = failed_runs(runs)
    long_rows = aggregate_long(runs)

    long_path = os.path.join(output_dir, "results_long.csv")
    obj_path = os.path.join(output_dir, "objective_summary.csv")
    status_path = os.path.join(output_dir, "run_status_summary.csv")
    report_path = os.path.join(output_dir, "summary.md")

    _write_csv(
        long_path, long_rows,
        ["run_id", "scenario_id", "scenario_label", "load_scale", "slot",
         "owner", "device", "variable", "value", "unit"],
    )
    _write_csv(
        obj_path, obj,
        ["scenario_id", "scenario_label", "load_scale", "objective",
         "delta_vs_baseline", "pct_change", "solver_status"],
    )
    _write_csv(
        status_path,
        [{"status": k, "count": v} for k, v in sorted(status.items())],
        ["status", "count"],
    )

    routine = runs[0]["routine"] if runs else "—"
    solver = runs[0]["solver"] if runs else "—"
    n_ok = status.get("optimal", 0)

    md = [
        "# AMS Scenario Study Report\n",
        "## Study configuration\n",
        f"- Study folder: `{study_dir}`",
        f"- Routine / solver: **{routine} / {solver}**",
        f"- Scenarios: **{len(runs)}**  ·  solved optimally: **{n_ok}/{len(runs)}**\n",
        "## Run status\n",
        _md_table([{"status": k, "count": v} for k, v in sorted(status.items())],
                  ["status", "count"], ["status", "count"]),
        "## Objective cost by scenario (Δ vs baseline)\n",
        _md_table(obj,
                  ["scenario_label", "load_scale", "objective", "delta_vs_baseline", "pct_change"],
                  ["scenario", "load_scale", "objective", "Δ vs base", "% change"]),
        "## Highest LMP by scenario\n",
        _md_table(lmp,
                  ["scenario_label", "load_scale", "max_lmp", "max_lmp_bus", "mean_lmp"],
                  ["scenario", "load_scale", "max LMP", "at bus", "mean LMP"]),
        "## Most-loaded line by scenario\n",
        "_Ranked by |flow| magnitude; true binding needs line ratings (see limitations)._\n",
        _md_table(lines,
                  ["scenario_label", "load_scale", "line", "abs_flow"],
                  ["scenario", "load_scale", "line", "|flow| (pu)"]),
        "## Dispatch change vs baseline (top shifts)\n",
        _md_table(sorted(disp, key=lambda d: abs(d["delta_pg"]), reverse=True)[:10],
                  ["scenario_label", "generator", "baseline_pg", "pg", "delta_pg"],
                  ["scenario", "generator", "base pg", "pg", "Δ pg"]),
        "## Failed / non-optimal runs\n",
        _md_table(failed,
                  ["scenario_label", "load_scale", "status", "error"],
                  ["scenario", "load_scale", "status", "error"]),
        "## Limitations\n",
        "- LMP is per-bus but records carry no bus labels yet, so buses are positional (`Bus_i`).",
        "- Line ranking is by |flow|, not loading vs `rate_a` (line limits not captured yet).",
        "- Multi-period (temporal) records aggregate per slot; dispatch deltas are single-period.\n",
    ]
    with open(report_path, "w") as fh:
        fh.write("\n".join(md))

    return {
        "report": report_path,
        "results_long": long_path,
        "objective_summary": obj_path,
        "run_status_summary": status_path,
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m agent.tools.write_report <study_dir>")
        raise SystemExit(2)
    paths = write_report(sys.argv[1])
    print("Wrote:")
    for name, path in paths.items():
        print(f"  {name:20} {path}")
