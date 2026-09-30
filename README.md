# Harborline Guide

Internal policy copilot for a fictional company. Employees ask about leave, onboarding, incidents, and the rest of a small handbook. The app retrieves the relevant sections and answers only from those sections.

The handbook in `data/policies` is original synthetic text. It is not a real employer's policy, it has no protected health information, and it is not copied from a public company wiki. See [data/README.md](data/README.md).

## What you get

- A chat page with history, loading and error states, keyboard use, and visible citations
- A FastAPI backend with a documented chat contract
- Retrieval over the handbook, then either a local generative model or direct quotations
- Refusal when the handbook does not cover the question
- Local feedback and audit logs
- Notes on prompt design, accuracy, and governance in `docs/`

## Setup

Use Python 3.11 or newer.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

macOS or Linux:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

No API key is required. Copy `.env.example` to `.env` only if you want to change the defaults. Values already set in the shell win over `.env`.

## Run

From the project root, with the virtual environment active:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

With the default `LLM_BACKEND=auto`, the app uses a local Hugging Face model when `transformers` is installed and otherwise quotes the handbook directly. The quote mode is enough to try every sample question. The page says which mode is active.

One question from the terminal:

```powershell
python -m app.cli "Summarize our leave policy."
```

### Enable a local generative model

CPU-only PyTorch, then the model libraries:

```powershell
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-llm.txt
```

```powershell
$env:LLM_BACKEND = "transformers"
$env:LLM_MODEL = "google/flan-t5-small"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The first chat request downloads `google/flan-t5-small` from Hugging Face (a few hundred megabytes) into the local cache. Later requests reuse it. Generation on CPU can take up to the timeout (`GENERATION_TIMEOUT_SECONDS`, default 90). If the download or the generation fails, the API still answers from the handbook and sets `degraded` to true.

Ollama is optional. Install it separately, pull a model, then:

```powershell
$env:LLM_BACKEND = "ollama"
$env:OLLAMA_MODEL = "llama3.2"
```

To force quotations even when a model library is installed:

```powershell
$env:LLM_BACKEND = "extractive"
```

## Try these

- Summarize our leave policy.
- What is the escalation process for incidents?
- Find information about onboarding steps.
- Can I work from another country for three months?
- What is our sabbatical policy? (the handbook has no sabbatical policy, so the app should refuse)

## Tests

```powershell
python -m pytest
python -m app.eval_retrieval
```

`eval_retrieval` prints the golden question list and uses extractive answers so it does not download a model.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Model mode, document count, chunk count |
| `POST` | `/api/chat` | Ask a question. Body: `message`, optional `session_id` |
| `GET` | `/api/sessions/{session_id}` | Conversation history |
| `DELETE` | `/api/sessions/{session_id}` | Forget the in-memory conversation |
| `POST` | `/api/feedback` | `rating` of `up` or `down`, optional `reason` and `comment` |
| `GET` | `/api/governance/summary` | Counts of saved feedback |

A chat response includes `answer`, `sources` (title, section, excerpt, score, owner, effective date), `confidence`, `refused`, `degraded`, `disclaimer`, `model`, `tools`, `explain`, and `latency_ms`.

Interactive schemas are at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) while the server is running.

Feedback and audit lines are written under `data/runtime/`. That folder is gitignored. It stays on the machine running the app.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `LLM_BACKEND` | `auto` | `auto`, `extractive`, `transformers`, or `ollama` |
| `LLM_MODEL` | `google/flan-t5-small` | Hugging Face model id for the transformers backend |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Local Ollama server |
| `OLLAMA_MODEL` | `llama3.2` | Model name already pulled in Ollama |
| `RETRIEVAL_TOP_K` | `4` | Excerpts passed to the answer step |
| `RETRIEVAL_MIN_SCORE` | `0.08` | Minimum TF-IDF cosine before an excerpt can support an answer |
| `GENERATION_TIMEOUT_SECONDS` | `90` | Limit for one model call |
| `POLICY_DIR` | `data/policies` | Handbook markdown |

## Layout

```text
app/            API, retrieval, prompt, model backends, orchestration
data/policies   Synthetic handbook
static/         Chat page
docs/           Architecture, prompt, accuracy, governance, design notes
tests/          Unit tests and the golden question list
```

## Written notes

- [Architecture](docs/ARCHITECTURE.md)
- [Prompt design and tools](docs/PROMPT_DESIGN.md)
- [Accuracy and limitations](docs/ACCURACY_AND_LIMITATIONS.md)
- [Responsible AI and governance](docs/RESPONSIBLE_AI.md)
- [Design rationale, assumptions, and follow-up work](docs/DESIGN_RATIONALE.md)

## Assumptions

English only, one shared handbook, no login, and sessions that vanish when the process stops. Scaling notes for a larger corpus, more users, and stricter access control are in the architecture and design notes.
