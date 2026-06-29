"""AMSContext: thin wrapper around a live ``ams.System``.

Owns a single ``System`` instance per session. All Route 3-6 operations
mutate the system in place, mirroring the ex2.ipynb workflow:

    sp = ams.load(...)             # load_case
    sp.PQ.alter(...); sp.RTED.update('pd')   # apply_load_change
    sp.StaticGen.set(...); sp.RTED.update()  # trip_gen / restore_gen
    sp.Line.alter(...); sp.RTED.update()     # trip_line / restore_line
    sp.RTED.disable([...])                   # disable_constraints
    sp.RTED.config.update(t=1)               # set_config_t
    sp.RTED.run(solver=...)                  # solve
"""

import os
from typing import Any, Dict, List, Optional

import ams
import numpy as np

from agent.ams_engine.routines import compatible_solvers, routine_family


# AMS-shipped cases keyed by short alias the user can type.
SHIPPED_CASES = {
    "pjm5bus": "5bus/pjm5bus_demo.xlsx",
    "pjm5bus_demo": "5bus/pjm5bus_demo.xlsx",
    "5bus": "5bus/pjm5bus_demo.xlsx",
    "pjm5bus_ev": "5bus/pjm5bus_ev.xlsx",
    "pjm5bus_jumper": "5bus/pjm5bus_jumper.xlsx",
    "ieee14": "ieee14/ieee14.json",
    "ieee14_uced": "ieee14/ieee14_uced.xlsx",
    "ieee14_conn": "ieee14/ieee14_conn.xlsx",
    "ieee14_raw": "ieee14/ieee14.raw",
    "ieee39": "ieee39/ieee39.xlsx",
    "ieee39_uced": "ieee39/ieee39_uced.xlsx",
    "case14": "matpower/case14.m",
    "case39": "matpower/case39.m",
    "case118": "matpower/case118.m",
    "case300": "matpower/case300.m",
    "npcc": "npcc/npcc.xlsx",
    "wecc": "wecc/wecc.xlsx",
}


def resolve_case_path(case: str) -> str:
    """Resolve a short alias or sub-path into a real case file path.

    Order of resolution:
    1. Absolute path that exists on disk
    2. Short alias in SHIPPED_CASES
    3. Pass-through to ``ams.get_case`` (handles AMS-shipped sub-paths
       like ``5bus/pjm5bus_demo.xlsx``)
    """
    if os.path.isabs(case) and os.path.exists(case):
        return case
    if case in SHIPPED_CASES:
        return ams.get_case(SHIPPED_CASES[case])
    return ams.get_case(case)


class AMSContext:
    """Holds the live AMS System and the active routine name."""

    def __init__(self):
        self.system: Optional[ams.System] = None
        self.case_path: Optional[str] = None
        self.routine_name: str = "RTED"

    # ---------- Route 3: case I/O ----------
    def load_case(self, case: str) -> Dict[str, Any]:
        path = resolve_case_path(case)
        self.system = ams.load(path, setup=True, no_output=True)
        self.case_path = path
        return self.case_info()

    def case_info(self) -> Dict[str, Any]:
        if self.system is None:
            return {"loaded": False}
        ss = self.system
        gen_idx = list(ss.StaticGen.get_all_idxes())
        return {
            "loaded": True,
            "case_path": self.case_path,
            "n_bus": len(ss.Bus.idx.v),
            "n_line": len(ss.Line.idx.v),
            "n_pq": len(ss.PQ.idx.v),
            "n_pv": len(ss.PV.idx.v),
            "n_slack": len(ss.Slack.idx.v),
            "n_staticgen": len(gen_idx),
            "load_idx": list(ss.PQ.idx.v),
            "gen_idx": gen_idx,
            "line_idx": list(ss.Line.idx.v),
        }

    # ---------- Route 4: configure ----------
    def set_routine(self, name: str) -> str:
        name = name.upper().strip()
        if self.system is None:
            self.routine_name = name
            return name
        if not hasattr(self.system, name):
            raise ValueError(f"Routine '{name}' not found on system.")
        self.routine_name = name
        return name

    def active_routine(self):
        if self.system is None:
            raise RuntimeError("No case loaded. Use case_io to load one first.")
        return getattr(self.system, self.routine_name)

    def set_config_t(self, t: float) -> None:
        rtn = self.active_routine()
        rtn.config.update(t=float(t))
        rtn.update()

    def disable_constraints(self, names: List[str]) -> List[str]:
        rtn = self.active_routine()
        names = [n for n in names if n in rtn.constrs and rtn.constrs[n].is_disabled is False]
        if names:
            rtn.disable(names)
        return names

    def enable_constraints(self, names: List[str]) -> List[str]:
        rtn = self.active_routine()
        names = [n for n in names if n in rtn.constrs]
        if names:
            rtn.enable(names)
        return names

    def constraint_status(self) -> Dict[str, bool]:
        rtn = self.active_routine()
        return {name: (not c.is_disabled) for name, c in rtn.constrs.items()}

    # ---------- Route 5: physical modifications ----------
    def alter_load_p0(self, load_idx: str, value: float) -> None:
        if self.system is None:
            raise RuntimeError("No case loaded.")
        self.system.PQ.alter(src="p0", idx=[load_idx], value=[float(value)])
        self.active_routine().update("pd")

    def set_gen_status(self, gen_idx: str, online: bool) -> None:
        if self.system is None:
            raise RuntimeError("No case loaded.")
        self.system.StaticGen.set(src="u", idx=gen_idx, attr="v", value=1 if online else 0)
        self.active_routine().update()

    def set_line_status(self, line_idx: str, online: bool) -> None:
        if self.system is None:
            raise RuntimeError("No case loaded.")
        self.system.Line.alter(src="u", idx=line_idx, value=1 if online else 0)
        self.active_routine().update()

    def alter_line_rate(self, line_idx: str, rate_a: float) -> None:
        if self.system is None:
            raise RuntimeError("No case loaded.")
        self.system.Line.set(src="rate_a", idx=[line_idx], attr="v", value=[float(rate_a)])
        self.active_routine().update("rate_a")

    # ---------- Route 6: solve ----------
    def solve(self, solver: str = "CLARABEL") -> Dict[str, Any]:
        if self.system is None:
            raise RuntimeError("No case loaded.")
        rtn = self.active_routine()
        compat = compatible_solvers(self.routine_name)
        if compat and solver not in compat and "(internal: pypower)" not in compat:
            raise ValueError(
                f"Solver '{solver}' is not compatible with routine '{self.routine_name}'. "
                f"Compatible: {compat}"
            )
        ok = rtn.run(solver=solver)
        out: Dict[str, Any] = {
            "routine": self.routine_name,
            "solver": solver,
            "converged": bool(getattr(rtn, "converged", ok)),
            "exit_code": int(getattr(rtn, "exit_code", 0)),
        }
        if hasattr(rtn, "obj") and rtn.obj is not None:
            try:
                out["objective"] = float(np.asarray(rtn.obj.v))
            except Exception:
                out["objective"] = None
        for var_name in ("pg", "plf", "pd", "pn", "aBus", "vBus", "ug"):
            if hasattr(rtn, var_name):
                try:
                    arr = np.asarray(getattr(rtn, var_name).v, dtype=float)
                    out[var_name] = arr.tolist()
                except Exception:
                    pass
        # element idxes for plotting / display
        out["gen_idx"] = list(self.system.StaticGen.get_all_idxes())
        out["line_idx"] = list(self.system.Line.idx.v)
        out["load_idx"] = list(self.system.PQ.idx.v)
        return out
