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
    assert "optimal" in scenario_csv          # unified vocab (was "success")


def test_non_converged_is_consistent_and_nulls_objective(tmp_path, monkeypatch):
    """A solve that returns without raising but does NOT converge must be marked
    'failed' consistently across the scenario table, results table, and record,
    and must not report an objective."""
    import agent.tools.run_small_study as rss

    monkeypatch.setattr(rss, "apply_load_scenario", lambda system, target, scale: [])

    class _Rtn:
        def update(self, *a):
            pass

    class _Ctx:
        case_path = "c"
        system = object()
        def load_case(self, case):
            pass
        def set_routine(self, name):
            pass
        def active_routine(self):
            return _Rtn()
        def solve(self, solver):
            # solver returns a value but did not converge
            return {"converged": False, "exit_code": 1, "objective": 42.0,
                    "pg": [1.0], "plf": [1.0], "pd": [1.0], "pi": [1.0],
                    "gen_idx": ["g"], "line_idx": ["l"], "load_idx": ["PQ_1"]}

    spec = StudySpec(load_sweep=LoadSweep(target="PQ_1", scales=[1.0]))
    mem = InMemoryAMSRunMemory()
    result = rss.run_small_study(spec, ctx=_Ctx(), memory=mem, output_dir=str(tmp_path))

    # scenario table row and summary agree — both 'failed', neither 'success'/'optimal'
    assert result["rows"][0]["status"] == "failed"
    assert result["summary"][0]["status"] == "failed"
    # objective nulled despite the solver returning 42.0
    assert result["summary"][0]["objective"] is None
    assert mem.list_runs()[0]["objective_cost"] is None
    # CSV files consistent
    assert "failed" in (tmp_path / "scenario_table.csv").read_text()
    assert "failed" in (tmp_path / "study_results.csv").read_text()
