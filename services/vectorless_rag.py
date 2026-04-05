"""
Vectorless RAG over the workspace: keyword relevance, directory tree, and readable excerpts.
No embeddings — deterministic ranking so agents get navigable code context.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from config.settings import settings

_STOP = frozenset(
    """
    the and for that this with from have will your what when were been their into than then them
    these those about which while where there other such some more very most also only just like
    make does using used use code file files project app add create build test run all any not
    are but can how new one two get set use out our may way who its now end may did per via
    """.split()
)

_CODE_EXT = frozenset(
    {
        ".py",
        ".java",
        ".kt",
        ".kts",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".ts",
        ".tsx",
        ".json",
        ".xml",
        ".gradle",
        ".properties",
        ".yml",
        ".yaml",
        ".md",
        ".go",
        ".rs",
        ".cs",
        ".php",
        ".rb",
        ".sql",
        ".html",
        ".css",
        ".scss",
        ".vue",
        ".svelte",
    }
)

_SKIP_DIRS = frozenset(
    {
        "node_modules",
        ".git",
        "__pycache__",
        ".idea",
        ".vscode",
        "dist",
        "build",
        "target",
        ".next",
        ".cache",
        "venv",
        ".venv",
        "env",
        ".mypy_cache",
        ".pytest_cache",
        "coverage",
        "htmlcov",
    }
)

_JAVA_DECL = re.compile(
    r"^\s*(?:@\w+(?:\([^)]*\))?\s*)*(?:public|private|protected|internal|open)?\s*"
    r"(?:abstract\s+|static\s+|final\s+|sealed\s+|non-sealed\s+)*"
    r"(?:class|interface|enum|record)\s+[\w$]+",
    re.MULTILINE,
)
_PY_DECL = re.compile(r"^\s*(?:async\s+def|def|class)\s+\w+", re.MULTILINE)


def _tokens(text: str) -> set[str]:
    out: set[str] = set()
    for m in re.finditer(r"[a-zA-Z][a-zA-Z0-9_]{2,}", text or ""):
        w = m.group(0).lower()
        if w not in _STOP:
            out.add(w)
    return out


def _iter_code_files(root: Path, *, max_scan: int) -> list[Path]:
    found: list[Path] = []
    for p in root.rglob("*"):
        if len(found) >= max_scan:
            break
        if not p.is_file():
            continue
        try:
            rel_parts = p.relative_to(root).parts
        except ValueError:
            continue
        if set(rel_parts) & _SKIP_DIRS:
            continue
        if any(part in _SKIP_DIRS for part in rel_parts):
            continue
        suf = p.suffix.lower()
        if suf not in _CODE_EXT and p.name not in {"Dockerfile", "Makefile"}:
            continue
        found.append(p)
    return found


def _read_head(path: Path, limit: int = 8000) -> str:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if "\x00" in raw[:4096]:
        return ""
    return raw[:limit]


def _score_file(rel: str, head: str, query_tokens: set[str]) -> int:
    if not query_tokens:
        return 0
    blob = f"{rel.lower()} {head.lower()}"
    score = 0
    for t in query_tokens:
        if t in blob:
            score += blob.count(t)
    return score


def _extract_signatures(text: str, suffix: str) -> str:
    if suffix == ".java":
        hits = _JAVA_DECL.findall(text[:12000])
        return "\n".join(hits[:40]) if hits else ""
    if suffix == ".py":
        hits = _PY_DECL.findall(text[:12000])
        return "\n".join(hits[:50]) if hits else ""
    return ""


def _format_excerpt(path: Path, root: Path, *, max_lines_full: int = 100, max_body: int = 3500) -> str:
    rel = path.relative_to(root).as_posix()
    suf = path.suffix.lower()
    try:
        full = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return f"## {rel}\n(unreadable)\n"
    if "\x00" in full[:2000]:
        return f"## {rel}\n(binary or minified — skipped)\n"

    lines = full.splitlines()
    sigs = _extract_signatures(full, suf)

    header = f"## {rel}\n"
    if sigs:
        header += "### signatures / entry points (extracted)\n```text\n" + sigs + "\n```\n"

    if len(lines) <= max_lines_full and len(full) <= max_body + 2000:
        lang = "java" if suf == ".java" else "python" if suf == ".py" else "typescript" if suf == ".ts" else ""
        fence = lang or "text"
        return header + f"### full file ({len(lines)} lines)\n```{fence}\n{full.strip()}\n```\n"

    head_lines = lines[: min(55, len(lines))]
    body = "\n".join(head_lines)
    if len(body) > max_body:
        body = body[:max_body] + "\n... [truncated]"
    fence = "java" if suf == ".java" else "python" if suf == ".py" else "text"
    return (
        header
        + f"### first ~{len(head_lines)} lines (file has {len(lines)} lines total)\n"
        f"```{fence}\n{body}\n```\n"
    )


def _build_tree(root: Path, *, max_depth: int = 4, max_lines: int = 120) -> str:
    lines: list[str] = []

    def walk(d: Path, prefix: str, depth: int) -> None:
        if depth > max_depth or len(lines) >= max_lines:
            return
        try:
            children = sorted([x for x in d.iterdir() if x.name not in _SKIP_DIRS], key=lambda x: x.name.lower())
        except OSError:
            return
        for i, ch in enumerate(children):
            if len(lines) >= max_lines:
                break
            last = i == len(children) - 1
            arm = "└── " if last else "├── "
            lines.append(f"{prefix}{arm}{ch.name}" + ("/" if ch.is_dir() else ""))
            if ch.is_dir():
                extension = "    " if last else "│   "
                walk(ch, prefix + extension, depth + 1)

    lines.append(root.name + "/")
    walk(root, "", 0)
    return "\n".join(lines)


def build_vectorless_code_context(
    query: str,
    root: Path | None = None,
    *,
    max_scan: int | None = None,
    top_k: int | None = None,
    max_chars: int | None = None,
) -> str:
    root = root or settings.workspace_root
    max_scan = max_scan if max_scan is not None else int(getattr(settings, "vectorless_rag_max_files_scanned", 4000))
    top_k = top_k if top_k is not None else int(getattr(settings, "vectorless_rag_top_files", 22))
    max_chars = max_chars if max_chars is not None else int(getattr(settings, "vectorless_rag_max_chars", 22000))

    if not root.exists():
        return ""

    q_tokens = _tokens(query)
    files = _iter_code_files(root, max_scan=max_scan)
    if not files:
        return ""

    scored: list[tuple[int, float, Path]] = []
    for p in files:
        rel = p.relative_to(root).as_posix()
        head = _read_head(p)
        sc = _score_file(rel, head, q_tokens)
        try:
            mtime = p.stat().st_mtime
        except OSError:
            mtime = 0.0
        scored.append((sc, mtime, p))

    scored.sort(key=lambda x: (-x[0], -x[1]))
    if q_tokens:
        picked = [p for sc, _mt, p in scored if sc > 0][:top_k]
        if not picked:
            picked = [p for _sc, _mt, p in scored[:top_k]]
    else:
        picked = [p for _sc, _mt, p in scored[:top_k]]

    parts: list[str] = []
    parts.append("### Directory tree (vectorless, depth-limited)\n```text\n" + _build_tree(root) + "\n```\n")
    parts.append(
        "### Ranked source excerpts (keyword overlap with query + recency; no embeddings)\n"
        "Read paths below when editing; signatures help scan large files.\n"
    )

    body = ""
    for p in picked:
        chunk = _format_excerpt(p, root)
        if len(body) + len(chunk) > max_chars:
            break
        body += chunk + "\n"

    parts.append(body)
    out = "\n".join(parts).strip()
    return out[:max_chars]
