from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI

from config.settings import settings
from LLMs.factory import chat_llm
from prompts.loader import load_prompt
from states.graph_state import AgentState

_SPECIALISTS: tuple[tuple[str, str, str], ...] = (
    ("architect", "Architect", "System structure, module boundaries, dependencies, and technical risks."),
    ("implementer", "Implementer", "Concrete sequencing, files, APIs, and how to ship."),
    ("critic", "Critic / QA", "Tests, edge cases, failure modes, security, and operability."),
)


def _clip(text: str, max_chars: int) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 24].rstrip() + "\n...[truncated]"


def _msg_content(msg: Any) -> str:
    if msg is None:
        return ""
    c = getattr(msg, "content", msg)
    return c if isinstance(c, str) else str(c or "")


async def _opening_one(
    llm: ChatOpenAI,
    *,
    role_title: str,
    role_mission: str,
    user_task: str,
    plan: str,
) -> str:
    body = load_prompt("team_specialist_opening").format(
        role_title=role_title,
        role_mission=role_mission,
        user_task=user_task,
        plan=plan,
    )
    out = await llm.ainvoke([HumanMessage(content=body)])
    return _clip(_msg_content(out), 4000)


async def _reply_one(
    llm: ChatOpenAI,
    *,
    role_title: str,
    role_mission: str,
    user_task: str,
    peers_block: str,
) -> str:
    body = load_prompt("team_specialist_reply").format(
        role_title=role_title,
        role_mission=role_mission,
        user_task=user_task,
        peers_block=peers_block,
    )
    out = await llm.ainvoke([HumanMessage(content=body)])
    return _clip(_msg_content(out), 4000)


async def _moderate(
    llm: ChatOpenAI,
    *,
    user_task: str,
    plan: str,
    round_open: str,
    round_discuss: str,
) -> str:
    body = load_prompt("team_moderator").format(
        user_task=user_task,
        plan=plan,
        round_open=round_open,
        round_discuss=round_discuss,
    )
    out = await llm.ainvoke([HumanMessage(content=body)])
    return _clip(_msg_content(out), 8000)


async def _run_panel_async(state: AgentState) -> tuple[str, str]:
    llm = chat_llm(temperature=0.35)
    user_task = _clip(state.get("user_task", ""), 6000)
    plan = _clip(state.get("plan", ""), 10000)

    openings = await asyncio.gather(
        *[
            _opening_one(
                llm,
                role_title=title,
                role_mission=mission,
                user_task=user_task,
                plan=plan,
            )
            for _sid, title, mission in _SPECIALISTS
        ]
    )

    peer_lines: list[str] = []
    for (_sid, title, _mission), text in zip(_SPECIALISTS, openings):
        peer_lines.append(f"### {title}\n{text}")
    peers_block = "\n\n".join(peer_lines)

    replies = await asyncio.gather(
        *[
            _reply_one(
                llm,
                role_title=title,
                role_mission=mission,
                user_task=user_task,
                peers_block=peers_block,
            )
            for _sid, title, mission in _SPECIALISTS
        ]
    )

    open_doc = peers_block
    discuss_lines = [
        f"### {title}\n{txt}" for (_sid, title, _mission), txt in zip(_SPECIALISTS, replies)
    ]
    discuss_doc = "\n\n".join(discuss_lines)

    consensus = await _moderate(
        chat_llm(temperature=0.15),
        user_task=user_task,
        plan=plan,
        round_open=open_doc,
        round_discuss=discuss_doc,
    )

    transcript = (
        "=== Opening (parallel) ===\n"
        + open_doc
        + "\n\n=== Discussion (parallel replies) ===\n"
        + discuss_doc
        + "\n\n=== Moderator consensus ===\n"
        + consensus
    )
    return _clip(consensus, 8000), _clip(transcript, 16000)


def team_panel_node(state: AgentState) -> AgentState:
    if not getattr(settings, "team_panel_enabled", True):
        return {
            "team_consensus": "",
            "team_transcript": "",
            "messages": [AIMessage(content="[team_panel] skipped (team_panel_enabled=false)")],
        }

    use_autogen = getattr(settings, "team_use_autogen", True)
    if use_autogen:
        try:
            from agents.autogen_team_panel import AUTOGEN_AGENTCHAT_AVAILABLE, run_autogen_team_panel_sync

            if AUTOGEN_AGENTCHAT_AVAILABLE:
                print(
                    "[team_panel] AutoGen RoundRobinGroupChat — agents take turns and see the full discussion"
                )
                consensus, transcript = run_autogen_team_panel_sync(
                    str(state.get("user_task", "")),
                    str(state.get("plan", "")),
                )
                print(f"[team_panel] consensus_chars={len(consensus)} transcript_chars={len(transcript)}")
                return {
                    "team_consensus": consensus,
                    "team_transcript": transcript,
                    "messages": [
                        AIMessage(
                            content=_clip(f"[team_panel:autogen]\n{consensus}", 6000),
                        )
                    ],
                }
        except Exception as e:
            print(f"[team_panel] AutoGen failed ({e!r}), falling back to LangChain panel")

    print("[team_panel] LangChain parallel specialists + discussion + moderator (fallback)")
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        consensus, transcript = _run_panel_sync_fallback(state)
    else:
        consensus, transcript = asyncio.run(_run_panel_async(state))
    print(f"[team_panel] consensus_chars={len(consensus)} transcript_chars={len(transcript)}")
    return {
        "team_consensus": consensus,
        "team_transcript": transcript,
        "messages": [
            AIMessage(
                content=_clip(f"[team_panel]\n{consensus}", 6000),
            )
        ],
    }


def _run_panel_sync_fallback(state: AgentState) -> tuple[str, str]:
    llm = chat_llm(temperature=0.35)
    user_task = _clip(state.get("user_task", ""), 6000)
    plan = _clip(state.get("plan", ""), 10000)
    openings: list[str] = []
    for _sid, title, mission in _SPECIALISTS:
        body = load_prompt("team_specialist_opening").format(
            role_title=title,
            role_mission=mission,
            user_task=user_task,
            plan=plan,
        )
        out = llm.invoke([HumanMessage(content=body)])
        openings.append(_clip(_msg_content(out), 4000))

    peer_lines = [
        f"### {title}\n{text}"
        for (_sid, title, _mission), text in zip(_SPECIALISTS, openings)
    ]
    peers_block = "\n\n".join(peer_lines)

    replies: list[str] = []
    for _sid, title, mission in _SPECIALISTS:
        body = load_prompt("team_specialist_reply").format(
            role_title=title,
            role_mission=mission,
            user_task=user_task,
            peers_block=peers_block,
        )
        out = llm.invoke([HumanMessage(content=body)])
        replies.append(_clip(_msg_content(out), 4000))

    open_doc = peers_block
    discuss_doc = "\n\n".join(
        f"### {title}\n{txt}" for (_sid, title, _mission), txt in zip(_SPECIALISTS, replies)
    )
    mod_llm = chat_llm(temperature=0.15)
    body = load_prompt("team_moderator").format(
        user_task=user_task,
        plan=plan,
        round_open=open_doc,
        round_discuss=discuss_doc,
    )
    consensus = _clip(_msg_content(mod_llm.invoke([HumanMessage(content=body)])), 8000)
    transcript = _clip(
        "=== Opening ===\n"
        + open_doc
        + "\n\n=== Discussion ===\n"
        + discuss_doc
        + "\n\n=== Moderator consensus ===\n"
        + consensus,
        16000,
    )
    return consensus, transcript
