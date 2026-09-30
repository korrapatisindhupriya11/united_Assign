from pathlib import Path

from app.config import ROOT
from app.rag.chunking import load_chunks, parse_front_matter, split_sections, window_text


def test_front_matter_and_sections():
    raw = "---\nid: demo\ntitle: Demo Policy\n---\n# Demo Policy\n\nIntro text.\n\n## Details\n\nDetail text.\n"
    meta, body = parse_front_matter(raw)
    assert meta["id"] == "demo"
    sections = split_sections(body)
    assert sections[0][0] == "Overview"
    assert "Intro text." in sections[0][1]
    assert sections[1] == ("Details", "Detail text.")


def test_long_section_is_windowed():
    windows = window_text("Sentence one.\n\n" + ("word " * 300), size=180, overlap=40)
    assert len(windows) > 1
    assert all(windows)


def test_handbook_chunks_are_unique_and_labeled():
    chunks = load_chunks(Path(ROOT) / "data" / "policies")
    ids = [chunk.chunk_id for chunk in chunks]
    assert len(ids) == len(set(ids))
    documents = {chunk.document_id for chunk in chunks}
    assert documents == {
        "leave-and-time-off",
        "onboarding",
        "incident-escalation",
        "remote-and-hybrid-work",
        "performance-reviews",
        "expenses-and-travel",
        "workplace-conduct",
        "benefits-overview",
    }
    assert all(chunk.owner and chunk.effective for chunk in chunks)
