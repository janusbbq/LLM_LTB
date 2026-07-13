"""Routine-aware mathematical formulations as structured LaTeX.

Sibling of :mod:`agent.ams_engine.formulations` (which emits Unicode/ASCII art
for the terminal). This module returns clean, accurate LaTeX so the web UI can
render each objective / constraint with MathJax instead of approximating the
symbols with box-drawing characters.

Each routine family maps to a structured dict::

    {
        "routine": "UC",
        "family":  "uc",
        "title":   "Unit Commitment  (UC)",
        "subtitle": "Mixed-integer linear program (MILP)",
        "sections": [
            {"heading": "Decision variables", "items": [{"latex": ..., "desc": ...}]},
            {"heading": "Objective",          "items": [{"latex": ..., "desc": ...}]},
            {"heading": "Constraints",        "items": [{"latex": ..., "desc": ...}]},
        ],
    }

``latex`` strings are raw TeX **without** delimiters; the frontend wraps each in
``\\[ ... \\]`` (display math) before handing it to MathJax.
"""

from typing import Dict

from agent.ams_engine.routines import routine_family


# --------------------------------------------------------------------------- DCOPF
_DCOPF = {
    "title": "DC Optimal Power Flow  (DCOPF)",
    "subtitle": "Linearly-constrained quadratic program (QP)",
    "sections": [
        {
            "heading": "Decision variables",
            "items": [
                {"latex": r"P_i", "desc": "active power output of generator $i$"},
            ],
        },
        {
            "heading": "Objective",
            "items": [
                {
                    "latex": r"\min_{P}\; \sum_{i}\left( c_{2i}\,P_i^{2} + c_{1i}\,P_i + c_{0i} \right)",
                    "desc": "minimize total quadratic generation cost",
                },
            ],
        },
        {
            "heading": "Constraints",
            "items": [
                {
                    "latex": r"\sum_{i} P_i \;=\; \sum_{j} P_{D,j}",
                    "desc": "system power balance",
                },
                {
                    "latex": r"P_i^{\min} \;\le\; P_i \;\le\; P_i^{\max}",
                    "desc": "generator output limits",
                },
                {
                    "latex": r"-P_{\ell}^{\max} \;\le\; P_{\ell} \;\le\; P_{\ell}^{\max},"
                             r"\qquad P_{\ell} = \sum_i \mathrm{PTDF}_{\ell i}\,(P_i - P_{D,i})",
                    "desc": "line flow limits via the power transfer distribution factors (PTDF)",
                },
            ],
        },
    ],
}

# --------------------------------------------------------------------------- RTED
_RTED = {
    "title": "Real-Time Economic Dispatch  (RTED)",
    "subtitle": r"DCOPF $+$ secondary-frequency regulation reserve",
    "sections": [
        {
            "heading": "Decision variables",
            "items": [
                {"latex": r"P_i", "desc": "active power output of generator $i$"},
                {"latex": r"R_i^{u},\; R_i^{d}", "desc": "regulation up / down reserve from generator $i$"},
            ],
        },
        {
            "heading": "Objective",
            "items": [
                {
                    "latex": r"\min_{P,\,R^{u},\,R^{d}}\; "
                             r"\sum_{i}\left( c_{2i}\,P_i^{2} + c_{1i}\,P_i + c_{0i} \right)"
                             r"\;+\; \sum_{i}\left( c_i^{u}\,R_i^{u} + c_i^{d}\,R_i^{d} \right)",
                    "desc": "dispatch cost plus up / down reserve cost",
                },
            ],
        },
        {
            "heading": "Constraints",
            "items": [
                {
                    "latex": r"\sum_{i} P_i \;=\; \sum_{j} P_{D,j}",
                    "desc": "system power balance",
                },
                {
                    "latex": r"P_i^{\min} \;\le\; P_i \;\le\; P_i^{\max}",
                    "desc": "generator output limits",
                },
                {
                    "latex": r"P_i + R_i^{u} \;\le\; P_i^{\max}, \qquad P_i - R_i^{d} \;\ge\; P_i^{\min}",
                    "desc": "reserve headroom above / below the dispatch point",
                },
                {
                    "latex": r"\sum_{i} R_i^{u} \;\ge\; \Delta^{u}, \qquad \sum_{i} R_i^{d} \;\ge\; \Delta^{d}",
                    "desc": "system up / down reserve requirements",
                },
                {
                    "latex": r"-P_{\ell}^{\max} \;\le\; P_{\ell} \;\le\; P_{\ell}^{\max}",
                    "desc": "line flow limits",
                },
            ],
        },
    ],
}

