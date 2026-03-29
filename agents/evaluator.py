from __future__ import annotations

import json
import re

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate

from LLMs.factory import chat_llm
from prompts.loader import load_prompt
from states.graph_state import AgentState


_JSON = re.compile(r"\{.*\}", re.DOTALL)


def evaluator_node(state: AgentState) -> AgentState:
    print("[evaluator] grading result")
    llm = chat_llm(temperature=0.0)
    tmpl = ChatPromptTemplate.from_messages([("system", load_prompt("evaluator"))])
    raw = llm.invoke(
        tmpl.format_messages(
            user_task=state.get("user_task", ""),
            code=state.get("code", ""),
            test_output=state.get("test_output", ""),
            structure_warnings="\n".join((state.get("meta") or {}).get("structure_warnings") or []),
        )
    ).content

    m = _JSON.search(raw or "")
    score, feedback = 0.0, (raw or "")
    if m:
        try:
            obj = json.loads(m.group(0))
            score = float(obj.get("score", 0))
            feedback = str(obj.get("feedback", ""))
        except Exception:
            pass
    print(f"[evaluator] score={score}")

    return {
        "eval_score": score,
        "eval_feedback": feedback,
        "messages": [AIMessage(content=f"[evaluator] score={score} {feedback}")],
    }