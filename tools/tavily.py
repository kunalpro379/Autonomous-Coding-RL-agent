from __future__ import annotations

from typing import Any

from config.settings import settings


def list_tavily_tool(fallback: str) -> list[dict[str, Any]]:
    key = (settings.tavily_api_key or "").strip()
    if not key:
        return [{"title": "tavily_disabled", "content": fallback, "url": ""}]

    # Prefer the new package when available, fall back to legacy tool.
    try:
        from langchain_tavily import TavilySearch  # type: ignore

        tool = TavilySearch(api_key=key, max_results=5)
        raw = tool.invoke({"query": fallback})
    except Exception:
        from langchain_community.tools.tavily_search import TavilySearchResults
        from langchain_community.utilities.tavily_search import TavilySearchAPIWrapper

        tool = TavilySearchResults(
            max_results=5,
            api_wrapper=TavilySearchAPIWrapper(tavily_api_key=key),
        )
        raw = tool.invoke(fallback)

    if isinstance(raw, list):
        return [x if isinstance(x, dict) else {"content": str(x)} for x in raw]
    return [{"content": str(raw)}]


def normalize_tavily_documents(rows: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for i, row in enumerate(rows, start=1):
        title = row.get("title") or row.get("name") or f"hit_{i}"
        url = row.get("url") or ""
        content = row.get("content") or row.get("snippet") or ""
        parts.append(f"[{i}] {title}\nURL: {url}\n{content}\n")
    return "\n".join(parts).strip()