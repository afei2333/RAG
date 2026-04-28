const uploadForm = document.querySelector("#uploadForm");
const fileInput = document.querySelector("#fileInput");
const filePickerLabel = document.querySelector(".file-picker span");
const uploadStatus = document.querySelector("#uploadStatus");
const documentList = document.querySelector("#documentList");
const refreshDocuments = document.querySelector("#refreshDocuments");
const queryForm = document.querySelector("#queryForm");
const questionInput = document.querySelector("#questionInput");
const topKInput = document.querySelector("#topKInput");
const answerStatus = document.querySelector("#answerStatus");
const conversation = document.querySelector("#conversation");
const historyList = document.querySelector("#historyList");
const historyCount = document.querySelector("#historyCount");
const newConversation = document.querySelector("#newConversation");

let currentConversationId = null;
let currentMessages = [];
let selectedDocumentId = "";
let documentsById = new Map();

async function apiFetch(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(readError(text, response.status));
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

function readError(text, status) {
  if (!text) {
    return `HTTP ${status}`;
  }
  try {
    const payload = JSON.parse(text);
    return payload.detail || text;
  } catch {
    return text;
  }
}

function setBusy(form, busy) {
  for (const element of form.querySelectorAll("button, input, textarea")) {
    element.disabled = busy;
  }
}

function statusText(document) {
  const chunks = document.chunk_count ?? 0;
  const statusMap = {
    completed: "已索引",
    failed: "失败",
    created: "已创建",
    processing: "处理中",
  };
  return `${statusMap[document.status] || document.status} · ${chunks} chunks`;
}

function renderDocuments(data) {
  documentsById = new Map(data.items.map((document) => [document.id, document]));
  if (!data.items.length) {
    documentList.innerHTML = '<div class="muted-box">还没有文档</div>';
    return;
  }

  documentList.innerHTML = `
    <button class="document-filter${selectedDocumentId ? "" : " is-selected"}" type="button" data-select-document="">
      <span class="document-title">全部文档</span>
      <span class="document-meta">跨知识库检索</span>
    </button>
    ${data.items
    .map((document) => {
      const statusClass = document.status === "failed" ? " status-failed" : "";
      const selectedClass = selectedDocumentId === document.id ? " is-selected" : "";
      return `
        <article class="document-item${selectedClass}">
          <div class="item-main">
            <button class="document-open" type="button" data-select-document="${escapeHtml(document.id)}">
              <span class="document-title">${escapeHtml(document.filename)}</span>
              <span class="document-meta${statusClass}">${escapeHtml(statusText(document))}</span>
            </button>
          </div>
          <button class="ghost-button danger-button" type="button" data-delete-document="${escapeHtml(document.id)}" title="删除文档">×</button>
        </article>
      `;
    })
    .join("")}
  `;
  updateActiveDocumentStatus();
}

async function loadDocuments() {
  refreshDocuments.disabled = true;
  try {
    const data = await apiFetch("/api/v1/documents?page=1&page_size=50");
    renderDocuments(data);
  } catch (error) {
    documentList.innerHTML = `<div class="muted-box status-failed">${escapeHtml(error.message)}</div>`;
  } finally {
    refreshDocuments.disabled = false;
  }
}

async function loadHistory() {
  try {
    const data = await apiFetch("/api/v1/queries?page=1&page_size=30");
    historyCount.textContent = data.total ? String(data.total) : "";
    renderHistory(data.items);
  } catch (error) {
    historyList.innerHTML = `<div class="muted-box status-failed">${escapeHtml(error.message)}</div>`;
  }
}

function renderHistory(items) {
  if (!items.length) {
    historyList.innerHTML = '<div class="muted-box">暂无历史</div>';
    return;
  }

  historyList.innerHTML = items
    .map((item) => {
      const historyKey = item.conversation_id || item.id;
      return `
      <article class="history-item" data-history-id="${escapeHtml(historyKey)}">
        <button class="history-open" type="button" data-open-history="${escapeHtml(historyKey)}">
          <span class="history-question">${escapeHtml(item.question)}</span>
          <span class="history-docs">${renderDocumentNames(item.document_ids || item.citations?.map((citation) => citation.document_id) || [])}</span>
          <span class="history-time">${escapeHtml(formatTime(item.created_at))}</span>
        </button>
        <button class="ghost-button danger-button" type="button" data-delete-history="${escapeHtml(historyKey)}" title="删除历史">×</button>
      </article>
    `;
    })
    .join("");

  for (const item of items) {
    const historyKey = item.conversation_id || item.id;
    const element = historyList.querySelector(`[data-history-id="${cssEscape(historyKey)}"]`);
    if (element) {
      element.historyItem = item;
    }
  }
}

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!fileInput.files.length) {
    uploadStatus.textContent = "请选择文件";
    return;
  }

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  setBusy(uploadForm, true);
  uploadStatus.textContent = "正在上传并索引...";
  try {
    const result = await apiFetch("/api/v1/documents", {
      method: "POST",
      body: formData,
    });
    uploadStatus.textContent =
      result.status === "completed" ? "索引完成" : `处理失败：${result.error || "未知错误"}`;
    fileInput.value = "";
    updateSelectedFileLabel();
    await loadDocuments();
  } catch (error) {
    uploadStatus.textContent = error.message;
  } finally {
    setBusy(uploadForm, false);
  }
});

