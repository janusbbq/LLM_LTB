"""Initial state + small helpers."""

from agent.schemas.inputs import Inputs


def create_initial_state(case_path: str = "5bus/pjm5bus_demo.xlsx",
                         routine: str = "RTED",
                         solver: str = "CLARABEL"):
    return {
        "messages": [],
        "message_type": None,
        "inputs": Inputs(case_path=case_path, routine=routine, solver=solver),
        "results": None,
        "error_info": None,
        "plan": None,
        "current_step": 0,
        "step_results": [],
        "is_compound": False,
        "retry_count": 0,
        "failed_node": None,
        "conversation_context": [],
        "next": None,
    }
