from __future__ import annotations

import re

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate

from LLMs.factory import chat_llm
from prompts.loader import load_prompt
from states.graph_state import AgentState


_CODE_FENCE = re.compile(r"```(?:json|python)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _extract_code(text: str) -> str:
    m = _CODE_FENCE.search(text or "")
    if m:
        return m.group(1).strip()
    return (text or "").strip()


def developer_node(state: AgentState) -> AgentState:
    print("[developer] producing build plan (JSON)")
    llm = chat_llm(temperature=0.2)
    tmpl = ChatPromptTemplate.from_messages([("system", load_prompt("developer"))])
    meta = state.get("meta") or {}
    msg = tmpl.format_messages(
        team_consensus=(state.get("team_consensus") or "").strip() or "(none)",
        plan=state.get("plan", ""),
        summarized_context=state.get("retrieval_context", ""),
        test_output=state.get("test_output", ""),
        user_task=state.get("user_task", ""),
        active_project_root=meta.get("active_project_root", ""),
        existing_project_files="\n".join((meta.get("executor_wrote_files") or [])[:120]),
        existing_edited_files="\n".join((meta.get("executor_edited_files") or [])[:120]),
    )
    out = llm.invoke(msg).content
    code = _extract_code(out)
    print(f"[developer] code_chars={len(code or '')}")
    return {
        "code": code,
        "messages": [AIMessage(content=f"[developer]\n{code[:4000]}")],
    }