const transcript = document.querySelector("#transcript");
const form = document.querySelector("#composer");
const question = document.querySelector("#question");
const statusLine = document.querySelector("#status");
const errorBox = document.querySelector("#error");
const sendButton = document.querySelector("#send");
const clearButton = document.querySelector("#clear");
const healthLine = document.querySelector("#health");
const SESSION_KEY = "harborline.session";

let sessionId = sessionStorage.getItem(SESSION_KEY);
let sending = false;
let lastQuestion = "";

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = question.value.trim();
  if (!text || sending) return;
  question.value = "";
  send(text, true);
});

question.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

clearButton.addEventListener("click", clearChat);

document.querySelectorAll("[data-question]").forEach((button) => {
  button.addEventListener("click", () => {
    if (sending) return;
    send(button.dataset.question, true);
  });
});

init();

async function init() {
  await loadHealth();
  if (!sessionId) return;
  try {
    const history = await getJson(`/api/sessions/${sessionId}`);
    history.messages.forEach((turn) => renderTurn(turn, false));
  } catch {
    sessionStorage.removeItem(SESSION_KEY);
    sessionId = null;
  }
}

async function loadHealth() {
  try {
    const data = await getJson("/api/health");
    const mode = data.generative
      ? `Generative model: ${data.model}`
      : "Quoting handbook text directly. A generative model is not loaded.";
    healthLine.textContent = `${data.documents} policies · ${data.chunks} sections · ${mode}`;
  } catch {
    healthLine.textContent = "The local assistant service is not responding.";
  }
}

async function send(text, echoUser) {
  lastQuestion = text;
  if (echoUser) renderUser(text);
  setBusy(true, "Searching the handbook and drafting an answer. Local models can take a minute.");
  hideError();
  try {
    const data = await postJson("/api/chat", { message: text, session_id: sessionId });
    sessionId = data.session_id;
    sessionStorage.setItem(SESSION_KEY, sessionId);
    const article = renderAssistant(data, true);
    article.focus();
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(false, "");
  }
}

async function clearChat() {
  if (sending) return;
  const previous = sessionId;
  sessionStorage.removeItem(SESSION_KEY);
  sessionId = null;
  transcript.replaceChildren();
  renderWelcome();
  hideError();
  question.value = "";
  question.focus();
  if (previous) {
    await fetch(`/api/sessions/${previous}`, { method: "DELETE" });
  }
}

function renderWelcome() {
  const article = document.createElement("article");
  article.className = "message assistant welcome";
  const heading = document.createElement("h2");
  heading.className = "visually-hidden";
  heading.textContent = "Welcome";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = "Ask about leave, onboarding, incidents, remote work, reviews, expenses, conduct, or benefits. I will show the handbook excerpts behind the answer. If the handbook does not cover it, I will say so.";
  article.append(heading, bubble);
  transcript.append(article);
}

function renderTurn(turn, focus) {
  if (turn.role === "user") renderUser(turn.content);
  else renderAssistant(turn, focus);
}

function renderUser(text) {
  const article = document.createElement("article");
  article.className = "message user";
  const heading = document.createElement("h2");
  heading.className = "visually-hidden";
  heading.textContent = "Your question";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  article.append(heading, bubble);
  transcript.append(article);
  article.scrollIntoView({ block: "nearest" });
}

function renderAssistant(data, focus) {
  const article = document.createElement("article");
  article.className = "message assistant";
  article.tabIndex = -1;
  article.dataset.messageId = data.message_id;

  const heading = document.createElement("h2");
  heading.className = "visually-hidden";
  heading.textContent = "Assistant answer";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = data.answer;

  const meta = document.createElement("p");
  meta.className = "meta";
  const badge = document.createElement("span");
  badge.className = `badge ${data.confidence || "low"}`;
  badge.textContent = `${data.confidence || "low"} confidence`;
  meta.append(badge);
  if (data.model) {
    const model = document.createElement("span");
    model.textContent = data.model;
    meta.append(model);
  }

  article.append(heading, bubble, meta);

  const mode = document.createElement("p");
  mode.className = "mode-note";
  if (data.degraded) {
    mode.textContent = "The language model did not respond, so this answer quotes the handbook directly.";
  } else if (data.model === "extractive-grounded") {
    mode.textContent = "Quoted from the handbook. A generative model is not enabled for this answer.";
  } else if (data.model && data.model !== "policy-tools") {
    mode.textContent = "Drafted from the excerpts below. Read them before you rely on the wording.";
  }
  if (mode.textContent) article.append(mode);

  if (data.explain) {
    const explain = document.createElement("p");
    explain.className = "explain";
    explain.textContent = data.explain;
    article.append(explain);
  }

  if (data.sources && data.sources.length) {
    const list = document.createElement("ul");
    list.className = "sources";
    list.setAttribute("aria-label", data.refused ? "Excerpts considered" : "Sources");
    article.append(list);
    data.sources.forEach((source) => {
      const item = document.createElement("li");
      const title = document.createElement("h3");
      title.textContent = `${source.title} — ${source.section}`;
      const facts = document.createElement("p");
      facts.textContent = `${source.owner} · effective ${source.effective} · retrieval score ${source.score}`;
      const excerpt = document.createElement("p");
      excerpt.textContent = source.excerpt;
      item.append(title, facts, excerpt);
      list.append(item);
    });
  }

  if (data.disclaimer) {
    const disclaimer = document.createElement("p");
    disclaimer.className = "disclaimer";
    disclaimer.textContent = data.disclaimer;
    article.append(disclaimer);
  }

  article.append(feedbackControls(data));
  transcript.append(article);
  if (focus) article.scrollIntoView({ block: "nearest" });
  return article;
}

