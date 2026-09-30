"""Local audit and feedback logs for the responsible-AI controls."""

from __future__ import annotations

import json
import threading
from pathlib import Path


class GovernanceLog:
    def __init__(self, feedback_path: Path, audit_path: Path) -> None:
        self.feedback_path = feedback_path
        self.audit_path = audit_path
        self._lock = threading.Lock()

    def audit(self, record: dict) -> None:
        self._append(self.audit_path, record)

    def feedback(self, record: dict) -> None:
        self._append(self.feedback_path, record)

    def feedback_summary(self) -> dict:
        ratings = {"up": 0, "down": 0}
        reasons: dict[str, int] = {}
        if not self.feedback_path.exists():
            return {"up": 0, "down": 0, "reasons": reasons}
        for record in self._read(self.feedback_path):
            rating = record.get("rating")
            if rating in ratings:
                ratings[rating] += 1
            reason = record.get("reason")
            if reason:
                reasons[reason] = reasons.get(reason, 0) + 1
        return {"up": ratings["up"], "down": ratings["down"], "reasons": reasons}

    def _append(self, path: Path, record: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False)
        with self._lock:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def _read(self, path: Path) -> list[dict]:
        rows: list[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rows.append(json.loads(line))
        return rows
