"""Routine-aware data tables.

Given the loaded AMS System and the active routine name, return a list of
``(title, rich.Table)`` items that surface the most relevant inputs for the
problem at hand:

  DCED (DCOPF / RTED / ED)   → gen dispatch · line limits · loads
  DCUC (UC variants)         → gen commitment params (Pmin/Pmax, ramp, min up/down)
  ACED (ACOPF)               → bus voltage · gen P/Q caps · branch r/x/b
  DED  (DOPF)                → temporal envelope (horizon size + ramps)
  PF   (DCPF / PFlow)        → bus state + line topology

The CLI calls ``display_snapshot(ams_ctx, routine)`` whenever the case
changes or the active routine changes, so the user always sees the data
that actually matters for what they're about to solve.
"""

from typing import List, Tuple

import pandas as pd
from rich.table import Table

from agent.ams_engine.routines import routine_family


# ---------------------------------------------------------------- helpers
def _safe_df(model) -> pd.DataFrame:
    """Return ``model.as_df()`` or an empty DataFrame on any failure."""
    try:
        return model.as_df()
    except Exception:
        return pd.DataFrame()


def _fmt(v, prec=3, max_abs=999.0) -> str:
    """Pretty number for a table cell."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return str(v)
    if abs(x) >= max_abs:
        return "—"
    return f"{x:.{prec}f}"


def _make_table(title: str, columns: List[str], styles=None) -> Table:
    """Build a rich.Table styled to match the brand theme."""
    t = Table(
        title=title,
        title_style="brand",
        header_style="brand",
        border_style="brand_dim",
        show_lines=False,
        padding=(0, 1),
    )
    styles = styles or {}
    for c in columns:
        t.add_column(c, style=styles.get(c, "white"), no_wrap=True)
    return t


# ---------------------------------------------------------------- per-family
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


def _snap_dced(ss) -> List[Table]:
    """Generator dispatch + line constraints + loads."""
    out: List[Table] = []

    sg = _safe_df(ss.StaticGen)
    cost = _gen_cost_lookup(ss)
    t1 = _make_table(
        "Generators — dispatch inputs (DCED)",
        ["idx", "bus", "u", "p0 (pu)", "Pmin (pu)", "Pmax (pu)", "c2", "c1", "c0", "ramp10"],
    )
    for _, row in sg.iterrows():
        c2, c1, c0 = cost.get(row["idx"], (0, 0, 0, 0, 0))[2:]
        t1.add_row(
            str(row["idx"]), str(row["bus"]),
            "ON" if row.get("u", 1) >= 0.5 else "OFF",
            _fmt(row.get("p0")), _fmt(row.get("pmin")), _fmt(row.get("pmax")),
            _fmt(c2), _fmt(c1), _fmt(c0),
            _fmt(row.get("R10")),
        )
    out.append(t1)

    ln = _safe_df(ss.Line)
    t2 = _make_table(
        "Lines — flow / rating",
        ["idx", "bus1", "bus2", "u", "x (pu)", "rate_a (pu)"],
    )
    for _, row in ln.iterrows():
        t2.add_row(
            str(row["idx"]), str(row["bus1"]), str(row["bus2"]),
            "ON" if row.get("u", 1) >= 0.5 else "OFF",
            _fmt(row.get("x"), prec=4),
            _fmt(row.get("rate_a")),
        )
    out.append(t2)

    pq = _safe_df(ss.PQ)
    t3 = _make_table("Loads — base demand", ["idx", "bus", "p0 (pu)", "q0 (pu)"])
    for _, row in pq.iterrows():
        t3.add_row(
            str(row["idx"]), str(row["bus"]),
            _fmt(row.get("p0")), _fmt(row.get("q0")),
        )
    out.append(t3)
    return out


def _snap_dcuc(ss) -> List[Table]:
    """UC focus: commitment parameters + cost (incl. csu/csd) + horizon size."""
    out: List[Table] = []

    sg = _safe_df(ss.StaticGen)
    cost = _gen_cost_lookup(ss)
    t1 = _make_table(
        "Generators — unit commitment parameters",
        ["idx", "bus", "u₀", "Pmin", "Pmax", "ramp10",
         "td1 (min up)", "td2 (min dn)", "ton0", "toff0",
         "csu", "csd", "c2", "c1", "c0"],
    )
    for _, row in sg.iterrows():
        csu, csd, c2, c1, c0 = cost.get(row["idx"], (0, 0, 0, 0, 0))
        t1.add_row(
            str(row["idx"]), str(row["bus"]),
            "ON" if row.get("u", 1) >= 0.5 else "OFF",
            _fmt(row.get("pmin")), _fmt(row.get("pmax")), _fmt(row.get("R10")),
            _fmt(row.get("td1")), _fmt(row.get("td2")),
            _fmt(row.get("ton0")), _fmt(row.get("toff0")),
            _fmt(csu), _fmt(csd),
            _fmt(c2), _fmt(c1), _fmt(c0),
        )
    out.append(t1)

    # Horizon size for UC
    if hasattr(ss, "Horizon"):
        h = _safe_df(ss.Horizon)
        n_uct = sum(str(name).startswith("UCT") for name in h.get("name", []))
        n_edt = sum(str(name).startswith("EDT") for name in h.get("name", []))
        t2 = _make_table("Horizon — time periods",
                         ["UC periods (UCT*)", "ED periods (EDT*)"])
        t2.add_row(str(n_uct), str(n_edt))
        out.append(t2)

    return out


def _snap_aced(ss) -> List[Table]:
    """ACOPF focus: voltage limits + P/Q caps + AC branch params."""
    out: List[Table] = []

    bus = _safe_df(ss.Bus)
    t1 = _make_table("Buses — voltage constraints",
                     ["idx", "Vn", "v0 (pu)", "a0 (rad)", "Vmin", "Vmax"])
    for _, row in bus.iterrows():
        t1.add_row(
            str(row["idx"]), _fmt(row.get("Vn"), prec=1),
            _fmt(row.get("v0"), prec=4), _fmt(row.get("a0"), prec=4),
            _fmt(row.get("vmin")), _fmt(row.get("vmax")),
        )
    out.append(t1)

    pv = _safe_df(ss.PV)
    if not pv.empty:
        cost = _gen_cost_lookup(ss)
        t2 = _make_table("Generators — AC capability + cost",
                         ["idx", "bus", "Pmin", "Pmax", "Qmin", "Qmax",
                          "v0", "c2", "c1", "c0"])
        for _, row in pv.iterrows():
            _, _, c2, c1, c0 = cost.get(row["idx"], (0, 0, 0, 0, 0))
            t2.add_row(
                str(row["idx"]), str(row["bus"]),
                _fmt(row.get("pmin")), _fmt(row.get("pmax")),
                _fmt(row.get("qmin")), _fmt(row.get("qmax")),
                _fmt(row.get("v0")),
                _fmt(c2), _fmt(c1), _fmt(c0),
            )
        out.append(t2)

    ln = _safe_df(ss.Line)
    t3 = _make_table("Branches — AC parameters",
                     ["idx", "bus1", "bus2", "r (pu)", "x (pu)", "b (pu)", "rate_a"])
    for _, row in ln.iterrows():
        t3.add_row(
            str(row["idx"]), str(row["bus1"]), str(row["bus2"]),
            _fmt(row.get("r"), prec=4), _fmt(row.get("x"), prec=4),
            _fmt(row.get("b"), prec=4), _fmt(row.get("rate_a")),
        )
    out.append(t3)
    return out


def _snap_ded(ss) -> List[Table]:
    """DOPF: ramp + horizon + load envelope."""
    out: List[Table] = []

    if hasattr(ss, "Horizon"):
        h = _safe_df(ss.Horizon)
        t1 = _make_table("Horizon — total time slots", ["total slots"])
        t1.add_row(str(len(h)))
        out.append(t1)

    sg = _safe_df(ss.StaticGen)
    cost = _gen_cost_lookup(ss)
    t2 = _make_table("Generators — temporal envelope",
                     ["idx", "bus", "Pmin", "Pmax", "ramp10", "c1"])
    for _, row in sg.iterrows():
        c2, c1, c0 = cost.get(row["idx"], (0, 0, 0, 0, 0))[2:]
        t2.add_row(
            str(row["idx"]), str(row["bus"]),
            _fmt(row.get("pmin")), _fmt(row.get("pmax")),
            _fmt(row.get("R10")), _fmt(c1),
        )
    out.append(t2)
    return out


def _snap_pf(ss) -> List[Table]:
    """Power flow: bus state (Vn / Vmin / Vmax) + lines."""
    out: List[Table] = []

    bus = _safe_df(ss.Bus)
    t1 = _make_table("Buses — base state",
                     ["idx", "Vn", "v0 (pu)", "a0 (rad)", "Vmin", "Vmax"])
    for _, row in bus.iterrows():
        t1.add_row(
            str(row["idx"]), _fmt(row.get("Vn"), prec=1),
            _fmt(row.get("v0"), prec=4), _fmt(row.get("a0"), prec=4),
            _fmt(row.get("vmin")), _fmt(row.get("vmax")),
        )
    out.append(t1)

    ln = _safe_df(ss.Line)
    t2 = _make_table("Branches — impedance + rating",
                     ["idx", "bus1", "bus2", "r (pu)", "x (pu)", "rate_a"])
    for _, row in ln.iterrows():
        t2.add_row(
            str(row["idx"]), str(row["bus1"]), str(row["bus2"]),
            _fmt(row.get("r"), prec=4), _fmt(row.get("x"), prec=4),
            _fmt(row.get("rate_a")),
        )
    out.append(t2)
    return out


# ---------------------------------------------------------------- dispatch
def get_snapshot(ams_ctx, routine_name: str) -> List[Tuple[str, Table]]:
    """Return a list of ``(family_label, table)`` pairs."""
    if ams_ctx.system is None:
        return []

    family = routine_family(routine_name)
    if family in ("uc", "uc2"):
        tables = _snap_dcuc(ams_ctx.system)
        label = "DCUC — Unit Commitment focus"
    elif family in ("acopf", "grbopt"):
        tables = _snap_aced(ams_ctx.system)
        label = "ACED — AC OPF focus"
    elif family in ("dopf",):
        tables = _snap_ded(ams_ctx.system)
        label = "DED — Multi-period dispatch focus"
    elif family in ("dcpf", "pflow", "pypower"):
        tables = _snap_pf(ams_ctx.system)
        label = "PF — Power flow focus"
    elif family in ("dcopf", "dcopf2", "rted", "rted2", "ed", "ed2"):
        tables = _snap_dced(ams_ctx.system)
        label = "DCED — DC Economic Dispatch focus"
    else:
        tables = _snap_dced(ams_ctx.system)
        label = f"{family} — generic focus"
    return [(label, t) for t in tables]