function feedbackControls(data) {
  const wrap = document.createElement("div");
  wrap.className = "feedback";
  if (!data.message_id) return wrap;
  if (data.feedback_rating) {
    const saved = document.createElement("p");
    saved.className = "saved";
    saved.textContent = "Feedback saved for review.";
    wrap.append(saved);
    return wrap;
  }

  const up = document.createElement("button");
  up.type = "button";
  up.textContent = "Helpful";
  const down = document.createElement("button");
  down.type = "button";
  down.textContent = "Not helpful";
  up.addEventListener("click", () => submitFeedback(data.message_id, "up", null, "", wrap));
  down.addEventListener("click", () => showDownForm(data.message_id, wrap));
  wrap.append(up, down);
  return wrap;
}

function showDownForm(messageId, wrap) {
  wrap.replaceChildren();
  const formEl = document.createElement("form");
  formEl.className = "feedback-form";
  formEl.innerHTML = `
    <label>What went wrong?
      <select name="reason">
        <option value="">Choose a reason</option>
        <option value="incorrect">Incorrect</option>
        <option value="incomplete">Incomplete</option>
        <option value="outdated">Outdated</option>
        <option value="unclear">Unclear</option>
        <option value="other">Other</option>
      </select>
    </label>
    <label>Comment, optional
      <input name="comment" maxlength="500" />
    </label>
    <button type="submit">Save feedback</button>
  `;
  formEl.addEventListener("submit", (event) => {
    event.preventDefault();
    const reason = formEl.elements.reason.value || null;
    const comment = formEl.elements.comment.value.trim();
    submitFeedback(messageId, "down", reason, comment, wrap);
  });
  wrap.append(formEl);
  formEl.elements.reason.focus();
}

async function submitFeedback(messageId, rating, reason, comment, wrap) {
  try {
    await postJson("/api/feedback", {
      session_id: sessionId,
      message_id: messageId,
      rating,
      reason,
      comment: comment || null,
    });
    wrap.replaceChildren();
    const saved = document.createElement("p");
    saved.className = "saved";
    saved.textContent = "Feedback saved for review.";
    wrap.append(saved);
  } catch (error) {
    showError(error.message);
  }
}

function setBusy(isBusy, message) {
  sending = isBusy;
  sendButton.disabled = isBusy;
  clearButton.disabled = isBusy;
  transcript.setAttribute("aria-busy", isBusy ? "true" : "false");
  statusLine.textContent = message;
}

function showError(message) {
  errorBox.hidden = false;
  errorBox.replaceChildren();
  const text = document.createElement("span");
  text.textContent = message;
  const retry = document.createElement("button");
  retry.type = "button";
  retry.textContent = "Try again";
  retry.addEventListener("click", () => {
    if (!lastQuestion || sending) return;
    send(lastQuestion, false);
  });
  errorBox.append(text, retry);
}

function hideError() {
  errorBox.hidden = true;
  errorBox.replaceChildren();
}

async function getJson(url) {
  const response = await fetch(url);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(errorMessage(payload, response.status));
  return payload;
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(errorMessage(payload, response.status));
  return payload;
}

function errorMessage(payload, status) {
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload.detail)) {
    return payload.detail.map((item) => item.msg || "Check the question and try again.").join(" ");
  }
  if (status === 0) return "The assistant service could not be reached.";
  return `The assistant service returned an error (${status}).`;
}
