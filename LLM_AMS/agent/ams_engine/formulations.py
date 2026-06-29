"""Routine-aware mathematical formulation display.

Each entry is a Unicode-art block: title in a double-line box, then the
decision variables / objective / constraints in a fixed-width pseudo-LaTeX
style. Rendered via ``agent.utils.display.display_formulation``.
"""

from agent.ams_engine.routines import (
    LP_QP_FAMILIES,
    MIP_FAMILIES,
    ACOPF_FAMILIES,
    PYPOWER_FAMILIES,
    routine_family,
)


_DCOPF = """\
╔══════════════════════════════════════════════════════════════════════╗
║                    DC Optimal Power Flow  (DCOPF)                    ║
╚══════════════════════════════════════════════════════════════════════╝

Decision variables:
    Pᵢ        — active power output of generator i

Objective:
    minimize    Σᵢ ( c₂ᵢ Pᵢ²  +  c₁ᵢ Pᵢ  +  c₀ᵢ )

Constraints:
    Σᵢ Pᵢ            =  Σⱼ Pᴅⱼ                  (system power balance)
    Pᵢᵐⁱⁿ  ≤  Pᵢ   ≤  Pᵢᵐᵃˣ                    (gen output limits)
    -Pᶠᵐᵃˣ  ≤  Pᶠ  ≤  Pᶠᵐᵃˣ                    (line flow limits, PTDF)
"""

_RTED = """\
╔══════════════════════════════════════════════════════════════════════╗
║              Real-Time Economic Dispatch  (RTED)                     ║
║              DCOPF  +  Secondary Frequency Reserve                   ║
╚══════════════════════════════════════════════════════════════════════╝

Decision variables:
    Pᵢ                — gen i active output
    Rᵢᵘ, Rᵢᵈ          — regulation up / down reserve from gen i

Objective:
    minimize    Σᵢ ( c₂ᵢ Pᵢ² + c₁ᵢ Pᵢ + c₀ᵢ )      ← dispatch cost
              + Σᵢ ( cᵤᵢ Rᵢᵘ  +  cᵈᵢ Rᵢᵈ )         ← reserve cost

Constraints:
    Σᵢ Pᵢ                =  Σⱼ Pᴅⱼ                 (balance)
    Pᵢᵐⁱⁿ ≤ Pᵢ ≤ Pᵢᵐᵃˣ                              (gen limits)
    Pᵢ + Rᵢᵘ ≤ Pᵢᵐᵃˣ ,    Pᵢ - Rᵢᵈ ≥ Pᵢᵐⁱⁿ          (headroom)
    Σᵢ Rᵢᵘ ≥ Δᵘ ,         Σᵢ Rᵢᵈ ≥ Δᵈ              (system reserve req.)
    -Pᶠᵐᵃˣ ≤ Pᶠ ≤ Pᶠᵐᵃˣ                            (line limits)
"""

_ED = """\
╔══════════════════════════════════════════════════════════════════════╗
║              Economic Dispatch (multi-period)  (ED)                  ║
╚══════════════════════════════════════════════════════════════════════╝

Decision variables:
    Pᵢ,ₜ      — gen i dispatch at time t   (t = 1 … T)

Objective:
    minimize    Σₜ Σᵢ ( c₂ᵢ Pᵢ,ₜ² + c₁ᵢ Pᵢ,ₜ + c₀ᵢ )

Constraints:
    Σᵢ Pᵢ,ₜ          =  Σⱼ Pᴅⱼ,ₜ                  ∀ t
    Pᵢᵐⁱⁿ ≤ Pᵢ,ₜ ≤ Pᵢᵐᵃˣ                          ∀ i, t
    |Pᵢ,ₜ - Pᵢ,ₜ₋₁|  ≤  Rᵢ                        (ramp limit)
    -Pᶠᵐᵃˣ ≤ Pᶠ,ₜ ≤ Pᶠᵐᵃˣ
"""

