"""Objective recomputation check (Section B — optimality / economic).

After an economic-dispatch solve, recompute the routine's reported objective
from primitives (generator cost coefficients + the solved dispatch) and compare
against the value the optimizer returned. A mismatch means the reported
objective is not internally consistent with the dispatch — a wrong solve, a
data problem, or a reporting bug.

This is the Section-B companion to :func:`constraint_check.check_constraints`
(Section A — physical limits). It is intentionally scoped to the single-period
economic-dispatch routines **DCOPF** and **RTED**; multi-period commitment
(ED / UC) and LMP/KKT checks are out of scope here.

The exact objective expressions are taken verbatim from the AMS routine
``obj.e_str`` (so this tracks what AMS actually optimizes, not an assumption):

    DCOPF:  sum(c2*pg**2) + sum(c1*pg) + sum(ug*c0)

    RTED:   t**2 * sum(c2*pg**2) + sum(ug*c0)
            + t * ( sum(c1*pg) + sum(cru*pru) + sum(crd*prd) )

where ``t = RTED.config.t`` is the dispatch interval in hours (5 min = 1/12 h),
``ug`` the commitment status, and ``cru/crd`` / ``pru/prd`` the reserve cost
coefficients / up- and down-reserve provisions. Note the RTED c2 term scales as
``t**2`` and the no-load term ``ug*c0`` is *not* scaled by ``t`` — so a naive
``t * energy_cost`` is only correct when c2 = 0 and c0 = 0.
"""

from typing import Any, Dict, Optional

import numpy as np

# Routines this check knows how to recompute.
SUPPORTED = ("DCOPF", "RTED")


def _gen_cost_coeffs(ss, gens):
    """Return (c2, c1, c0) arrays aligned to ``gens`` dispatch order."""
    gc_idx = ss.GCost.find_idx(keys="gen", values=list(gens))
    c2 = np.asarray(ss.GCost.get(src="c2", idx=gc_idx, attr="v"), dtype=float)
    c1 = np.asarray(ss.GCost.get(src="c1", idx=gc_idx, attr="v"), dtype=float)
    c0 = np.asarray(ss.GCost.get(src="c0", idx=gc_idx, attr="v"), dtype=float)
    return c2, c1, c0


def _reserve_cost(rtn) -> float:
    """RTED reserve term ``sum(cru*pru) + sum(crd*prd)`` (0 if reserves are free).

    Only cost-bearing reserves contribute, so zero-cost coefficients are skipped
    before touching the provision arrays.
    """
    total = 0.0
    for cost_name, prov_name in (("cru", "pru"), ("crd", "prd")):
        if not (hasattr(rtn, cost_name) and hasattr(rtn, prov_name)):
            continue
        c = np.asarray(getattr(rtn, cost_name).v, dtype=float)
        p = np.asarray(getattr(rtn, prov_name).v, dtype=float)
        mask = c != 0.0
        if mask.any():
            total += float((c[mask] * p[mask]).sum())
    return total


def recompute_objective(ss, results: dict) -> Optional[float]:
    """Recompute the objective from primitives, or ``None`` if unsupported.

    ``None`` means "no recompute attempted" — the routine isn't DCOPF/RTED or
    the dispatch isn't single-period (a 2-D ``pg`` from a multi-period run).
    """
    routine = results.get("routine")
    if routine not in SUPPORTED:
        return None
    pg = np.asarray(results.get("pg"), dtype=float)
    if pg.ndim != 1:  # DCOPF/RTED are single-period
        return None

    gens = results.get("gen_idx") or list(ss.StaticGen.get_all_idxes())
    c2, c1, c0 = _gen_cost_coeffs(ss, gens)
    rtn = getattr(ss, routine)
    ug = (np.asarray(rtn.ug.v, dtype=float)
          if hasattr(rtn, "ug") else np.ones_like(pg))

    if routine == "DCOPF":
        return float((c2 * pg ** 2).sum() + (c1 * pg).sum() + (ug * c0).sum())

    # RTED
    t = float(rtn.config.t)
    reserve = _reserve_cost(rtn)
    return float(t ** 2 * (c2 * pg ** 2).sum()
                 + (ug * c0).sum()
                 + t * ((c1 * pg).sum() + reserve))


def check_objective(ams_ctx, results: dict,
                    rtol: float = 1e-4, atol: float = 1e-6) -> Dict[str, Any]:
    """Compare the reported objective against a from-primitives recompute.

    Mirrors :func:`constraint_check.check_constraints` (takes the ``AMSContext``
    and the ``results`` dict from ``solve()``). Returns a dict:

        ``routine``     the routine name
        ``status``      "PASS" | "FAIL" | "SKIP" | "ERROR"
        ``passed``      True / False, or None when not applicable
        ``reported``    objective returned by the optimizer
        ``recomputed``  objective rebuilt from cost coeffs + dispatch
        ``abs_err`` / ``rel_err``   agreement metrics (None when not applicable)
        ``detail``      short human-readable message

    Errors while reading the system are surfaced in ``detail`` with
    ``status="ERROR"`` — never silently swallowed.
    """
    routine = results.get("routine")
    reported = results.get("objective")
    out: Dict[str, Any] = {
        "routine": routine,
        "status": "SKIP",
        "passed": None,
        "reported": reported,
        "recomputed": None,
        "abs_err": None,
        "rel_err": None,
        "detail": "",
    }

    ss = getattr(ams_ctx, "system", ams_ctx)
    if ss is None:
        out["detail"] = "no system loaded"
        return out
    if routine not in SUPPORTED:
        out["detail"] = f"objective recompute not implemented for {routine}"
        return out
    if reported is None:
        out["detail"] = "no reported objective to compare against"
        return out

    try:
        recomputed = recompute_objective(ss, results)
    except Exception as exc:  # visible, not swallowed
        out["status"] = "ERROR"
        out["detail"] = f"{type(exc).__name__}: {exc}"
        return out

    if recomputed is None:
        out["detail"] = "dispatch not single-period; recompute skipped"
        return out

    abs_err = abs(recomputed - reported)
    scale = max(abs(reported), abs(recomputed), 1.0)
    rel_err = abs_err / scale
    passed = (abs_err <= atol) or (rel_err <= rtol)

    out.update(
        status="PASS" if passed else "FAIL",
        passed=bool(passed),
        recomputed=recomputed,
        abs_err=abs_err,
        rel_err=rel_err,
        detail=(f"reported={reported:.6g} recomputed={recomputed:.6g} "
                f"abs_err={abs_err:.2e} rel_err={rel_err:.2e}"),
    )
    return out
