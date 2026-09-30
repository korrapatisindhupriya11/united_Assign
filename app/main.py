"""FastAPI application for Harborline Guide."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import Settings, get_settings
from app.llm import ExtractiveGenerator
from app.orchestrator import Orchestrator
from app.schemas import (
    ChatRequest,
    ChatResponse,
    FeedbackRequest,
    FeedbackResponse,
    GovernanceSummary,
    HealthResponse,
    HistoryMessage,
    HistoryResponse,
    SourceCitation,
    valid_session_id,
)
from app.sessions import utc_now

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def create_app(
    settings: Settings | None = None,
    orchestrator: Orchestrator | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    orchestrator = orchestrator or Orchestrator.from_settings(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        guide = app.state.orchestrator
        logger.info(
            "Harborline Guide ready (%s chunks, model=%s)",
            len(guide.index.chunks),
            getattr(guide.generator, "model_name", "unknown"),
        )
        yield

    app = FastAPI(
        title="Harborline Guide",
        version=__version__,
        summary="Internal handbook copilot grounded in published policy text.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.orchestrator = orchestrator

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        guide: Orchestrator = app.state.orchestrator
        generative = not isinstance(guide.generator, ExtractiveGenerator)
        return HealthResponse(
            status="ok",
            llm_backend=guide.settings.llm_backend,
            model=getattr(guide.generator, "model_name", "unknown"),
            generative=generative,
            documents=len(guide.index.documents),
            chunks=len(guide.index.chunks),
        )

    @app.post("/api/chat", response_model=ChatResponse)
    def chat(body: ChatRequest) -> ChatResponse:
        guide: Orchestrator = app.state.orchestrator
        result = guide.chat(body.session_id, body.message)
        return ChatResponse(
            session_id=result.session_id,
            message_id=result.message_id,
            answer=result.answer,
            sources=[SourceCitation(**source) for source in result.sources],
            confidence=result.confidence,  # type: ignore[arg-type]
            refused=result.refused,
            degraded=result.degraded,
            disclaimer=result.disclaimer,
            model=result.model,
            tools=result.tools,
            explain=result.explain,
            latency_ms=result.latency_ms,
        )

    @app.get("/api/sessions/{session_id}", response_model=HistoryResponse)
    def history(session_id: str) -> HistoryResponse:
        if not valid_session_id(session_id):
            raise HTTPException(status_code=422, detail="session_id is not valid.")
        guide: Orchestrator = app.state.orchestrator
        if not guide.sessions.contains(session_id):
            raise HTTPException(status_code=404, detail="That conversation was not found.")
        messages = [
            HistoryMessage(
                message_id=turn.message_id,
                role=turn.role,  # type: ignore[arg-type]
                content=turn.content,
                created_at=turn.created_at,
                sources=[SourceCitation(**source) for source in turn.sources],
                confidence=turn.confidence,
                refused=turn.refused,
                degraded=turn.degraded,
                disclaimer=turn.disclaimer,
                model=turn.model,
                tools=turn.tools,
                explain=turn.explain,
                feedback_rating=turn.feedback_rating,
            )
            for turn in guide.sessions.history(session_id)
        ]
        return HistoryResponse(session_id=session_id, messages=messages)

    @app.delete("/api/sessions/{session_id}", status_code=204)
    def clear_session(session_id: str) -> None:
        if not valid_session_id(session_id):
            raise HTTPException(status_code=422, detail="session_id is not valid.")
        guide: Orchestrator = app.state.orchestrator
        if not guide.sessions.clear(session_id):
            raise HTTPException(status_code=404, detail="That conversation was not found.")

    @app.post("/api/feedback", response_model=FeedbackResponse)
    def feedback(body: FeedbackRequest) -> FeedbackResponse:
        guide: Orchestrator = app.state.orchestrator
        if not guide.sessions.set_feedback(body.session_id, body.message_id, body.rating):
            raise HTTPException(status_code=404, detail="That answer was not found in the conversation.")
        question = ""
        for turn in guide.sessions.history(body.session_id):
            if turn.role == "user":
                question = turn.content
            if turn.message_id == body.message_id:
                break
        guide.governance.feedback(
            {
                "timestamp": utc_now(),
                "session_id": body.session_id,
                "message_id": body.message_id,
                "rating": body.rating,
                "reason": body.reason,
                "comment": body.comment,
                "question": question,
            }
        )
        return FeedbackResponse(status="saved", message_id=body.message_id)

    @app.get("/api/governance/summary", response_model=GovernanceSummary)
    def governance_summary() -> GovernanceSummary:
        guide: Orchestrator = app.state.orchestrator
        return GovernanceSummary(**guide.governance.feedback_summary())

    @app.get("/")
    def index(request: Request) -> FileResponse:
        page = Path(request.app.state.settings.root) / "static" / "index.html"
        return FileResponse(page)

    static_dir = settings.root / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    return app


app = create_app()
