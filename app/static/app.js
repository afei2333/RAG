/* ─── DOM refs ─── */
const uploadForm        = document.querySelector("#uploadForm");
const fileInput         = document.querySelector("#fileInput");
const fileLabel         = document.querySelector("#fileLabel");
const uploadStatus      = document.querySelector("#uploadStatus");
const documentList      = document.querySelector("#documentList");
const refreshDocuments  = document.querySelector("#refreshDocuments");
const queryForm         = document.querySelector("#queryForm");
const questionInput     = document.querySelector("#questionInput");
const topKInput         = document.querySelector("#topKInput");
const answerStatus      = document.querySelector("#answerStatus");
const statusDot         = document.querySelector(".status-dot");
const conversation      = document.querySelector("#conversation");
const historyList       = document.querySelector("#historyList");
const historyCount      = document.querySelector("#historyCount");
const historyTitle      = document.querySelector("#historyTitle");
const newConversation   = document.querySelector("#newConversation");
const dropZone          = document.querySelector("#dropZone");
const projectSection    = document.querySelector("#projectSection");
const historySection    = document.querySelector("#historySection");
const backToProjects    = document.querySelector("#backToProjects");

/* ─── State ─── */
let currentConversationId = null;
let currentMessages = [];
let documentsById = new Map();
let projectsById = new Map();
let currentProjectId = "";
let projectBuilderOpen = false;
let selectedProjectDocumentIds = new Set();

/* ═══════════════════════════════════════════
   API helpers
   ═══════════════════════════════════════════ */
async function apiFetch(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(readError(text, response.status));
  }
  if (response.status === 204) return null;
  return response.json();
}

function readError(text, status) {
  if (!text) return `HTTP ${status}`;
  try {
    const payload = JSON.parse(text);
    return payload.detail || text;
  } catch {
    return text;
  }
}

/* ═══════════════════════════════════════════
   Status helpers
   ═══════════════════════════════════════════ */
function setBusy(form, busy) {
  for (const el of form.querySelectorAll("button, input, textarea")) {
    el.disabled = busy;
  }
}

function setStatus(text, type = "") {
  answerStatus.textContent = text;
  statusDot.className = "status-dot" + (type === "busy" ? " is-busy" : "");
}

function setUploadStatus(text, type = "") {
  uploadStatus.textContent = text;
  uploadStatus.className = "status-line" + (type ? ` is-${type}` : "");
}

function docStatusText(doc) {
  const chunks = doc.chunk_count ?? 0;
  const map = { completed: "已索引", failed: "失败", created: "已创建", processing: "处理中" };
  return `${map[doc.status] || doc.status} · ${chunks} chunks`;
}

/* ═══════════════════════════════════════════
   Drag & drop on upload zone
   ═══════════════════════════════════════════ */
dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("drag-over");
});

["dragleave", "drop"].forEach((evt) =>
  dropZone.addEventListener(evt, () => dropZone.classList.remove("drag-over"))
);

dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  const file = e.dataTransfer?.files?.[0];
  if (file) {
    // Manually assign to file input doesn't work via DataTransfer in all browsers,
    // so we store it separately and use it during submit.
    dropZone._droppedFile = file;
    updateSelectedFileLabel(file);
  }
});

/* ═══════════════════════════════════════════
   Projects and documents
   ═══════════════════════════════════════════ */
async function loadDocuments() {
  refreshDocuments.classList.add("is-spinning");
  refreshDocuments.disabled = true;
  try {
    const data = await apiFetch("/api/v1/documents?page=1&page_size=50");
    documentsById = new Map(data.items.map((d) => [d.id, d]));
    renderProjectView();
  } catch (error) {
    documentList.innerHTML = `<div class="muted-box" style="color:#c03a2b">${escapeHtml(error.message)}</div>`;
  } finally {
    refreshDocuments.disabled = false;
    // Keep spin class briefly so the animation plays fully
    setTimeout(() => refreshDocuments.classList.remove("is-spinning"), 700);
  }
}

