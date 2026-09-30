"""Split handbook markdown into retrieval chunks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_HEADING = re.compile(r"^##\s+")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    title: str
    section: str
    text: str
    owner: str
    effective: str

    def search_text(self) -> str:
        return f"{self.title}. {self.section}. {self.text}"


def parse_front_matter(raw: str) -> tuple[dict[str, str], str]:
    if not raw.startswith("---"):
        return {}, raw
    end = raw.find("\n---", 3)
    if end == -1:
        return {}, raw
    meta: dict[str, str] = {}
    for line in raw[3:end].strip().splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()
    body = raw[end + 4 :].lstrip("\n")
    return meta, body


def split_sections(body: str) -> list[tuple[str, str]]:
    current_title = "Overview"
    current: list[str] = []
    sections: list[tuple[str, str]] = []
    for line in body.splitlines():
        if line.startswith("# "):
            continue
        if _HEADING.match(line):
            text = "\n".join(current).strip()
            if text:
                sections.append((current_title, text))
            current_title = line[3:].strip()
            current = []
            continue
        current.append(line)
    tail = "\n".join(current).strip()
    if tail:
        sections.append((current_title, tail))
    return sections


def window_text(text: str, size: int = 900, overlap: int = 150) -> list[str]:
    compact = text.strip()
    if len(compact) <= size:
        return [compact]
    paragraphs = [part.strip() for part in compact.split("\n\n") if part.strip()]
    if not paragraphs:
        return [compact[:size]]
    windows: list[str] = []
    buffer = ""
    for paragraph in paragraphs:
        candidate = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph
        if buffer and len(candidate) > size:
            windows.append(buffer)
            tail = buffer[-overlap:]
            buffer = f"{tail}\n\n{paragraph}".strip()
        else:
            buffer = candidate
    if buffer:
        windows.append(buffer)
    return windows


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "section"


def load_chunks(policy_dir: Path) -> list[Chunk]:
    paths = sorted(policy_dir.glob("*.md"))
    if not paths:
        raise FileNotFoundError(f"No policy markdown files in {policy_dir}")
    chunks: list[Chunk] = []
    for path in paths:
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        document_id = meta.get("id") or path.stem
        title = meta.get("title") or document_id
        owner = meta.get("owner") or "Unassigned"
        effective = meta.get("effective") or "unknown"
        for section, text in split_sections(body):
            for index, piece in enumerate(window_text(text)):
                chunks.append(
                    Chunk(
                        chunk_id=f"{document_id}:{_slug(section)}:{index}",
                        document_id=document_id,
                        title=title,
                        section=section,
                        text=piece,
                        owner=owner,
                        effective=effective,
                    )
                )
    if not chunks:
        raise ValueError(f"Policy files in {policy_dir} did not produce any chunks")
    return chunks