fileInput.addEventListener("change", updateSelectedFileLabel);

questionInput.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) {
    return;
  }
  event.preventDefault();
  if (!queryForm.querySelector(".send-button")?.disabled) {
    queryForm.requestSubmit();
  }
});

queryForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question) {
    answerStatus.textContent = "请输入问题";
    questionInput.focus();
    return;
  }

  setBusy(queryForm, true);
  answerStatus.textContent = "正在生成...";
  const pendingMessage = {
    question,
    answer: "",
    citations: [],
    loading: true,
  };
  currentMessages.push(pendingMessage);
  renderConversation();

  try {
    const result = await apiFetch("/api/v1/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        conversation_id: currentConversationId,
        document_id: selectedDocumentId || null,
        top_k: Number(topKInput.value || 5),
      }),
    });
    currentConversationId = result.conversation_id || currentConversationId;
    Object.assign(pendingMessage, {
      id: result.query_id,
      conversation_id: currentConversationId,
      question,
      answer: result.answer,
      citations: result.citations || [],
      loading: false,
    });
    renderConversation();
    questionInput.value = "";
    answerStatus.textContent = "已完成";
    await loadHistory();
  } catch (error) {
    Object.assign(pendingMessage, {
      question,
      answer: error.message,
      citations: [],
      loading: false,
      error: true,
    });
    renderConversation();
    answerStatus.textContent = "生成失败";
  } finally {
    setBusy(queryForm, false);
  }
});

refreshDocuments.addEventListener("click", loadDocuments);
newConversation.addEventListener("click", () => {
  currentConversationId = null;
  currentMessages = [];
  renderEmptyState();
  updateActiveDocumentStatus();
});

documentList.addEventListener("click", async (event) => {
  const selectButton = event.target.closest("[data-select-document]");
  if (selectButton) {
    selectedDocumentId = selectButton.dataset.selectDocument || "";
    currentConversationId = null;
    currentMessages = [];
    renderDocuments({ items: [...documentsById.values()] });
    renderEmptyState();
    return;
  }

  const button = event.target.closest("[data-delete-document]");
  if (!button) {
    return;
  }
  const id = button.dataset.deleteDocument;
  button.disabled = true;
  uploadStatus.textContent = "正在删除文档...";
  try {
    await apiFetch(`/api/v1/documents/${encodeURIComponent(id)}`, { method: "DELETE" });
    if (selectedDocumentId === id) {
      selectedDocumentId = "";
      currentConversationId = null;
      currentMessages = [];
      renderEmptyState();
    }
    uploadStatus.textContent = "文档已删除";
    await loadDocuments();
  } catch (error) {
    uploadStatus.textContent = error.message;
    button.disabled = false;
  }
});

historyList.addEventListener("click", async (event) => {
  const deleteButton = event.target.closest("[data-delete-history]");
  if (deleteButton) {
    const id = deleteButton.dataset.deleteHistory;
    deleteButton.disabled = true;
    try {
      await apiFetch(`/api/v1/queries/${encodeURIComponent(id)}`, { method: "DELETE" });
      if (currentConversationId === id || currentMessages.some((message) => message.id === id)) {
        renderEmptyState();
      }
      await loadHistory();
      answerStatus.textContent = "历史已删除";
    } catch (error) {
      answerStatus.textContent = error.message;
      deleteButton.disabled = false;
    }
    return;
  }

  const openButton = event.target.closest("[data-open-history]");
  if (!openButton) {
    return;
  }
  const row = openButton.closest(".history-item");
  const historyItem = row.historyItem;
  try {
    const data = await apiFetch(`/api/v1/queries/${encodeURIComponent(historyItem.conversation_id || historyItem.id)}`);
    currentConversationId = historyItem.conversation_id || historyItem.id;
    currentMessages = data.items;
    const documentId = historyItem.document_ids?.[0] || data.items[0]?.document_ids?.[0] || "";
    if (documentId && documentsById.has(documentId)) {
      selectedDocumentId = documentId;
      renderDocuments({ items: [...documentsById.values()] });
    } else {
      updateActiveDocumentStatus();
    }
    renderConversation();
    answerStatus.textContent = "历史对话";
  } catch (error) {
    answerStatus.textContent = error.message;
  }
});