# --------------------------------------------------------------------------- ED
_ED = {
    "title": "Economic Dispatch — multi-period  (ED)",
    "subtitle": r"Time-coupled DCOPF over horizon $t = 1,\dots,T$",
    "sections": [
        {
            "heading": "Decision variables",
            "items": [
                {"latex": r"P_{i,t}", "desc": r"dispatch of generator $i$ at period $t$"},
            ],
        },
        {
            "heading": "Objective",
            "items": [
                {
                    "latex": r"\min_{P}\; \sum_{t=1}^{T}\sum_{i}"
                             r"\left( c_{2i}\,P_{i,t}^{2} + c_{1i}\,P_{i,t} + c_{0i} \right)",
                    "desc": "total cost summed over all periods",
                },
            ],
        },
        {
            "heading": "Constraints",
            "items": [
                {
                    "latex": r"\sum_{i} P_{i,t} \;=\; \sum_{j} P_{D,j,t} \qquad \forall\, t",
                    "desc": "power balance in every period",
                },
                {
                    "latex": r"P_i^{\min} \;\le\; P_{i,t} \;\le\; P_i^{\max} \qquad \forall\, i,\,t",
                    "desc": "generator output limits",
                },
                {
                    "latex": r"\left| P_{i,t} - P_{i,t-1} \right| \;\le\; R_i",
                    "desc": "inter-period ramp limit",
                },
                {
                    "latex": r"-P_{\ell}^{\max} \;\le\; P_{\ell,t} \;\le\; P_{\ell}^{\max} \qquad \forall\, t",
                    "desc": "line flow limits each period",
                },
            ],
        },
    ],
}

# --------------------------------------------------------------------------- UC
_UC = {
    "title": "Unit Commitment  (UC)",
    "subtitle": "Mixed-integer linear / quadratic program (MILP / MIQP)",
    "sections": [
        {
            "heading": "Decision variables",
            "items": [
                {"latex": r"u_{i,t} \in \{0,1\}", "desc": r"on / off commitment status of unit $i$ at period $t$"},
                {"latex": r"y_{i,t} \in \{0,1\}", "desc": r"startup indicator ($0 \to 1$ transition)"},
                {"latex": r"z_{i,t} \in \{0,1\}", "desc": r"shutdown indicator ($1 \to 0$ transition)"},
                {"latex": r"P_{i,t}", "desc": r"dispatch of unit $i$ at period $t$"},
            ],
        },
        {
            "heading": "Objective",
            "items": [
                {
                    "latex": r"\min\; \sum_{t}\sum_{i}\Big[\,"
                             r"c_{2i}\,P_{i,t}^{2} + c_{1i}\,P_{i,t} + c_{0i}\,u_{i,t}"
                             r"\;+\; c_i^{\mathrm{su}}\,y_{i,t} + c_i^{\mathrm{sd}}\,z_{i,t}"
                             r"\,\Big]",
                    "desc": "production cost plus startup and shutdown costs",
                },
            ],
        },
        {
            "heading": "Constraints",
            "items": [
                {
                    "latex": r"\sum_{i} P_{i,t} \;=\; \sum_{j} P_{D,j,t} \qquad \forall\, t",
                    "desc": "power balance in every period",
                },
                {
                    "latex": r"u_{i,t}\,P_i^{\min} \;\le\; P_{i,t} \;\le\; u_{i,t}\,P_i^{\max}",
                    "desc": "output is zero when off, bounded when on (commitment-coupled)",
                },
                {
                    "latex": r"y_{i,t} - z_{i,t} \;=\; u_{i,t} - u_{i,t-1}",
                    "desc": "startup / shutdown state-transition logic",
                },
                {
                    "latex": r"\sum_{\tau = t - T_i^{u} + 1}^{t} y_{i,\tau} \;\le\; u_{i,t}",
                    "desc": r"minimum up-time $T_i^{u}$",
                },
                {
                    "latex": r"\sum_{\tau = t - T_i^{d} + 1}^{t} z_{i,\tau} \;\le\; 1 - u_{i,t}",
                    "desc": r"minimum down-time $T_i^{d}$",
                },
                {
                    "latex": r"\left| P_{i,t} - P_{i,t-1} \right| \;\le\; R_i",
                    "desc": "inter-period ramp limit",
                },
                {
                    "latex": r"-P_{\ell}^{\max} \;\le\; P_{\ell,t} \;\le\; P_{\ell}^{\max}",
                    "desc": "line flow limits",
                },
            ],
        },
    ],
}

