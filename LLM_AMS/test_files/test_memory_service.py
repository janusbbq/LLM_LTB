"""Unit tests for the memory record builder + reference stores (no AMS)."""

from agent.memory_service import (
    InMemoryAMSRunMemory,
    JsonFileAMSRunMemory,
    make_ams_run_record,
)


def _fake_results(obj=9.5, converged=True):
    return {
        "routine": "DCOPF",
        "solver": "CLARABEL",
        "converged": converged,
        "exit_code": 0,
        "objective": obj,
        "pg": [0.2, 1.6, 0.6],
        "plf": [-0.4, 0.5, 0.1],
        "pi": [0.77, 0.10, 3.0, 1.57, 0.92],
    }


def test_record_is_built_from_structured_data():
    rec = make_ams_run_record(
        case_path="/x/5bus.xlsx",
        routine="DCOPF",
        solver="CLARABEL",
        scenario_label="high_10",
        inputs={"load_changes": [{"idx": "PQ_1", "to": 3.3}]},
        results=_fake_results(),
    )
    assert rec["objective_cost"] == 9.5
    assert rec["solver_status"] == "optimal"
    assert rec["scenario_label"] == "high_10"
    assert rec["pg_shape"] == [3]
    assert rec["lmp_summary"]["max"] == 3.0
    assert rec["load_changes"][0]["idx"] == "PQ_1"
    # full numeric results are persisted (Step 2 needs them without re-solving)
    assert rec["results"]["pg"] == [0.2, 1.6, 0.6]
    assert rec["results"]["plf"] == [-0.4, 0.5, 0.1]
    assert rec["results"]["pi"][2] == 3.0


def test_failed_solve_marks_status_and_nulls_objective():
    # solver returned an objective (42.0) but did NOT converge
    rec = make_ams_run_record(
        case_path="c", routine="UC", solver="SCIP", scenario_label=None,
        inputs={}, results=_fake_results(obj=42.0, converged=False),
    )
    assert rec["solver_status"] == "failed"
    assert rec["objective_cost"] is None   # not trusted unless converged


def test_in_memory_store_roundtrip():
    mem = InMemoryAMSRunMemory()
    rec = make_ams_run_record(
        case_path="c", routine="DCOPF", solver="CLARABEL",
        scenario_label="baseline", inputs={}, results=_fake_results(),
    )
    run_id = mem.save_run(rec)
    assert mem.get_run(run_id)["scenario_label"] == "baseline"
    assert len(mem.list_runs({"routine": "DCOPF"})) == 1
    assert mem.list_runs({"routine": "UC"}) == []


def test_json_file_store_roundtrip(tmp_path):
    mem = JsonFileAMSRunMemory(root_dir=str(tmp_path))
    rec = make_ams_run_record(
        case_path="c", routine="DCOPF", solver="CLARABEL",
        scenario_label="baseline", inputs={}, results=_fake_results(),
    )
    run_id = mem.save_run(rec)
    assert mem.get_run(run_id)["objective_cost"] == 9.5
    assert len(mem.list_runs()) == 1


def test_safe_run_id_strips_separators():
    from agent.memory_service import safe_run_id
    assert "/" not in safe_run_id("a/b")
    assert "\\" not in safe_run_id("a\\b")
    assert safe_run_id("../../etc/passwd").count("/") == 0
    assert safe_run_id("") == "run"


def test_json_store_prevents_path_traversal(tmp_path):
    # A hostile run_id (as an external caller in web mode could supply) must not
    # escape the store directory.
    store = tmp_path / "store"
    mem = JsonFileAMSRunMemory(root_dir=str(store))
    rec = make_ams_run_record(
        case_path="c", routine="DCOPF", solver="CLARABEL",
        scenario_label="baseline", inputs={}, results=_fake_results(),
    )
    rec["run_id"] = "../../evil"          # bypasses make_ams_run_record sanitization
    mem.save_run(rec)

    # nothing written outside the store dir
    assert not (tmp_path / "evil.json").exists()
    assert not (tmp_path.parent / "evil.json").exists()
    assert list(store.glob("*.json"))     # the file is inside the store
    # get_run with the same hostile id resolves to the same in-store file
    assert mem.get_run("../../evil") is not None
