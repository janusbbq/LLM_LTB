"""Cross-scenario rankings and deltas over loaded runs (roadmap Step 2.4).

Pure functions over the ``load_study`` output. Numbers come straight from the
records — nothing is inferred by an LLM. Baseline is the ``load_scale == 1.0``
(or ``scenario_label == "baseline"``) run; deltas are computed against it.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional


def _baseline(runs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for run in runs:
        if run.get("scenario_label") == "baseline" or run.get("load_scale") == 1.0:
            return run
    return None


def _flat_max_index(values: List[Any], key=abs) -> Optional[int]:
    """Index of the max (by ``key``) among 1-D numeric entries, or None."""
    candidates = [(i, v) for i, v in enumerate(values) if not isinstance(v, list)]
    if not candidates:
        return None
    return max(candidates, key=lambda iv: key(iv[1]))[0]


def objective_summary(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Per scenario: objective, delta and % change vs the baseline run."""
    base = _baseline(runs)
    base_obj = base["objective"] if base else None
    out: List[Dict[str, Any]] = []
    for run in runs:
        obj = run["objective"]
        delta = obj - base_obj if (obj is not None and base_obj is not None) else None
        pct = (delta / base_obj * 100.0) if (delta is not None and base_obj) else None
        out.append(
            {
                "scenario_id": run["scenario_id"],
                "scenario_label": run["scenario_label"],
                "load_scale": run["load_scale"],
                "objective": obj,
                "delta_vs_baseline": delta,
                "pct_change": pct,
                "solver_status": run["solver_status"],
            }
        )
    return out


def lmp_ranking(runs: List[Dict[str, Any]], top_n: int = 10) -> List[Dict[str, Any]]:
    """Scenarios ranked by peak LMP (from the record's pi / lmp_summary)."""
    rows: List[Dict[str, Any]] = []
    for run in runs:
        record = run.get("record")
        if not record:
            continue
        lmp = record.get("lmp_summary")
        pi = (record.get("results") or {}).get("pi")
        if not lmp or not pi:
            continue
        bus = _flat_max_index(pi, key=lambda x: x)
        rows.append(
            {
                "scenario_id": run["scenario_id"],
                "scenario_label": run["scenario_label"],
                "load_scale": run["load_scale"],
                "max_lmp": lmp.get("max"),
                "mean_lmp": lmp.get("mean"),
                "max_lmp_bus": f"Bus_{bus}" if bus is not None else None,
            }
        )
    rows.sort(key=lambda r: (r["max_lmp"] is not None, r["max_lmp"] or 0.0), reverse=True)
    return rows[:top_n]


def most_loaded_lines(runs: List[Dict[str, Any]], top_n: int = 10) -> List[Dict[str, Any]]:
    """Scenarios ranked by their most heavily-flowed line.

    NOTE: this ranks by |plf| magnitude, NOT loading vs. rate_a — the records do
    not carry line limits yet. True "binding line" detection needs rate_a
    captured in engine.solve() (a small additive follow-up).
    """
    rows: List[Dict[str, Any]] = []
    for run in runs:
        record = run.get("record")
        if not record:
            continue
        results = record.get("results") or {}
        plf = results.get("plf")
        lines = results.get("line_idx")
        if not plf or not lines:
            continue
        i = _flat_max_index(plf, key=abs)
        if i is None:
            continue
        rows.append(
            {
                "scenario_id": run["scenario_id"],
                "scenario_label": run["scenario_label"],
                "load_scale": run["load_scale"],
                "line": lines[i] if i < len(lines) else f"Line_{i}",
                "abs_flow": abs(plf[i]),
            }
        )
    rows.sort(key=lambda r: r["abs_flow"], reverse=True)
    return rows[:top_n]


def dispatch_delta(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Per generator, dispatch change vs the baseline run (single-period)."""
    base = _baseline(runs)
    if not base or not base.get("record"):
        return []
    base_res = base["record"].get("results") or {}
    base_pg = base_res.get("pg")
    gens = base_res.get("gen_idx")
    if not base_pg or not gens:
        return []
    out: List[Dict[str, Any]] = []
    for run in runs:
        record = run.get("record")
        if not record or run is base:
            continue
        pg = (record.get("results") or {}).get("pg")
        if not pg:
            continue
        for gen, b, v in zip(gens, base_pg, pg):
            if isinstance(v, list) or isinstance(b, list):
                continue  # multi-period delta deferred
            out.append(
                {
                    "scenario_id": run["scenario_id"],
                    "scenario_label": run["scenario_label"],
                    "generator": gen,
                    "baseline_pg": b,
                    "pg": v,
                    "delta_pg": v - b,
                }
            )
    return out


def run_status_summary(runs: List[Dict[str, Any]]) -> Dict[str, int]:
    """Counts by solver status (optimal / failed / error / ...)."""
    return dict(Counter((run.get("solver_status") or "unknown") for run in runs))


def failed_runs(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Scenarios that did not solve optimally, with any error message."""
    return [
        {
            "scenario_id": run["scenario_id"],
            "scenario_label": run["scenario_label"],
            "load_scale": run["load_scale"],
            "status": run["solver_status"],
            "error": run["error"],
        }
        for run in runs
        if run.get("solver_status") != "optimal"
    ]
