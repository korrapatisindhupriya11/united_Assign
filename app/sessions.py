"""In-memory chat sessions. A restart clears them; that is documented."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Turn:
    message_id: str
    role: str
    content: str
    created_at: str
    sources: list[dict] = field(default_factory=list)
    confidence: str | None = None
    refused: bool = False
    degraded: bool = False
    disclaimer: str | None = None
    model: str | None = None
    tools: list[str] = field(default_factory=list)
    explain: str | None = None
    feedback_rating: str | None = None


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, list[Turn]] = {}
        self._lock = threading.Lock()

    def get_or_create(self, session_id: str | None) -> str:
        with self._lock:
            if session_id:
                self._sessions.setdefault(session_id, [])
                return session_id
            new_id = str(uuid.uuid4())
            self._sessions[new_id] = []
            return new_id

    def append(self, session_id: str, turn: Turn) -> None:
        with self._lock:
            self._sessions.setdefault(session_id, []).append(turn)

    def history(self, session_id: str) -> list[Turn]:
        with self._lock:
            return list(self._sessions.get(session_id, []))

    def contains(self, session_id: str) -> bool:
        with self._lock:
            return session_id in self._sessions

    def clear(self, session_id: str) -> bool:
        with self._lock:
            if session_id not in self._sessions:
                return False
            del self._sessions[session_id]
            return True

    def find(self, session_id: str, message_id: str) -> Turn | None:
        with self._lock:
            for turn in self._sessions.get(session_id, []):
                if turn.message_id == message_id:
                    return turn
        return None

    def set_feedback(self, session_id: str, message_id: str, rating: str) -> bool:
        with self._lock:
            for turn in self._sessions.get(session_id, []):
                if turn.message_id == message_id and turn.role == "assistant":
                    turn.feedback_rating = rating
                    return True
        return False
