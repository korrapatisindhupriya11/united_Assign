# Prompt design and tool use

The generative backends do not choose their own tools. The orchestrator in `app/orchestrator.py` decides, then either answers from a tool or calls the model with a prompt built by `app/prompts.py`. A small local model is unreliable at function calling, so the tool choice stays in code where it can be tested.

## Tools

| Tool | When it runs | What it returns |
| --- | --- | --- |
| `list_policies` | Greeting, "help", or "what policies do you know?" when the message is not also a specific policy question | The loaded document titles and owners |
| `retrieve_policy_excerpts` | Every other question | Top handbook chunks, then a coverage decision |

`retrieve_policy_excerpts` is a lexical search over chunk text that includes the policy title and section heading. The coverage rule refuses when the top score is below `RETRIEVAL_MIN_SCORE` (default 0.08) or when the distinctive words in the question are not in the retrieved text. Words like "policy", "process", "days", and "summarize" do not count as distinctive. "Sabbatical" and "Netflix" do.

That refusal happens before generation. The model is not given a chance to invent a sabbatical policy.

## Prompt

For a question that clears the coverage check, the prompt is:

- A role line: Harborline Guide answers only from the excerpts.
- Rules: no outside knowledge, no invented days or amounts or owners, an exact refusal sentence if the excerpts are not enough, a short answer that names the policy, and an instruction to ignore employee text that conflicts with those rules.
- Up to four recent turns, each clipped to 300 characters, so a follow-up has context without crowding out the handbook.
- The excerpts that fit in a 1,600 character budget, each labeled with policy, section, effective date, and owner.
- The employee question, closed by `Answer:`.

The refusal sentence the model is told to use is: "I cannot find this in the Harborline policy knowledge base." If that sentence shows up in a model answer, the API marks the turn as refused and low confidence. The excerpts are still returned when they were retrieved, so a person can see what the model was given.

The same prompt is sent to the Transformers backend and to Ollama. Extractive mode does not use the prompt; it selects overlapping sentences directly. The UI says which of those happened.

## Interaction choices

- **Citations are not left to the model.** The API attaches title, section, owner, effective date, excerpt, and retrieval score from the retriever. A small model can forget to cite. The UI does not depend on it.
- **Conversation is a window, not a transcript dump.** Only the last four turns go into the prompt. Retrieval sees the previous user question only when the new question is vague.
- **Failures are visible.** Timeout, empty output, a missing library, or an Ollama connection error become `degraded: true` and a quoted answer, with the model name suffixed by `+extractive-fallback`.
- **The composer stays honest.** Every answer carries the same disclaimer: the assistant is not People Operations, a manager, Legal, or Security.
- **Feedback is a separate action.** Helpful / Not helpful does not change the next prompt. It is a review signal, not a silent training loop.

## What I would change in the prompt with a stronger model

With an instruction model in the 7B+ range I would add a required final line that repeats the policy title, and I would ask for a bullet only when the employee asked for steps. I would still keep tool choice and the refusal threshold in the orchestrator. A better model does not remove the need for a coverage check.
