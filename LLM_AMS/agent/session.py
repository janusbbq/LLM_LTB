"""Session manager: holds state + ams_ctx, streams graph execution per turn."""

from datetime import datetime
from typing import Any, Dict, Generator, Tuple

from langchain_core.messages import HumanMessage

from agent.utils.common_utils import create_initial_state


class SessionManager:
    def __init__(self, graph, llm, ams_ctx, provider: str,
                 case_path: str = "5bus/pjm5bus_demo.xlsx",
                 routine: str = "RTED", solver: str = "CLARABEL"):
        self.graph = graph
        self.llm = llm
        self.ams_ctx = ams_ctx
        self.provider = provider
        self.model_name = getattr(llm, "_model_name", "unknown")
        self.state = create_initial_state(case_path=case_path, routine=routine, solver=solver)
        self.session_start = datetime.now()
        self.session_id = f"session_{self.session_start.strftime('%Y%m%d_%H%M%S')}"

    def bootstrap(self):
        """Eagerly load the default case + set routine, mirroring ex2 setup."""
        inputs = self.state["inputs"]
        self.ams_ctx.load_case(inputs.case_path)
        self.ams_ctx.set_routine(inputs.routine)
        # Reflect actual resolved path back into inputs
        self.state["inputs"] = inputs.model_copy(update={"case_path": self.ams_ctx.case_path})

    def execute_turn_streaming(self, user_input: str,
                               config: Dict[str, Any] = None
                               ) -> Generator[Tuple[str, Dict[str, Any]], None, None]:
        if config is None:
            config = {"recursion_limit": 50}

        self.state["messages"] = self.state.get("messages", []) + [HumanMessage(content=user_input)]

        for chunk in self.graph.stream(self.state, config=config, stream_mode="updates"):
            for node_name, state_update in chunk.items():
                yield node_name, state_update
                for k, v in state_update.items():
                    if k == "messages":
                        self.state["messages"] = self.state.get("messages", []) + v
                    else:
                        self.state[k] = v
