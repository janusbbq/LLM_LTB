"""Unit tests for generate_scenarios — pure, no AMS, no LLM."""

from agent.schemas.study import LoadSweep, StudySpec
from agent.tools.generate_scenarios import generate_scenarios


def test_default_sweep_labels_and_ids():
    spec = StudySpec(load_sweep=LoadSweep(target="PQ_1"))
    rows, csv_path = generate_scenarios(spec)

    assert csv_path is None
    assert [r["scenario_id"] for r in rows] == ["S000", "S001", "S002", "S003", "S004"]
    assert [r["scenario_label"] for r in rows] == [
        "low_10", "low_5", "baseline", "high_5", "high_10",
    ]
    assert all(r["target_type"] == "load" and r["target_id"] == "PQ_1" for r in rows)
    assert all(r["status"] == "pending" for r in rows)


def test_target_all_is_typed_all():
    rows, _ = generate_scenarios(StudySpec(load_sweep=LoadSweep(target="all")))
    assert rows[0]["target_type"] == "all"


def test_writes_csv(tmp_path):
    spec = StudySpec(load_sweep=LoadSweep(target="PQ_1", scales=[1.0, 1.1]))
    rows, csv_path = generate_scenarios(spec, output_dir=str(tmp_path))

    assert csv_path is not None
    content = (tmp_path / "scenario_table.csv").read_text()
    assert "scenario_id" in content and "high_10" in content
    assert len(rows) == 2
