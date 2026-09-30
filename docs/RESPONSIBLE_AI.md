# Responsible AI and governance

## Intended use

Harborline Guide is a proof of concept for an internal handbook assistant. An employee may ask what the published policies say about leave, onboarding, incident escalation, remote work, performance reviews, expenses, workplace conduct, and benefits.

The intended user is an employee who can already read the handbook. The assistant is a retrieval aid with a draft answer, not a new source of rules.

## Out of scope

- Approving leave, expenses, access, or a performance rating
- Declaring or downgrading an incident
- Answering from anything other than the files in `data/policies`
- Medical, legal, or compensation decisions
- Questions about a real person, including pay
- Any workflow that needs protected health information or another employer's confidential policies

The dataset is original synthetic text for a fictional employer. It contains no patient data, no real employee records, and no copied internal handbook. Addresses use the reserved `.example` domain.

## Controls in this POC

| Control | Where it lives | What it does |
| --- | --- | --- |
| Grounding | `app/orchestrator.py` | Refuses when retrieval does not cover the question, and puts only the retrieved excerpts in the prompt |
| Explainability | Chat response and the UI | Shows the tool used, a one-line explanation, the section, the owner, the effective date, and the retrieval score |
| Uncertainty | `confidence` and `refused` | Low confidence on refusal. The badge is a retrieval signal, and the UI does not call it a probability |
| Fallback | `app/llm.py` | If generation fails, quote the handbook and set `degraded` so the failure is not silent |
| Disclaimer | Every assistant message | States that the draft is not a decision by People Operations, a manager, Legal, or Security |
| Feedback | Helpful / Not helpful | Stores rating, optional reason, optional comment, and the question. It does not retrain the model |
| Audit | `data/runtime/audit.jsonl` | Local record of the question, sources, scores, model, refusal flag, and latency |
| Input bounds | API schema | Questions are limited to 2,000 characters. Session ids are restricted to a simple token shape |

Feedback reasons are `incorrect`, `incomplete`, `outdated`, `unclear`, and `other`. A reviewer can read `data/runtime/feedback.jsonl` or `GET /api/governance/summary` for counts. In this POC that summary is unauthenticated. A production service would restrict it to the policy owners and the team that runs the assistant.

## Accuracy stance

The assistant will sometimes quote the wrong section or, with a generative model, smooth the wording in a way the handbook did not. Refusing an uncovered question is the preferred error. Details and the known gaps are in [ACCURACY_AND_LIMITATIONS.md](ACCURACY_AND_LIMITATIONS.md).

People Operations remains accountable for the policy text. The assistant team would be accountable for retrieval quality, the prompt, and the review of downvotes. This POC has no separate team, so both roles are documented rather than staffed.

## Feedback handling

1. The employee marks an answer helpful or not helpful. A negative mark can include a reason and a short comment.
2. The API checks that the message belongs to the session, then appends one JSON line.
3. Nothing in that line updates the index or the model.
4. With more time, a downvote would open a review item: check the excerpts, fix the chunk or the prompt, and add the question to the golden set if it was a miss.

Do not put medical details, account numbers, or allegations about a named coworker into the chat or the comment box. The audit log stores the question text on the machine running the app.

## Privacy and retention

- Sessions live in process memory and disappear on restart.
- Audit and feedback files are local, gitignored, and are not sent to a hosted model API in the extractive, Transformers, or Ollama setups in this repo.
- There is no account system, so the logs are not tied to a corporate identity. They also are not access-controlled.
- A production version would name a retention period, redact identifiers before storage, and keep policy text access separate from chat logs.

## Human oversight

The handbook files are the authority. Effective dates are carried onto each citation so a reader can see which version was indexed. There is no automatic publish step: changing a policy means editing the markdown and restarting the app so the index rebuilds.
