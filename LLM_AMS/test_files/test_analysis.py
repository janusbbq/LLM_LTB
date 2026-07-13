"""Tests for the cross-scenario analytics (Option A / roadmap Step 2)."""

from agent.analysis.aggregate import aggregate_long
from agent.analysis.rank import (
    dispatch_delta,
    failed_runs,
    lmp_ranking,
    most_loaded_lines,
    objective_summary,
    run_status_summary,
)


def _run(sid, label, scale, objective, status="optimal", pg=None, pi=None, plf=None):
    record = None
    if status == "optimal":
        pi = pi or [0.5, 3.0]
        record = {
            "results": {
                "pg": pg or [1.0, 2.0], "gen_idx": ["G1", "G2"],
                "pi": pi,
                "plf": plf or [0.4, -0.8], "line_idx": ["L1", "L2"],
                "pd": [3.0], "load_idx": ["PQ_1"],
            },
            "lmp_summary": {"min": min(pi), "mean": sum(pi) / len(pi), "max": max(pi)},
        }
    return {
        "scenario_id": sid, "scenario_label": label, "load_scale": scale,
        "routine": "DCOPF", "solver": "CLARABEL", "objective": objective,
        "solver_status": status, "run_id": f"r_{sid}", "error": None, "record": record,
    }


# ---------------------------------------------------------------- aggregate
def test_aggregate_long_unpivots_all_variables():
    rows = aggregate_long([_run("S0", "baseline", 1.0, 10.0)])
    # pg(2) + pi(2) + plf(2) + pd(1) = 7 rows
    assert len(rows) == 7
    pi_rows = [r for r in rows if r["variable"] == "pi"]
    assert {r["device"] for r in pi_rows} == {"Bus_0", "Bus_1"}   # positional bus labels
    g1 = next(r for r in rows if r["variable"] == "pg" and r["device"] == "G1")
    assert g1["value"] == 1.0 and g1["owner"] == "StaticGen" and g1["slot"] == ""


def test_aggregate_long_handles_2d_multiperiod():
    run = _run("S0", "baseline", 1.0, 10.0)
    run["record"]["results"]["pg"] = [[1.0, 1.5], [2.0, 2.5]]   # (device, slot)
    rows = [r for r in aggregate_long([run]) if r["variable"] == "pg"]
    assert {r["slot"] for r in rows} == {0, 1}
    assert len(rows) == 4   # 2 gens x 2 slots


# ---------------------------------------------------------------- rankings
def test_objective_delta_vs_baseline():
    runs = [_run("S0", "baseline", 1.0, 10.0), _run("S1", "high_10", 1.1, 12.0)]
    summ = {r["scenario_label"]: r for r in objective_summary(runs)}
    assert summ["baseline"]["delta_vs_baseline"] == 0.0
    assert summ["high_10"]["delta_vs_baseline"] == 2.0
    assert abs(summ["high_10"]["pct_change"] - 20.0) < 1e-9


def test_lmp_ranking_orders_by_peak_and_finds_bus():
    runs = [
        _run("S0", "baseline", 1.0, 10.0, pi=[0.5, 3.0]),
        _run("S1", "high_10", 1.1, 12.0, pi=[9.0, 1.0]),
    ]
    ranked = lmp_ranking(runs)
    assert ranked[0]["scenario_label"] == "high_10"      # 9.0 > 3.0
    assert ranked[0]["max_lmp"] == 9.0
    assert ranked[0]["max_lmp_bus"] == "Bus_0"


def test_most_loaded_line_by_magnitude():
    runs = [_run("S0", "baseline", 1.0, 10.0, plf=[0.4, -0.9])]
    top = most_loaded_lines(runs)
    assert top[0]["line"] == "L2" and abs(top[0]["abs_flow"] - 0.9) < 1e-9


def test_dispatch_delta_vs_baseline():
    runs = [
        _run("S0", "baseline", 1.0, 10.0, pg=[1.0, 2.0]),
        _run("S1", "high_10", 1.1, 12.0, pg=[1.5, 2.0]),
    ]
    deltas = {d["generator"]: d for d in dispatch_delta(runs)}
    assert deltas["G1"]["delta_pg"] == 0.5
    assert deltas["G2"]["delta_pg"] == 0.0


def test_status_summary_and_failed_runs():
    runs = [
        _run("S0", "baseline", 1.0, 10.0),
        _run("S1", "high_10", 1.1, None, status="failed"),
        _run("S2", "high_20", 1.2, None, status="error"),
    ]
    assert run_status_summary(runs) == {"optimal": 1, "failed": 1, "error": 1}
    failed = failed_runs(runs)
    assert {f["scenario_label"] for f in failed} == {"high_10", "high_20"}


# ---------------------------------------------------------------- end-to-end
def test_write_report_end_to_end(tmp_path):
    from agent.memory_service import JsonFileAMSRunMemory
    from agent.schemas.study import LoadSweep, StudySpec
    from agent.tools.run_small_study import run_small_study
    from agent.tools.write_report import write_report

    spec = StudySpec(
        base_case="5bus", routine="DCOPF", solver="CLARABEL",
        load_sweep=LoadSweep(target="PQ_1", scales=[0.9, 1.0, 1.1]),
    )
    # records must be persisted to <study_dir>/run_memory/ (as the CLI does),
    # since write_report reads them from disk
    memory = JsonFileAMSRunMemory(root_dir=str(tmp_path / "run_memory"))
    run_small_study(spec, memory=memory, output_dir=str(tmp_path))

    paths = write_report(str(tmp_path))
    report = (tmp_path / "summary.md").read_text()
    assert "AMS Scenario Study Report" in report
    assert "Highest LMP by scenario" in report
    assert "Objective cost by scenario" in report

    obj_csv = (tmp_path / "objective_summary.csv").read_text()
    assert "delta_vs_baseline" in obj_csv
    long_csv = (tmp_path / "results_long.csv").read_text()
    assert "pi" in long_csv and "Bus_0" in long_csv
    assert all(k in paths for k in ("report", "results_long", "objective_summary"))
