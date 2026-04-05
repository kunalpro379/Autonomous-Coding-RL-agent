from __future__ import annotations

import json

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate

from agents.rl_bandit import ContextualBandit
from config.settings import settings
from LLMs.factory import chat_llm
from prompts.loader import load_prompt
from states.graph_state import AgentState

_ALLOWED_ISSUES = frozenset(
    {"execution_error", "logic_error", "structure_issue", "stagnation", "unclear"}
)


def _extract_json_object(text: str) -> dict | None:
    if not text or not text.strip():
        return None
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i, c in enumerate(text[start:], start):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start : i + 1])
                    return obj if isinstance(obj, dict) else None
                except json.JSONDecodeError:
                    return None
    return None


def _compute_reward(state: AgentState) -> float:
    """Reward from evaluator score (0–10) and change since last RL step—no rule-based penalties."""
    score = float(state.get("eval_score") or 0.0)
    score = max(0.0, min(10.0, score))
    base = score / 10.0
    meta = state.get("meta") or {}
    prev = meta.get("prev_eval_score")
    if isinstance(prev, (int, float)):
        prev_f = float(prev)
        prev_f = max(0.0, min(10.0, prev_f))
        progress = (score - prev_f) / 10.0
        r = base + progress
    else:
        r = base
    return max(-1.0, min(1.0, r))


_PARSE_RETRY_HINT = (
    "Your previous reply was not valid JSON. Reply with ONLY a single JSON object matching the schema "
    "(issue_type, severity, confidence, analysis_summary). No other text."
)


def _normalize_issue(raw: object) -> str:
    s = str(raw or "").strip().lower().replace(" ", "_")
    if s in _ALLOWED_ISSUES:
        return s
    return "unclear"


def _retry_bucket(retries: int) -> str:
    if retries <= 0:
        return "0"
    if retries <= 2:
        return "12"
    return "3p"


def _score_bucket(score: float, min_accept: float) -> str:
    if score < 5.0:
        return "low"
    if score < min_accept:
        return "mid"
    return "ok"


def _build_state_key(diagnosis: dict[str, object], state: AgentState) -> str:
    issue = _normalize_issue(diagnosis.get("issue_type"))
    retries = int(state.get("retry_count") or 0)
    score = float(state.get("eval_score") or 0.0)
    min_accept = float(getattr(settings, "min_accept_score", 7.0))
    rb = _retry_bucket(retries)
    sb = _score_bucket(score, min_accept)
    return f"{issue}|r{rb}|s{sb}"


def _parse_diagnosis_payload(obj: dict) -> dict[str, object] | None:
    try:
        sev = float(obj.get("severity", 0.5) or 0.5)
        conf = float(obj.get("confidence", 0.5) or 0.5)
    except (TypeError, ValueError):
        return None
    summary = str(obj.get("analysis_summary", "")).strip()
    if not summary:
        return None
    return {
        "issue_type": _normalize_issue(obj.get("issue_type")),
        "severity": max(0.0, min(1.0, sev)),
        "confidence": max(0.0, min(1.0, conf)),
        "analysis_summary": summary,
    }


def _llm_diagnosis(state: AgentState, reward: float) -> dict[str, object]:
    """LLM-only diagnosis; retries on parse failure. No heuristic issue classification."""
    llm = chat_llm(temperature=0.0)
    base_system = load_prompt("rl_agent")
    meta = state.get("meta") or {}
    ctx = dict(
        reward=reward,
        eval_score=state.get("eval_score", 0.0),
        retry_count=state.get("retry_count", 0),
        max_retries=state.get("max_retries", 1),
        eval_feedback=state.get("eval_feedback", ""),
        executor_error=meta.get("executor_error", ""),
        structure_warnings="\n".join(meta.get("structure_warnings") or []),
        test_output=state.get("test_output", ""),
    )

    last_text = ""
    for attempt in range(3):
        system = base_system if attempt == 0 else f"{base_system}\n\n{_PARSE_RETRY_HINT}"
        tmpl = ChatPromptTemplate.from_messages([("system", system)])
        raw = llm.invoke(tmpl.format_messages(**ctx)).content
        last_text = raw if isinstance(raw, str) else str(raw or "")
        obj = _extract_json_object(last_text)
        if obj:
            parsed = _parse_diagnosis_payload(obj)
            if parsed:
                return parsed

    return {
        "issue_type": "unclear",
        "severity": 1.0,
        "confidence": 0.0,
        "analysis_summary": (
            "Diagnosis JSON was missing or invalid after retries; last model output (truncated): "
            f"{last_text[:400]}"
        ),
    }