# --------------------------------------------------------------------------- ACOPF
_ACOPF = {
    "title": "AC Optimal Power Flow  (ACOPF)",
    "subtitle": "Nonconvex nonlinear program (NLP)",
    "sections": [
        {
            "heading": "Decision variables",
            "items": [
                {"latex": r"P_i,\; Q_i", "desc": r"active / reactive output of generator $i$"},
                {"latex": r"V_j,\; \theta_j", "desc": r"voltage magnitude / angle at bus $j$"},
            ],
        },
        {
            "heading": "Objective",
            "items": [
                {
                    "latex": r"\min\; \sum_{i}\left( c_{2i}\,P_i^{2} + c_{1i}\,P_i + c_{0i} \right)",
                    "desc": "minimize total generation cost",
                },
            ],
        },
        {
            "heading": "Constraints",
            "items": [
                {
                    "latex": r"P_j^{\mathrm{inj}} = V_j \sum_{k} V_k \left( G_{jk}\cos\theta_{jk} + B_{jk}\sin\theta_{jk} \right) \quad \forall\, j",
                    "desc": r"active power balance, $\theta_{jk} = \theta_j - \theta_k$",
                },
                {
                    "latex": r"Q_j^{\mathrm{inj}} = V_j \sum_{k} V_k \left( G_{jk}\sin\theta_{jk} - B_{jk}\cos\theta_{jk} \right) \quad \forall\, j",
                    "desc": "reactive power balance",
                },
                {
                    "latex": r"P_i^{\min} \le P_i \le P_i^{\max}, \qquad Q_i^{\min} \le Q_i \le Q_i^{\max}",
                    "desc": "generator active / reactive limits",
                },
                {
                    "latex": r"V_j^{\min} \le V_j \le V_j^{\max}",
                    "desc": "bus voltage limits",
                },
                {
                    "latex": r"S_{jk}^{2} \;\le\; \left( S_{jk}^{\max} \right)^{2}",
                    "desc": "branch apparent-power (MVA) limit",
                },
            ],
        },
    ],
}

# --------------------------------------------------------------------------- DCPF
_DCPF = {
    "title": "DC Power Flow  (DCPF)",
    "subtitle": "Linear network solve (no optimization)",
    "sections": [
        {
            "heading": "Solve for bus angles",
            "items": [
                {
                    "latex": r"\sum_{i \in j} P_i \;-\; P_{D,j} \;=\; \sum_{k} \frac{\theta_j - \theta_k}{x_{jk}} \qquad \forall\, j,"
                             r"\quad \theta_{\mathrm{slack}} = 0",
                    "desc": "nodal real-power balance with reactances $x_{jk}$",
                },
            ],
        },
        {
            "heading": "Recover line flows",
            "items": [
                {
                    "latex": r"P_{\ell,\,jk} \;=\; \frac{\theta_j - \theta_k}{x_{jk}}",
                    "desc": "branch active power flow",
                },
            ],
        },
    ],
}

