"""Request and response contracts for the chat API."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

_SESSION = re.compile(r"^[A-Za-z0-9-]{8,64}$")


def valid_session_id(value: str) -> bool:
    return _SESSION.fullmatch(value) is not None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Enter a question.")
        return cleaned

    @field_validator("session_id")
    @classmethod
    def check_session(cls, value: str | None) -> str | None:
        if value is None or _SESSION.fullmatch(value):
            return value
        raise ValueError("session_id is not valid.")


class SourceCitation(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    section: str
    excerpt: str
    score: float
    owner: str
    effective: str


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    answer: str
    sources: list[SourceCitation]
    confidence: Literal["high", "medium", "low"]
    refused: bool
    degraded: bool
    disclaimer: str
    model: str
    tools: list[str]
    explain: str
    latency_ms: int


class HistoryMessage(BaseModel):
    message_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: str
    sources: list[SourceCitation] = Field(default_factory=list)
    confidence: str | None = None
    refused: bool = False
    degraded: bool = False
    disclaimer: str | None = None
    model: str | None = None
    tools: list[str] = Field(default_factory=list)
    explain: str | None = None
    feedback_rating: str | None = None


class HistoryResponse(BaseModel):
    session_id: str
    messages: list[HistoryMessage]


class FeedbackRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    message_id: str = Field(min_length=8, max_length=64)
    rating: Literal["up", "down"]
    reason: Literal["incorrect", "incomplete", "outdated", "unclear", "other"] | None = None
    comment: str | None = Field(default=None, max_length=500)

    @field_validator("session_id", "message_id")
    @classmethod
    def check_id(cls, value: str) -> str:
        if not _SESSION.fullmatch(value):
            raise ValueError("id is not valid.")
        return value

    @field_validator("comment")
    @classmethod
    def strip_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class FeedbackResponse(BaseModel):
    status: str
    message_id: str


class HealthResponse(BaseModel):
    status: str
    llm_backend: str
    model: str
    generative: bool
    documents: int
    chunks: int


class GovernanceSummary(BaseModel):
    up: int
    down: int
    reasons: dict[str, int]
