from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import AIMessage

from LLMs.factory import chat_llm
from tools.command_tools import run_command
from tools.file_tools import FileTools
from states.graph_state import AgentState


_JSON = re.compile(r"\{.*\}", re.DOTALL)


def _parse_build_plan(raw: str) -> dict[str, Any]:
    raw = (raw or "").strip()
    # Strip markdown fences if model accidentally adds them.
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    m = _JSON.search(raw)
    if m:
        raw = m.group(0)
    try:
        return json.loads(raw)
    except Exception:
        cleaned = _clean_json_like(raw)
        try:
            return json.loads(cleaned)
        except Exception:
            repaired = _repair_json_with_llm(raw)
            return json.loads(repaired)


def _clean_json_like(text: str) -> str:
    # Remove JS-style comments and trailing commas.
    t = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
    t = re.sub(r"/\*.*?\*/", "", t, flags=re.DOTALL)
    t = re.sub(r",\s*([}\]])", r"\1", t)
    return t.strip()


def _repair_json_with_llm(raw: str) -> str:
    llm = chat_llm(temperature=0.0)
    prompt = (
        "Repair the following content into STRICT valid JSON only.\n"
        "Do not add markdown. Do not add commentary.\n"
        "Keep keys and values semantically equivalent.\n\n"
        "CONTENT START\n"
        f"{raw}\n"
        "CONTENT END"
    )
    out = llm.invoke(prompt).content
    out = (out or "").strip()
    if out.startswith("```"):
        out = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", out)
        out = re.sub(r"\s*```$", "", out)
    m = _JSON.search(out)
    return m.group(0) if m else out


def executor_node(state: AgentState) -> AgentState:
    """
    Apply developer's build plan:
    - write files into sandbox workspace
    - run declared commands (install/build)
    """
    print("[executor] applying build plan (write files + run commands)")

    build_raw = state.get("code", "") or ""
    try:
        plan = _parse_build_plan(build_raw)
    except Exception as e:
        msg = f"[executor_error] invalid_json: {e}"
        print(msg)
        return {
            "meta": {**(state.get("meta") or {}), "executor_error": msg},
            "messages": [AIMessage(content=msg)],
        }

    meta = dict(state.get("meta") or {})
    active_root = str(meta.get("active_project_root") or "").strip()
    plan = _lock_and_normalize_plan(plan, active_root=active_root)
    locked_root = str(plan.get("project_root") or "").strip()
    if not active_root and locked_root:
        active_root = locked_root

    ft = FileTools()
    files = plan.get("files") or []
    edits = plan.get("edits") or []
    wrote: list[str] = []
    edited: list[str] = []

    # Apply targeted edits first (read + modify existing files).
    for e in edits:
        if not isinstance(e, dict):
            continue
        path = str(e.get("path") or "")
        action = str(e.get("action") or "").strip().lower()
        if not path or not action:
            continue
        try:
            current = ft.read_file(path)
        except Exception:
            current = ""

        if action == "replace_text":
            old_text = str(e.get("old_text") or "")
            new_text = str(e.get("new_text") or "")
            if old_text and (old_text in current):
                ft.write_file(path, current.replace(old_text, new_text, 1))
                edited.append(path)
            elif new_text and not current:
                # file missing: create with new_text to avoid dead-ends
                ft.write_file(path, new_text)
                edited.append(path)
        elif action == "append":
            new_text = str(e.get("new_text") or "")
            if new_text:
                updated = current + ("" if current.endswith("\n") or not current else "\n") + new_text
                ft.write_file(path, updated)
                edited.append(path)
        elif action == "overwrite":
            new_text = str(e.get("new_text") or "")
            ft.write_file(path, new_text)
            edited.append(path)
    for f in files:
        path = str(f.get("path") or "")
        content = _materialize_content(f)
        if not path:
            continue
        ft.write_file(path, content)
        wrote.append(path)

    cmd_rows = plan.get("commands") or []
    cmd_out: list[dict[str, Any]] = []
    for row in cmd_rows:
        cwd = row.get("cwd")
        cmd = row.get("cmd")
        if not cmd:
            continue
        cmd_out.append(run_command(str(cmd), cwd=str(cwd) if cwd else None, timeout_sec=600))

    structure_warnings = _validate_structure(state.get("user_task", ""), wrote, str(plan.get("project_root") or ""))
    meta["project_root"] = plan.get("project_root")
    meta["active_project_root"] = active_root or plan.get("project_root")
    meta["executor_wrote_files"] = wrote[:200]
    meta["executor_edited_files"] = edited[:200]
    meta["executor_commands"] = cmd_out[-10:]
    meta["test_commands"] = plan.get("test_commands") or []
    meta["structure_warnings"] = structure_warnings

    if structure_warnings:
        print(f"[executor] structure_warnings={len(structure_warnings)}")

    return {
        "meta": meta,
        "messages": [
            AIMessage(
                content=f"[executor] edited_files={len(edited)} wrote_files={len(wrote)} commands_ran={len(cmd_out)}"
            )
        ],
    }


