from __future__ import annotations

import json
import re

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate

from config.settings import settings
from LLMs.factory import chat_llm
from prompts.loader import load_prompt
from states.graph_state import AgentState

_JSON = re.compile(r"\{.*\}", re.DOTALL)


def _compute_reward(state: AgentState) -> float:
    """Scalar reward from eval score + latest execution result."""
    score = float(state.get("eval_score") or 0.0)  # 0–10
    meta = state.get("meta") or {}
    last_exit = int(meta.get("last_exit_code", 0))
    executor_error = bool(meta.get("executor_error"))
    structure_warnings = len(meta.get("structure_warnings") or [])
    no_test_commands = "no test_commands provided" in str(state.get("test_output") or "").lower()

    # Base reward from score (0–1)
    r = score / 10.0

    # Penalty/bonus from execution
    if last_exit != 0:
        r -= 0.3
    if executor_error:
        r -= 0.35
    if no_test_commands:
        r -= 0.25
    if structure_warnings >= 2:
        r -= 0.15
    elif score >= 8.0:
        r += 0.2

    # Clamp to a reasonable range
    if r < -1.0:
        r = -1.0
    if r > 1.5:
        r = 1.5
    return r


def _heuristic(state: AgentState) -> tuple[str, str]:
    score = float(state.get("eval_score") or 0.0)
    retries = int(state.get("retry_count") or 0)
    max_r = int(state.get("max_retries") or 1)
    min_accept = float(getattr(settings, "min_accept_score", 7.0))
    hard_max = int(getattr(settings, "hard_max_retries", 8))
    meta = state.get("meta") or {}
    executor_error = bool(meta.get("executor_error"))
    structure_warnings = len(meta.get("structure_warnings") or [])
    no_test_commands = "no test_commands provided" in str(state.get("test_output") or "").lower()
    prev_score = meta.get("prev_eval_score")
    stagnant = False
    if isinstance(prev_score, (int, float)):
        stagnant = abs(score - float(prev_score)) < 0.25 and score < min_accept

    if score >= min_accept:
        return "STOP", "meets_acceptance_threshold"
    if retries >= hard_max:
        return "STOP", "hard_max_retries_exhausted"
    # Fix execution-contract issues first by rewriting output format/content.
    if executor_error or no_test_commands:
        return "REWRITE_CODE", "execution_contract_failure"
    # If we keep rewriting with no gains, replan architecture.
    if stagnant and retries >= 1:
        return "REPLAN", "stagnant_low_progress"
    if structure_warnings >= 3 and retries >= 2:
        return "REPLAN", "persistent_structure_issues"
    # Prefer rewrite on low score first; replan later only if stuck.
    if score < 5.0:
        return "REWRITE_CODE", "low_score_needs_concrete_fixes"
    if retries >= max_r:
        return "REPLAN", "soft_max_retries_reached"
    return "REWRITE_CODE", "mid_score"


def rl_node(state: AgentState) -> AgentState:
    reward = _compute_reward(state)
    decision, reason = _heuristic(state)
    retries = int(state.get("retry_count") or 0)
    max_r = int(state.get("max_retries") or 1)
    print(f"[rl_agent] retries={retries}/{max_r} score={state.get('eval_score', 0.0)} reward={reward:.2f}")

    llm = chat_llm(temperature=0.0)
    tmpl = ChatPromptTemplate.from_messages([("system", load_prompt("rl_agent"))])
    raw = llm.invoke(
        tmpl.format_messages(
            reward=reward,
            eval_score=state.get("eval_score", 0.0),
            retry_count=state.get("retry_count", 0),
            max_retries=state.get("max_retries", 1),
            eval_feedback=state.get("eval_feedback", ""),
            executor_error=(state.get("meta") or {}).get("executor_error", ""),
            structure_warnings="\n".join((state.get("meta") or {}).get("structure_warnings") or []),
            test_output=state.get("test_output", ""),
        )
    ).content

    m = _JSON.search(raw or "")
    if m:
        try:
            obj = json.loads(m.group(0))
            decision = str(obj.get("decision", decision)).upper()
            reason = str(obj.get("reason", reason))
        except Exception:
            pass

    allowed = {"REPLAN", "REWRITE_CODE", "STOP"}
    if decision not in allowed:
        bad = decision
        decision = "STOP"
        reason = f"invalid_decision_fallback: {bad}"

    hard_max = int(getattr(settings, "hard_max_retries", 8))
    if retries >= hard_max:
        decision = "STOP"
        reason = "hard_max_retries_exhausted"
    print(f"[rl_agent] decision={decision} reason={reason}")

    return {
        "reward": reward,
        "rl_decision": decision,
        "rl_reason": reason,
        "meta": {
            **(state.get("meta") or {}),
            "prev_eval_score": float(state.get("eval_score") or 0.0),
        },
        "messages": [AIMessage(content=f"[rl_agent] r={reward:.2f} {decision}: {reason}")],
    }