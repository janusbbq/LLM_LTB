"""JSON-friendly, routine-aware case data tables for the web UI.

Parallels :mod:`agent.ams_engine.snapshots` (which builds ``rich.Table`` objects
for the terminal). Here every table is a plain dict::

    {"title": str, "columns": [str, ...], "rows": [[str, ...], ...]}

so it serializes straight to JSON for the browser. The selection of *which*
tables to show is driven by the active routine's family, exactly like the CLI.
"""

from typing import List

import pandas as pd

from agent.ams_engine.routines import routine_family


# ----------------------------------------------------------------- helpers
def _safe_df(model) -> pd.DataFrame:
    try:
        return model.as_df()
    except Exception:
        return pd.DataFrame()


def _fmt(v, prec: int = 3, max_abs: float = 999.0) -> str:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return str(v)
    if abs(x) >= max_abs:
        return "—"
    return f"{x:.{prec}f}"


def _table(title: str, columns: List[str], rows: List[List[str]]) -> dict:
    return {"title": title, "columns": columns, "rows": rows}


def _gen_cost_lookup(ss):
    """idx -> (csu, csd, c2, c1, c0) for each generator from GCost."""
    g = _safe_df(ss.GCost)
    out = {}
    if not g.empty:
        for _, row in g.iterrows():
            out[row["gen"]] = (
                row.get("csu", 0.0), row.get("csd", 0.0),
                row.get("c2", 0.0), row.get("c1", 0.0), row.get("c0", 0.0),
            )
    return out


# ----------------------------------------------------------------- per-family
def _dced(ss) -> List[dict]:
    """Generator dispatch + line limits + loads (DCOPF / RTED / ED)."""
    out: List[dict] = []
    cost = _gen_cost_lookup(ss)

    rows = []
    for _, row in _safe_df(ss.StaticGen).iterrows():
        c2, c1, c0 = cost.get(row["idx"], (0, 0, 0, 0, 0))[2:]
        rows.append([
            str(row["idx"]), str(row["bus"]),
            "ON" if row.get("u", 1) >= 0.5 else "OFF",
            _fmt(row.get("p0")), _fmt(row.get("pmin")), _fmt(row.get("pmax")),
            _fmt(c2), _fmt(c1), _fmt(c0), _fmt(row.get("R10")),
        ])
    out.append(_table(
        "Generators — dispatch inputs",
        ["idx", "bus", "u", "p0 (pu)", "Pmin (pu)", "Pmax (pu)", "c2", "c1", "c0", "ramp10"],
        rows,
    ))

    rows = []
    for _, row in _safe_df(ss.Line).iterrows():
        rows.append([
            str(row["idx"]), str(row["bus1"]), str(row["bus2"]),
            "ON" if row.get("u", 1) >= 0.5 else "OFF",
            _fmt(row.get("x"), prec=4), _fmt(row.get("rate_a")),
        ])
    out.append(_table(
        "Lines — flow / rating",
        ["idx", "bus1", "bus2", "u", "x (pu)", "rate_a (pu)"],
        rows,
    ))

    rows = []
    for _, row in _safe_df(ss.PQ).iterrows():
        rows.append([
            str(row["idx"]), str(row["bus"]),
            _fmt(row.get("p0")), _fmt(row.get("q0")),
        ])
    out.append(_table("Loads — base demand", ["idx", "bus", "p0 (pu)", "q0 (pu)"], rows))
    return out


def _dcuc(ss) -> List[dict]:
    """UC: commitment parameters + costs + horizon size."""
    out: List[dict] = []
    cost = _gen_cost_lookup(ss)

    rows = []
    for _, row in _safe_df(ss.StaticGen).iterrows():
        csu, csd, c2, c1, c0 = cost.get(row["idx"], (0, 0, 0, 0, 0))
        rows.append([
            str(row["idx"]), str(row["bus"]),
            "ON" if row.get("u", 1) >= 0.5 else "OFF",
            _fmt(row.get("pmin")), _fmt(row.get("pmax")), _fmt(row.get("R10")),
            _fmt(row.get("td1")), _fmt(row.get("td2")),
            _fmt(row.get("ton0")), _fmt(row.get("toff0")),
            _fmt(csu), _fmt(csd), _fmt(c2), _fmt(c1), _fmt(c0),
        ])
    out.append(_table(
        "Generators — unit commitment parameters",
        ["idx", "bus", "u0", "Pmin", "Pmax", "ramp10",
         "td1 (min up)", "td2 (min dn)", "ton0", "toff0",
         "csu", "csd", "c2", "c1", "c0"],
        rows,
    ))

    if hasattr(ss, "Horizon"):
        h = _safe_df(ss.Horizon)
        names = list(h.get("name", []))
        n_uct = sum(str(n).startswith("UCT") for n in names)
        n_edt = sum(str(n).startswith("EDT") for n in names)
        out.append(_table(
            "Horizon — time periods",
            ["UC periods (UCT*)", "ED periods (EDT*)"],
            [[str(n_uct), str(n_edt)]],
        ))
    return out


