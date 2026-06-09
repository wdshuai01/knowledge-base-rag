const fileInput = document.getElementById("fileInput");
const uploadBtn = document.getElementById("uploadBtn");
const uploadStatus = document.getElementById("uploadStatus");
const questionInput = document.getElementById("questionInput");
const askBtn = document.getElementById("askBtn");
const messages = document.getElementById("messages");
const references = document.getElementById("references");
const refreshMonitorBtn = document.getElementById("refreshMonitorBtn");
const monitorLogs = document.getElementById("monitorLogs");
const refreshDocsBtn = document.getElementById("refreshDocsBtn");
const dedupeDocsBtn = document.getElementById("dedupeDocsBtn");
const documentsPanel = document.getElementById("documentsPanel");
const runEvalBtn = document.getElementById("runEvalBtn");
const evalPanel = document.getElementById("evalPanel");
const refreshHistoryBtn = document.getElementById("refreshHistoryBtn");
const questionHistory = document.getElementById("questionHistory");
const healthBtn = document.getElementById("healthBtn");
const healthStatus = document.getElementById("healthStatus");

async function parseResponse(res) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || data.message || `HTTP ${res.status}`);
  }
  return data;
}

function setBusy(button, busy, text) {
  if (!button) return;
  if (busy) {
    button.dataset.label = button.textContent;
    button.textContent = text || "Processing...";
    button.disabled = true;
  } else {
    button.textContent = button.dataset.label || button.textContent;
    button.disabled = false;
  }
}

function addMessage(role, text) {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  wrapper.appendChild(bubble);
  messages.appendChild(wrapper);
  messages.scrollTop = messages.scrollHeight;
  return bubble;
}

function renderReferences(refs) {
  references.innerHTML = "";
  if (!Array.isArray(refs) || refs.length === 0) {
    references.innerHTML = `<p class="empty">No references</p>`;
    return;
  }

  refs.forEach((ref) => {
    const content = String(ref.content || "");
    const card = document.createElement("div");
    card.className = "ref-card";
    card.innerHTML = `
      <h3>[${ref.id}] ${escapeHtml(ref.filename || "")}</h3>
      <p>${escapeHtml(content.slice(0, 260))}${content.length > 260 ? "..." : ""}</p>
      <div class="score">
        score=${Number(ref.score || 0).toFixed(3)}
        text=${Number(ref.text_score || 0).toFixed(3)}
        vector=${Number(ref.vector_score || 0).toFixed(3)}
      </div>
    `;
    references.appendChild(card);
  });
}

function renderQuestionHistory(logs) {
  questionHistory.innerHTML = "";
  if (!Array.isArray(logs) || logs.length === 0) {
    questionHistory.innerHTML = `<p class="empty">No history</p>`;
    return;
  }

  logs.forEach((log) => {
    const item = document.createElement("button");
    item.className = "history-item";
    item.textContent = log.question || "";
    item.title = log.question || "";
    item.addEventListener("click", () => {
      questionInput.value = log.question || "";
      if (log.answer) {
        addMessage("user", log.question);
        addMessage("assistant", log.answer);
        renderReferences(log.chunks || []);
      }
    });
    questionHistory.appendChild(item);
  });
}

function renderDocuments(docs) {
  documentsPanel.innerHTML = "";
  if (!Array.isArray(docs) || docs.length === 0) {
    documentsPanel.innerHTML = `<p class="empty">No documents</p>`;
    return;
  }

  docs.forEach((doc) => {
    const card = document.createElement("div");
    card.className = "doc-card";
    card.innerHTML = `
      <strong>${escapeHtml(doc.filename || "")}</strong>
      <p>doc_id: ${escapeHtml(doc.doc_id || "")}</p>
      <p>chunks: ${Number(doc.chunks || 0)}</p>
      <button class="secondary-btn">Delete</button>
    `;
    card.querySelector("button").addEventListener("click", async () => {
      try {
        await parseResponse(await fetch("/api/documents", {
          method: "DELETE",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({doc_id: doc.doc_id}),
        }));
        await loadDocuments();
      } catch (err) {
        alert(`Delete failed: ${err.message}`);
      }
    });
    documentsPanel.appendChild(card);
  });
}

async function loadDocuments() {
  try {
    const data = await parseResponse(await fetch("/api/documents"));
    renderDocuments(data.data);
  } catch (err) {
    documentsPanel.innerHTML = `<p class="empty">Load documents failed: ${escapeHtml(err.message)}</p>`;
  }
}

