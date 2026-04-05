from __future__ import annotations

import json

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate

from LLMs.factory import chat_llm
from prompts.loader import load_prompt
from services.retrieval import RetrievalService
from states.graph_state import AgentState


def retriever_node(state: AgentState) -> AgentState:
    print("[retriever] building context (vectorless RAG + vectordb + tavily + scrape)")
    service = RetrievalService()
    task = state.get("user_task", "") or ""
    consensus = (state.get("team_consensus") or "").strip()
    if consensus:
        task = f"{task}\n\n### Team panel consensus (use for retrieval focus)\n{consensus[:6000]}"
    raw = service.build_context(task)
    print(f"[retriever] raw_chars={len(raw or '')}")

    llm = chat_llm(temperature=0.1)
    tmpl = ChatPromptTemplate.from_messages(
        [
            ("system", load_prompt("retriever")),
        ]
    )
    summarized = llm.invoke(
        tmpl.format_messages(
            user_task=state.get("user_task", ""),
            retrieval_context=raw,
        )
    ).content
    print(f"[retriever] summary_chars={len(summarized or '')}")

    snapshot = json.dumps({"retrieval_chars": len(raw), "summary_chars": len(summarized)})
    return {
        "retrieval_context": f"{summarized}\n\n---\nRAW:\n{raw[:8000]}",
        "meta": {**(state.get("meta") or {}), "retriever_snapshot": snapshot},
        "messages": [AIMessage(content=f"[retriever]\n{summarized}")],
    }