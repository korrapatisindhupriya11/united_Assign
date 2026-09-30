"""Tool orchestration: retrieve, decide whether to answer, then call the LLM."""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass, field

from app.config import Settings, get_settings
from app.governance import GovernanceLog
from app.llm import (
    ExtractiveGenerator,
    LLMError,
    OllamaGenerator,
    TransformersGenerator,
    grounded_extract,
    is_summary_question,
    transformers_installed,
)
from app.prompts import DISCLAIMER, REFUSAL_SENTENCE, build_prompt
from app.rag.chunking import load_chunks
from app.rag.retrieve import (
    PolicyIndex,
    ScoredChunk,
    excerpts_cover_query,
    sections_for_document,
    specific_terms,
)
from app.sessions import SessionStore, Turn, utc_now

logger = logging.getLogger(__name__)

_GREETING = re.compile(
    r"^(hi|hello|hey|good morning|good afternoon|good evening)[!.\s]*$",
    re.IGNORECASE,
)
_CATALOG_CUES = (
    "what policies",
    "which policies",
    "what can you help",
    "what do you know",
    "list the policies",
    "list policies",
)
_MODEL_REFUSAL = (
    "cannot find this",
    "can't find this",
    "do not contain",
    "don't contain",
    "not in the policy",
    "not in the excerpts",
)


@dataclass
class ChatResult:
    session_id: str
    message_id: str
    answer: str
    sources: list[dict]
    confidence: str
    refused: bool
    degraded: bool
    disclaimer: str
    model: str
    tools: list[str]
    explain: str
    latency_ms: int
    created_at: str = field(default_factory=utc_now)


class Orchestrator:
    def __init__(
        self,
        settings: Settings,
        index: PolicyIndex,
        sessions: SessionStore,
        governance: GovernanceLog,
        generator: object,
    ) -> None:
        self.settings = settings
        self.index = index
        self.sessions = sessions
        self.governance = governance
        self.generator = generator

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> Orchestrator:
        settings = settings or get_settings()
        index = PolicyIndex(load_chunks(settings.policy_dir))
        return cls(
            settings=settings,
            index=index,
            sessions=SessionStore(),
            governance=GovernanceLog(settings.feedback_path, settings.audit_path),
            generator=build_generator(settings),
        )

    def chat(self, session_id: str | None, message: str) -> ChatResult:
        started = time.perf_counter()
        active_session = self.sessions.get_or_create(session_id)
        prior = self.sessions.history(active_session)
        self.sessions.append(
            active_session,
            Turn(message_id=str(uuid.uuid4()), role="user", content=message, created_at=utc_now()),
        )
        result = self._answer(active_session, message, prior)
        result.latency_ms = int((time.perf_counter() - started) * 1000)
        self.sessions.append(active_session, _assistant_turn(result))
        self._audit(message, result)
        return result

    def _answer(self, session_id: str, message: str, prior: list[Turn]) -> ChatResult:
        if _GREETING.match(message.strip()):
            return self._direct(
                session_id,
                self._welcome(),
                tools=["list_policies"],
                explain="Greeting detected, so no policy retrieval was required.",
            )
        if _is_catalog(message):
            return self._direct(
                session_id,
                self._catalog_answer(),
                tools=["list_policies"],
                explain="The question asks which policies are loaded, so the catalog tool answered.",
            )

        query = _retrieval_query(message, prior)
        chunks = self.index.search(query, self.settings.top_k)
        if not excerpts_cover_query(query, chunks, self.settings.min_score):
            return self._direct(
                session_id,
                self._refusal(),
                tools=["retrieve_policy_excerpts"],
                explain=(
                    "No excerpt cleared the relevance check, so the assistant refused "
                    "instead of guessing."
                ),
                refused=True,
                confidence="low",
            )
        summarized = False
        if is_summary_question(message):
            expanded = sections_for_document(self.index, chunks[0].document_id, chunks[0].score)
            if expanded:
                chunks = expanded
                summarized = True

        history = [(turn.role, turn.content) for turn in prior if turn.role in {"user", "assistant"}]
        use_extractive = isinstance(self.generator, ExtractiveGenerator)
        degraded = False
        model_name = getattr(self.generator, "model_name", "unknown")
        if use_extractive:
            answer = grounded_extract(message, chunks)
            model_name = ExtractiveGenerator.model_name
        else:
            prompt = build_prompt(
                message,
                chunks,
                history,
                excerpt_char_budget=self.settings.excerpt_char_budget,
            )
            try:
                answer = str(self.generator.generate(prompt)).strip()
                if not answer:
                    raise LLMError("The model returned an empty answer.")
            except LLMError as exc:
                logger.warning("LLM failed, using extractive fallback: %s", exc)
                answer = grounded_extract(message, chunks)
                degraded = True
                model_name = f"{model_name}+extractive-fallback"

        refused = _looks_like_refusal(answer)
        if not answer:
            refused = True
            answer = self._refusal()
        confidence = "low" if refused else _confidence(chunks[0].score)
        top = chunks[0]
        if summarized:
            explain = (
                f"Retrieved {top.title} with retrieve_policy_excerpts "
                f"(top score {top.score:.2f}) and opened its sections for a summary. "
                "The draft used only those excerpts."
            )
        else:
            explain = (
                f"Retrieved {len(chunks)} excerpt(s) with retrieve_policy_excerpts. "
                f"Top match was {top.title} / {top.section} at score {top.score:.2f}. "
                "The draft used only those excerpts."
            )
        return ChatResult(
            session_id=session_id,
            message_id=str(uuid.uuid4()),
            answer=answer,
            sources=[_source_payload(chunk) for chunk in chunks],
            confidence=confidence,
            refused=refused,
            degraded=degraded,
            disclaimer=DISCLAIMER,
            model=model_name,
            tools=["retrieve_policy_excerpts"],
            explain=explain,
            latency_ms=0,
        )

    def _direct(
        self,
        session_id: str,
        answer: str,
        tools: list[str],
        explain: str,
        refused: bool = False,
        confidence: str = "high",
    ) -> ChatResult:
        return ChatResult(
            session_id=session_id,
            message_id=str(uuid.uuid4()),
            answer=answer,
            sources=[],
            confidence=confidence,
            refused=refused,
            degraded=False,
            disclaimer=DISCLAIMER,
            model="policy-tools",
            tools=tools,
            explain=explain,
            latency_ms=0,
        )

    def _welcome(self) -> str:
        titles = ", ".join(document.title for document in self.index.documents)
        return (
            "Hello. I answer questions from the Harborline handbook only. "
            f"I can help with: {titles}. "
            "Ask in your own words, and I will show the excerpts I used."
        )

    def _catalog_answer(self) -> str:
        lines = [
            f"{document.title} (owner: {document.owner})"
            for document in self.index.documents
        ]
        return (
            "These handbook documents are loaded:\n"
            + "\n".join(f"- {line}" for line in lines)
            + "\n\nAsk about one of them and I will cite the section I used."
        )

    def _refusal(self) -> str:
        titles = ", ".join(document.title for document in self.index.documents)
        return (
            f"{REFUSAL_SENTENCE} I will not guess. Loaded handbooks: {titles}. "
            "For anything else, contact People Operations at people-ops@harborline.example."
        )

    def _audit(self, message: str, result: ChatResult) -> None:
        record = {
            "timestamp": result.created_at,
            "session_id": result.session_id,
            "message_id": result.message_id,
            "question": message,
            "tools": result.tools,
            "source_ids": [source["chunk_id"] for source in result.sources],
            "scores": [source["score"] for source in result.sources],
            "refused": result.refused,
            "degraded": result.degraded,
            "model": result.model,
            "latency_ms": result.latency_ms,
            "confidence": result.confidence,
        }
        try:
            self.governance.audit(record)
        except OSError:
            logger.exception("Failed to write the audit log")


