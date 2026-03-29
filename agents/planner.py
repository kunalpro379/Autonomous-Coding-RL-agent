from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from LLMs.factory import chat_llm
from prompts.loader import load_prompt
from states.graph_state import AgentState


def planner_node(state: AgentState) -> AgentState:
    print("[planner] generating plan")
    llm = chat_llm()
    tmpl = ChatPromptTemplate.from_messages(
        [("system", load_prompt("planner")), ("human", "{user_task}")]
    )
    prompt = tmpl.format_messages(user_task=state.get("user_task", ""))
    out = llm.invoke(prompt)
    plan = out.content if hasattr(out, "content") else str(out)
    print(f"[planner] plan_chars={len(plan or '')}")
    return {
        "plan": plan,
        "messages": [
            AIMessage(content=f"[planner]\n{plan}"),
        ],
    }