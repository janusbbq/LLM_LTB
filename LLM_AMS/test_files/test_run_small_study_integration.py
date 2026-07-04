"""Integration test: a real 5-bus DCOPF sweep end-to-end.

Marked integration because it invokes AMS/cvxpy (per the roadmap test principle).
Run with:  python -m pytest test_files/test_run_small_study_integration.py -v
"""

from agent.memory_service import InMemoryAMSRunMemory
from agent.schemas.study import LoadSweep, StudySpec
from agent.tools.run_small_study import run_small_study


def test_five_scale_sweep_saves_records(tmp_path):
    spec = StudySpec(
        base_case="5bus",
        routine="DCOPF",
        solver="CLARABEL",
        load_sweep=LoadSweep(target="PQ_1", scales=[0.90, 0.95, 1.00, 1.05, 1.10]),
    )
    mem = InMemoryAMSRunMemory()
    result = run_small_study(spec, memory=mem, output_dir=str(tmp_path))

    # all five scenarios solved
    assert len(result["summary"]) == 5
    assert all(s["status"] == "optimal" for s in result["summary"])

    # five records persisted, each self-contained with full results
    records = mem.list_runs()
    assert len(records) == 5
    for rec in records:
        assert rec["objective_cost"] is not None
        assert rec["solver_status"] == "optimal"
        assert rec["scenario_label"] is not None
        assert rec["load_changes"][0]["idx"] == "PQ_1"
        assert rec["lmp_summary"] is not None
        for key in ("pg", "plf", "pd", "pi"):
            assert rec["results"][key] is not None

    # objective is monotonically increasing with load (sanity of the sweep)
    objs = [s["objective"] for s in result["summary"]]
    assert objs == sorted(objs)

    # final result table written, and scenario_table statuses no longer 'pending'
    results_csv = (tmp_path / "study_results.csv").read_text()
    assert "objective" in results_csv and "solver_status" in results_csv
    scenario_csv = (tmp_path / "scenario_table.csv").read_text()
    assert "pending" not in scenario_csv
    assert "success" in scenario_csv
