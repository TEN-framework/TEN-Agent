from pydantic import BaseModel
from typing import Literal, Union, Dict, Any
from ten_ai_base.types import LLMToolMetadata


# ==== Base Event ====


class AgentEventBase(BaseModel):
    """Base class for all agent-level events."""

    type: Literal["cmd", "data"]
    name: str


# ==== CMD Events ====


class UserJoinedEvent(AgentEventBase):
    """Event triggered when a user joins the session."""

    type: Literal["cmd"] = "cmd"
    name: Literal["on_user_joined"] = "on_user_joined"


class UserLeftEvent(AgentEventBase):
    """Event triggered when a user leaves the session."""

    type: Literal["cmd"] = "cmd"
    name: Literal["on_user_left"] = "on_user_left"


class ToolRegisterEvent(AgentEventBase):
    """Event triggered when a tool is registered by the user."""

    type: Literal["cmd"] = "cmd"
    name: Literal["tool_register"] = "tool_register"
    tool: LLMToolMetadata
    source: str


# ==== DATA Events ====


class ASRResultEvent(AgentEventBase):
    """Event triggered when ASR result is received (partial or final)."""

    type: Literal["data"] = "data"
    name: Literal["asr_result"] = "asr_result"
    text: str
    final: bool
    metadata: Dict[str, Any]
    start_ms: int | None = None


class ASRCommitTimeoutEvent(AgentEventBase):
    """The speech-final fallback deadline for one ASR session."""

    type: Literal["data"] = "data"
    name: Literal["asr_commit_timeout"] = "asr_commit_timeout"
    session_id: str
    stream_id: int
    generation: int


class LLMResponseEvent(AgentEventBase):
    """Event triggered when LLM returns a streaming response."""

    type: Literal["message", "reasoning"] = "message"
    name: Literal["llm_response"] = "llm_response"
    delta: str
    text: str
    is_final: bool


class ModelRouteEvent(AgentEventBase):
    """The selected LLM destination for a user turn."""

    type: Literal["data"] = "data"
    name: Literal["model_route"] = "model_route"
    destination: str
    status: str
    latency_ms: int
    choice: str | None = None
    confidence: float | None = None


# ==== Unified Event Union ====

AgentEvent = Union[
    UserJoinedEvent,
    UserLeftEvent,
    ToolRegisterEvent,
    ASRResultEvent,
    ASRCommitTimeoutEvent,
    LLMResponseEvent,
    ModelRouteEvent,
]