async function loadProjects() {
  const data = await apiFetch("/api/v1/projects");
  projectsById = new Map(data.items.map((item) => [item.id, item]));
  renderProjectView();
}

function renderProjectView() {
  projectSection.classList.remove("is-hidden");
  historySection.classList.add("is-hidden");

  const docs = [...documentsById.values()];
  const projects = [...projectsById.values()];
  const builder = projectBuilderOpen ? renderProjectBuilder(docs) : "";
  const projectItems = projects.length
    ? projects.map(renderProjectItem).join("")
    : '<div class="muted-box">还没有项目，多选文档创建一个知识库范围</div>';

  documentList.innerHTML = `
    <button class="document-filter" type="button" data-toggle-project-builder>
      <span class="document-title">${projectBuilderOpen ? "收起新建项目" : "新建项目"}</span>
      <span class="document-meta">多选已索引文档作为知识库范围</span>
    </button>
    ${builder}
    <div class="project-list">${projectItems}</div>`;
  updateActiveDocumentStatus();
}

function renderProjectBuilder(docs) {
  const selectableDocs = docs.filter((doc) => doc.status === "completed");
  const docItems = selectableDocs.length
    ? selectableDocs.map((doc) => {
        const checked = selectedProjectDocumentIds.has(doc.id) ? " checked" : "";
        return `
          <label class="project-doc-option">
            <input type="checkbox" data-project-doc="${escapeHtml(doc.id)}"${checked}>
            <span>
              <span class="document-title">${escapeHtml(doc.filename)}</span>
              <span class="document-meta">${escapeHtml(docStatusText(doc))}</span>
            </span>
          </label>`;
      }).join("")
    : '<div class="muted-box">暂无已索引完成的文档</div>';

  return `
    <section class="project-builder">
      <input id="projectNameInput" class="project-name-input" type="text" placeholder="项目名称">
      <div class="project-docs">${docItems}</div>
      <button class="index-button project-create-button" type="button" data-create-project>创建项目</button>
    </section>`;
}

function renderProjectItem(project, index) {
  const names = project.document_ids
    .map((id) => documentsById.get(id)?.filename)
    .filter(Boolean);
  const meta = names.length ? names.join("、") : "暂无文档";
  return `
    <article class="document-item" style="animation-delay:${index * 40}ms">
      <div class="item-main">
        <button class="document-open" type="button" data-open-project="${escapeHtml(project.id)}">
          <span class="document-title">${escapeHtml(project.name)}</span>
          <span class="document-meta">${escapeHtml(project.document_count)} 个文档 · ${escapeHtml(meta)}</span>
        </button>
      </div>
      <button class="ghost-button" type="button" data-delete-project="${escapeHtml(project.id)}" title="删除项目">×</button>
    </article>`;
}

function renderHistoryView() {
  const project = projectsById.get(currentProjectId);
  projectSection.classList.add("is-hidden");
  historySection.classList.remove("is-hidden");
  historyTitle.textContent = project?.name || "对话历史";
  updateActiveDocumentStatus();
}

/* ─── Upload ─── */
uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const file = dropZone._droppedFile || fileInput.files?.[0];
  if (!file) {
    setUploadStatus("请先选择文件", "error");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  setBusy(uploadForm, true);
  setUploadStatus("正在上传并索引…");
  try {
    const result = await apiFetch("/api/v1/documents", { method: "POST", body: formData });
    if (result.status === "completed") {
      setUploadStatus("索引完成 ✓", "success");
    } else {
      setUploadStatus(`处理失败：${result.error || "未知错误"}`, "error");
    }
    fileInput.value = "";
    dropZone._droppedFile = null;
    updateSelectedFileLabel(null);
    await loadDocuments();
    await loadProjects();
  } catch (error) {
    setUploadStatus(error.message, "error");
  } finally {
    setBusy(uploadForm, false);
  }
});

fileInput.addEventListener("change", () => {
  dropZone._droppedFile = null;
  updateSelectedFileLabel(fileInput.files?.[0]);
});

