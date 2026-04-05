from __future__ import annotations

import re

from langchain_core.messages import AIMessage

from tools.command_tools import run_command
from states.graph_state import AgentState


def _maven_aggregator_cwd(wrote_files: list[str]) -> str | None:
    """Parent directory of the shallowest */pom.xml (usually the multi-module parent)."""
    poms: list[str] = []
    for f in wrote_files:
        p = str(f).replace("\\", "/")
        if p.endswith("pom.xml"):
            poms.append(p)
    if not poms:
        return None
    best = min(poms, key=lambda x: (x.count("/"), len(x)))
    return best.rsplit("/", 1)[0]


def _normalize_maven_test_cwd(rows: list[dict], wrote_files: list[str]) -> list[dict]:
    """If developer used monorepo root as cwd but POMs live in backend/, point mvn at the real POM."""
    files_norm = [str(x).replace("\\", "/") for x in wrote_files]
    pom_paths = {p for p in files_norm if p.endswith("pom.xml")}
    agg = _maven_aggregator_cwd(files_norm)
    if not agg or not pom_paths:
        return rows
    out: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cmd = str(row.get("cmd") or "")
        if "mvn" not in cmd.lower():
            out.append(dict(row))
            continue
        cwd = str(row.get("cwd") or "").replace("\\", "/").rstrip("/")
        expected = f"{cwd}/pom.xml" if cwd else ""
        if expected in pom_paths:
            out.append(dict(row))
            continue
        fixed = dict(row)
        fixed["cwd"] = agg
        out.append(fixed)
    return out


def _is_server_like(cmd: str) -> bool:
    c = (cmd or "").lower()
    return bool(
        re.search(r"\bnpm\s+run\s+(dev|start|server|serve|watch)\b", c)
        or "react-scripts start" in c
        or "--watch" in c
    )


def tester_node(state: AgentState) -> AgentState:
    print("[tester] running project test commands")
    meta = state.get("meta") or {}
    rows = meta.get("test_commands") or []
    if (not isinstance(rows, list)) or (not rows):
        rows = _infer_test_commands(meta)
    if not isinstance(rows, list) or not rows:
        blob = "no test_commands provided"
        print("[tester] no test_commands provided")
        return {
            "test_output": blob,
            "meta": {**meta, "last_exit_code": 1},
            "messages": [AIMessage(content=f"[tester]\n{blob}")],
        }

    wrote = [str(x).replace("\\", "/") for x in (meta.get("executor_wrote_files") or [])]
    rows = _normalize_maven_test_cwd([dict(r) for r in rows if isinstance(r, dict)], wrote)

    outputs: list[str] = []
    last_exit = 0
    for i, row in enumerate(rows[:12], start=1):
        cwd = row.get("cwd")
        cmd = row.get("cmd")
        if not cmd:
            continue
        cmd_text = str(cmd)
        if _is_server_like(cmd_text):
            res = run_command(
                cmd_text,
                cwd=str(cwd) if cwd else None,
                is_background=True,
            )
            outputs.append(
                f"## [{i}] cwd={res.get('cwd')}\n$ {' '.join(res.get('cmd') or [])}\nexit=0\n"
                "stdout:\n"
                "server-like command started in background\n"
                f"stderr:\n{res.get('stderr')}\n"
            )
            continue

        res = run_command(cmd_text, cwd=str(cwd) if cwd else None, timeout_sec=240, probe_sec=8)
        last_exit = int(res.get("exit_code") or 0)
        outputs.append(
            f"## [{i}] cwd={res.get('cwd')}\n$ {' '.join(res.get('cmd') or [])}\nexit={last_exit}\n"
            f"stdout:\n{(res.get('stdout') or '')[:4000]}\n"
            f"stderr:\n{(res.get('stderr') or '')[:4000]}\n"
        )
        if last_exit != 0:
            break

    blob = "\n".join(outputs).strip()

    # Quality gate: passing build with no real sources/tests is scaffolding, not completion.
    low_signal_markers = [
        "No sources to compile",
        "No tests to run",
        "skip non existing resourceDirectory",
    ]
    if all(m in blob for m in low_signal_markers):
        last_exit = 2
        blob += (
            "\n\n[quality_gate] Build looks like empty scaffold "
            "(no sources/tests). Marking as failed for another iteration."
        )

    print(f"[tester] last_exit_code={last_exit} out_chars={len(blob)}")
    return {
        "test_output": blob[:20000],
        "meta": {
            **meta,
            "last_exit_code": last_exit,
        },
        "messages": [AIMessage(content=f"[tester]\n{blob[:4000]}")],
    }


def _infer_test_commands(meta: dict) -> list[dict]:
    files = [str(x).replace("\\", "/") for x in (meta.get("executor_wrote_files") or [])]
    root = str(meta.get("active_project_root") or meta.get("project_root") or "").strip().replace("\\", "/")
    if not files or not root:
        return []

    has_maven = any(p.endswith("pom.xml") for p in files)
    has_gradle = any(p.endswith(("build.gradle", "build.gradle.kts")) for p in files)
    has_npm = any(p.endswith("package.json") for p in files)
    has_python = any(p.endswith(("requirements.txt", "pyproject.toml")) for p in files)

    cmds: list[dict] = []
    if has_maven:
        mvn_cwd = _maven_aggregator_cwd(files) or root
        cmds.append({"cwd": mvn_cwd, "cmd": "mvn -q test"})
    elif has_gradle:
        cmds.append({"cwd": root, "cmd": "gradlew test"})
    elif has_npm:
        cmds.append({"cwd": root, "cmd": "npm run build"})
    elif has_python:
        cmds.append({"cwd": root, "cmd": "python -m pytest -q"})
    return cmds