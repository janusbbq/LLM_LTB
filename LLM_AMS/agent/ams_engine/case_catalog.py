"""Deterministic, keyword-based case retrieval for AMS-shipped cases.

Design goals (so users are not forced into rigid GUI-style phrasing):

* **The bus-count number is the strongest signal.** "5 bus", "ieee39", "case118"
  all resolve primarily by their number. A number that does not match a case is
  disqualifying (so "14" never returns a 39-bus case).
* **Secondary keywords disambiguate** when one number maps to several cases
  (e.g. ``ieee14`` has json / raw / conn / uced variants plus MATPOWER
  ``case14``). Tokens like ``uced``, ``conn``, ``matpower``, ``ev`` pick one.
* **When nothing distinguishes them, we pick a sensible default and say so.**
  The resolver returns ``status="ambiguous"`` with the full version list and a
  one-line description of each, so the caller can load the default *and* tell the
  user how to switch.
* **Cases without a number** (wecc, npcc, hawaii, pglib) resolve by name keyword.

Everything here is pure/deterministic — no LLM — so it can be exhaustively
validated by permutation testing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# Bus-count numbers that actually appear in the shipped catalog. Only these are
# treated as "bus numbers"; trailing digits inside modifier tokens (regcv1,
# esd1, pvd1, uc2, rted2) are therefore ignored.
KNOWN_NUMBERS = (5, 14, 39, 40, 118, 123, 300, 2000)


@dataclass(frozen=True)
class CaseEntry:
    key: str                    # canonical alias (unique)
    path: str                   # AMS sub-path passed to ams.get_case
    desc: str                   # one-line human description
    number: Optional[int]       # bus-count number, or None if non-numeric name
    group: str                  # physical-system group id (for defaulting)
    rank: int                   # lower = preferred default within a candidate set
    tags: frozenset             # single-token keywords that select this case
    fmt: str                    # file format: xlsx / json / raw / m
    caveat: str = ""            # known ltbams load limitation, if any


def _e(key, path, desc, number, group, rank, tags, fmt, caveat="") -> CaseEntry:
    return CaseEntry(key, path, desc, number, group, rank,
                     frozenset(tags.split()), fmt, caveat)


# ---------------------------------------------------------------- catalog
# rank 0 == the default choice for its (number/group) family.
CASES: List[CaseEntry] = [
    # ---- PJM 5-bus family ----
    _e("pjm5bus", "5bus/pjm5bus_demo.xlsx",
       "PJM 5-bus demo system — the default 5-bus case",
       5, "pjm5bus", 0, "pjm5bus pjm 5bus demo", "xlsx"),
    _e("pjm5bus_json", "5bus/pjm5bus_demo.json",
       "PJM 5-bus demo in JSON format",
       5, "pjm5bus", 3, "pjm5bus pjm 5bus demo json", "json"),
    _e("pjm5bus_ev", "5bus/pjm5bus_ev.xlsx",
       "PJM 5-bus with an EV (electric-vehicle) aggregate load",
       5, "pjm5bus", 1, "pjm5bus pjm 5bus ev", "xlsx",
       caveat="ltbams cannot load this case (EV model references missing Bus_2)"),
    _e("pjm5bus_jumper", "5bus/pjm5bus_jumper.xlsx",
       "PJM 5-bus with a zero-impedance jumper line",
       5, "pjm5bus", 2, "pjm5bus pjm 5bus jumper", "xlsx"),

    # ---- IEEE 14-bus family ----
    _e("ieee14", "ieee14/ieee14.json",
       "IEEE 14-bus (JSON) — the default 14-bus case",
       14, "ieee14", 0, "ieee14 ieee json", "json"),
    _e("ieee14_conn", "ieee14/ieee14_conn.xlsx",
       "IEEE 14-bus with explicit bus-connectivity data",
       14, "ieee14", 1, "ieee14 ieee conn connectivity", "xlsx"),
    _e("ieee14_uced", "ieee14/ieee14_uced.xlsx",
       "IEEE 14-bus prepared for unit-commitment / economic-dispatch (UCED)",
       14, "ieee14", 2, "ieee14 ieee uced uc ed commitment", "xlsx"),
    _e("ieee14_raw", "ieee14/ieee14.raw",
       "IEEE 14-bus in PSS/E RAW format",
       14, "ieee14", 3, "ieee14 ieee raw psse", "raw"),

    # ---- IEEE 39-bus (New England) family ----
    _e("ieee39", "ieee39/ieee39.xlsx",
       "IEEE 39-bus (New England) — the default 39-bus case",
       39, "ieee39", 0, "ieee39 ieee newengland", "xlsx"),
    _e("ieee39_uced", "ieee39/ieee39_uced.xlsx",
       "IEEE 39-bus prepared for UCED",
       39, "ieee39", 1, "ieee39 ieee uced uc ed commitment", "xlsx"),
    _e("ieee39_uced_esd1", "ieee39/ieee39_uced_esd1.xlsx",
       "IEEE 39-bus UCED with ESD1 energy-storage devices",
       39, "ieee39", 2, "ieee39 ieee uced esd1 esd storage battery commitment", "xlsx"),
    _e("ieee39_uced_pvd1", "ieee39/ieee39_uced_pvd1.xlsx",
       "IEEE 39-bus UCED with PVD1 distributed PV",
       39, "ieee39", 3, "ieee39 ieee uced pvd1 pv solar commitment", "xlsx"),
    _e("ieee39_uced_vis", "ieee39/ieee39_uced_vis.xlsx",
       "IEEE 39-bus UCED (VIS visualization variant)",
       39, "ieee39", 4, "ieee39 ieee uced vis commitment", "xlsx"),

    # ---- IEEE 123-bus distribution feeder ----
    _e("ieee123", "ieee123/ieee123.xlsx",
       "IEEE 123-bus distribution feeder — the default 123-bus case",
       123, "ieee123", 0, "ieee123 ieee", "xlsx"),
    _e("ieee123_regcv1", "ieee123/ieee123_regcv1.xlsx",
       "IEEE 123-bus with REGCV1 grid-forming renewable model",
       123, "ieee123", 1, "ieee123 ieee regcv1 regcv regc", "xlsx"),

    # ---- Hawaii 40-bus ----
    _e("hawaii40", "hawaii40/Hawaii40.m",
       "Hawaii (Oahu) 40-bus system (MATPOWER format)",
       40, "hawaii40", 0, "hawaii hawaii40 oahu", "m",
       caveat="ltbams cannot load this case (unsupported MATPOWER gencost model)"),

    # ---- MATPOWER standalone cases ----
    _e("case5", "matpower/case5.m",
       "MATPOWER 5-bus case (PJM 5-bus, MATPOWER format)",
       5, "matpower5", 4, "case5 matpower mp", "m"),
    _e("case14", "matpower/case14.m",
       "MATPOWER IEEE 14-bus case",
       14, "matpower14", 4, "case14 matpower mp", "m"),
    _e("case39", "matpower/case39.m",
       "MATPOWER IEEE 39-bus case",
       39, "matpower39", 5, "case39 matpower mp", "m"),
    _e("case118", "matpower/case118.m",
       "MATPOWER IEEE 118-bus case",
       118, "matpower118", 0, "case118 matpower mp ieee118", "m"),
    _e("case300", "matpower/case300.m",
       "MATPOWER IEEE 300-bus case",
       300, "matpower300", 0, "case300 matpower mp ieee300", "m"),
    _e("case2000", "matpower/case_ACTIVSg2000.m",
       "MATPOWER ACTIVSg 2000-bus synthetic Texas grid",
       2000, "activsg2000", 0, "case2000 activsg activsg2000 activ texas synthetic matpower", "m"),

    # ---- Regional interconnection models (name-keyed, no number in name) ----
    _e("npcc", "npcc/npcc.m",
       "NPCC 140-bus Northeast-US system (MATPOWER)",
       None, "npcc", 0, "npcc northeast", "m"),
    _e("npcc_uced", "npcc/npcc_uced.xlsx",
       "NPCC system prepared for UCED",
       None, "npcc", 1, "npcc uced uc ed northeast commitment", "xlsx"),
    _e("wecc", "wecc/wecc.m",
       "WECC 179-bus Western-US system (MATPOWER)",
       None, "wecc", 0, "wecc western west", "m"),
    _e("wecc_uced", "wecc/wecc_uced.xlsx",
       "WECC system prepared for UCED",
       None, "wecc", 1, "wecc uced uc ed western west commitment", "xlsx"),

    # ---- PGLib-OPF benchmark (39-bus; ranked last so it never becomes the
    #      default for a bare "39", but is still reachable) ----
    _e("pglib_case39", "pglib/pglib_opf_case39_epri__api.m",
       "PGLib-OPF 39-bus EPRI API benchmark case",
       39, "pglib", 6, "pglib epri api pglib39", "m",
       caveat="ltbams cannot load this case (PGLib parser KeyError 'gen')"),
]


# ---------------------------------------------------------------- indexes
ALIAS_INDEX: Dict[str, CaseEntry] = {e.key: e for e in CASES}
PATH_INDEX: Dict[str, CaseEntry] = {e.path.lower(): e for e in CASES}

# Extra hand aliases kept for backward compatibility / convenience.
_EXTRA_ALIASES = {
    "5bus": "pjm5bus",
    "pjm5bus_demo": "pjm5bus",
    "pjm": "pjm5bus",
    "activsg2000": "case2000",
    "activsg": "case2000",
    "ieee14_json": "ieee14",
}
for _a, _k in _EXTRA_ALIASES.items():
    ALIAS_INDEX.setdefault(_a, ALIAS_INDEX[_k])


# Backward-compatible flat alias -> path map (used by discovery / snapshots).
SHIPPED_CASES: Dict[str, str] = {k: e.path for k, e in ALIAS_INDEX.items()}


# ---------------------------------------------------------------- resolution
@dataclass
class CaseResolution:
    status: str                       # "single" | "ambiguous" | "not_found"
    path: Optional[str] = None        # sub-path to load (default for ambiguous)
    entry: Optional[CaseEntry] = None # chosen / default entry
    candidates: List[CaseEntry] = field(default_factory=list)
    message: str = ""                 # user-facing note (esp. for ambiguous)
    query: str = ""


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_PATH_RE = re.compile(r"[A-Za-z0-9_./\\-]+\.(?:xlsx|json|raw|m)", re.IGNORECASE)


def _tokens(text: str) -> set:
    return set(_TOKEN_RE.findall(text.lower()))


def _bus_numbers(text: str) -> set:
    """Extract only *known* bus numbers, with digit boundaries so that e.g.
    "140" does not match 14 and "regcv1" contributes nothing."""
    found = set()
    for n in KNOWN_NUMBERS:
        if re.search(rf"(?<!\d){n}(?!\d)", text):
            found.add(n)
    return found


def _looks_like_path(text: str) -> bool:
    t = text.lower()
    return "/" in t or "\\" in t or t.endswith((".xlsx", ".json", ".raw", ".m"))


def _group_label(entries: List[CaseEntry]) -> str:
    nums = {e.number for e in entries}
    if len(nums) == 1 and None not in nums:
        return f"{next(iter(nums))}-bus"
    groups = {e.group for e in entries}
    if len(groups) == 1:
        return next(iter(groups))
    return "matching"


def _ambiguous_message(default: CaseEntry, entries: List[CaseEntry]) -> str:
    label = _group_label(entries)
    lines = []
    for e in entries:
        marker = "  ← default" if e is default else ""
        lines.append(f"  • `{e.key}` — {e.desc}{marker}")
    others = [e.key for e in entries if e is not default]
    hint = f" (e.g. say `{others[0]}`)" if others else ""
    return (
        f"Several {label} cases are available; defaulting to `{default.key}`.\n"
        + "\n".join(lines)
        + f"\nTo pick another, mention its keyword{hint}."
    )


def _not_found_message(query: str) -> str:
    groups = sorted({e.group for e in CASES})
    return (
        f"Couldn't match a case to '{query}'. "
        "Try a bus number (e.g. `5`, `14`, `39`, `118`, `300`), a name "
        "(`pjm`, `ieee14`, `ieee39`, `wecc`, `npcc`, `hawaii`, `pglib`), "
        "or a file path (e.g. `matpower/case118.m`)."
    )


def resolve_case(query: str) -> CaseResolution:
    """Resolve a free-form case request into a concrete case.

    Returns a :class:`CaseResolution`:
      * ``single``    — exactly one case matched (``path``/``entry`` set).
      * ``ambiguous`` — several matched; ``entry`` is the default and
        ``candidates`` lists them all, with ``message`` explaining the choice.
      * ``not_found`` — nothing matched.
    """
    q = (query or "").strip()
    if not q:
        return CaseResolution("not_found", message="Empty request.", query=query)
    ql = q.lower()

    # 1. Explicit file path / catalog sub-path (extract the path token from any
    #    surrounding words like "load case matpower/case118.m").
    if _looks_like_path(ql):
        m = _PATH_RE.search(q)
        if m:
            cand = m.group(0).replace("\\", "/").lower()
            e = PATH_INDEX.get(cand)
            if e:
                return CaseResolution("single", e.path, e, query=query)
            if "/" in cand:
                # Unknown sub-path: pass through to ams.get_case downstream.
                return CaseResolution("single", m.group(0).replace("\\", "/"),
                                      None, query=query)
            # Bare filename like "case14.m": drop the extension, resolve by keyword.
            ql = re.sub(r"\.(xlsx|json|raw|m)$", "", cand)
            q = ql

    # 2. Exact alias / key.
    if ql in ALIAS_INDEX:
        e = ALIAS_INDEX[ql]
        return CaseResolution("single", e.path, e, query=query)

    tokens = _tokens(ql)
    nums = _bus_numbers(ql)

    # 3. Keyword + number scoring.
    scored = []  # (hits, entry)
    for e in CASES:
        if nums and (e.number is None or e.number not in nums):
            continue  # number is decisive
        hits = len(tokens & e.tags)
        scored.append((hits, e))

    if not scored:
        return CaseResolution("not_found", message=_not_found_message(q), query=query)

    max_hits = max(h for h, _ in scored)
    if max_hits == 0:
        if not nums:
            # No number and no keyword hit → genuinely unrecognised.
            return CaseResolution("not_found", message=_not_found_message(q), query=query)
        # Number only (e.g. "14"): the whole number family is the candidate set.
        top = [e for _, e in scored]
    else:
        top = [e for h, e in scored if h == max_hits]

    if len(top) == 1:
        e = top[0]
        return CaseResolution("single", e.path, e, query=query)

    top = sorted(top, key=lambda e: (e.rank, e.key))
    default = top[0]
    return CaseResolution(
        "ambiguous", default.path, default, top,
        _ambiguous_message(default, top), query,
    )


def catalog_summary() -> str:
    """Grouped, human-readable catalog for discovery / help output."""
    by_group: Dict[str, List[CaseEntry]] = {}
    for e in CASES:
        by_group.setdefault(e.group, []).append(e)
    order = ["pjm5bus", "ieee14", "ieee39", "ieee123", "hawaii40",
             "matpower5", "matpower14", "matpower39", "matpower118",
             "matpower300", "activsg2000", "npcc", "wecc", "pglib"]
    lines = []
    for g in order:
        items = by_group.get(g)
        if not items:
            continue
        for e in sorted(items, key=lambda x: x.rank):
            note = f"  [{e.caveat}]" if e.caveat else ""
            lines.append(f"- `{e.key}`: {e.desc}{note}")
    return "\n".join(lines)