function updateSelectedFileLabel(file) {
  fileLabel.textContent = file ? file.name : "上传文件";
  fileLabel.title = file ? file.name : "";
}

/* ─── Document selection & deletion ─── */
documentList.addEventListener("click", async (event) => {
  const builderBtn = event.target.closest("[data-toggle-project-builder]");
  if (builderBtn) {
    projectBuilderOpen = !projectBuilderOpen;
    renderProjectView();
    return;
  }

  const openProjectBtn = event.target.closest("[data-open-project]");
  if (openProjectBtn) {
    currentProjectId = openProjectBtn.dataset.openProject || "";
    currentConversationId = null;
    currentMessages = [];
    renderHistoryView();
    renderEmptyState();
    await loadHistory();
    return;
  }

  const createProjectBtn = event.target.closest("[data-create-project]");
  if (createProjectBtn) {
    await createProjectFromSelection(createProjectBtn);
    return;
  }

  const deleteProjectBtn = event.target.closest("[data-delete-project]");
  if (deleteProjectBtn) {
    await deleteProject(deleteProjectBtn.dataset.deleteProject, deleteProjectBtn);
    return;
  }

  const deleteBtn = event.target.closest("[data-delete-document]");
  if (!deleteBtn) return;

  const id = deleteBtn.dataset.deleteDocument;
  const article = deleteBtn.closest(".document-item");
  deleteBtn.disabled = true;
  setUploadStatus("正在删除…");

  try {
    await apiFetch(`/api/v1/documents/${encodeURIComponent(id)}`, { method: "DELETE" });
    if (article) {
      article.classList.add("is-removing");
      await sleep(200);
    }
    setUploadStatus("文档已删除", "success");
    await loadDocuments();
    await loadProjects();
  } catch (error) {
    setUploadStatus(error.message, "error");
    deleteBtn.disabled = false;
  }
});

documentList.addEventListener("change", (event) => {
  const checkbox = event.target.closest("[data-project-doc]");
  if (!checkbox) return;
  const id = checkbox.dataset.projectDoc;
  if (checkbox.checked) selectedProjectDocumentIds.add(id);
  else selectedProjectDocumentIds.delete(id);
});

async function createProjectFromSelection(button) {
  const input = document.querySelector("#projectNameInput");
  const documentIds = [...selectedProjectDocumentIds];
  if (!documentIds.length) {
    setUploadStatus("请至少选择一个已索引文档", "error");
    return;
  }
  const fallbackName = documentIds
    .map((id) => documentsById.get(id)?.filename)
    .filter(Boolean)
    .slice(0, 2)
    .join("、");
  const name = input.value.trim() || fallbackName || "未命名项目";

  button.disabled = true;
  try {
    await apiFetch("/api/v1/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, document_ids: documentIds }),
    });
    selectedProjectDocumentIds = new Set();
    projectBuilderOpen = false;
    setUploadStatus("项目已创建", "success");
    await loadProjects();
  } catch (error) {
    setUploadStatus(error.message, "error");
  } finally {
    button.disabled = false;
  }
}

async function deleteProject(projectId, button) {
  button.disabled = true;
  try {
    await apiFetch(`/api/v1/projects/${encodeURIComponent(projectId)}`, { method: "DELETE" });
    if (currentProjectId === projectId) {
      currentProjectId = "";
      currentConversationId = null;
      currentMessages = [];
      renderEmptyState();
    }
    await loadProjects();
    setUploadStatus("项目已删除", "success");
  } catch (error) {
    setUploadStatus(error.message, "error");
    button.disabled = false;
  }
}

/* ═══════════════════════════════════════════
   History
   ═══════════════════════════════════════════ */
async function loadHistory() {
  try {
    const params = currentProjectId
      ? `?project_id=${encodeURIComponent(currentProjectId)}&page_size=30`
      : "?page=1&page_size=30";
    const data = await apiFetch(`/api/v1/queries${params}`);
    historyCount.textContent = data.total ? String(data.total) : "";
    renderHistory(data.items);
  } catch (error) {
    historyList.innerHTML = `<div class="muted-box" style="color:#c03a2b">${escapeHtml(error.message)}</div>`;
  }
}

