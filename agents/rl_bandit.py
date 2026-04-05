from __future__ import annotations

import json
import random
from pathlib import Path


class ContextualBandit:
    """Incremental Q-values per discrete context; epsilon-greedy selection."""

    def __init__(self, path: Path, *, alpha: float = 0.25, epsilon: float = 0.12) -> None:
        self.path = path
        self.alpha = alpha
        self.epsilon = epsilon
        self.q: dict[str, dict[str, float]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
            self.q = data.get("q") or {}
            if not isinstance(self.q, dict):
                self.q = {}
        except (OSError, json.JSONDecodeError):
            self.q = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"q": self.q}, indent=2), encoding="utf-8")

    def update(self, state_key: str, action: str, reward: float) -> None:
        if not state_key or not action:
            return
        bucket = self.q.setdefault(state_key, {})
        old = float(bucket.get(action, 0.0))
        bucket[action] = old + self.alpha * (reward - old)

    def select(self, state_key: str, actions: list[str]) -> str:
        if not actions:
            return "STOP"
        if random.random() < self.epsilon:
            return random.choice(actions)
        qs = self.q.get(state_key, {})
        best_val = max(qs.get(a, 0.0) for a in actions)
        tied = [a for a in actions if qs.get(a, 0.0) == best_val]
        if len(tied) > 1 and "REWRITE_CODE" in tied:
            return "REWRITE_CODE"
        return tied[0]