def _aced(ss) -> List[dict]:
    """ACOPF: voltage limits + P/Q caps + AC branch params."""
    out: List[dict] = []

    rows = []
    for _, row in _safe_df(ss.Bus).iterrows():
        rows.append([
            str(row["idx"]), _fmt(row.get("Vn"), prec=1),
            _fmt(row.get("v0"), prec=4), _fmt(row.get("a0"), prec=4),
            _fmt(row.get("vmin")), _fmt(row.get("vmax")),
        ])
    out.append(_table(
        "Buses — voltage constraints",
        ["idx", "Vn", "v0 (pu)", "a0 (rad)", "Vmin", "Vmax"],
        rows,
    ))

    pv = _safe_df(ss.PV)
    if not pv.empty:
        cost = _gen_cost_lookup(ss)
        rows = []
        for _, row in pv.iterrows():
            _, _, c2, c1, c0 = cost.get(row["idx"], (0, 0, 0, 0, 0))
            rows.append([
                str(row["idx"]), str(row["bus"]),
                _fmt(row.get("pmin")), _fmt(row.get("pmax")),
                _fmt(row.get("qmin")), _fmt(row.get("qmax")),
                _fmt(row.get("v0")), _fmt(c2), _fmt(c1), _fmt(c0),
            ])
        out.append(_table(
            "Generators — AC capability + cost",
            ["idx", "bus", "Pmin", "Pmax", "Qmin", "Qmax", "v0", "c2", "c1", "c0"],
            rows,
        ))

    rows = []
    for _, row in _safe_df(ss.Line).iterrows():
        rows.append([
            str(row["idx"]), str(row["bus1"]), str(row["bus2"]),
            _fmt(row.get("r"), prec=4), _fmt(row.get("x"), prec=4),
            _fmt(row.get("b"), prec=4), _fmt(row.get("rate_a")),
        ])
    out.append(_table(
        "Branches — AC parameters",
        ["idx", "bus1", "bus2", "r (pu)", "x (pu)", "b (pu)", "rate_a"],
        rows,
    ))
    return out


def _ded(ss) -> List[dict]:
    """DOPF: horizon size + temporal generator envelope."""
    out: List[dict] = []

    if hasattr(ss, "Horizon"):
        h = _safe_df(ss.Horizon)
        out.append(_table("Horizon — total time slots", ["total slots"], [[str(len(h))]]))

    cost = _gen_cost_lookup(ss)
    rows = []
    for _, row in _safe_df(ss.StaticGen).iterrows():
        c2, c1, c0 = cost.get(row["idx"], (0, 0, 0, 0, 0))[2:]
        rows.append([
            str(row["idx"]), str(row["bus"]),
            _fmt(row.get("pmin")), _fmt(row.get("pmax")),
            _fmt(row.get("R10")), _fmt(c1),
        ])
    out.append(_table(
        "Generators — temporal envelope",
        ["idx", "bus", "Pmin", "Pmax", "ramp10", "c1"],
        rows,
    ))
    return out


def _pf(ss) -> List[dict]:
    """Power flow: bus state + line topology."""
    out: List[dict] = []

    rows = []
    for _, row in _safe_df(ss.Bus).iterrows():
        rows.append([
            str(row["idx"]), _fmt(row.get("Vn"), prec=1),
            _fmt(row.get("v0"), prec=4), _fmt(row.get("a0"), prec=4),
            _fmt(row.get("vmin")), _fmt(row.get("vmax")),
        ])
    out.append(_table(
        "Buses — base state",
        ["idx", "Vn", "v0 (pu)", "a0 (rad)", "Vmin", "Vmax"],
        rows,
    ))

    rows = []
    for _, row in _safe_df(ss.Line).iterrows():
        rows.append([
            str(row["idx"]), str(row["bus1"]), str(row["bus2"]),
            _fmt(row.get("r"), prec=4), _fmt(row.get("x"), prec=4), _fmt(row.get("rate_a")),
        ])
    out.append(_table(
        "Branches — impedance + rating",
        ["idx", "bus1", "bus2", "r (pu)", "x (pu)", "rate_a"],
        rows,
    ))
    return out


# ----------------------------------------------------------------- dispatch
def get_case_tables(ss, routine_name: str) -> dict:
    """Return ``{"label": str, "tables": [table, ...]}`` for the active routine."""
    if ss is None:
        return {"label": "", "tables": []}

    family = routine_family(routine_name)
    if family in ("uc", "uc2"):
        return {"label": "DCUC — Unit Commitment focus", "tables": _dcuc(ss)}
    if family in ("acopf", "grbopt"):
        return {"label": "ACED — AC OPF focus", "tables": _aced(ss)}
    if family in ("dopf",):
        return {"label": "DED — Multi-period dispatch focus", "tables": _ded(ss)}
    if family in ("dcpf", "pflow", "pypower"):
        return {"label": "PF — Power flow focus", "tables": _pf(ss)}
    if family in ("dcopf", "dcopf2", "rted", "rted2", "ed", "ed2"):
        return {"label": "DCED — DC Economic Dispatch focus", "tables": _dced(ss)}
    return {"label": f"{family} — generic focus", "tables": _dced(ss)}
