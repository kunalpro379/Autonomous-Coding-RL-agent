from __future__ import annotations

import uuid

from dotenv import load_dotenv

from config.settings import settings
# Keep direct import from the actual folder name in this project.
from orchastration.graph import build_graph
from services.vector_store import VectorStoreService


def seed_kb_example() -> None:
    store = VectorStoreService()
    # Optional: seed documentation snippets you want the Developer to reuse
    store.add_texts(
        [
            "Project convention: prefer pathlib over os.path.",
            "Testing: keep print outputs short; avoid interactive input.",
        ],
        metadatas=[{"source": "conventions"}] * 2,
    )


def main() -> None:
    load_dotenv()

    settings.workspace_root.mkdir(parents=True, exist_ok=True)
    settings.chroma_path.mkdir(parents=True, exist_ok=True)

    # seed_kb_example()

    graph = build_graph()
    thread_id = str(uuid.uuid4())

    task = input("Describe the coding task:\n> ").strip()
    initial = {
        "user_task": task,
        "retry_count": 0,
        "max_retries": settings.max_retries,
        "meta": {"dev_loop_count": 0},
    }

    result = graph.invoke(
        initial,
        config={
            "configurable": {"thread_id": thread_id},
            # Allow enough steps for (planner->...->rl) * retries.
            "recursion_limit": max(60, int(settings.max_retries) * 12),
        },
    )

    print("\n=== FINAL ===")
    print("score:", result.get("eval_score"))
    print("decision:", result.get("rl_decision"))
    print("\n--- code ---\n", result.get("code"))
    print("\n--- tests ---\n", result.get("test_output"))


if __name__ == "__main__":
    main()