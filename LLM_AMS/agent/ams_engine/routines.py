"""Routine metadata: solver compatibility, families, descriptions."""

from typing import List

import cvxpy as _cp
from ams.routines import all_routines, class_names
from ams.shared import mip_solvers, misocp_solvers


# Routine family -> high-level problem class
# (Used to decide which solvers are compatible.)
LP_QP_FAMILIES = {"dcpf", "pflow", "dcopf", "dcopf2", "rted", "rted2", "ed", "ed2", "dopf"}
MIP_FAMILIES = {"uc", "uc2"}
ACOPF_FAMILIES = {"acopf"}  # SOCP-ish in AMS; use ECOS/CLARABEL/SCS
PYPOWER_FAMILIES = {"pypower"}  # solver argument is ignored (uses PYPOWER internally)
GUROBI_FAMILIES = {"grbopt"}    # OPF via gurobi-optimods


def routine_family(routine_name: str) -> str:
    """Return the family key for an AMS routine class name (e.g. 'RTED' -> 'rted')."""
    for family, classes in all_routines.items():
        if routine_name in classes:
            return family
    return "unknown"


def all_routine_names() -> List[str]:
    """Flat list of all routine class names (e.g. ['DCPF', 'PFlow', 'ACOPF', ...])."""
    return list(class_names)


def installed_solvers() -> List[str]:
    """Solvers cvxpy can actually call right now."""
    return list(_cp.installed_solvers())


def compatible_solvers(routine_name: str) -> List[str]:
    """Solvers that can solve the given routine, restricted to what's installed.

    Phase 1 routines (DCOPF/RTED/ED/DCPF/PFlow) are LP/QP and accept any conic solver.
    UC is MIP and needs MIP-capable solvers.
    """
    family = routine_family(routine_name)
    installed = installed_solvers()

    if family in PYPOWER_FAMILIES:
        # Internal solver — no cvxpy choice
        return ["(internal: pypower)"]
    if family in GUROBI_FAMILIES:
        return ["GUROBI"] if "GUROBI" in installed else []

    if family in MIP_FAMILIES:
        return [s for s in installed if s in mip_solvers]

    if family in ACOPF_FAMILIES:
        # SOCP-capable solvers
        preferred = ["CLARABEL", "SCS", "ECOS", "MOSEK"]
        return [s for s in preferred if s in installed]

    if family in LP_QP_FAMILIES:
        # Any conic solver works for LP/QP
        preferred = ["CLARABEL", "OSQP", "SCS", "HIGHS", "SCIPY", "SCIP",
                     "GUROBI", "MOSEK", "CPLEX", "ECOS"]
        return [s for s in preferred if s in installed]

    return installed