function renderConversation() {
  if (!currentMessages.length) {
    renderEmptyState();
    return;
  }
  conversation.innerHTML = currentMessages.map(renderExchange).join("");
  conversation.scrollTop = conversation.scrollHeight;
}

function renderExchange(exchange) {
  return `
    <section class="exchange">
      <article class="message message-user">
        <div class="message-label">提问</div>
        <div class="message-body">${escapeHtml(exchange.question)}</div>
      </article>
      <article class="message message-answer${exchange.error ? " message-error" : ""}">
        <div class="message-label">回答</div>
        <div class="message-body markdown-body">${exchange.loading ? '<span class="loader">生成中...</span>' : renderMarkdown(exchange.answer)}</div>
      </article>
      ${renderCitations(exchange.citations || [])}
    </section>
  `;
}

function renderEmptyState() {
  currentMessages = [];
  conversation.innerHTML = `
    <div class="empty-state">
      <h3>开始一次检索式问答</h3>
      <p>上传文档后，直接在下方输入问题。回答会保留引用来源，方便回看依据。</p>
    </div>
  `;
}

function renderCitations(citations) {
  if (!citations.length) {
    return "";
  }

  return `
    <section class="citations">
      <details>
        <summary>引用 ${citations.length}</summary>
      ${citations
        .map((citation, index) => {
          const page = citation.page_number ? ` · 第 ${citation.page_number} 页` : "";
          const score = renderCitationScore(citation);
          return `
            <article class="citation">
              <div class="citation-title">${index + 1}. ${escapeHtml(citation.source_name)}${page}${score}</div>
              <div class="citation-text">${escapeHtml(citation.text)}</div>
            </article>
          `;
        })
        .join("")}
      </details>
    </section>
  `;
}

function updateSelectedFileLabel() {
  const file = fileInput.files?.[0];
  filePickerLabel.textContent = file ? file.name : "选择文件";
  filePickerLabel.title = file ? file.name : "";
}

function renderCitationScore(citation) {
  if (citation.retrieval_role === "neighbor" || Number(citation.score || 0) <= 0) {
    return " · 相邻上下文";
  }
  return ` · score ${Number(citation.score).toFixed(3)}`;
}

function renderDocumentNames(ids) {
  const names = [...new Set(ids)]
    .map((id) => documentsById.get(id)?.filename)
    .filter(Boolean);
  return escapeHtml(names.length ? names.join("、") : "未关联文档");
}

function updateActiveDocumentStatus() {
  const documentName = selectedDocumentId
    ? documentsById.get(selectedDocumentId)?.filename || "已选择文档"
    : "全部文档";
  answerStatus.textContent = `当前范围：${documentName}`;
}

function renderMarkdown(value) {
  const lines = String(value ?? "").split(/\r?\n/);
  const blocks = [];
  let paragraph = [];
  let list = [];
  let inCode = false;
  let codeLines = [];

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push(`<p>${renderInlineMarkdown(paragraph.join(" "))}</p>`);
      paragraph = [];
    }
  };
  const flushList = () => {
    if (list.length) {
      blocks.push(`<ul>${list.map((item) => `<li>${renderInlineMarkdown(item)}</li>`).join("")}</ul>`);
      list = [];
    }
  };

  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      if (inCode) {
        blocks.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
        codeLines = [];
        inCode = false;
      } else {
        flushParagraph();
        flushList();
        inCode = true;
      }
      continue;
    }
    if (inCode) {
      codeLines.push(line);
      continue;
    }
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      flushList();
      const level = heading[1].length + 2;
      blocks.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
      continue;
    }
    const bullet = line.match(/^\s*[-*]\s+(.+)$/);
    if (bullet) {
      flushParagraph();
      list.push(bullet[1]);
      continue;
    }
    if (!line.trim()) {
      flushParagraph();
      flushList();
      continue;
    }
    paragraph.push(line.trim());
  }

  if (inCode) {
    blocks.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
  }
  flushParagraph();
  flushList();
  return blocks.join("");
}

function renderInlineMarkdown(value) {
  let html = escapeHtml(value);
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  return html;
}

function formatTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function cssEscape(value) {
  if (window.CSS?.escape) {
    return CSS.escape(value);
  }
  return String(value).replaceAll('"', '\\"');
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

initialize();

async function initialize() {
  await loadDocuments();
  await loadHistory();
}
