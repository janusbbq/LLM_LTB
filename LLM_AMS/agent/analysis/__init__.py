"""Cross-scenario analytics over saved AMS run records (roadmap Step 2).

Deterministic, LLM-free: reads the structured records a study writes
(``study_results.csv`` + ``run_memory/*.json``) and turns them into
comparison tables and rankings. The report writer lives in
``agent/tools/write_report.py``.
"""

from agent.analysis.aggregate import aggregate_long, load_study
from agent.analysis.rank import (
    dispatch_delta,
    failed_runs,
    lmp_ranking,
    most_loaded_lines,
    objective_summary,
    run_status_summary,
)

__all__ = [
    "load_study",
    "aggregate_long",
    "objective_summary",
    "lmp_ranking",
    "most_loaded_lines",
    "dispatch_delta",
    "run_status_summary",
    "failed_runs",
]
