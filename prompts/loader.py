from pathlib import Path


_SHARED_FOR = {"planner", "retriever", "developer", "evaluator"}


def load_prompt(name: str) -> str:
    base = Path(__file__).resolve().parent
    path = base / f"{name}.txt"
    main = path.read_text(encoding="utf-8")
    if name not in _SHARED_FOR:
        return main

    shared_parts: list[str] = []
    for shared_name in ("agent_core", "tools_catalog"):
        shared_path = base / f"{shared_name}.txt"
        if shared_path.exists():
            shared_parts.append(shared_path.read_text(encoding="utf-8"))

    if not shared_parts:
        return main
    return "\n\n".join(shared_parts + [main])