def rl_node(state: AgentState) -> AgentState:
    reward = _compute_reward(state)
    retries = int(state.get("retry_count") or 0)
    max_r = int(state.get("max_retries") or 1)
    score = float(state.get("eval_score") or 0.0)
    min_accept = float(getattr(settings, "min_accept_score", 7.0))
    hard_max = int(getattr(settings, "hard_max_retries", 8))

    bandit_path = settings.workspace_root / ".contextual_bandit_rl.json"
    bandit = ContextualBandit(bandit_path)

    meta = dict(state.get("meta") or {})
    prev_key = meta.get("rl_bandit_state_key")
    prev_action = meta.get("rl_bandit_action")
    if isinstance(prev_key, str) and isinstance(prev_action, str) and prev_action in (
        "REWRITE_CODE",
        "REPLAN",
    ):
        bandit.update(prev_key, prev_action, reward)

    print(f"[rl_agent] retries={retries}/{max_r} score={score} reward={reward:.2f}")

    try:
        diagnosis = _llm_diagnosis(state, reward)
    except Exception as e:
        diagnosis = {
            "issue_type": "unclear",
            "severity": 1.0,
            "confidence": 0.0,
            "analysis_summary": f"Diagnosis LLM call failed: {e!s}",
        }

    state_key = _build_state_key(diagnosis, state)

    decision: str
    reason: str
    summary = str(diagnosis.get("analysis_summary", ""))

    if score >= min_accept:
        decision = "STOP"
        reason = "meets_acceptance_threshold"
        meta.pop("rl_bandit_state_key", None)
        meta.pop("rl_bandit_action", None)
    elif retries >= hard_max:
        decision = "STOP"
        reason = "hard_max_retries_exhausted"
        meta.pop("rl_bandit_state_key", None)
        meta.pop("rl_bandit_action", None)
    elif retries >= max_r:
        # Soft cap: prefer replanning, but still let bandit learn from prior transitions.
        decision = "REPLAN"
        reason = f"soft_max_retries_reached; context={state_key}; {summary}"
        meta["rl_bandit_state_key"] = state_key
        meta["rl_bandit_action"] = decision
    else:
        decision = bandit.select(state_key, ["REWRITE_CODE", "REPLAN"])
        q_rewrite = bandit.q.get(state_key, {}).get("REWRITE_CODE", 0.0)
        q_replan = bandit.q.get(state_key, {}).get("REPLAN", 0.0)
        reason = (
            f"contextual_bandit Q(rw={q_rewrite:.3f},rp={q_replan:.3f}) -> {decision}; "
            f"{state_key}; {summary}"
        )
        meta["rl_bandit_state_key"] = state_key
        meta["rl_bandit_action"] = decision

    bandit.save()

    meta["rl_diagnosis"] = diagnosis
    meta["prev_eval_score"] = score

    print(f"[rl_agent] decision={decision} reason={reason}")

    return {
        "reward": reward,
        "rl_decision": decision,
        "rl_reason": reason,
        "meta": meta,
        "messages": [
            AIMessage(
                content=(
                    f"[rl_agent] r={reward:.2f} {decision}: {reason}\n"
                    f"diagnosis={diagnosis.get('issue_type')} "
                    f"sev={diagnosis.get('severity')} conf={diagnosis.get('confidence')}"
                )
            )
        ],
    }
