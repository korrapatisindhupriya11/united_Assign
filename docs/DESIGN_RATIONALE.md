# Design rationale

## What I optimized for

The assignment asks for a chat workflow, a backend that orchestrates retrieval and a model, and a visible responsible-AI posture, running on a normal laptop with public material. I optimized for a path that installs, answers, and shows its evidence without an API key.

The handbook is original synthetic text for a fictional employer, Harborline. I did not scrape a company wiki or check in a copyrighted handbook. Eight short policies are enough to exercise leave, onboarding, and incident escalation, and small enough that a wrong citation is easy to spot in review.

## Main choices

**Sparse retrieval instead of a downloaded embedding model.** TF-IDF over title, section, and body is deterministic, fast, and good enough when the questions use the same words as the policies. A dense embedder would help paraphrases ("time away from work" for leave) and is the first retrieval upgrade I would make. It is not required to run the POC, and it would add a large model download before the first question.

**Tool choice in the orchestrator, not in the model.** Greetings and catalog questions are answered by `list_policies`. Policy questions go through `retrieve_policy_excerpts`, a coverage gate, then generation. Small models are poor at deciding when to call a tool. Keeping that decision in code makes the refusal behavior testable.

**Extractive answers as a real mode, not only a catch.** `LLM_BACKEND=auto` uses a local Transformers model when that library is installed, and otherwise quotes the handbook. Quotes are less fluent and more faithful. The generative prompt is still the path for `transformers` and `ollama`, with a timeout and a fallback to the same quotes if the model fails. I would rather show a sentence from the leave policy than block the demo on a 2 GB install.

**Citations computed outside the model.** The response carries the section, owner, effective date, excerpt, and score from the index. Explainability then survives a model that does not mention its source.

**A plain FastAPI service and a static page.** There is no frontend build. The page is one HTML document, one stylesheet, and one script, so a reviewer can run `uvicorn` and open the chat. The UI keeps conversation history, a loading state, an error with retry, keyboard send, labels, a skip link, and a live region for new messages.

## Assumptions

- English only.
- One fictional company, and every employee in that fiction may read every policy. There is no per-document authorization.
- The handbook on disk is the current version. Restarting the process reloads it.
- One user at a time is the capacity target. Sessions are in memory.
- A retrieval score is a ranking signal. It is not a calibrated probability.
- `.example` mailboxes are documentation, not inboxes.
- No paid API, GPU, or hosted vector database is available.

## What I would improve with more time

1. Hybrid retrieval: BM25 or TF-IDF plus a local embedding model, then a small reranker on the top 20 chunks.
2. A golden set scored on answer faithfulness, not only on the document id, including paraphrases and multi-hop questions ("I am in Finance and want leave on quarter close").
3. Streaming tokens and a cancellation button, with the same timeout budget.
4. Authentication, document-level access checks before a chunk can enter the prompt, and an admin-only feedback queue.
5. Redaction of the audit log and a stated retention window.
6. A larger instruction model via Ollama for employees who already have one, kept behind the same prompt and fallback.
7. Ingestion that tracks file hashes and refuses to serve a policy past a review date.
8. Rate limits and a concurrency cap so one CPU generation cannot stall every other request.

I would not remove the refusal gate or the visible excerpts in order to make the answers sound smoother.
