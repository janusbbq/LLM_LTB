"""Route 3: load / inspect a case file. Phase 1 covers load + inspect."""

import re
from datetime import datetime

from langchain_core.messages import AIMessage

from agent.schemas.response import NodeResponse
from agent.state.app_state import State
from agent.utils.display import display_executing_node


_CASE_PATTERN = re.compile(
    r"[A-Za-z0-9_./-]+?\.(?:xlsx|json|raw|m)",
    flags=re.IGNORECASE,
)
_ALIAS_PATTERN = re.compile(
    r"\b(pjm5bus(?:_demo|_ev|_jumper)?|5bus|ieee14(?:_uced|_conn|_raw)?|ieee39(?:_uced)?|"
    r"case14|case39|case118|case300|npcc|wecc)\b",
    flags=re.IGNORECASE,
)


def _parse_case(text: str) -> str | None:
    m = _CASE_PATTERN.search(text)
    if m:
        return m.group(0)
    m = _ALIAS_PATTERN.search(text)
    if m:
        return m.group(0).lower()
    return None


def case_io_agent(state: State, llm, prompts, ams_ctx):
    display_executing_node("case_io")

    last_message = state["messages"][-1]
    text = last_message.content
    inputs = state["inputs"]

    wants_inspect = any(k in text.lower() for k in ("show", "inspect", "current case", "case info"))
    case_arg = _parse_case(text)

    if case_arg is None and wants_inspect:
        info = ams_ctx.case_info()
        content = (
            f"**Case info**: {info.get('case_path', '(none)')}\n\n"
            f"- Buses: {info.get('n_bus')}\n"
            f"- Lines: {info.get('n_line')}\n"
            f"- Loads (PQ): {info.get('n_pq')}\n"
            f"- Generators (StaticGen): {info.get('n_staticgen')} "
            f"(PV: {info.get('n_pv')}, Slack: {info.get('n_slack')})\n"
        )
        reply = AIMessage(content=content)
        nr = NodeResponse(
            node_type="case_io",
            success=True,
            data={"action": "inspect", "info": info},
            message=content,
            timestamp=datetime.now(),
        )
        return {"messages": [reply], "node_response": nr}

    if case_arg is None:
        msg = (
            "I couldn't parse a case from your request. Try a file path "
            "(e.g. `5bus/pjm5bus_demo.xlsx`, `matpower/case118.m`) or an alias "
            "(e.g. `pjm5bus`, `ieee14_uced`, `case118`)."
        )
        reply = AIMessage(content=msg)
        nr = NodeResponse(
            node_type="case_io", success=False, data={}, message=msg,
            timestamp=datetime.now(),
        )
        return {"messages": [reply], "node_response": nr}

    try:
        info = ams_ctx.load_case(case_arg)
    except Exception as exc:
        err = {"error_type": "case_load_error", "error_message": str(exc),
               "user_input": text, "current_inputs": inputs.model_dump()}
        return {"error_info": err, "failed_node": "case_io"}

    # Reset session-level modifications since we just loaded a fresh case.
    new_inputs = inputs.model_copy(update={
        "case_path": info["case_path"],
        "load_overrides": {},
        "gen_off": [],
        "line_off": [],
        "line_rate_overrides": {},
        "disabled_constraints": [],
    })

    content = (
        f"Loaded case: `{info['case_path']}`\n"
        f"- Buses: {info['n_bus']}, Lines: {info['n_line']}, "
        f"Loads: {info['n_pq']}, StaticGens: {info['n_staticgen']}\n"
        f"- Session modifications reset."
    )
    reply = AIMessage(content=content)
    nr = NodeResponse(
        node_type="case_io",
        success=True,
        data={"action": "load", "info": info},
        message=content,
        timestamp=datetime.now(),
    )
    return {"messages": [reply], "inputs": new_inputs, "node_response": nr}
