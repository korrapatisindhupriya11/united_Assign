"""Lexical retrieval over policy chunks."""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.rag.chunking import Chunk

GENERIC_TERMS = {
    "policy",
    "policies",
    "process",
    "processes",
    "information",
    "info",
    "employee",
    "employees",
    "handbook",
    "company",
    "harborline",
    "work",
    "working",
    "step",
    "steps",
    "please",
    "explain",
    "describe",
    "tell",
    "need",
    "help",
    "question",
    "questions",
    "about",
    "overview",
    "summary",
    "summarize",
    "find",
    "details",
    "detail",
    "rule",
    "rules",
    "many",
    "much",
    "long",
    "length",
    "time",
    "day",
    "days",
    "week",
    "weeks",
    "month",
    "months",
    "year",
    "years",
    "internal",
    "guide",
    "submit",
    "request",
    "approve",
    "approval",
    "contact",
    "apply",
    "using",
    "provide",
    "offered",
    "offer",
    "available",
    "allowed",
    "does",
    "what",
    "how",
    "when",
    "where",
    "who",
}
NUMBER_WORDS = {
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "hundred",
    "thousand",
}
SHORT_KEEP = {"hr", "pip", "pto", "sev", "ceo"}
_TOKEN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class ScoredChunk:
    chunk_id: str
    document_id: str
    title: str
    section: str
    text: str
    owner: str
    effective: str
    score: float


@dataclass(frozen=True)
class DocumentInfo:
    document_id: str
    title: str
    owner: str


class PolicyIndex:
    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self.vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            min_df=1,
            max_df=0.9,
            sublinear_tf=True,
        )
        self.matrix = self.vectorizer.fit_transform([chunk.search_text() for chunk in chunks])
        self.documents = _documents(chunks)

    def search(self, query: str, top_k: int) -> list[ScoredChunk]:
        if not query.strip():
            return []
        query_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.matrix).ravel()
        scores = np.nan_to_num(scores, nan=0.0, posinf=0.0, neginf=0.0)
        order = np.argsort(scores)[::-1][:top_k]
        results: list[ScoredChunk] = []
        for position in order:
            score = float(scores[position])
            if score <= 0:
                continue
            chunk = self.chunks[int(position)]
            results.append(
                ScoredChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    title=chunk.title,
                    section=chunk.section,
                    text=chunk.text,
                    owner=chunk.owner,
                    effective=chunk.effective,
                    score=round(score, 4),
                )
            )
        return results


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def specific_terms(text: str) -> list[str]:
    skipped = set(ENGLISH_STOP_WORDS) | GENERIC_TERMS | NUMBER_WORDS
    found: list[str] = []
    for token in tokens(text):
        if token.isdigit():
            continue
        if token in skipped:
            continue
        if len(token) < 3 and token not in SHORT_KEEP:
            continue
        if token not in found:
            found.append(token)
    return found


def term_in_text(term: str, text: str) -> bool:
    haystack = set(tokens(text))
    variants = {term}
    if len(term) > 4 and term.endswith("s"):
        variants.add(term[:-1])
    elif len(term) > 3:
        variants.add(term + "s")
    return any(variant in haystack for variant in variants)


def excerpts_cover_query(query: str, chunks: list[ScoredChunk], min_score: float) -> bool:
    """Refuse weak retrieval so the model is not asked to guess."""
    if not chunks or chunks[0].score < min_score:
        return False
    terms = specific_terms(query)
    if not terms:
        return True
    blob = " ".join(f"{chunk.title} {chunk.section} {chunk.text}" for chunk in chunks)
    missing = [term for term in terms if not term_in_text(term, blob)]
    if len(terms) <= 2:
        return not missing
    return len(missing) <= 1


def sections_for_document(
    index: PolicyIndex,
    document_id: str,
    score: float,
    limit: int = 5,
) -> list[ScoredChunk]:
    """Return the opening chunk of each section, in handbook order.

    A summary query such as "summarize our leave policy" matches every section
    that repeats the word "leave". Walking the document keeps the allowance,
    sick leave, and parental leave in the answer instead of only the overview.
    """
    chosen: list[ScoredChunk] = []
    seen: set[str] = set()
    for chunk in index.chunks:
        if chunk.document_id != document_id or chunk.section in seen:
            continue
        seen.add(chunk.section)
        chosen.append(
            ScoredChunk(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                title=chunk.title,
                section=chunk.section,
                text=chunk.text,
                owner=chunk.owner,
                effective=chunk.effective,
                score=score,
            )
        )
        if len(chosen) == limit:
            break
    return chosen


def _documents(chunks: list[Chunk]) -> list[DocumentInfo]:
    seen: dict[str, DocumentInfo] = {}
    for chunk in chunks:
        if chunk.document_id not in seen:
            seen[chunk.document_id] = DocumentInfo(
                document_id=chunk.document_id,
                title=chunk.title,
                owner=chunk.owner,
            )
    return list(seen.values())
