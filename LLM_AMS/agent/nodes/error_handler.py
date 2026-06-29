from datetime import datetime

from agent.schemas.response import NodeResponse
from agent.state.app_state import State
from agent.utils.display import display_executing_node


def error_handler_agent(state: State, llm, prompts):
    display_executing_node("error_handler")

    err = state.get("error_info") or {}
    context = (
        f"Error type: {err.get('error_type', 'unknown')}\n"
        f"Error message: {err.get('error_message', 'n/a')}\n"
        f"Failed node: {state.get('failed_node', 'n/a')}\n"
        f"Current inputs: {err.get('current_inputs', 'n/a')}\n"
        f"User input: {err.get('user_input', 'n/a')}"
    )
    reply = llm.invoke([
        {"role": "system", "content": prompts["error_handler"]["system"]},
        {"role": "user", "content": prompts["error_handler"]["user"].format(error_context=context)},
    ])

    nr = NodeResponse(node_type="error_handler", success=True,
                      data={"error_type": err.get("error_type", "unknown")},
                      message=reply.content, timestamp=datetime.now())
    return {"messages": [reply], "error_info": None, "failed_node": None,
            "retry_count": 0, "node_response": nr}
