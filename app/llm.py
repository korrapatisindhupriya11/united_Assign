"""Local language-model backends. Extractive mode needs no model download."""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from threading import Lock

import httpx

from app.rag.retrieve import ScoredChunk, specific_terms, term_in_text

logger = logging.getLogger(__name__)

_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="llm")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


class LLMError(RuntimeError):
    """The generative model did not return a usable answer."""


class ExtractiveGenerator:
    """Quote the closest handbook sentences. Used when no LLM is configured."""

    model_name = "extractive-grounded"

    def generate(self, prompt: str) -> str:
        raise LLMError("Extractive mode does not call a generative model.")


class OllamaGenerator:
    def __init__(self, base_url: str, model: str, timeout_seconds: int) -> None:
        self.base_url = base_url
        self.model_name = model
        self.timeout_seconds = timeout_seconds

    def generate(self, prompt: str) -> str:
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 220},
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(f"{self.base_url}/api/generate", json=payload)
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError(f"Ollama request failed: {exc}") from exc
        text = clean_model_text(str(body.get("response") or ""))
        if not text:
            raise LLMError("Ollama returned an empty answer.")
        return text


class TransformersGenerator:
    def __init__(self, model_name: str, timeout_seconds: int) -> None:
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self._lock = Lock()
        self._tokenizer = None
        self._model = None
        self._encoder_decoder = False

    def generate(self, prompt: str) -> str:
        future = _EXECUTOR.submit(self._generate_locked, prompt)
        try:
            return future.result(timeout=self.timeout_seconds)
        except FuturesTimeout as exc:
            raise LLMError(
                f"Generation exceeded {self.timeout_seconds} seconds."
            ) from exc
        except LLMError:
            raise
        except Exception as exc:  # model libraries raise a wide set of errors
            raise LLMError(str(exc)) from exc

    def _generate_locked(self, prompt: str) -> str:
        with self._lock:
            self._ensure_loaded()
            if self._encoder_decoder:
                return self._generate_seq2seq(prompt)
            return self._generate_causal(prompt)

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            from transformers import (
                AutoConfig,
                AutoModelForCausalLM,
                AutoModelForSeq2SeqLM,
                AutoTokenizer,
            )
        except ImportError as exc:
            raise LLMError(
                "transformers is not installed. Install requirements-llm.txt "
                "or set LLM_BACKEND=extractive."
            ) from exc
        logger.info("Loading local model %s", self.model_name)
        config = AutoConfig.from_pretrained(self.model_name)
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self._encoder_decoder = bool(getattr(config, "is_encoder_decoder", False))
        loader = AutoModelForSeq2SeqLM if self._encoder_decoder else AutoModelForCausalLM
        self._model = loader.from_pretrained(self.model_name)
        self._model.eval()

    def _generate_seq2seq(self, prompt: str) -> str:
        import torch

        inputs = self._tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            output = self._model.generate(
                **inputs,
                max_new_tokens=180,
                do_sample=False,
            )
        return clean_model_text(self._tokenizer.decode(output[0], skip_special_tokens=True))

    def _generate_causal(self, prompt: str) -> str:
        import torch

        inputs = self._tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024)
        input_len = inputs["input_ids"].shape[1]
        with torch.no_grad():
            output = self._model.generate(
                **inputs,
                max_new_tokens=180,
                do_sample=False,
            )
        new_tokens = output[0][input_len:]
        return clean_model_text(self._tokenizer.decode(new_tokens, skip_special_tokens=True))


def transformers_installed() -> bool:
    try:
        import transformers  # noqa: F401
    except ImportError:
        return False
    return True


def clean_model_text(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^(answer:)\s*", "", cleaned, flags=re.IGNORECASE)
    parts = [part.strip() for part in re.split(r"\n{2,}", cleaned) if part.strip()]
    deduped: list[str] = []
    for part in parts:
        if not deduped or deduped[-1] != part:
            deduped.append(part)
    return "\n\n".join(deduped)[:2000].strip()


def is_summary_question(question: str) -> bool:
    lowered = question.lower()
    markers = ("summarize", "summary", "overview", "what is our", "explain our")
    return any(marker in lowered for marker in markers)


def grounded_extract(question: str, chunks: list[ScoredChunk]) -> str:
    """Build a readable answer by quoting the matching handbook sentences."""
    summary = is_summary_question(question)
    paragraphs: list[str] = []
    for chunk in chunks:
        chosen = _select_sentences(chunk.text, question, summary=summary)
        if not chosen:
            continue
        paragraphs.append(f"{chunk.title} - {chunk.section}: {' '.join(chosen)}")
        limit = 4 if summary else 3
        if len(paragraphs) == limit:
            break
    return "\n\n".join(paragraphs)


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE.split(" ".join(text.split()))
    return [part.strip() for part in parts if part.strip()]


def _select_sentences(text: str, question: str, summary: bool) -> list[str]:
    sentences = _split_sentences(text)
    if not sentences:
        return []
    if summary:
        return sentences[:2]
    terms = specific_terms(question)
    if not terms:
        return sentences[:2]
    ranked = []
    for index, sentence in enumerate(sentences):
        overlap = sum(1 for term in terms if term_in_text(term, sentence))
        ranked.append((overlap, index, sentence))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    chosen = [sentence for overlap, _index, sentence in ranked if overlap > 0][:2]
    if not chosen:
        chosen = sentences[:1]
    order = {sentence: index for index, sentence in enumerate(sentences)}
    chosen.sort(key=lambda sentence: order[sentence])
    return chosen
