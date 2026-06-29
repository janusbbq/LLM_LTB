from datetime import datetime

from agent.schemas.response import NodeResponse
from agent.state.app_state import State
from agent.utils.display import display_executing_node


_MULTI_STEP_HINTS = ("then ", "after that", "and then", "followed by", "; ")
_COMPARE_HINTS = ("compare ", "versus ", " vs ", "both ")


def router(state: State):
    display_executing_node("router")

    message_type = state.get("message_type", "question_general")
    last = state["messages"][-1] if state.get("messages") else None
    user_input = last.content.lower() if last and hasattr(last, "content") else ""

    is_multi = any(k in user_input for k in _MULTI_STEP_HINTS) or any(
        k in user_input for k in _COMPARE_HINTS
    )
    # Heuristic: "change X to Y and solve" → planner
    has_solve_after_change = ("solve" in user_input or "run" in user_input) and (
        "change" in user_input or "set " in user_input or "trip" in user_input
    )
    needs_planning = is_multi or has_solve_after_change

    if needs_planning:
        next_node, is_compound = "planner", True
    else:
        next_node = message_type if message_type in {
            "question_general", "question_parameter", "case_io",
            "configure", "modify", "solve",
        } else "question_general"
        is_compound = False

    nr = NodeResponse(
        node_type="router",
        success=True,
        data={"next": next_node, "message_type": message_type, "is_compound": is_compound},
        message=f"Routing to: {next_node}",
        timestamp=datetime.now(),
    )
    return {"next": next_node, "is_compound": is_compound, "node_response": nr}
