from __future__ import annotations

import os
import re
import shlex
import subprocess
import time
from typing import Any
from typing import Sequence

from config.settings import settings


def _shell_cmd(parts: Sequence[str] | str) -> list[str]:
    if isinstance(parts, str):
        return shlex.split(parts)
    return list(parts)


def _looks_long_running(cmd_text: str) -> bool:
    c = (cmd_text or "").lower()
    if re.search(r"\bnpm\s+run\s+(dev|start|server|serve|watch)\b", c):
        return True
    if re.search(r"\b(yarn|pnpm)\s+(dev|start|serve|watch)\b", c):
        return True
    if re.search(r"\bnode\s+.*(server|index)\.js\b", c):
        return True
    markers = [
        "npm start",
        "npm run dev",
        "npm run start",
        "npm run server",
        "npm run watch",
        "vite",
        "next dev",
        "nodemon",
        "react-scripts start",
        "uvicorn",
        "flask run",
        "python -m http.server",
        "--watch",
    ]
    return any(m in c for m in markers)


def run_command(
    cmd: str | Sequence[str],
    *,
    timeout_sec: int = 60,
    cwd: str | None = None,
    probe_sec: int = 12,
    is_background: bool = False,
) -> dict[str, Any]:
    """
    Run a shell command inside the workspace sandbox.

    Returns JSON-serializable dict:
    {
      "cmd": [...],
      "cwd": "...",
      "exit_code": int,
      "stdout": str,
      "stderr": str,
    }
    """
    workdir = settings.workspace_root if cwd is None else settings.workspace_root / cwd
    workdir.mkdir(parents=True, exist_ok=True)

    # On Windows, many CLIs (npm/npx) are resolved via cmd.exe and .cmd shims.
    # Use cmd.exe /c so commands resolve consistently.
    # Build display string once for long-running detection.
    if isinstance(cmd, str):
        cmd_text = cmd
    else:
        cmd_text = " ".join(_shell_cmd(cmd))

    is_long = _looks_long_running(cmd_text)

    try:
        if os.name == "nt":
            if is_background:
                full_cmd = ["cmd.exe", "/c", cmd_text]
                proc = subprocess.Popen(
                    full_cmd,
                    cwd=str(workdir),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
                return {
                    "cmd": full_cmd,
                    "cwd": str(workdir),
                    "exit_code": 0,
                    "stdout": "",
                    "stderr": f"[background] started pid={proc.pid}",
                    "pid": proc.pid,
                }
            if is_long:
                full_cmd = ["cmd.exe", "/c", cmd_text]
                proc = subprocess.Popen(
                    full_cmd,
                    cwd=str(workdir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                started = time.time()
                # Probe for a short time, then terminate to avoid hanging forever.
                while True:
                    if proc.poll() is not None:
                        out, err = proc.communicate()
                        return {
                            "cmd": full_cmd,
                            "cwd": str(workdir),
                            "exit_code": proc.returncode,
                            "stdout": out or "",
                            "stderr": err or "",
                        }
                    if time.time() - started >= probe_sec:
                        proc.terminate()
                        try:
                            out, err = proc.communicate(timeout=5)
                        except Exception:
                            proc.kill()
                            out, err = proc.communicate()
                        return {
                            "cmd": full_cmd,
                            "cwd": str(workdir),
                            "exit_code": 0,
                            "stdout": (out or "")[:4000],
                            "stderr": (err or "")[:4000]
                            + "\n[info] long-running command auto-stopped after probe",
                        }
                    time.sleep(0.5)
            elif isinstance(cmd, str):
                proc = subprocess.run(
                    ["cmd.exe", "/c", cmd],
                    cwd=str(workdir),
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec,
                )
                cmd_repr = ["cmd.exe", "/c", cmd]
            else:
                args = _shell_cmd(cmd)
                proc = subprocess.run(
                    ["cmd.exe", "/c", " ".join(args)],
                    cwd=str(workdir),
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec,
                )
                cmd_repr = ["cmd.exe", "/c", " ".join(args)]
        else:
            if is_background:
                args = _shell_cmd(cmd)
                proc = subprocess.Popen(
                    args,
                    cwd=str(workdir),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
                return {
                    "cmd": args,
                    "cwd": str(workdir),
                    "exit_code": 0,
                    "stdout": "",
                    "stderr": f"[background] started pid={proc.pid}",
                    "pid": proc.pid,
                }
            args = _shell_cmd(cmd)
            proc = subprocess.run(
                args,
                cwd=str(workdir),
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
            cmd_repr = args

        return {
            "cmd": cmd_repr,
            "cwd": str(workdir),
            "exit_code": proc.returncode,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
        }
    except subprocess.TimeoutExpired as e:
        # Convert timeout to a normal result so the graph can continue.
        return {
            "cmd": [str(cmd)],
            "cwd": str(workdir),
            "exit_code": 124,
            "stdout": (e.stdout or "")[:4000] if isinstance(e.stdout, str) else "",
            "stderr": ((e.stderr or "")[:4000] if isinstance(e.stderr, str) else "")
            + "\n[timeout] command exceeded timeout and was stopped",
        }
    except FileNotFoundError as e:
        # Make missing CLIs visible without crashing the graph.
        return {
            "cmd": [str(cmd)],
            "cwd": str(workdir),
            "exit_code": 127,
            "stdout": "",
            "stderr": f"[command_not_found] {e}",
        }

