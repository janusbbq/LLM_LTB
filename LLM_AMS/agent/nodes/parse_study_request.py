"""Parse a natural-language study request into a StudySpec (Step 1.3).

This is the *optional* NL entry point. It is a plain callable — it is NOT
registered in the LangGraph workflow yet, so it introduces no shared-file
change. Wire it into ``classifier`` / ``route`` / ``workflow`` later in one
coordinated commit (see FURTHER_DEVELOPMENT.md Step 1.7).

The deterministic execution path (generate_scenarios -> run_small_study) does
NOT depend on this module, so studies can also be built by constructing a
StudySpec directly (e.g. from the CLI) without invoking the LLM.
"""

from __future__ import annotations

from agent.schemas.study import StudySpec


PARSE_SYSTEM = (
    "You convert a user's request for an AMS load-scenario study into a "
    "structured StudySpec. Load is an exogenous input, not a decision variable: "
    "the study characterizes system response across assumed load levels. "
    "Extract the routine (default DCOPF), solver (default CLARABEL), base_case "
    "(default '5bus'), and the load sweep (target load id or 'all', and the list "
    "of scale multipliers where 1.0 is baseline). For '±5% and ±10%' use scales "
    "[0.90, 0.95, 1.00, 1.05, 1.10]."
)


def parse_study_request(text: str, llm) -> StudySpec:
    """Use the LLM's structured-output mode to produce a validated StudySpec."""
    structured = llm.with_structured_output(StudySpec)
    return structured.invoke(f"{PARSE_SYSTEM}\n\nRequest: {text}")
