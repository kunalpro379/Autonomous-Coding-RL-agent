from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from config.settings import settings
from services.vector_store import VectorStoreService
from tools.scrape_url import scrape_url_to_text
from tools.tavily import list_tavily_tool, normalize_tavily_documents


class RetrievalService:
    def __init__(self, store: VectorStoreService | None = None) -> None:
        self.store = store or VectorStoreService()

    def build_context(self, user_task: str) -> str:
        chunks: list[str] = []

        if _should_use_local_context(user_task):
            local_ctx = _collect_local_codebase_context(settings.workspace_root)
            if local_ctx.strip():
                chunks.append("### Existing local codebase\n" + local_ctx)

        vtxt = self.store.query(user_task, k=4)
        if vtxt.strip():
            chunks.append("### VectorDB hits\n" + vtxt)

        tavily_hits = list_tavily_tool(user_task)
        chunks.append("### Tavily\n" + normalize_tavily_documents(tavily_hits))

        url = _guess_url(user_task)
        if url:
            chunks.append("### Scraped page\n" + scrape_url_to_text(url))

        return "\n\n".join(chunks).strip()


def _guess_url(task: str) -> str | None:
    for token in task.split():
        if token.startswith("http://") or token.startswith("https://"):
            try:
                urlparse(token)
                return token.strip(").,;]}>'\"")
            except Exception:
                return None
    return None


def _should_use_local_context(task: str) -> bool:
    t = (task or "").lower()
    hints = [
        "existing project",
        "existing code",
        "already written",
        "current project",
        "this project",
        "codebase",
        "folder",
        "file",
        "refactor",
        "fix bug",
        "update",
        "modify",
    ]
    return any(h in t for h in hints)


def _collect_local_codebase_context(root: Path, *, max_files: int = 20, max_chars: int = 10000) -> str:
    if not root.exists():
        return ""

    allowed_ext = {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".json",
        ".md",
        ".yml",
        ".yaml",
    }
    ignore_dirs = {"node_modules", ".git", "__pycache__", "dist", "build", ".next", ".cache"}

    paths: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in allowed_ext:
            continue
        rel_parts = set(p.relative_to(root).parts)
        if rel_parts & ignore_dirs:
            continue
        paths.append(p)

    # Newer files first usually reflect active work.
    paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    picked = paths[:max_files]

    lines: list[str] = ["Project tree (sample):"]
    for p in picked:
        lines.append(f"- {p.relative_to(root).as_posix()}")

    lines.append("\nKey file snippets:")
    for p in picked[:8]:
        rel = p.relative_to(root).as_posix()
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        snippet = text[:900].strip()
        if not snippet:
            continue
        lines.append(f"\n## {rel}\n{snippet}")
        if sum(len(x) for x in lines) > max_chars:
            break

    out = "\n".join(lines)
    return out[:max_chars]