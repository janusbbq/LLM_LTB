"""Execute a small load-scenario study (Step 1.6).

Plain orchestration function — it loops the scenario table over the *existing*
engine (``AMSContext.solve``) and saves one structured record per run. It needs
NO LangGraph change, so it is fully conflict-free with the web side. The NL
entry point (``parse_study_request``) is a separate, optional layer.

Isolation: each scenario reloads the base case, so perturbations never leak
between scenarios.
"""

from __future__ import annotations

import csv
import os
from typing import Any, Dict, List, Optional

from agent.ams_engine.engine import AMSContext
from agent.ams_engine.scenario_applier import apply_load_scenario
from agent.memory_service import (
    AMSRunMemory,
    InMemoryAMSRunMemory,
    make_ams_run_record,
)
from agent.schemas.study import StudySpec
from agent.tools.generate_scenarios import COLUMNS, generate_scenarios


RESULT_COLUMNS = [
    "scenario_id",
    "scenario_label",
    "load_scale",
    "routine",
    "solver",
    "objective",
    "solver_status",
    "run_id",
]


def _rewrite_scenario_table(rows: List[Dict[str, Any]], output_dir: str) -> str:
    """Re-write scenario_table.csv so its status column reflects the run."""
    path = os.path.join(output_dir, "scenario_table.csv")
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_results_table(
    summary: List[Dict[str, Any]], spec: StudySpec, output_dir: str
) -> str:
    """Write the final result table with objective + status per scenario."""
    path = os.path.join(output_dir, "study_results.csv")
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=RESULT_COLUMNS)
        writer.writeheader()
        for s in summary:
            writer.writerow(
                {
                    "scenario_id": s["scenario_id"],
                    "scenario_label": s["label"],
                    "load_scale": s["load_scale"],
                    "routine": spec.routine,
                    "solver": spec.solver,
                    "objective": s["objective"],
                    "solver_status": s["status"],
                    "run_id": s["run_id"],
                }
            )
    return path


def run_small_study(
    spec: StudySpec,
    ctx: Optional[AMSContext] = None,
    memory: Optional[AMSRunMemory] = None,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate scenarios, run each, and persist one record per run.

    Returns a summary dict: ``scenario_table`` path, the ``rows`` (with updated
    status), a per-scenario ``summary`` list, and the ``memory`` used.
    """
    rows, csv_path = generate_scenarios(spec, output_dir=output_dir)
    ctx = ctx or AMSContext()
    memory = memory or InMemoryAMSRunMemory()

    summary: List[Dict[str, Any]] = []
    for row in rows:
        try:
            ctx.load_case(spec.base_case)                      # fresh base — isolation
            ctx.set_routine(spec.routine)
            load_changes = apply_load_scenario(
                ctx.system, row["target_id"], row["load_scale"]
            )
            ctx.active_routine().update("pd")
            results = ctx.solve(spec.solver)

            record = make_ams_run_record(
                case_path=ctx.case_path,
                routine=spec.routine,
                solver=spec.solver,
                scenario_label=row["scenario_label"],
                inputs={
                    "load_changes": load_changes,
                    "generator_changes": [],
                    "line_changes": [],
                    "time_horizon": None,
                },
                results=results,
            )
            run_id = memory.save_run(record)
            row["status"] = "success"
            summary.append(
                {
                    "scenario_id": row["scenario_id"],
                    "label": row["scenario_label"],
                    "load_scale": row["load_scale"],
                    "objective": results.get("objective"),
                    "status": record["solver_status"],
                    "run_id": run_id,
                }
            )
        except Exception as exc:  # a failed scenario must not abort the study
            row["status"] = "failed"
            summary.append(
                {
                    "scenario_id": row["scenario_id"],
                    "label": row["scenario_label"],
                    "load_scale": row["load_scale"],
                    "objective": None,
                    "status": f"error: {exc}",
                    "run_id": None,
                }
            )

    results_table = None
    if output_dir:
        csv_path = _rewrite_scenario_table(rows, output_dir)   # statuses now filled
        results_table = _write_results_table(summary, spec, output_dir)

    return {
        "scenario_table": csv_path,
        "results_table": results_table,
        "rows": rows,
        "summary": summary,
        "memory": memory,
    }


def _print_summary(result: Dict[str, Any]) -> None:
    print("\nStudy complete — "
          f"{sum(1 for s in result['summary'] if s['status'] == 'optimal')}"
          f"/{len(result['summary'])} solved, records saved.\n")
    print(f"{'scenario_id':<12}{'label':<10}{'scale':>7}   {'objective':>12}   status")
    print("-" * 56)
    for s in result["summary"]:
        obj = f"{s['objective']:.6f}" if isinstance(s["objective"], (int, float)) else "—"
        print(f"{s['scenario_id']:<12}{s['label']:<10}{s['load_scale']:>7.2f}   {obj:>12}   {s['status']}")
    if result["scenario_table"]:
        print(f"\nscenario_table: {result['scenario_table']}")
    if result["results_table"]:
        print(f"results_table:  {result['results_table']}")


if __name__ == "__main__":
    # Live demo: a 5-scale sweep on PQ_1 of the 5-bus case with DCOPF.
    from agent.memory_service import JsonFileAMSRunMemory
    from agent.schemas.study import LoadSweep

    demo_spec = StudySpec(
        base_case="5bus",
        routine="DCOPF",
        solver="CLARABEL",
        load_sweep=LoadSweep(target="PQ_1", scales=[0.90, 0.95, 1.00, 1.05, 1.10]),
    )
    mem = JsonFileAMSRunMemory(root_dir="generated/study_demo/run_memory")
    result = run_small_study(demo_spec, memory=mem, output_dir="generated/study_demo")
    _print_summary(result)
    print(f"saved {len(mem.list_runs())} AMSRunRecords → generated/study_demo/run_memory/")
