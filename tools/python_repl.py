from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


def run_python_code(code: str, *, timeout_sec: int = 20) -> tuple[int, str, str]:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "snippet.py"
        path.write_text(code, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""