function renderHistory(items) {
  if (!items.length) {
    historyList.innerHTML = '<div class="muted-box">暂无历史记录</div>';
    return;
  }

  historyList.innerHTML = items.map((item, i) => {
    const key = item.conversation_id || item.id;
    return `
      <article class="history-item" data-history-id="${escapeHtml(key)}" style="animation-delay:${i * 30}ms">
        <button class="history-open" type="button" data-open-history="${escapeHtml(key)}">
          <span class="history-question">${escapeHtml(item.question)}</span>
          <span class="history-docs">${renderDocumentNames(item.document_ids || item.citations?.map((c) => c.document_id) || [])}</span>
          <span class="history-time">${escapeHtml(formatTime(item.created_at))}</span>
        </button>
        <button class="ghost-button" type="button" data-delete-history="${escapeHtml(key)}" title="删除">×</button>
      </article>`;
  }).join("");

  for (const item of items) {
    const key = item.conversation_id || item.id;
    const el = historyList.querySelector(`[data-history-id="${cssEscape(key)}"]`);
    if (el) el.historyItem = item;
  }
}

historyList.addEventListener("click", async (event) => {
  const deleteBtn = event.target.closest("[data-delete-history]");
  if (deleteBtn) {
    const id = deleteBtn.dataset.deleteHistory;
    deleteBtn.disabled = true;
    try {
      await apiFetch(`/api/v1/queries/${encodeURIComponent(id)}`, { method: "DELETE" });
      if (currentConversationId === id || currentMessages.some((m) => m.id === id)) {
        renderEmptyState();
      }
      await loadHistory();
      setStatus("历史已删除");
    } catch (error) {
      setStatus(error.message);
      deleteBtn.disabled = false;
    }
    return;
  }

  const openBtn = event.target.closest("[data-open-history]");
  if (!openBtn) return;
  const row = openBtn.closest(".history-item");
  const historyItem = row.historyItem;
  try {
    const data = await apiFetch(`/api/v1/queries/${encodeURIComponent(historyItem.conversation_id || historyItem.id)}`);
    currentConversationId = historyItem.conversation_id || historyItem.id;
    currentMessages = data.items;
    currentProjectId = historyItem.project_id || currentProjectId;
    updateActiveDocumentStatus();
    renderConversation();
    setStatus("历史对话");
  } catch (error) {
    setStatus(error.message);
  }
});

/* ═══════════════════════════════════════════
   Query / Chat
   ═══════════════════════════════════════════ */
questionInput.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
  event.preventDefault();
  if (!queryForm.querySelector(".send-button")?.disabled) {
    queryForm.requestSubmit();
  }
});

// Auto-resize textarea
questionInput.addEventListener("input", () => {
  questionInput.style.height = "auto";
  questionInput.style.height = Math.min(questionInput.scrollHeight, 200) + "px";
});

queryForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question) {
    setStatus("请先输入问题");
    questionInput.focus();
    return;
  }

  setBusy(queryForm, true);
  setStatus("正在生成…", "busy");

  const pending = { question, answer: "", citations: [], loading: true };
  currentMessages.push(pending);
  renderConversation();

  try {
    const result = await apiFetch("/api/v1/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        conversation_id: currentConversationId,
        project_id: currentProjectId || null,
        document_ids: currentProjectId
          ? null
          : [...documentsById.values()]
              .filter((doc) => doc.status === "completed")
              .map((doc) => doc.id),
        top_k: Number(topKInput.value || 5),
      }),
    });
    currentConversationId = result.conversation_id || currentConversationId;
    Object.assign(pending, {
      id: result.query_id,
      conversation_id: currentConversationId,
      answer: result.answer,
      citations: result.citations || [],
      loading: false,
    });
    renderConversation();
    questionInput.value = "";
    questionInput.style.height = "auto";
    setStatus("已完成");
    await loadHistory();
  } catch (error) {
    Object.assign(pending, { answer: error.message, citations: [], loading: false, error: true });
    renderConversation();
    setStatus("生成失败");
  } finally {
    setBusy(queryForm, false);
  }
});

