r"""End-to-end retrieval smoke test (uses the live AMS System).

Run:  .\.venv\Scripts\python.exe _validate_load.py

Loads every shipped case through AMSContext (the exact path the app uses) via
its keyword alias, and sets every routine on a loaded system, to confirm that
retrieval actually results in a working system + routine — not just a matched
string. Exits non-zero on any failure.
"""

import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agent.ams_engine.case_catalog import CASES
from agent.ams_engine.engine import AMSContext
from agent.ams_engine.routines import all_routine_names


def main():
    fails = []
    caveats = []
    known_caveat = {e.key: e.caveat for e in CASES if e.caveat}

    print("=" * 66)
    print("LOADING EVERY CASE THROUGH AMSContext (by keyword alias)")
    print("=" * 66)
    for e in CASES:
        try:
            ctx = AMSContext()
            info = ctx.load_case(e.key)  # alias -> resolve_case -> ams.load(setup=True)
            if not info.get("loaded"):
                fails.append(f"LOAD {e.key}: reported not loaded")
                continue
            tag = "  (NOTE: catalog caveat is now stale — this loads)" if e.key in known_caveat else ""
            print(f"  ok  {e.key:16} {info['n_bus']:>5} bus  "
                  f"{info['n_line']:>4} line  {info['n_staticgen']:>3} gen   ({e.path}){tag}")
        except Exception as exc:
            detail = f"{e.key} ({e.path}): {type(exc).__name__}: {exc}"
            if e.key in known_caveat:
                caveats.append(f"{detail}\n         documented as: {known_caveat[e.key]}")
            else:
                fails.append(f"LOAD {detail}")

    print("\n" + "=" * 66)
    print("SETTING EVERY ROUTINE ON A LOADED SYSTEM")
    print("=" * 66)
    try:
        ctx = AMSContext()
        ctx.load_case("ieee14")
        optional = {"OPF"}  # gurobi-optimods routine; may be absent without gurobi
        for name in all_routine_names():
            try:
                got = ctx.set_routine(name)
                if got not in all_routine_names():
                    fails.append(f"SETROUTINE {name} -> {got!r} (not a routine class)")
                else:
                    print(f"  ok  {name:12} -> {got}")
            except Exception as exc:
                if name in optional:
                    caveats.append(f"routine {name}: not attached to this system "
                                   f"({type(exc).__name__})")
                else:
                    fails.append(f"SETROUTINE {name}: {type(exc).__name__}: {exc}")
    except Exception as exc:
        fails.append(f"SETUP for routine test: {exc}")

    print("\n" + "=" * 66)
    if caveats:
        print(f"KNOWN AMS LOAD CAVEATS (retrieval OK; ltbams can't parse these): {len(caveats)}")
        for c in caveats:
            print("  " + c)
        print("=" * 66)
    if fails:
        print(f"FAILURES: {len(fails)}")
        for f in fails:
            print("  " + f)
        print("=" * 66)
        return 1
    print("ALL CASES RETRIEVED; ALL LOADABLE CASES LOADED; ALL ROUTINES SET OK")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())
