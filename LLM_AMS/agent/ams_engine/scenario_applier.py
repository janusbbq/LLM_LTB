"""Apply a load scenario to a live AMS system (Step 1.5).

Uses ``PQ.set`` (in-memory, ephemeral) — NOT ``PQ.alter`` (persistent) — so each
scenario is a temporary, isolated perturbation of a freshly-loaded base case.
The caller is responsible for the routine ``update('pd')`` afterwards.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _target_loads(system, target: str) -> List[str]:
    all_idx = list(system.PQ.idx.v)
    if target == "all":
        return all_idx
    if target in all_idx:
        return [target]
    raise ValueError(
        f"Load target '{target}' not found. Use 'all' or one of {all_idx}."
    )


def apply_load_scenario(system, target: str, load_scale: float) -> List[Dict[str, Any]]:
    """Scale ``p0`` of the target load(s) by ``load_scale`` relative to base.

    Assumes ``system`` was freshly loaded (so the current p0 IS the base p0).
    Returns the structured load changes for the run record.
    """
    changes: List[Dict[str, Any]] = []
    for idx in _target_loads(system, target):
        base = float(system.PQ.get(src="p0", idx=idx, attr="v"))
        new = base * float(load_scale)
        system.PQ.set(src="p0", idx=idx, attr="v", value=new)
        changes.append(
            {"idx": idx, "param": "p0", "from": base, "to": new, "scale": float(load_scale)}
        )
    return changes
