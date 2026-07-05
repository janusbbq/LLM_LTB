"""Structured run memory for AMS scenario studies (Step 0.3 / 0.4).

Two things live here and *only* here on the agent side:

  1. ``AMSRunMemory``   — a database-agnostic Protocol (the contract).
  2. ``make_ams_run_record`` — builds a structured record from Inputs + engine
     results only (never from assistant prose).

Plus two lightweight reference implementations so the CLI and tests are
unblocked without a database:

  * ``InMemoryAMSRunMemory``  — a dict, for tests.
  * ``JsonFileAMSRunMemory``  — one JSON file per run, for the CLI demo.

The production SQLite-backed implementation is intentionally NOT here — it
lives under ``web/backend/services/`` and is owned by the web side. Keep the
Protocol here, keep the DB there (mirrors pv-curve-llm).
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

import numpy as np


# A run_id is derived from user-influenced fields (routine / scenario_label) and,
# in web mode, may arrive from an external request. Never let it reach the
# filesystem raw — strip path separators and any other unsafe characters so it
# cannot escape the store directory (path traversal). Platform-independent:
# whitelisting drops both "/" and "\" regardless of os.sep.
_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


def safe_run_id(run_id: str) -> str:
    """Return a filename-safe token for ``run_id`` (no traversal, no separators)."""
    cleaned = _UNSAFE_FILENAME.sub("_", str(run_id)).strip("._")
    return cleaned or "run"


# --------------------------------------------------------------------------- #
# Contract
# --------------------------------------------------------------------------- #
@runtime_checkable
class AMSRunMemory(Protocol):
    """Database-agnostic store for structured AMS run records."""

    def save_run(self, record: Dict[str, Any]) -> str:
        """Persist a record; return its ``run_id``."""
        ...

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Return one record by id, or ``None``."""
        ...

    def list_runs(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Return all records, optionally filtered by exact field match."""
        ...


# --------------------------------------------------------------------------- #
# Record builder — structured data only
# --------------------------------------------------------------------------- #
def _summarize(values: Any) -> Optional[Dict[str, float]]:
    """min / mean / max over a (possibly 2-D) numeric array, or None."""
    if values is None:
        return None
    try:
        arr = np.asarray(values, dtype=float).ravel()
        if arr.size == 0:
            return None
        return {"min": float(arr.min()), "mean": float(arr.mean()), "max": float(arr.max())}
    except Exception:
        return None


def make_ams_run_record(
    *,
    case_path: str,
    routine: str,
    solver: str,
    scenario_label: Optional[str],
    inputs: Dict[str, Any],
    results: Dict[str, Any],
    export_paths: Optional[Dict[str, str]] = None,
    plot_paths: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build one ``AMSRunRecord`` from structured inputs + engine results.

    ``inputs`` carries the deterministic scenario changes (load/gen/line) and an
    optional ``time_horizon``. ``results`` is the dict returned by
    ``AMSContext.solve()``. No assistant text is read here.
    """
    pg = results.get("pg")
    pg_shape = list(np.asarray(pg).shape) if pg is not None else None
    converged = bool(results.get("converged", False))

    lmp = _summarize(results.get("pi"))
    if lmp is not None:
        lmp["values"] = list(np.asarray(results["pi"], dtype=float).ravel())

    return {
        "run_id": safe_run_id(f"{routine}_{scenario_label or 'run'}_{uuid.uuid4().hex[:6]}"),
        "case_path": case_path,
        "routine": routine,
        "solver": solver,
        "scenario_label": scenario_label,
        "time_horizon": inputs.get("time_horizon"),
        "load_changes": inputs.get("load_changes", []),
        "generator_changes": inputs.get("generator_changes", []),
        "line_changes": inputs.get("line_changes", []),
        # Only trust the objective when the solve converged — a non-converged
        # solve can still return a stale/meaningless value.
        "objective_cost": results.get("objective") if converged else None,
        "solver_status": "optimal" if converged else "failed",
        "pg_shape": pg_shape,
        "lmp_summary": lmp,
        "line_flow_summary": _summarize(results.get("plf")),
        "congestion_summary": None,  # filled by Step 2 analytics
        # Full numeric results, so a record is self-contained for Step 2
        # analytics and cross-scenario comparison (no re-solve needed).
        "results": {
            "pg": results.get("pg"),
            "plf": results.get("plf"),
            "pd": results.get("pd"),
            "pi": results.get("pi"),
            "gen_idx": results.get("gen_idx"),
            "line_idx": results.get("line_idx"),
            "load_idx": results.get("load_idx"),
        },
        "export_paths": export_paths or {},
        "plot_paths": plot_paths or [],
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "notes": None,
    }


# --------------------------------------------------------------------------- #
# Reference implementations (agent-side; NOT the production DB)
# --------------------------------------------------------------------------- #
def _matches(record: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> bool:
    if not filters:
        return True
    return all(record.get(k) == v for k, v in filters.items())


class InMemoryAMSRunMemory:
    """Dict-backed store — for tests and ephemeral CLI sessions."""

    def __init__(self) -> None:
        self._runs: Dict[str, Dict[str, Any]] = {}

    def save_run(self, record: Dict[str, Any]) -> str:
        run_id = record["run_id"]
        self._runs[run_id] = dict(record)
        return run_id

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        return self._runs.get(run_id)

    def list_runs(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return [r for r in self._runs.values() if _matches(r, filters)]


class JsonFileAMSRunMemory:
    """One JSON file per run under ``root_dir`` — for the CLI demo."""

    def __init__(self, root_dir: str = "generated/run_memory") -> None:
        self.root_dir = root_dir
        os.makedirs(self.root_dir, exist_ok=True)

    def _path(self, run_id: str) -> str:
        # Sanitize here too (defense in depth): save_run/get_run may receive an
        # externally-supplied run_id that never went through make_ams_run_record.
        return os.path.join(self.root_dir, f"{safe_run_id(run_id)}.json")

    def save_run(self, record: Dict[str, Any]) -> str:
        run_id = record["run_id"]
        with open(self._path(run_id), "w") as fh:
            json.dump(record, fh, indent=2)
        return run_id

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        path = self._path(run_id)
        if not os.path.exists(path):
            return None
        with open(path) as fh:
            return json.load(fh)

    def list_runs(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for name in sorted(os.listdir(self.root_dir)):
            if name.endswith(".json"):
                with open(os.path.join(self.root_dir, name)) as fh:
                    rec = json.load(fh)
                if _matches(rec, filters):
                    out.append(rec)
        return out
