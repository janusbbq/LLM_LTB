from datetime import datetime

from langchain_core.messages import AIMessage

from agent.schemas.response import NodeResponse
from agent.state.app_state import State
from agent.utils.display import display_executing_node


def summary_agent(state: State):
    display_executing_node("summary")

    plan = state.get("plan")
    step_results = state.get("step_results", [])

    parts = [f"Completed multi-step request: {plan.description if plan else 'unknown'}\n"]
    for i, r in enumerate(step_results):
        action = (plan.steps[i].action if plan and i < len(plan.steps)
                  else r.get("action", "unknown"))
        snippet = r["result"][:120] + ("…" if len(r["result"]) > 120 else "")
        parts.append(f"Step {i+1} ({action}): {snippet}")

    summary = "\n".join(parts)
    reply = AIMessage(content=summary)
    nr = NodeResponse(node_type="summary", success=True,
                      data={"steps_completed": len(step_results)},
                      message=summary, timestamp=datetime.now())
    return {"messages": [reply], "node_response": nr}