function renderMonitorLogs(logs) {
  monitorLogs.innerHTML = "";
  if (!Array.isArray(logs) || logs.length === 0) {
    monitorLogs.innerHTML = `<p class="empty">No logs</p>`;
    return;
  }

  logs.forEach((log) => {
    const topChunk = log.chunks && log.chunks.length > 0 ? log.chunks[0] : null;
    const card = document.createElement("div");
    card.className = "monitor-card";
    card.innerHTML = `
      <h3>${escapeHtml(log.question || "")}</h3>
      <p>retrieval: ${Number(log.retrieval_time_ms || 0).toFixed(1)} ms</p>
      <p>generation: ${Number(log.generation_time_ms || 0).toFixed(1)} ms</p>
      <p>total: ${Number(log.total_time_ms || 0).toFixed(1)} ms</p>
      <p>Top chunk: ${topChunk ? escapeHtml(topChunk.filename || "") + " / score=" + Number(topChunk.score || 0).toFixed(3) : "none"}</p>
    `;
    monitorLogs.appendChild(card);
  });
}

async function loadMonitorLogs() {
  try {
    const data = await parseResponse(await fetch("/api/monitor/logs?limit=10"));
    renderMonitorLogs(data.data);
    renderQuestionHistory(data.data);
  } catch (err) {
    monitorLogs.innerHTML = `<p class="empty">Load logs failed: ${escapeHtml(err.message)}</p>`;
    questionHistory.innerHTML = `<p class="empty">Load history failed: ${escapeHtml(err.message)}</p>`;
  }
}

function renderEvalResult(data) {
  if (!data || data.total === 0) {
    evalPanel.innerHTML = `<p class="empty">${escapeHtml(data.message || "No eval result")}</p>`;
    return;
  }
  const metrics = Object.entries(data.metrics)
    .map(([key, value]) => `<p>${key}: ${(value * 100).toFixed(1)}%</p>`)
    .join("");
  evalPanel.innerHTML = `<div class="monitor-card"><h3>Eval questions: ${data.total}</h3>${metrics}</div>`;
}

async function checkHealth() {
  try {
    const data = await parseResponse(await fetch("/api/health"));
    healthStatus.textContent = data.elasticsearch
      ? `ES connected: ${data.es_url} / ${data.index}`
      : `ES not connected: ${data.es_url}`;
  } catch (err) {
    healthStatus.textContent = `Health check failed: ${err.message}`;
  }
}

uploadBtn.addEventListener("click", async () => {
  const file = fileInput.files[0];
  if (!file) {
    uploadStatus.textContent = "Choose a file first";
    return;
  }

  const formData = new FormData();
  formData.append("file", file);
  uploadStatus.textContent = "Uploading, chunking, embedding, and indexing...";
  setBusy(uploadBtn, true, "Indexing...");

  try {
    const data = await parseResponse(await fetch("/api/upload", {method: "POST", body: formData}));
    uploadStatus.textContent = `${data.message}, child chunks: ${data.data.chunks}`;
    await loadDocuments();
  } catch (err) {
    uploadStatus.textContent = `Upload failed: ${err.message}`;
  } finally {
    setBusy(uploadBtn, false);
  }
});

askBtn.addEventListener("click", async () => {
  const question = questionInput.value.trim();
  if (!question) return;

  addMessage("user", question);
  questionInput.value = "";
  const pending = addMessage("assistant", "Retrieving from Elasticsearch and calling Bailian...");
  renderReferences([]);
  setBusy(askBtn, true, "Generating...");

  try {
    const data = await parseResponse(await fetch("/api/ask", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({question}),
    }));
    pending.textContent = data.answer;
    renderReferences(data.references || []);
    await loadMonitorLogs();
  } catch (err) {
    pending.textContent = `Request failed: ${err.message}`;
  } finally {
    setBusy(askBtn, false);
  }
});

questionInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    askBtn.click();
  }
});

runEvalBtn.addEventListener("click", async () => {
  evalPanel.innerHTML = `<p class="empty">Running eval...</p>`;
  try {
    renderEvalResult(await parseResponse(await fetch("/api/eval/recall")));
  } catch (err) {
    evalPanel.innerHTML = `<p class="empty">Eval failed: ${escapeHtml(err.message)}</p>`;
  }
});

refreshDocsBtn.addEventListener("click", loadDocuments);
dedupeDocsBtn.addEventListener("click", async () => {
  setBusy(dedupeDocsBtn, true, "Deduplicating...");
  try {
    const data = await parseResponse(await fetch("/api/documents/deduplicate", {method: "POST"}));
    alert(`Removed duplicated documents: ${data.removed_count}`);
    await loadDocuments();
  } catch (err) {
    alert(`Deduplicate failed: ${err.message}`);
  } finally {
    setBusy(dedupeDocsBtn, false);
  }
});
refreshMonitorBtn.addEventListener("click", loadMonitorLogs);
refreshHistoryBtn.addEventListener("click", loadMonitorLogs);
healthBtn.addEventListener("click", checkHealth);

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

checkHealth();
loadDocuments();
loadMonitorLogs();