def build_generator(settings: Settings) -> object:
    backend = settings.llm_backend
    if backend == "extractive":
        return ExtractiveGenerator()
    if backend == "ollama":
        return OllamaGenerator(
            settings.ollama_base_url,
            settings.ollama_model,
            settings.generation_timeout_seconds,
        )
    if backend == "transformers":
        return TransformersGenerator(settings.llm_model, settings.generation_timeout_seconds)
    if backend == "auto":
        if transformers_installed():
            return TransformersGenerator(settings.llm_model, settings.generation_timeout_seconds)
        return ExtractiveGenerator()
    raise ValueError(
        "LLM_BACKEND must be one of: auto, extractive, transformers, ollama."
    )


def _retrieval_query(message: str, prior: list[Turn]) -> str:
    if len(specific_terms(message)) >= 2:
        return message
    previous_user = [turn.content for turn in prior if turn.role == "user"]
    if not previous_user:
        return message
    return f"{previous_user[-1]} {message}"


def _is_catalog(message: str) -> bool:
    lowered = message.lower().strip()
    if lowered in {"help", "menu", "start"}:
        return True
    if any(cue in lowered for cue in _CATALOG_CUES) and len(specific_terms(message)) <= 1:
        return True
    return False


def _looks_like_refusal(answer: str) -> bool:
    lowered = answer.lower()
    return any(marker in lowered for marker in _MODEL_REFUSAL)


def _confidence(score: float) -> str:
    if score >= 0.2:
        return "high"
    return "medium"


def _source_payload(chunk: ScoredChunk) -> dict:
    return {
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "title": chunk.title,
        "section": chunk.section,
        "excerpt": _trim(chunk.text, 320),
        "score": chunk.score,
        "owner": chunk.owner,
        "effective": chunk.effective,
    }


def _trim(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    cut = compact[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def _assistant_turn(result: ChatResult) -> Turn:
    return Turn(
        message_id=result.message_id,
        role="assistant",
        content=result.answer,
        created_at=result.created_at,
        sources=result.sources,
        confidence=result.confidence,
        refused=result.refused,
        degraded=result.degraded,
        disclaimer=result.disclaimer,
        model=result.model,
        tools=result.tools,
        explain=result.explain,
    )
