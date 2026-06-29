"""Route 4: change routine / solver / config_t / enable-disable constraints."""

from datetime import datetime

from langchain_core.messages import AIMessage

from agent.ams_engine.routines import compatible_solvers
from agent.schemas.parameter import ConfigureChanges
from agent.schemas.response import NodeResponse
from agent.state.app_state import State
from agent.utils.display import display_executing_node


def configure_agent(state: State, llm, prompts, ams_ctx):
    display_executing_node("configure")

    last_message = state["messages"][-1]
    inputs = state["inputs"]

    extractor = llm.with_structured_output(ConfigureChanges)
    result = extractor.invoke([
        {"role": "system", "content": prompts["configure_extract"]["system"].format(
            case_path=inputs.case_path,
            routine=inputs.routine,
            solver=inputs.solver,
            disabled=inputs.disabled_constraints,
        )},
        {"role": "user", "content": last_message.content},
    ])

    if not result.changes:
        reply = AIMessage(content="No configuration changes detected.")
        nr = NodeResponse(node_type="configure", success=True, data={},
                          message=reply.content, timestamp=datetime.now())
        return {"messages": [reply], "node_response": nr}

    updates = {}
    disabled = list(inputs.disabled_constraints)
    summary = []

    for ch in result.changes:
        try:
            if ch.target == "case_path":
                updates["case_path"] = str(ch.value)
                summary.append(f"case_path → {ch.value}  (use 'load case ...' to actually load)")

            elif ch.target == "routine":
                name = str(ch.value).upper()
                ams_ctx.set_routine(name)
                updates["routine"] = name
                summary.append(f"routine → {name}")

            elif ch.target == "solver":
                solver = str(ch.value).upper()
                compat = compatible_solvers(inputs.routine)
                if compat and solver not in compat and "(internal: pypower)" not in compat:
                    summary.append(
                        f"⚠ solver {solver} is not in the compatible list for "
                        f"{inputs.routine}: {compat}. Setting anyway; solve will fail."
                    )
                updates["solver"] = solver
                summary.append(f"solver → {solver}")

            elif ch.target == "config_t":
                t = float(ch.value)
                if ams_ctx.system is not None:
                    ams_ctx.set_config_t(t)
                updates["config_t"] = t
                summary.append(f"config_t → {t} hour")

            elif ch.target == "disable_constraint":
                name = str(ch.value)
                if ams_ctx.system is not None:
                    ams_ctx.disable_constraints([name])
                if name not in disabled:
                    disabled.append(name)
                summary.append(f"disabled constraint: {name}")

            elif ch.target == "enable_constraint":
                name = str(ch.value)
                if ams_ctx.system is not None:
                    ams_ctx.enable_constraints([name])
                if name in disabled:
                    disabled.remove(name)
                summary.append(f"enabled constraint: {name}")

        except Exception as exc:
            return {"error_info": {
                "error_type": "configure_error",
                "error_message": str(exc),
                "current_inputs": inputs.model_dump(),
                "user_input": last_message.content,
            }, "failed_node": "configure"}

    updates["disabled_constraints"] = disabled
    new_inputs = inputs.model_copy(update=updates)

    content = "Updated configuration:\n" + "\n".join(f"• {s}" for s in summary)
    reply = AIMessage(content=content)
    nr = NodeResponse(node_type="configure", success=True,
                      data={"changes": [c.model_dump() for c in result.changes]},
                      message=content, timestamp=datetime.now())
    return {"messages": [reply], "inputs": new_inputs, "node_response": nr}