def _lock_and_normalize_plan(plan: dict[str, Any], *, active_root: str) -> dict[str, Any]:
    out = dict(plan)
    plan_root = str(out.get("project_root") or "").strip().strip("/\\")
    root = active_root.strip().strip("/\\") or plan_root
    out["project_root"] = root

    def normalize_path(path: str) -> str:
        p = (path or "").replace("\\", "/").strip().strip("/")
        if not p:
            return p
        if not root:
            return p
        if active_root and plan_root and p.startswith(plan_root + "/"):
            p = root + p[len(plan_root) :]
        elif not p.startswith(root + "/") and p != root:
            p = f"{root}/{p}"
        return p

    files = out.get("files") or []
    for f in files:
        if isinstance(f, dict):
            f["path"] = normalize_path(str(f.get("path") or ""))
    out["files"] = files

    for key in ("commands", "test_commands"):
        rows = out.get(key) or []
        fixed: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            cwd = str(row.get("cwd") or "").replace("\\", "/").strip().strip("/")
            if root:
                if active_root and plan_root and cwd.startswith(plan_root + "/"):
                    cwd = root + cwd[len(plan_root) :]
                elif cwd and not cwd.startswith(root + "/") and cwd != root:
                    cwd = f"{root}/{cwd}"
                elif not cwd:
                    cwd = root
            row["cwd"] = cwd
            fixed.append(row)
        out[key] = fixed

    return out


def _materialize_content(file_obj: dict[str, Any]) -> str:
    """
    Supports either:
    - {"content": "..."} (string)
    - {"content_lines": ["line1", "line2", ...]} (preferred for large files)
    """
    if "content_lines" in file_obj and isinstance(file_obj.get("content_lines"), list):
        lines = [str(x) for x in (file_obj.get("content_lines") or [])]
        return "\n".join(lines) + ("\n" if lines else "")
    return str(file_obj.get("content") or "")


def _validate_structure(user_task: str, wrote: list[str], project_root: str) -> list[str]:
    roots = project_root.strip("/\\")
    wrote_norm = {p.replace("\\", "/") for p in wrote}
    warnings: list[str] = []

    # Generic professional baseline (stack-agnostic).
    if roots and f"{roots}/README.md" not in wrote_norm:
        warnings.append(f"missing_recommended_file:{roots}/README.md")
    if roots and f"{roots}/.gitignore" not in wrote_norm:
        warnings.append(f"missing_recommended_file:{roots}/.gitignore")

    # At least one implementation source file should be present.
    source_ext = (
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".java",
        ".go",
        ".rs",
        ".cs",
        ".rb",
        ".php",
    )
    has_source = any(p.endswith(source_ext) for p in wrote_norm)
    if not has_source:
        warnings.append("missing_core_source_files")

    # If user asked for a complete app, require config/build metadata.
    task = (user_task or "").lower()
    if any(k in task for k in ("complete", "from scratch", "full", "application", "app")):
        has_build_file = any(
            p.endswith(("package.json", "pom.xml", "build.gradle", "requirements.txt", "pyproject.toml", "Cargo.toml", "go.mod"))
            for p in wrote_norm
        )
        if not has_build_file:
            warnings.append("missing_build_or_dependency_manifest")

    return warnings

