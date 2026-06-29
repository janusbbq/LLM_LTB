"""Route 1: Q&A about AMS / scheduling concepts."""

from datetime import datetime

from agent.schemas.response import NodeResponse
from agent.state.app_state import State
from agent.utils.display import display_executing_node


def question_general_agent(state: State, llm, prompts, ams_ctx):
    display_executing_node("question_general")

    inputs = state["inputs"]
    last_message = state["messages"][-1]

    system_prompt = prompts["question_general"]["system"].format(
        context=prompts["question_general"]["context"],
        case_path=inputs.case_path,
        routine=inputs.routine,
        solver=inputs.solver,
    )
    reply = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompts["question_general"]["user"].format(
            user_input=last_message.content
        )},
    ])

    nr = NodeResponse(
        node_type="question_general",
        success=True,
        data={"response": reply.content},
        message=reply.content,
        timestamp=datetime.now(),
    )
    return {"messages": [reply], "node_response": nr}
