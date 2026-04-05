"""
AutoGen AgentChat: true multi-agent round-robin discussion (agents see each other's messages).

Uses OpenAI-compatible API (DeepSeek) via autogen-ext. Falls back is handled in team_panel.py.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from config.settings import settings

# Optional imports — team_panel checks AUTOGEN_AGENTCHAT_AVAILABLE
try:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
    from autogen_agentchat.teams import RoundRobinGroupChat
    from autogen_ext.models.openai import OpenAIChatCompletionClient

    AUTOGEN_AGENTCHAT_AVAILABLE = True
except ImportError:
    AUTOGEN_AGENTCHAT_AVAILABLE = False
    AssistantAgent = Any  # type: ignore
    OpenAIChatCompletionClient = Any  # type: ignore
    RoundRobinGroupChat = Any  # type: ignore
    MaxMessageTermination = Any  # type: ignore
    TextMentionTermination = Any  # type: ignore


def _clip(text: str, max_chars: int) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 24].rstrip() + "\n...[truncated]"


def _task_to_strings(result: Any) -> tuple[str, str]:
    lines: list[str] = []
    moderator_chunks: list[str] = []
    for m in getattr(result, "messages", []) or []:
        src = getattr(m, "source", "?")
        content = getattr(m, "content", "")
        if not isinstance(content, str):
            content = str(content)
        block = f"### {src}\n{content.strip()}"
        lines.append(block)
        if str(src).lower() == "moderator":
            moderator_chunks.append(content.strip())
    transcript = "\n\n".join(lines)
    consensus_raw = moderator_chunks[-1] if moderator_chunks else transcript
    consensus = consensus_raw.replace("CONSENSUS_DONE", "").strip()
    return _clip(consensus, 8000), _clip(transcript, 20000)


async def _run_autogen_async(*, user_task: str, plan: str) -> tuple[str, str]:
    max_msg = int(getattr(settings, "team_autogen_max_messages", 24))
    client = OpenAIChatCompletionClient(
        model=settings.default_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )
    try:
        architect = AssistantAgent(
            "architect",
            model_client=client,
            system_message=(
                "You are the Architect in a live engineering panel. "
                "Focus on structure, boundaries, dependencies, and risks. "
                "Reply concisely (short paragraphs or bullets). "
                "Respond to what Implementer and Critic said in prior turns when relevant."
            ),
        )
        implementer = AssistantAgent(
            "implementer",
            model_client=client,
            system_message=(
                "You are the Implementer. Focus on concrete files, APIs, sequencing, and delivery. "
                "Reply concisely. Build on or challenge Architect and Critic using the thread."
            ),
        )
        critic = AssistantAgent(
            "critic",
            model_client=client,
            system_message=(
                "You are Critic/QA: tests, edge cases, security, operability. "
                "Reply concisely. Reference others' points by role when disagreeing."
            ),
        )
        moderator = AssistantAgent(
            "moderator",
            model_client=client,
            system_message=(
                "You are the Moderator. Synthesize Architect, Implementer, and Critic after each round. "
                "When the approach is stable enough for a developer, output: "
                "(1) agreed approach, (2) decisions, (3) risks, (4) directives for implementation. "
                "End your message with the exact line CONSENSUS_DONE (nothing after it)."
            ),
        )

        team = RoundRobinGroupChat(
            [architect, implementer, critic, moderator],
            termination_condition=(
                TextMentionTermination("CONSENSUS_DONE") | MaxMessageTermination(max_msg)
            ),
        )

        task_body = (
            "Multi-agent panel: discuss this coding task and converge.\n\n"
            f"USER TASK:\n{user_task}\n\n"
            f"PLANNER OUTLINE:\n{plan}\n\n"
            "Rules: Take turns in round-robin order. Be specific. "
            "Resolve disagreements. Moderator must eventually emit CONSENSUS_DONE."
        )

        result = await team.run(task=task_body)
        return _task_to_strings(result)
    finally:
        await client.close()


def run_autogen_team_panel_sync(user_task: str, plan: str) -> tuple[str, str]:
    if not AUTOGEN_AGENTCHAT_AVAILABLE:
        raise ImportError("autogen-agentchat / autogen-ext not installed")

    ut = _clip(user_task, 6000)
    pl = _clip(plan, 10000)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_run_autogen_async(user_task=ut, plan=pl))

    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(asyncio.run, _run_autogen_async(user_task=ut, plan=pl))
        return fut.result()
