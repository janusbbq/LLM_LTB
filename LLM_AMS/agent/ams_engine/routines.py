"""Routine metadata: solver compatibility, families, descriptions."""

import re
from dataclasses import dataclass, field
from typing import List, Optional

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


# ---------------------------------------------------------------- routine name resolution
# Deterministic (no-LLM) mapping of free-form routine requests to canonical AMS
# class names, so "unit commitment", "real-time economic dispatch", "dc opf",
# "rted 2 with storage" etc. all resolve without relying on the model guessing.

_CLASS_LOWER = {c.lower(): c for c in class_names}

# Base family -> accepted phrases (checked as whole words; longest match wins).
_BASE_ALIASES = [
    ("ACOPF", ["acopf", "ac opf", "ac-opf", "ac optimal power flow"]),
    ("DCOPF", ["dcopf", "dc opf", "dc-opf", "dc optimal power flow",
               "optimal power flow"]),
    ("DCPF",  ["dcpf", "dc power flow", "dc pf", "dc-pf", "dc powerflow"]),
    ("PFlow", ["pflow", "power flow", "powerflow", "ac power flow", "ac pf", "pf"]),
    ("RTED",  ["rted", "real-time economic dispatch", "real time economic dispatch",
               "realtime economic dispatch", "rt economic dispatch", "real-time ed"]),
    ("ED",    ["ed", "economic dispatch", "econ dispatch"]),
    ("UC",    ["uc", "unit commitment", "commitment"]),
    ("DOPF",  ["dopf", "distribution opf", "distributional opf", "distributed opf",
               "distribution optimal power flow"]),
    ("OPF",   ["grbopt", "gurobi opf", "gurobi optimods"]),
]


@dataclass
class RoutineResolution:
    status: str                          # "single" | "ambiguous" | "not_found"
    name: Optional[str] = None           # canonical class name
    candidates: List[str] = field(default_factory=list)
    message: str = ""
    query: str = ""


def _strip_sep(text: str) -> str:
    return re.sub(r"[\s_\-]+", "", text)


def _detect_modifier(ql: str, tokens: set) -> str:
    if "esp" in tokens:
        return "ESP"
    if "es" in tokens or "esd" in tokens or "energy storage" in ql \
            or "storage" in ql or "battery" in ql:
        return "ES"
    if "dg" in tokens or "distributed generation" in ql \
            or "distributed generator" in ql:
        return "DG"
    if "vis" in tokens or "visualization" in ql or "visualisation" in ql:
        return "VIS"
    return ""


def resolve_routine(query: str) -> RoutineResolution:
    """Resolve a free-form routine request into a canonical AMS class name."""
    q = (query or "").strip()
    if not q:
        return RoutineResolution("not_found", message="Empty routine request.", query=query)
    ql = q.lower()
    tokens = set(re.findall(r"[a-z0-9]+", ql))

    # 1. Exact class name, tolerant of separators: "rted 2 es" -> "rted2es".
    for cand in (ql, _strip_sep(ql)):
        if cand in _CLASS_LOWER:
            name = _CLASS_LOWER[cand]
            # Bare "opf" is the gurobi routine; steer to DCOPF (usually intended).
            if name == "OPF" and cand == "opf":
                return RoutineResolution(
                    "ambiguous", "DCOPF", ["DCOPF", "ACOPF", "OPF"],
                    "Interpreting 'OPF' as DCOPF (say 'acopf' or 'grbopt' for the others).",
                    query)
            return RoutineResolution("single", name, query=query)

    # 2. Base family by longest matching alias phrase.
    base = None
    best_len = 0
    for canon, phrases in _BASE_ALIASES:
        for p in phrases:
            if re.search(rf"(?<![a-z]){re.escape(p)}(?![a-z])", ql) and len(p) > best_len:
                base, best_len = canon, len(p)

    if base is None:
        return RoutineResolution(
            "not_found",
            message=(f"Couldn't identify a routine from '{query}'. Known routines: "
                     f"{', '.join(class_names)}."),
            query=query)

    if base == "OPF":
        return RoutineResolution("single", "OPF", query=query)

    # 3. Compose base + optional version(2) + optional modifier, validate against AMS.
    ver = "2" if ("2" in tokens or "ii" in tokens or "v2" in tokens
                  or "version2" in _strip_sep(ql) or "type2" in _strip_sep(ql)) else ""
    mod = _detect_modifier(ql, tokens)

    for cand in (base + ver + mod, base + ver, base + mod, base):
        if cand.lower() in _CLASS_LOWER:
            return RoutineResolution("single", _CLASS_LOWER[cand.lower()], query=query)

    return RoutineResolution("single", base, query=query)


def is_routine_class(name: str) -> bool:
    """True if *name* is exactly an AMS routine class name (case-sensitive).

    Lets callers that already hold a canonical class name (e.g. the web UI
    selecting "OPF") bypass the natural-language steering in ``resolve_routine``.
    """
    return name in class_names


def routine_help() -> str:
    """Short human-readable routine catalog for discovery / help output."""
    families = {
        "Power flow": ["DCPF", "PFlow", "ACOPF"],
        "OPF / dispatch": ["DCOPF", "RTED", "ED", "UC", "DOPF"],
    }
    lines = []
    for label, names in families.items():
        avail = [n for n in names if n in class_names]
        lines.append(f"- {label}: {', '.join(avail)}")
    return "\n".join(lines)



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
