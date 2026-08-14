const form = document.querySelector("#run-form");
const ideaInput = document.querySelector("#idea");
const characterCount = document.querySelector("#character-count");
const runButton = document.querySelector("#run-button");
const runButtonLabel = document.querySelector("#run-button-label");
const formMessage = document.querySelector("#form-message");
const connectionStatus = document.querySelector("#connection-status");
const environment = document.querySelector(".environment");
const emptyState = document.querySelector("#empty-state");
const runResults = document.querySelector("#run-results");
const runMeta = document.querySelector("#run-meta");
const timeline = document.querySelector("#timeline");
const toast = document.querySelector("#toast");
let latestResult = null;
let toastTimer = null;

const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

function showToast(message) {
  toast.textContent = message;
  toast.dataset.visible = "true";
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => { toast.dataset.visible = "false"; }, 1800);
}

async function checkHealth() {
  try {
    const response = await fetch("/api/health", { cache: "no-store" });
    if (!response.ok) throw new Error("offline");
    const payload = await response.json();
    environment.dataset.online = "true";
    connectionStatus.textContent = payload.api_key_required
      ? "本地编排器在线 · 需要 API Key"
      : "本地编排器在线 · 无需 API Key";
  } catch {
    environment.dataset.online = "false";
    connectionStatus.textContent = "本地编排器未连接";
  }
}

function setLoading(loading) {
  runButton.disabled = loading;
  runButton.dataset.loading = String(loading);
  ideaInput.disabled = loading;
  runButtonLabel.textContent = loading ? "Agents 正在协作…" : "运行完整流水线";
}

function renderTimeline(stages) {
  timeline.innerHTML = stages.map((stage, index) => `
    <li data-status="${escapeHtml(stage.status)}" title="${escapeHtml(stage.summary)}">
      <strong>${String(index + 1).padStart(2, "0")} · ${escapeHtml(stage.label)}</strong>
      <span>${escapeHtml(stage.duration_ms)}ms · ${escapeHtml(stage.status)}</span>
    </li>
  `).join("");
}

function renderSpec(result) {
  const spec = result.product_spec;
  const architecture = result.architecture;
  document.querySelector("#panel-spec").innerHTML = `
    <h3 class="artifact-title">${escapeHtml(spec.project_name)}</h3>
    <p class="artifact-copy">${escapeHtml(spec.one_liner)}</p>
    <dl class="metric-grid">
      <div><dt>核心能力</dt><dd>${spec.core_features.length} 项</dd></div>
      <div><dt>API 边界</dt><dd>${architecture.api_design.length} 个</dd></div>
      <div><dt>部署目标</dt><dd>${escapeHtml(architecture.deploy_target)}</dd></div>
    </dl>
    <ul class="feature-list">
      ${spec.core_features.map((feature, index) => `
        <li><span class="item-index">0${index + 1}</span><div class="item-detail"><strong>${escapeHtml(feature)}</strong><span>${escapeHtml(spec.user_stories[index]?.so_that || "进入 MVP 范围")}</span></div></li>
      `).join("")}
    </ul>
  `;
}

function renderDag(result) {
  const nodes = result.dag.nodes;
  document.querySelector("#panel-dag").innerHTML = `
    <h3 class="artifact-title">${nodes.length} 个可执行节点</h3>
    <p class="artifact-copy">节点已经过实际 DAG 校验，并保留负责人、风险和依赖关系。</p>
    <ul class="dag-list">
      ${nodes.map((node, index) => `
        <li>
          <span class="item-index">${String(index + 1).padStart(2, "0")}</span>
          <div class="item-detail"><strong>${escapeHtml(node.id)}</strong><span>${escapeHtml(node.owner)} · ${escapeHtml(node.risk)} · 依赖 ${escapeHtml(node.depends.join(", ") || "无")}</span></div>
        </li>
      `).join("")}
    </ul>
  `;
}

function renderFiles(result) {
  const file = result.generated_files[0];
  document.querySelector("#panel-files").innerHTML = `
    <div class="file-toolbar">
      <span class="file-name">${escapeHtml(file.path)}</span>
      <button class="copy-button" id="copy-file" type="button">复制代码</button>
    </div>
    <pre><code>${escapeHtml(file.content)}</code></pre>
  `;
  document.querySelector("#copy-file").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(file.content);
      showToast("代码已复制");
    } catch {
      showToast("浏览器未授予剪贴板权限");
    }
  });
}

function renderQuality(result) {
  const quality = result.quality;
  const items = [
    ["UI 静态审计", quality.ui?.passed ? "通过" : "需要复核", `${quality.ui?.findings?.length || 0} 个发现`],
    ["Reviewer", quality.review?.passed ? "通过" : "未通过", quality.review?.summary || "无报告"],
    ["Security", quality.security?.passed ? "通过" : "阻塞", `风险等级 ${quality.security?.risk_level || "unknown"}`],
    ["Warnings", quality.warnings.length ? "需要关注" : "无", `${quality.warnings.length} 条提醒`],
  ];
  document.querySelector("#panel-quality").innerHTML = `
    <div class="quality-verdict">${result.status === "completed" ? "全部质量门已完成" : "流水线被阻塞"}</div>
    <ul class="quality-list">
      ${items.map((item, index) => `
        <li><span class="item-index">0${index + 1}</span><div class="item-detail"><strong>${escapeHtml(item[0])} · ${escapeHtml(item[1])}</strong><span>${escapeHtml(item[2])}</span></div></li>
      `).join("")}
    </ul>
  `;
}

function renderResult(result) {
  latestResult = result;
  emptyState.hidden = true;
  runResults.hidden = false;
  runMeta.hidden = false;
  runMeta.textContent = `${result.run_id} · ${result.duration_ms}ms · ${result.llm_calls} calls`;
  renderTimeline(result.stages);
  renderSpec(result);
  renderDag(result);
  renderFiles(result);
  renderQuality(result);
  document.querySelector("#tab-spec").click();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  formMessage.textContent = "";
  const idea = ideaInput.value.trim();
  if (!idea) {
    formMessage.textContent = "请先输入一句产品想法。";
    ideaInput.focus();
    return;
  }
  setLoading(true);
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idea }),
      signal: controller.signal,
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error?.message || "流水线运行失败。");
    renderResult(payload);
    showToast("Mock 流水线运行完成");
  } catch (error) {
    formMessage.textContent = error.name === "AbortError" ? "运行超时，请重试。" : error.message;
  } finally {
    window.clearTimeout(timeout);
    setLoading(false);
  }
});

ideaInput.addEventListener("input", () => { characterCount.textContent = ideaInput.value.length; });

document.querySelectorAll("[data-example]").forEach((button) => {
  button.addEventListener("click", () => {
    ideaInput.value = button.dataset.example;
    ideaInput.dispatchEvent(new Event("input"));
    ideaInput.focus();
  });
});

document.querySelectorAll('[role="tab"]').forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll('[role="tab"]').forEach((candidate) => {
      const selected = candidate === tab;
      candidate.setAttribute("aria-selected", String(selected));
      document.querySelector(`#${candidate.getAttribute("aria-controls")}`).hidden = !selected;
    });
  });
});

void checkHealth();
