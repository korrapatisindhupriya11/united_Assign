"""Runtime configuration loaded from the environment and an optional .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path) -> None:
    """Load KEY=VALUE lines. Existing environment variables are left untouched."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    root: Path
    policy_dir: Path
    feedback_path: Path
    audit_path: Path
    llm_backend: str
    llm_model: str
    ollama_base_url: str
    ollama_model: str
    top_k: int
    min_score: float
    generation_timeout_seconds: int
    excerpt_char_budget: int = 1600

    def with_overrides(self, **kwargs: object) -> Settings:
        return replace(self, **kwargs)


def _build_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    policy_dir = Path(os.environ.get("POLICY_DIR", ROOT / "data" / "policies"))
    runtime = ROOT / "data" / "runtime"
    return Settings(
        root=ROOT,
        policy_dir=policy_dir,
        feedback_path=Path(os.environ.get("FEEDBACK_PATH", runtime / "feedback.jsonl")),
        audit_path=Path(os.environ.get("AUDIT_PATH", runtime / "audit.jsonl")),
        llm_backend=os.environ.get("LLM_BACKEND", "auto").strip().lower(),
        llm_model=os.environ.get("LLM_MODEL", "google/flan-t5-small").strip(),
        ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
        ollama_model=os.environ.get("OLLAMA_MODEL", "llama3.2").strip(),
        top_k=int(os.environ.get("RETRIEVAL_TOP_K", "4")),
        min_score=float(os.environ.get("RETRIEVAL_MIN_SCORE", "0.08")),
        generation_timeout_seconds=int(os.environ.get("GENERATION_TIMEOUT_SECONDS", "90")),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return _build_settings()