# --------------------------------------------------------------------------- PFlow
_PFLOW = {
    "title": "AC Power Flow  (PFlow)",
    "subtitle": "Nonlinear network solve via Newton–Raphson",
    "sections": [
        {
            "heading": "Nodal balance (solve for $V_j,\\ \\theta_j$)",
            "items": [
                {
                    "latex": r"P_j = V_j \sum_{k} V_k \left( G_{jk}\cos\theta_{jk} + B_{jk}\sin\theta_{jk} \right)",
                    "desc": "active power injection at every bus",
                },
                {
                    "latex": r"Q_j = V_j \sum_{k} V_k \left( G_{jk}\sin\theta_{jk} - B_{jk}\cos\theta_{jk} \right)",
                    "desc": "reactive power injection at every bus",
                },
            ],
        },
        {
            "heading": "Reference",
            "items": [
                {
                    "latex": r"V_{\mathrm{slack}} = V^{\mathrm{ref}}, \qquad \theta_{\mathrm{slack}} = 0",
                    "desc": "slack-bus voltage and angle are fixed",
                },
            ],
        },
    ],
}

# --------------------------------------------------------------------------- DOPF
_DOPF = {
    "title": "Distribution OPF  (DOPF / DOPFVIS)",
    "subtitle": "Linearized distribution-network dispatch",
    "sections": [
        {
            "heading": "Decision variables",
            "items": [
                {"latex": r"P_i,\; Q_i", "desc": "active / reactive set-points of DER / inverter $i$"},
            ],
        },
        {
            "heading": "Objective",
            "items": [
                {
                    "latex": r"\min\; \sum_{i} c_i(P_i) \;+\; \sum_{i} c_i(Q_i)",
                    "desc": "cost of active and reactive dispatch",
                },
            ],
        },
        {
            "heading": "Constraints",
            "items": [
                {
                    "latex": r"\mathbf{A}\,\mathbf{P} + \mathbf{B}\,\mathbf{Q} = \mathbf{d}",
                    "desc": "linearized per-bus active / reactive power balance",
                },
                {
                    "latex": r"V_j^{\min} \le V_j \le V_j^{\max}",
                    "desc": "voltage limits (DOPFVIS uses a voltage-sensitivity linearization)",
                },
            ],
        },
    ],
}


# Map family key -> formulation dict (mirrors formulations._BY_FAMILY)
_BY_FAMILY: Dict[str, dict] = {
    "dcopf":   _DCOPF,
    "dcopf2":  _DCOPF,
    "rted":    _RTED,
    "rted2":   _RTED,
    "ed":      _ED,
    "ed2":     _ED,
    "uc":      _UC,
    "uc2":     _UC,
    "acopf":   _ACOPF,
    "dcpf":    _DCPF,
    "pflow":   _PFLOW,
    "dopf":    _DOPF,
    "grbopt":  _ACOPF,
    "pypower": _DCPF,
}


def get_latex_formulation(routine_name: str) -> dict:
    """Return the structured LaTeX formulation for an AMS routine.

    Always returns a dict with ``routine``, ``family``, ``title``,
    ``subtitle`` and ``sections``. Unknown routines yield a placeholder so
    the frontend can render a graceful "no formulation" message.
    """
    family = routine_family(routine_name)
    base = _BY_FAMILY.get(family)
    if base is None:
        return {
            "routine": routine_name,
            "family": family,
            "title": f"{routine_name}",
            "subtitle": "No symbolic formulation registered for this routine.",
            "sections": [],
        }
    return {
        "routine": routine_name,
        "family": family,
        "title": base["title"],
        "subtitle": base.get("subtitle", ""),
        "sections": base["sections"],
    }
