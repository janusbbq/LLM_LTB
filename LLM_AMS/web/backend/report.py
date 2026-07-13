"""Human-readable **Power System Analysis Report** builder (Markdown).

Given a solved AMS routine, this module renders a structured, Markdown report
that a human can skim to understand *what the optimization decided* and *what
to pay attention to*. It is intentionally generic across the scheduling
families shipped by AMS:

    Economic Dispatch / DC-OPF   (ED, ED2, RTED, RTED2, DCOPF, DCOPF2, …)
    Unit Commitment              (UC, UC2, UCDG, UCES, …)
    AC Optimal Power Flow        (ACOPF, OPF)
    Distribution OPF             (DOPF, DOPFVIS)
    Power Flow                   (DCPF, PFlow)

Each class ships a short "what to focus on" guide that highlights the numerical
analyses most worth a human's attention for that problem type, followed by
auto-generated result tables, a constraint/violation summary, and the result
plots produced by :func:`agent.ams_engine.plotting.plot_results` (served from
``/generated``).

The renderer is defensive: any analytic that cannot be computed is skipped
rather than raising, so a report is always produced for a converged solve.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np


# --------------------------------------------------------------------------- #
#  Problem-class taxonomy + "what to focus on" guidance
# --------------------------------------------------------------------------- #
# Keyed by a normalized class id derived from the routine *name* (most robust).
CLASS_ED = "ED"          # economic dispatch / DC-OPF (cost-minimizing MW dispatch)
CLASS_UC = "UC"          # unit commitment (binary on/off + dispatch over a horizon)
CLASS_ACOPF = "ACOPF"    # AC optimal power flow (voltages + reactive power)
CLASS_DOPF = "DOPF"      # distribution OPF
CLASS_PF = "PF"          # plain power flow (no objective)
CLASS_GENERIC = "GENERIC"


def classify_routine(routine: str, family: str = "") -> str:
    """Map a routine name to a high-level problem class id."""
    r = (routine or "").upper().strip()
    if r.startswith("UC"):
        return CLASS_UC
    if r.startswith("RTED") or r.startswith("ED"):
        return CLASS_ED
    if r.startswith("DCOPF"):
        return CLASS_ED
    if r.startswith("ACOPF") or r == "OPF":
        return CLASS_ACOPF
    if r.startswith("DOPF"):
        return CLASS_DOPF
    if r in {"DCPF", "PFLOW"}:
        return CLASS_PF
    # fall back to the AMS family grouping if the name was unusual
    fam = (family or "").lower()
    if fam in {"uc", "uc2"}:
        return CLASS_UC
    if fam in {"acopf"}:
        return CLASS_ACOPF
    if fam in {"dopf"}:
        return CLASS_DOPF
    if fam in {"dcpf", "pflow"}:
        return CLASS_PF
    if fam in {"dcopf", "dcopf2", "rted", "rted2", "ed", "ed2"}:
        return CLASS_ED
    return CLASS_GENERIC


# Per-class descriptive guidance. ``focus`` items are the numerical analyses a
# human should weigh most heavily when reading this class of result.
_GUIDE: Dict[str, Dict[str, Any]] = {
    CLASS_ED: {
        "title": "Economic Dispatch / DC Optimal Power Flow",
        "intro": (
            "Economic dispatch finds the **least-cost generator output** that "
            "meets demand while respecting generation limits and DC line "
            "thermal limits. Network losses are neglected (DC approximation), "
            "so total generation equals total demand."
        ),
        "focus": [
            "**Total production cost** (the objective, $/h) — the headline number "
            "the dispatch minimizes.",
            "**Generator dispatch `pg` vs limits** — which units sit at `Pmax` "
            "(fully committed, cheap) versus at `Pmin` or idle (expensive). Units "
            "*between* limits are *marginal* and set the system price.",
            "**Line loading `plf` vs `rate_a`** — lines near 100 % are congested "
            "and create locational price separation; congestion is the usual "
            "reason a cheaper unit is held back.",
            "**Supply–demand balance** — Σ`pg` should equal Σ`pd` (DC has no "
            "losses); a mismatch signals an infeasibility or slack pickup.",
            "**Ramp headroom (RTED)** — for real-time dispatch, check the change "
            "from the previous set-point against each unit's 10-min ramp `R10`.",
        ],
    },
    CLASS_UC: {
        "title": "Unit Commitment",
        "intro": (
            "Unit commitment is a **mixed-integer** schedule over a time horizon: "
            "for every period it decides which units are **on/off** (`ug`) *and* "
            "how much each dispatches (`pg`), minimizing start-up, shut-down, "
            "no-load and production cost subject to minimum up/down times and "
            "ramp limits."
        ),
        "focus": [
            "**Commitment schedule `ug`** — the on/off pattern per unit per period "
            "is the central decision; read it as the unit's operating window.",
            "**Total horizon cost** (objective) — includes start-up/shut-down "
            "costs, not just fuel; expensive starts discourage cycling.",
            "**Start-up / shut-down events** — how often units cycle; frequent "
            "cycling hints at tight ramps or a peaky load.",
            "**Min up/down feasibility** — once started, a unit must stay on for "
            "`td1` periods (and off for `td2`); verify the schedule honours them.",
            "**Peak-vs-offpeak dispatch & reserve** — confirm enough capacity is "
            "committed to cover the peak period plus spinning reserve.",
        ],
    },
    CLASS_ACOPF: {
        "title": "AC Optimal Power Flow",
        "intro": (
            "AC-OPF co-optimizes **real and reactive power** over the full AC "
            "network, minimizing cost while keeping **bus voltages** within "
            "limits and honouring thermal limits. Unlike DC models it captures "
            "voltage magnitude, reactive support and network losses."
        ),
        "focus": [
            "**Bus voltage profile** — every bus magnitude must stay within "
            "`[Vmin, Vmax]` (typically 0.94–1.06 pu); flag the lowest/highest.",
            "**Reactive power `qg` vs `[Qmin, Qmax]`** — units pinned at a reactive "
            "limit are propping up local voltage and may indicate voltage stress.",
            "**Network losses** — Σ`pg` − Σ`pd` is the real-power loss the AC model "
            "exposes (DC hides this); rising losses flag inefficiency.",
            "**Thermal loading vs `rate_a`** — branch flows near rating are "
            "congested, same as DC but now with reactive contribution.",
            "**Total cost** — the objective, comparable to DC dispatch but higher "
            "because losses must also be generated.",
        ],
    },
    CLASS_DOPF: {
        "title": "Distribution Optimal Power Flow",
        "intro": (
            "Distribution OPF schedules resources on a (often radial) distribution "
            "feeder over time, balancing cost against voltage and thermal limits "
            "with distributed energy resources in the mix."
        ),
        "focus": [
            "**Voltage along the feeder** — radial networks see voltage sag toward "
            "the feeder end; check the worst bus each period.",
            "**Generator / DER dispatch vs limits** — confirm each resource stays "
            "within its capability band over the horizon.",
            "**Line loading vs `rate_a`** — distribution conductors are thermally "
            "limited; watch the head-of-feeder sections.",
            "**Total cost over the horizon** — the minimized objective.",
        ],
    },
    CLASS_PF: {
        "title": "Power Flow",
        "intro": (
            "Power flow is a **feasibility** solve (no objective): given fixed "
            "injections it computes the resulting flows and (for AC) voltages. "
            "Use it to check a network state rather than to optimize it."
        ),
        "focus": [
            "**Line flows `plf` vs `rate_a`** — identify any thermally overloaded "
            "branch in the given operating state.",
            "**Bus angles / voltages** — large angle spreads (DC) or out-of-band "
            "voltages (AC) flag a stressed network.",
            "**Slack pick-up** — the slack bus absorbs the imbalance; a large "
            "slack injection means the schedule was unbalanced.",
        ],
    },
    CLASS_GENERIC: {
        "title": "Power System Optimization",
        "intro": "Optimization result for the selected AMS routine.",
        "focus": [
            "**Objective value** — the quantity the routine minimizes.",
            "**Decision variables vs their limits** — confirm the solution is "
            "interior to / at the physical bounds as expected.",
            "**Constraint violations** — review the violation summary below.",
        ],
    },
}


# --------------------------------------------------------------------------- #
#  Small formatting helpers
# --------------------------------------------------------------------------- #
def _f(x: Any, prec: int = 4) -> str:
    try:
        return f"{float(x):.{prec}f}"
    except (TypeError, ValueError):
        return "—"


def _arr(x) -> Optional[np.ndarray]:
    if x is None:
        return None
    try:
        a = np.asarray(x, dtype=float)
    except (TypeError, ValueError):
        return None
    return a if a.size else None


def _reduce_dev(a: np.ndarray, how: str = "max") -> np.ndarray:
    """Collapse a possibly 2-D (device, time) array to a per-device 1-D array."""
    if a.ndim == 1:
        return a
    if how == "min":
        return a.min(axis=1)
    if how == "mean":
        return a.mean(axis=1)
    return np.abs(a).max(axis=1)


def _limits(ss, model: str, attr: str) -> Optional[np.ndarray]:
    try:
        return np.asarray(getattr(getattr(ss, model), attr).v, dtype=float)
    except Exception:
        return None


# --------------------------------------------------------------------------- #
#  Section builders
# --------------------------------------------------------------------------- #
def _summary_section(routine, case_label, solver, results, info, cls) -> List[str]:
    converged = results.get("converged")
    exit_code = results.get("exit_code")
    obj = results.get("objective")
    status = "Converged" if converged else "Did not converge"
    n_bus = info.get("n_bus", "—")
    n_line = info.get("n_line", "—")
    n_load = info.get("n_pq", "—")
    n_gen = info.get("n_staticgen", "—")

    pg = _arr(results.get("pg"))
    multiperiod = pg is not None and pg.ndim == 2
    n_t = pg.shape[1] if multiperiod else 1

    lines = [
        "# Power System Analysis Report",
        "",
        f"### {_GUIDE[cls]['title']}",
        "",
        "| | |",
        "| --- | --- |",
        f"| **Routine** | `{routine}` |",
        f"| **Network** | {case_label} |",
        f"| **Solver** | `{solver}` |",
        f"| **Solution status** | {status} (exit code `{exit_code}`) |",
        f"| **Report generated** | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |",
        "",
        "---",
        "",
        "## 1 · Executive summary",
        "",
        f"> {_GUIDE[cls]['title']} solved on a network of **{n_bus} buses, "
        f"{n_line} lines, {n_load} loads and {n_gen} generators**"
        + (f", over a **{n_t}-period** scheduling horizon." if multiperiod
           else "."),
        "",
    ]

    bullets = []
    if obj is not None:
        unit = "total cost over the horizon" if multiperiod else "total cost"
        bullets.append(f"- **Objective ({unit}):** `{_f(obj, 4)}`")
    if pg is not None:
        tot = float(_reduce_dev(pg, "max").sum()) if multiperiod else float(pg.sum())
        label = "peak aggregate dispatch" if multiperiod else "aggregate dispatch"
        bullets.append(f"- **Generation ({label}):** `{_f(tot, 3)} pu`")
    viol = [v for v in (results.get("violations") or []) if v[2] == "VIOLATION"]
    warn = [v for v in (results.get("violations") or []) if v[2] == "WARN"]
    if viol:
        bullets.append(f"- **Limit assessment:** **{len(viol)} violation(s)** and "
                       f"{len(warn)} warning(s) recorded — see §4.")
    elif warn:
        bullets.append(f"- **Limit assessment:** {len(warn)} near-limit warning(s) "
                       "and no hard violations — see §4.")
    else:
        bullets.append("- **Limit assessment:** all monitored limits respected.")
    lines += bullets + [""]
    return lines


def _focus_section(cls) -> List[str]:
    g = _GUIDE[cls]
    lines = [
        "## 2 · Analytical focus",
        "",
        f"**{g['title']}.** {g['intro']}",
        "",
        "When reviewing this class of result, the following analyses warrant the "
        "closest attention, in order of priority:",
        "",
    ]
    for i, item in enumerate(g["focus"], 1):
        lines.append(f"{i}. {item}")
    lines.append("")
    return lines


def _objective_section(results) -> List[str]:
    obj = results.get("objective")
    if obj is None:
        return []
    return [
        "### 3.1 · Objective",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Optimized objective | `{_f(obj, 6)}` |",
        f"| Routine | `{results.get('routine', '—')}` |",
        f"| Solver | `{results.get('solver', '—')}` |",
        f"| Converged | `{results.get('converged')}` |",
        "",
    ]


def _gen_section(ss, results) -> List[str]:
    pg = _arr(results.get("pg"))
    if pg is None:
        return []
    gen_idx = results.get("gen_idx") or list(range(pg.shape[0]))
    pmax = _limits(ss, "StaticGen", "pmax")
    pmin = _limits(ss, "StaticGen", "pmin")
    pg_dev = _reduce_dev(pg, "max")
    multiperiod = pg.ndim == 2

    head_p = "P_g max (pu)" if multiperiod else "P_g (pu)"
    rows = [
        "### 3.2 · Generator dispatch",
        "",
        ("> Values are the per-unit maximum over the horizon. Units held at "
         "`Pmax` are fully utilized; units strictly between `Pmin` and `Pmax` "
         "are marginal and set the system price."
         if multiperiod else
         "> Units at `Pmax` are fully utilized; units strictly between `Pmin` "
         "and `Pmax` are marginal and set the system price."),
        "",
        f"| Generator | {head_p} | Pmin | Pmax | Utilization | Assessment |",
        "| --- | ---: | ---: | ---: | ---: | :--- |",
    ]
    n = min(len(gen_idx), pg_dev.shape[0])
    for i in range(n):
        p = pg_dev[i]
        hi = pmax[i] if pmax is not None and i < len(pmax) else None
        lo = pmin[i] if pmin is not None and i < len(pmin) else None
        util = (100.0 * p / hi) if (hi and abs(hi) > 1e-6 and hi < 900) else None
        if hi is not None and hi < 900 and p > hi * 0.999:
            assess = "At Pmax"
        elif lo is not None and lo > -50 and p <= lo + 1e-4:
            assess = "At Pmin"
        elif util is not None and util > 90:
            assess = "Near Pmax"
        else:
            assess = "Marginal"
        rows.append(
            f"| `{gen_idx[i]}` | {_f(p, 4)} | "
            f"{_f(lo, 3) if lo is not None else '—'} | "
            f"{_f(hi, 3) if hi is not None else '—'} | "
            f"{(_f(util, 1) + ' %') if util is not None else '—'} | {assess} |"
        )
    rows.append("")
    return rows


def _line_section(ss, results) -> List[str]:
    plf = _arr(results.get("plf"))
    if plf is None:
        return []
    line_idx = results.get("line_idx") or list(range(plf.shape[0]))
    rate = _limits(ss, "Line", "rate_a")
    plf_dev = _reduce_dev(plf, "max")  # abs-max over time for 2-D

    # only list the most loaded lines to keep the report skimmable
    order = np.argsort(-np.abs(plf_dev))
    top = order[: min(12, len(order))]

    rows = [
        "### 3.3 · Line loading",
        "",
        "> Branches are ordered by loading. Any branch at or above approximately "
        "90 % is congested and a likely driver of price separation and curtailed "
        "low-cost generation.",
        "",
        "| Line | \\|P_lf\\| (pu) | rate_a | Loading | Assessment |",
        "| --- | ---: | ---: | ---: | :--- |",
    ]
    for i in top:
        flow = abs(plf_dev[i])
        r = rate[i] if rate is not None and i < len(rate) else None
        load = (100.0 * flow / r) if (r and abs(r) > 1e-6 and r < 900) else None
        if load is None:
            assess = "—"
        elif load > 100.5:
            assess = "Overloaded"
        elif load > 90:
            assess = "Congested"
        else:
            assess = "Within limits"
        rows.append(
            f"| `{line_idx[i]}` | {_f(flow, 4)} | "
            f"{_f(r, 3) if (r is not None and r < 900) else '—'} | "
            f"{(_f(load, 1) + ' %') if load is not None else '—'} | {assess} |"
        )
    rows.append("")
    return rows


def _voltage_section(ss, results) -> List[str]:
    v = _arr(results.get("vBus"))
    if v is None:
        return []
    vmin = _limits(ss, "Bus", "vmin")
    vmax = _limits(ss, "Bus", "vmax")
    lo_i = int(np.argmin(v if v.ndim == 1 else v.min(axis=1)))
    hi_i = int(np.argmax(v if v.ndim == 1 else v.max(axis=1)))
    vmn = float(v.min())
    vmx = float(v.max())
    rows = [
        "### 3.4 · Bus voltage profile",
        "",
        "| Metric | Bus | Value | Limit |",
        "| --- | --- | ---: | ---: |",
        f"| Lowest voltage | `{lo_i}` | {_f(vmn, 4)} pu | "
        f"{(_f(vmin[lo_i], 3) + ' pu') if vmin is not None and lo_i < len(vmin) else '—'} |",
        f"| Highest voltage | `{hi_i}` | {_f(vmx, 4)} pu | "
        f"{(_f(vmax[hi_i], 3) + ' pu') if vmax is not None and hi_i < len(vmax) else '—'} |",
        "",
    ]
    return rows


def _balance_section(results) -> List[str]:
    pg = _arr(results.get("pg"))
    pd = _arr(results.get("pd"))
    if pg is None or pd is None:
        return []
    g = float(_reduce_dev(pg, "max").sum()) if pg.ndim == 2 else float(pg.sum())
    d = float(_reduce_dev(pd, "max").sum()) if pd.ndim == 2 else float(pd.sum())
    gap = g - d
    note = ("Balanced (DC model neglects losses)" if abs(gap) < 1e-3
            else "Generation minus demand (losses / slack pick-up)")
    return [
        "### 3.5 · Supply–demand balance",
        "",
        "| Total generation (pu) | Total demand (pu) | Gap (pu) | Interpretation |",
        "| ---: | ---: | ---: | :--- |",
        f"| {_f(g, 3)} | {_f(d, 3)} | {_f(gap, 4)} | {note} |",
        "",
    ]


def _violation_section(results) -> List[str]:
    viol = results.get("violations") or []
    rows = ["## 4 · Constraint &amp; violation register", ""]
    if not viol:
        rows += [
            "**All monitored limits respected.** Generator outputs lie within "
            "`[Pmin, Pmax]`, line flows lie within `rate_a`, and, where checked, "
            "reserves are adequate.",
            "",
        ]
        return rows
    label = {"VIOLATION": "Violation", "WARN": "Warning",
             "LOW": "Low", "OK": "OK"}
    rows += [
        "| Item | Value | Severity |",
        "| :--- | :--- | :--- |",
    ]
    order = {"VIOLATION": 0, "WARN": 1, "LOW": 2, "OK": 3}
    for item, value, sev in sorted(viol, key=lambda t: order.get(t[2], 9)):
        rows.append(f"| {item} | {value} | {label.get(sev, sev)} |")
    rows.append("")
    return rows


def _plots_section(plot_urls: Dict[str, str]) -> List[str]:
    if not plot_urls:
        return []
    captions = {
        "pg": "Generator output `P_g`: dispatch per unit "
              "(bar chart for a single period, one line per unit over the horizon).",
        "plf": "Line flow `P_lf`: power on each branch, to be compared against "
               "`rate_a` for congestion.",
        "pd": "Load `P_d`: demand per bus that the dispatch must serve.",
    }
    rows = ["## 5 · Result figures", ""]
    for key in ("pg", "plf", "pd"):
        url = plot_urls.get(key)
        if not url:
            continue
        rows += [
            f"![{captions.get(key, key)}]({url})",
            "",
        ]
    return rows


def _repro_section(routine, case_alias, solver) -> List[str]:
    return [
        "---",
        "",
        "## 6 · Reproduction",
        "",
        "This report reflects the most recent solve of the selected routine. The "
        "equivalent terminal-agent instructions are:",
        "",
        "```text",
        f"load case {case_alias}",
        f"run {routine} with {solver}",
        "```",
        "",
        "Figures are produced by the same solve and archived under `generated/`.",
        "",
    ]


# --------------------------------------------------------------------------- #
#  Public entry point
# --------------------------------------------------------------------------- #
def build_report(
    ss,
    *,
    routine: str,
    family: str,
    case_alias: str,
    case_label: str,
    solver: str,
    info: Dict[str, Any],
    results: Dict[str, Any],
    plot_urls: Dict[str, str],
) -> str:
    """Render the full Markdown analysis report for a solved routine.

    Parameters
    ----------
    ss
        The live ``ams.System`` (used to read static limits for utilization).
    routine, family, case_alias, case_label, solver
        Identifiers for the solve being reported.
    info
        Output of :meth:`AMSContext.case_info`.
    results
        Output of :meth:`AMSContext.solve` augmented with ``violations``.
    plot_urls
        Mapping ``{"pg"|"plf"|"pd": "/generated/<file>.png"}``.
    """
    cls = classify_routine(routine, family)

    parts: List[str] = []
    parts += _summary_section(routine, case_label, solver, results, info, cls)
    parts += _focus_section(cls)
    parts += ["## 3 · Key numerical results", ""]
    parts += _objective_section(results)
    parts += _gen_section(ss, results)
    parts += _line_section(ss, results)
    if cls == CLASS_ACOPF:
        parts += _voltage_section(ss, results)
    parts += _balance_section(results)
    parts += _violation_section(results)
    parts += _plots_section(plot_urls)
    parts += _repro_section(routine, case_alias, solver)

    return "\n".join(parts)
