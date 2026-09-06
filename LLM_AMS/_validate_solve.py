r"""Objective-recompute validation for DCOPF / RTED (uses the live AMS System).

Run:  /opt/anaconda3/envs/llm-ams/bin/python _validate_solve.py

For every shipped case, solves DCOPF and RTED and checks that the reported
objective matches an independent recompute from generator cost coefficients and
the solved dispatch (``agent.ams_engine.objective_check.check_objective``).

This is the *result*-verification layer — "is the solved answer self-consistent?"
— complementing ``_validate_retrieval.py`` / ``_validate_load.py``, which check
*retrieval* ("did the right case / routine load?"). Exits non-zero on any
objective mismatch. A case/routine that can't load, set, or converge is a SKIP,
not a failure (solvability is not what this validator asserts).
"""

import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agent.ams_engine.case_catalog import CASES
from agent.ams_engine.engine import AMSContext
from agent.ams_engine.objective_check import SUPPORTED, check_objective

SOLVER = "CLARABEL"


def main():
    fails = []
    skips = []
    n_checked = 0

    print("=" * 72)
    print("OBJECTIVE RECOMPUTE — DCOPF / RTED (reported vs from-primitives)")
    print("=" * 72)

    for e in CASES:
        try:
            ctx = AMSContext()
            info = ctx.load_case(e.key)
            if not info.get("loaded"):
                skips.append(f"{e.key}: not loaded")
                continue
        except Exception as exc:
            skips.append(f"{e.key}: load failed ({type(exc).__name__})")
            continue

        for routine in SUPPORTED:
            try:
                ctx.set_routine(routine)
                results = ctx.solve(SOLVER)
            except Exception as exc:
                skips.append(f"{e.key}/{routine}: solve error "
                             f"({type(exc).__name__}: {exc})")
                continue
            if not results.get("converged"):
                skips.append(f"{e.key}/{routine}: did not converge")
                continue

            res = check_objective(ctx, results)
            status = res["status"]
            if status == "PASS":
                n_checked += 1
                print(f"  ok   {e.key:16} {routine:6}  "
                      f"obj={res['reported']:.6g}  rel_err={res['rel_err']:.1e}")
            elif status == "SKIP":
                skips.append(f"{e.key}/{routine}: {res['detail']}")
            else:  # FAIL or ERROR
                fails.append(f"{e.key}/{routine}: {status} — {res['detail']}")
                print(f"  FAIL {e.key:16} {routine:6}  {res['detail']}")

    print("\n" + "=" * 72)
    if skips:
        print(f"SKIPPED (not solvable / not applicable): {len(skips)}")
        for s in skips:
            print("  " + s)
        print("=" * 72)
    if fails:
        print(f"OBJECTIVE MISMATCHES: {len(fails)}")
        for f in fails:
            print("  " + f)
        print("=" * 72)
        return 1
    print(f"ALL {n_checked} DCOPF/RTED OBJECTIVES MATCH THE RECOMPUTE")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
