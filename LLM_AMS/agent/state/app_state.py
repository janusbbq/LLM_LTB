"""LangGraph TypedDict state.

Notes:
- ``inputs`` is a pydantic ``Inputs`` instance (see ``agent.schemas.inputs``).
- ``ams_context`` is *not* part of the LangGraph state because it wraps a
  live ``ams.System`` (non-serializable). It is held by the SessionManager
  and bound into node closures (same pattern as ``retriever`` in pv-curve).
"""

from typing import Any, List, Optional
from typing_extensions import Annotated, TypedDict
from langgraph.graph.message import add_messages


class State(TypedDict):
    messages: Annotated[list, add_messages]
    message_type: Optional[str]
    is_multi_step: bool
    inputs: Any
    results: Optional[dict]
    error_info: Optional[dict]
    plan: Optional[Any]
    current_step: int
    step_results: List[dict]
    is_compound: bool
    retry_count: int
    failed_node: Optional[str]
    conversation_context: List[dict]
    next: Optional[str]
