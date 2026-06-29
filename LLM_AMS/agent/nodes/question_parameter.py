"""Route 2: discovery — what cases / routines / solvers / elements are available."""

from datetime import datetime

from agent.ams_engine.engine import SHIPPED_CASES
from agent.ams_engine.routines import (
    all_routine_names,
    compatible_solvers,
    installed_solvers,
)
from agent.schemas.response import NodeResponse
from agent.state.app_state import State
from agent.utils.display import display_executing_node


def _build_snapshot(state, ams_ctx) -> str:
    inputs = state["inputs"]
    parts = [
        f"- Loaded case: {inputs.case_path}",
        f"- Active routine: {inputs.routine}",
        f"- Active solver: {inputs.solver}",
        "",
        f"- All AMS routines: {', '.join(all_routine_names())}",
        f"- Installed cvxpy solvers: {', '.join(installed_solvers())}",
        f"- Solvers compatible with {inputs.routine}: {', '.join(compatible_solvers(inputs.routine)) or '(none)'}",
        "",
        f"- AMS-shipped case aliases: {', '.join(sorted(SHIPPED_CASES.keys()))}",
    ]

    info = ams_ctx.case_info() if ams_ctx.system is not None else {"loaded": False}
    if info.get("loaded"):
        parts.extend([
            "",
            f"- Buses: {info['n_bus']}, Lines: {info['n_line']}, Loads: {info['n_pq']}, "
            f"PV gens: {info['n_pv']}, Slack gens: {info['n_slack']}",
            f"- Load idxes (PQ): {info['load_idx']}",
            f"- Generator idxes (StaticGen): {info['gen_idx']}",
            f"- Line idxes (first 20): {info['line_idx'][:20]}",
        ])
        try:
            constrs = ams_ctx.constraint_status()
            on = [n for n, v in constrs.items() if v]
            off = [n for n, v in constrs.items() if not v]
            parts.append(f"- Constraints ON: {on}")
            parts.append(f"- Constraints OFF: {off}")
        except Exception:
            pass
    else:
        parts.append("- No case loaded yet.")
    return "\n".join(parts)


def question_parameter_agent(state: State, llm, prompts, ams_ctx):
    display_executing_node("question_parameter")

    snapshot = _build_snapshot(state, ams_ctx)
    last_message = state["messages"][-1]

    reply = llm.invoke([
        {"role": "system", "content": prompts["question_parameter"]["system"].format(snapshot=snapshot)},
        {"role": "user", "content": last_message.content},
    ])

    nr = NodeResponse(
        node_type="question_parameter",
        success=True,
        data={"response": reply.content, "snapshot_chars": len(snapshot)},
        message=reply.content,
        timestamp=datetime.now(),
    )
    return {"messages": [reply], "node_response": nr}