_UC = """\
╔══════════════════════════════════════════════════════════════════════╗
║                  Unit Commitment  (UC, MILP)                         ║
╚══════════════════════════════════════════════════════════════════════╝

Decision variables:
    uᵢ,ₜ ∈ {0,1}     — on/off status of gen i at time t
    yᵢ,ₜ ∈ {0,1}     — startup indicator   (0 → 1 transition)
    zᵢ,ₜ ∈ {0,1}     — shutdown indicator  (1 → 0 transition)
    Pᵢ,ₜ              — dispatch at time t

Objective:
    minimize    Σₜ Σᵢ [ c₂ᵢ Pᵢ,ₜ² + c₁ᵢ Pᵢ,ₜ + c₀ᵢ
                       +  csuᵢ · yᵢ,ₜ  +  csdᵢ · zᵢ,ₜ ]

Constraints:
    Σᵢ Pᵢ,ₜ          =  Σⱼ Pᴅⱼ,ₜ                  ∀ t
    uᵢ,ₜ Pᵢᵐⁱⁿ ≤ Pᵢ,ₜ ≤ uᵢ,ₜ Pᵢᵐᵃˣ                (commitment-coupled)
    yᵢ,ₜ - zᵢ,ₜ  =  uᵢ,ₜ - uᵢ,ₜ₋₁                  (state logic)
    Σ_{τ=t-Tᵤ+1}ᵗ yᵢ,τ ≤ uᵢ,ₜ                     (min up-time Tᵤ)
    Σ_{τ=t-Tᵈ+1}ᵗ zᵢ,τ ≤ 1 - uᵢ,ₜ                 (min down-time Tᵈ)
    |Pᵢ,ₜ - Pᵢ,ₜ₋₁| ≤ Rᵢ                          (ramp limits)
"""

_ACOPF = """\
╔══════════════════════════════════════════════════════════════════════╗
║                  AC Optimal Power Flow  (ACOPF)                      ║
╚══════════════════════════════════════════════════════════════════════╝

Decision variables:
    Pᵢ, Qᵢ        — gen i active / reactive output
    Vⱼ, θⱼ        — bus j voltage magnitude / angle

Objective:
    minimize    Σᵢ ( c₂ᵢ Pᵢ² + c₁ᵢ Pᵢ + c₀ᵢ )

Constraints:
    Pⱼⁱⁿʲ  =  Vⱼ Σₖ Vₖ ( Gⱼₖ cos(θⱼₖ) + Bⱼₖ sin(θⱼₖ) )    ∀ j   (P balance)
    Qⱼⁱⁿʲ  =  Vⱼ Σₖ Vₖ ( Gⱼₖ sin(θⱼₖ) - Bⱼₖ cos(θⱼₖ) )    ∀ j   (Q balance)
    Pᵢᵐⁱⁿ ≤ Pᵢ ≤ Pᵢᵐᵃˣ ,   Qᵢᵐⁱⁿ ≤ Qᵢ ≤ Qᵢᵐᵃˣ
    Vⱼᵐⁱⁿ ≤ Vⱼ ≤ Vⱼᵐᵃˣ
    Sᵢⱼ²       ≤ (Sᵢⱼᵐᵃˣ)²                                       (branch MVA)
"""

_DCPF = """\
╔══════════════════════════════════════════════════════════════════════╗
║                       DC Power Flow  (DCPF)                          ║
╚══════════════════════════════════════════════════════════════════════╝

Solve for θⱼ (with slack bus θ_slack = 0) such that:

    Σᵢ∈ⱼ Pᵢ  -  Σⱼ Pᴅⱼ  =  Σₖ (θⱼ - θₖ) / xⱼₖ           ∀ j

Then  Pᶠⱼₖ  =  (θⱼ - θₖ) / xⱼₖ
"""

_PFLOW = """\
╔══════════════════════════════════════════════════════════════════════╗
║                       AC Power Flow  (PFlow)                         ║
╚══════════════════════════════════════════════════════════════════════╝

Solve for Vⱼ, θⱼ such that the AC power-flow equations balance at every
bus (P injections + Q injections), with the slack bus voltage fixed.
Uses Newton-Raphson / Fast-Decoupled iterations.
"""

_DOPF = """\
╔══════════════════════════════════════════════════════════════════════╗
║                Distribution OPF  (DOPF / DOPFVIS)                    ║
╚══════════════════════════════════════════════════════════════════════╝

Decision variables:
    Pᵢ, Qᵢ        — gen / inverter active and reactive set-points
    (DOPFVIS adds voltage-sensitivity-based linearization)

Objective:
    minimize    Σᵢ cᵢ(Pᵢ)  +  Σᵢ cᵢ(Qᵢ)

Constraints:
    Linearized P/Q balance per bus
    V violation penalties or hard limits
"""


# Map family key -> formulation text
_BY_FAMILY = {
    "dcopf":  _DCOPF,
    "dcopf2": _DCOPF,
    "rted":   _RTED,
    "rted2":  _RTED,
    "ed":     _ED,
    "ed2":    _ED,
    "uc":     _UC,
    "uc2":    _UC,
    "acopf":  _ACOPF,
    "dcpf":   _DCPF,
    "pflow":  _PFLOW,
    "dopf":   _DOPF,
    "grbopt": _ACOPF,
    "pypower": _DCPF,
}


def get_formulation(routine_name: str) -> str:
    """Return the Unicode-art math formulation block for the routine.

    Returns an empty string if the routine is unknown.
    """
    family = routine_family(routine_name)
    return _BY_FAMILY.get(family, "")