/* ─── New conversation ─── */
refreshDocuments.addEventListener("click", async () => {
  await loadDocuments();
  await loadProjects();
  if (currentProjectId) await loadHistory();
});
backToProjects.addEventListener("click", () => {
  currentProjectId = "";
  currentConversationId = null;
  currentMessages = [];
  renderProjectView();
  renderEmptyState();
});
newConversation.addEventListener("click", () => {
  currentConversationId = null;
  currentMessages = [];
  renderEmptyState();
  updateActiveDocumentStatus();
});

/* ═══════════════════════════════════════════
   Render helpers
   ═══════════════════════════════════════════ */
function renderConversation() {
  if (!currentMessages.length) { renderEmptyState(); return; }
  conversation.innerHTML = currentMessages.map(renderExchange).join("");
  typesetMath(conversation);
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
        <div class="message-body markdown-body">
          ${exchange.loading
            ? '<span class="loader">emmm，让我看一下文档</span>'
            : renderMarkdown(exchange.answer)}
        </div>
      </article>
      ${renderCitations(exchange.citations || [])}
    </section>`;
}

function renderEmptyState() {
  currentMessages = [];
  conversation.innerHTML = `
    <div class="empty-state">
      <div class="empty-icon">
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
          <circle cx="20" cy="20" r="18" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
          <path d="M13 20h14M20 13v14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity="0.6"/>
        </svg>
      </div>
      <h3>今天想查点什么？</h3>
      <p>从左侧上传知识文件，然后直接提问。回答会带上引用来源，方便核对依据。</p>
      <div class="hint-chips">
        <span class="chip">📄 支持 PDF、Word、Markdown</span>
        <span class="chip">🔗 引用溯源</span>
        <span class="chip">💬 多轮对话</span>
      </div>
    </div>`;
}

function renderCitations(citations) {
  if (!citations.length) return "";
  const figureCount = citations.filter((c) => c.image_url).length;
  const summaryText = figureCount
    ? `引用来源 ${citations.length} 条 · 相关图片 ${figureCount} 张`
    : `引用来源 ${citations.length} 条`;
  const items = citations.map((c, i) => {
    const page = c.page_number ? ` · 第 ${c.page_number} 页` : "";
    const score = renderCitationScore(c);
    const media = renderCitationMedia(c);
    return `
      <article class="citation">
        <div class="citation-header">
          <span class="citation-index">${i + 1}</span>
          <span class="citation-title">${escapeHtml(c.source_name)}${escapeHtml(page)}</span>
          <span class="citation-score">${escapeHtml(score)}</span>
        </div>
        ${media}
        <div class="citation-text">${escapeHtml(c.text)}</div>
      </article>`;
  }).join("");

  return `
    <section class="citations">
      <details>
        <summary>${escapeHtml(summaryText)}</summary>
        <div class="citations-body">${items}</div>
      </details>
    </section>`;
}

function renderCitationMedia(citation) {
  if (!citation.image_url) return "";
  const caption = citation.caption || citation.text || "论文图片";
  return `
    <figure class="citation-figure">
      <a href="${escapeHtml(citation.image_url)}" target="_blank" rel="noreferrer">
        <img src="${escapeHtml(citation.image_url)}" alt="${escapeHtml(caption)}" loading="lazy">
      </a>
      ${caption ? `<figcaption>${escapeHtml(caption)}</figcaption>` : ""}
    </figure>`;
}

function renderCitationScore(citation) {
  if (citation.retrieval_role === "neighbor" || Number(citation.score || 0) <= 0) {
    return "相邻上下文";
  }
  return `score ${Number(citation.score).toFixed(3)}`;
}

function renderDocumentNames(ids) {
  const names = [...new Set(ids)].map((id) => documentsById.get(id)?.filename).filter(Boolean);
  return escapeHtml(names.length ? names.join("、") : "未关联文档");
}

function updateActiveDocumentStatus() {
  const project = projectsById.get(currentProjectId);
  const name = project
    ? `${project.name} · ${project.document_count} 个文档`
    : "全部已索引文档";
  setStatus(`范围：${name}`);
}

/* ═══════════════════════════════════════════
   Markdown renderer
   ═══════════════════════════════════════════ */
function renderMarkdown(value) {
  const lines = String(value ?? "").split(/\r?\n/);
  const blocks = [];
  let paragraph = [], list = [], inCode = false, codeLines = [], inMath = false, mathLines = [];

  const flush = () => {
    if (paragraph.length) { blocks.push(`<p>${renderInlineMarkdown(paragraph.join(" "))}</p>`); paragraph = []; }
    if (list.length) { blocks.push(`<ul>${list.map((li) => `<li>${renderInlineMarkdown(li)}</li>`).join("")}</ul>`); list = []; }
  };

  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      if (inCode) { blocks.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`); codeLines = []; inCode = false; }
      else { flush(); inCode = true; }
      continue;
    }
    if (inCode) { codeLines.push(line); continue; }
    if (inMath) {
      if (line.trim().endsWith("$$")) {
        const content = line.trim() === "$$" ? "" : line.trim().slice(0, -2);
        if (content) mathLines.push(content);
        blocks.push(renderMathBlock(mathLines.join("\n")));
        mathLines = [];
        inMath = false;
      } else {
        mathLines.push(line);
      }
      continue;
    }
    if (line.trim().startsWith("$$")) {
      flush();
      const remainder = line.trim().slice(2);
      if (remainder.endsWith("$$") && remainder.length > 2) {
        blocks.push(renderMathBlock(remainder.slice(0, -2)));
      } else if (remainder) {
        inMath = true;
        mathLines.push(remainder);
      } else {
        inMath = true;
      }
      continue;
    }
    const image = line.match(/^!\[([^\]]*)\]\(([^)\s]+)\)$/);
    if (image) {
      flush();
      blocks.push(renderMarkdownImage(image[2], image[1]));
      continue;
    }
    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      flush();
      const level = heading[1].length;
      blocks.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
      continue;
    }
    const bullet = line.match(/^\s*[-*]\s+(.+)$/);
    if (bullet) { if (paragraph.length) { blocks.push(`<p>${renderInlineMarkdown(paragraph.join(" "))}</p>`); paragraph = []; } list.push(bullet[1]); continue; }
    if (!line.trim()) { flush(); continue; }
    if (list.length) { blocks.push(`<ul>${list.map((li) => `<li>${renderInlineMarkdown(li)}</li>`).join("")}</ul>`); list = []; }
    paragraph.push(line.trim());
  }

  if (inCode) blocks.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
  if (inMath) blocks.push(renderMathBlock(mathLines.join("\n")));
  flush();
  return blocks.join("");
}

function renderMathBlock(value) {
  return `<div class="math-block">$$${escapeHtml(value)}$$</div>`;
}

function renderMarkdownImage(url, alt) {
  return `
    <figure class="markdown-figure">
      <a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">
        <img src="${escapeHtml(url)}" alt="${escapeHtml(alt)}" loading="lazy">
      </a>
    </figure>`;
}

function renderInlineMarkdown(value) {
  let html = escapeHtml(value);
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  return html;
}

function typesetMath(root) {
  if (!window.MathJax?.typesetPromise) return;
  window.MathJax.typesetPromise([root]).catch(() => {});
}

/* ═══════════════════════════════════════════
   Utilities
   ═══════════════════════════════════════════ */
function formatTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(date);
}

function cssEscape(value) {
  return window.CSS?.escape ? CSS.escape(value) : String(value).replaceAll('"', '\\"');
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

/* ─── Init ─── */
(async function initialize() {
  await loadDocuments();
  await loadProjects();
})();
