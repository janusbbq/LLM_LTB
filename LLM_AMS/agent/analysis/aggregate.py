"""Load a study's records and unpivot them into a long-form table.

A "run" here combines a row of ``study_results.csv`` (scenario_id, load_scale,
run_id, status) with its full ``run_memory/<run_id>.json`` record (pg / plf /
pd / pi arrays). ``aggregate_long`` flattens the per-device arrays into one row
per (run, variable, device, slot) — the shape the report + rankings consume.

The ``slot`` dimension is kept even for single-period runs so the same
aggregation works unchanged for multi-period (temporal) records later.
"""

from __future__ import annotations

import csv
import json
import os
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _read_results_table(study_dir: str) -> List[Dict[str, str]]:
    path = os.path.join(study_dir, "study_results.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"No study_results.csv found in {study_dir!r}")
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def _load_record(study_dir: str, run_id: str) -> Optional[Dict[str, Any]]:
    if not run_id:
        return None
    path = os.path.join(study_dir, "run_memory", f"{run_id}.json")
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        return json.load(fh)


def _to_float(value: Optional[str]) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load_study(study_dir: str) -> List[Dict[str, Any]]:
    """Return one dict per scenario: results-table row + attached record."""
    runs: List[Dict[str, Any]] = []
    for row in _read_results_table(study_dir):
        run_id = (row.get("run_id") or "").strip()
        runs.append(
            {
                "scenario_id": row.get("scenario_id"),
                "scenario_label": row.get("scenario_label"),
                "load_scale": _to_float(row.get("load_scale")),
                "routine": row.get("routine"),
                "solver": row.get("solver"),
                "objective": _to_float(row.get("objective")),
                "solver_status": row.get("solver_status"),
                "run_id": run_id or None,
                "error": (row.get("error") or None),
                "record": _load_record(study_dir, run_id),
            }
        )
    return runs


# variable -> (idx key in record.results, owner model, unit)
_VAR_META: Dict[str, Tuple[Optional[str], str, str]] = {
    "pg": ("gen_idx", "StaticGen", "pu"),
    "plf": ("line_idx", "Line", "pu"),
    "pd": ("load_idx", "PQ", "pu"),
    "pi": (None, "Bus", "$/pu (LMP)"),  # pi is per-bus; records carry no bus_idx
}


def _iter_device_slot(values: List[Any], labels: List[str]) -> Iterable[Tuple[str, Any, Any]]:
    """Yield (device, slot, value). Handles 1-D (per device) and 2-D
    (device x slot) arrays — the latter is the multi-period shape."""
    for device, v in zip(labels, values):
        if isinstance(v, list):                # 2-D: one value per time slot
            for slot, sv in enumerate(v):
                yield device, slot, sv
        else:
            yield device, "", v


def aggregate_long(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flatten runs into long-form rows keyed by run/variable/device/slot."""
    rows: List[Dict[str, Any]] = []
    for run in runs:
        record = run.get("record")
        if not record:
            continue
        results = record.get("results") or {}
        for var, (idx_key, owner, unit) in _VAR_META.items():
            values = results.get(var)
            if not values:
                continue
            if idx_key is None:                # pi: label buses positionally
                labels = [f"Bus_{i}" for i in range(len(values))]
            else:
                labels = results.get(idx_key) or [str(i) for i in range(len(values))]
            for device, slot, value in _iter_device_slot(values, labels):
                rows.append(
                    {
                        "run_id": run["run_id"],
                        "scenario_id": run["scenario_id"],
                        "scenario_label": run["scenario_label"],
                        "load_scale": run["load_scale"],
                        "slot": slot,
                        "owner": owner,
                        "device": device,
                        "variable": var,
                        "value": value,
                        "unit": unit,
                    }
                )
    return rows
