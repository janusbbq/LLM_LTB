"""Classifier output: which Route 1-6 should handle this turn."""

from typing_extensions import Literal
from pydantic import BaseModel, ConfigDict, Field


class MessageClassifier(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_type: Literal[
        "question_general",   # Route 1: Q&A about AMS / scheduling concepts
        "question_parameter", # Route 2: discovery — what cases/routines/solvers exist
        "case_io",            # Route 3: load / inspect / export a case file
        "configure",          # Route 4: change routine, solver, config_t, enable/disable constraints
        "modify",             # Route 5: change load p0, trip gen/line, change line rate
        "solve",              # Route 6: run the active routine
    ] = Field(
        ...,
        description=(
            "Classify into one route: question_general (concepts), "
            "question_parameter (discovery of available cases/routines/solvers), "
            "case_io (load/inspect/export case file), "
            "configure (routine/solver/config/constraint enable-disable), "
            "modify (load p0, trip gen/line, line rate), "
            "solve (run the active routine)."
        ),
    )
