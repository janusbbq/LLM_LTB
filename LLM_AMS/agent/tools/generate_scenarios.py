"""Turn a StudySpec into a scenario table (Step 1.4).

Pure function — no AMS, no LLM — so it is fast and trivially unit-testable.
"""

from __future__ import annotations

import csv
import os
from typing import Any, Dict, List, Optional, Tuple

from agent.schemas.study import StudySpec


COLUMNS = [
    "scenario_id",
    "scenario_label",
    "routine",
    "solver",
    "target_type",
    "target_id",
    "load_scale",
    "slot",
    "tags",
    "status",
]


def _label(scale: float) -> str:
    if abs(scale - 1.0) < 1e-9:
        return "baseline"
    pct = int(round(abs(scale - 1.0) * 100))
    return f"{'high' if scale > 1.0 else 'low'}_{pct}"


def _target_type(target: str) -> str:
    if target == "all":
        return "all"
    if target.lower().startswith("area"):
        return "area"
    return "load"


def generate_scenarios(
    spec: StudySpec, output_dir: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Build the scenario rows; optionally write ``scenario_table.csv``.

    Returns ``(rows, csv_path)`` where ``csv_path`` is ``None`` if not written.
    """
    target = spec.load_sweep.target
    ttype = _target_type(target)
    tags = ",".join(spec.tags)

    rows: List[Dict[str, Any]] = []
    for i, scale in enumerate(spec.load_sweep.scales):
        rows.append(
            {
                "scenario_id": f"S{i:03d}",
                "scenario_label": _label(scale),
                "routine": spec.routine,
                "solver": spec.solver,
                "target_type": ttype,
                "target_id": target,
                "load_scale": float(scale),
                "slot": "",
                "tags": tags,
                "status": "pending",
            }
        )

    csv_path: Optional[str] = None
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        csv_path = os.path.join(output_dir, "scenario_table.csv")
        with open(csv_path, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

    return rows, csv_path
