"""Generic node-response envelope used by every workflow node."""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class NodeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    node_type: str
    success: bool
    data: Dict[str, Any]
    message: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None
