from __future__ import annotations

import operator
from typing import Annotated, Any, Optional, TypedDict

from langchain_core.messages import BaseMessage


class AgentState(TypedDict, total=False):
    """Shared LangGraph state (your Excalidraw \"States\" snapshot)."""

    messages: Annotated[list[BaseMessage], operator.add]
    user_task: str
    plan: str
    retrieval_context: str
    code: str
    test_output: str
    eval_score: float
    eval_feedback: str
    rl_decision: str
    rl_reason: str
    reward: float
    retry_count: int
    max_retries: int
    human_note: Optional[str]
    meta: dict[str, Any]