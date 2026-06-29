from langchain_core.messages import HumanMessage

from agent.state.app_state import State
from agent.utils.display import display_executing_node


def step_controller(state: State):
    display_executing_node("step_controller")

    plan = state.get("plan")
    current = state.get("current_step", 0)

    if not plan or current >= len(plan.steps):
        return {"next": "summary"}

    step = plan.steps[current]
    step_msg = HumanMessage(content=step.content)
    return {"messages": [step_msg], "message_type": step.action, "next": step.action}
