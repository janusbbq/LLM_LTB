from agent.state.app_state import State
from agent.utils.display import display_executing_node


def advance_step(state: State):
    display_executing_node("advance_step")

    current = state.get("current_step", 0)
    plan = state.get("plan")
    step_results = state.get("step_results", [])

    if state.get("messages"):
        last = state["messages"][-1]
        action = plan.steps[current].action if plan and current < len(plan.steps) else "unknown"
        step_results.append({
            "step": current,
            "action": action,
            "result": last.content if hasattr(last, "content") else str(last),
        })

    next_idx = current + 1
    return {
        "current_step": next_idx,
        "step_results": step_results,
        "next": "step_controller" if plan and next_idx < len(plan.steps) else "summary",
    }
