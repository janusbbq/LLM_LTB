"""Structured scenario-study spec (Step 1).

Kept in its own module and imported directly (``from agent.schemas.study import
StudySpec``) so it does not require touching ``agent/schemas/__init__.py`` —
minimizes merge surface with the web side.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class LoadSweep(BaseModel):
    """A load-scaling sweep over one target."""

    target: str = Field(
        default="all",
        description="PQ load idx (e.g. 'PQ_1'), or 'all' to scale every load.",
    )
    scales: List[float] = Field(
        default_factory=lambda: [0.90, 0.95, 1.00, 1.05, 1.10],
        description="Multipliers applied to the base p0 (1.00 = baseline).",
    )


class StudySpec(BaseModel):
    """A small load-scenario study over a single AMS case + routine."""

    routine: str = "DCOPF"
    solver: str = "CLARABEL"
    base_case: str = "5bus"
    load_sweep: LoadSweep = Field(default_factory=LoadSweep)
    tags: List[str] = Field(default_factory=lambda: ["baseline", "sensitivity"])
