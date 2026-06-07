const state = {
  templateItems: [],
  sourceName: "",
  result: null,
  activeTab: "lines",
  skipKeywords: ["营养餐"],
};

const fields = ["owner", "supplier", "product", "unit", "quantity", "price", "note", "agreement_price"];

const el = {
  templateStatus: document.querySelector("#templateStatus"),
  templateForm: document.querySelector("#templateForm"),
  templateFile: document.querySelector("#templateFile"),
  templateSearch: document.querySelector("#templateSearch"),
  templateCount: document.querySelector("#templateCount"),
  templateTableBody: document.querySelector("#templateTable tbody"),
  addTemplateRow: document.querySelector("#addTemplateRow"),
  saveTemplate: document.querySelector("#saveTemplate"),
  orderForm: document.querySelector("#orderForm"),
  orderFiles: document.querySelector("#orderFiles"),
  orderFileList: document.querySelector("#orderFileList"),
  skipKeywordList: document.querySelector("#skipKeywordList"),
  addSkipKeyword: document.querySelector("#addSkipKeyword"),
  fuzzyThreshold: document.querySelector("#fuzzyThreshold"),
  includeTemplateRows: document.querySelector("#includeTemplateRows"),
  message: document.querySelector("#message"),
  downloadLinks: document.querySelector("#downloadLinks"),
  debugExportLink: document.querySelector("#debugExportLink"),
  summaryStrip: document.querySelector("#summaryStrip"),
  resultHead: document.querySelector("#resultTable thead"),
  resultBody: document.querySelector("#resultTable tbody"),
};

document.addEventListener("DOMContentLoaded", init);

function init() {
  bindEvents();
  renderSkipKeywords();
  loadTemplate();
  renderResultTable();
}

function bindEvents() {
  el.templateForm.addEventListener("submit", uploadTemplate);
  el.templateSearch.addEventListener("input", renderTemplateTable);
  el.addTemplateRow.addEventListener("click", addTemplateRow);
  el.saveTemplate.addEventListener("click", saveTemplate);
  el.orderFiles.addEventListener("change", renderOrderFiles);
  el.orderForm.addEventListener("submit", processOrders);
  el.addSkipKeyword.addEventListener("click", addSkipKeyword);

  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeTab = button.dataset.tab;
      document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab === button));
      renderResultTable();
    });
  });
}

async function loadTemplate() {
  try {
    const data = await apiJson("/api/template");
    state.templateItems = data.items || [];
    state.sourceName = data.sourceName || "";
    updateTemplateStatus();
    renderTemplateTable();
  } catch (error) {
    setMessage(error.message, true);
  }
}

async function uploadTemplate(event) {
  event.preventDefault();
  const file = el.templateFile.files[0];
  if (!file) {
    setMessage("请选择模板文件", true);
    return;
  }

  const form = new FormData();
  form.append("template", file);
  setMessage("正在上传模板...");
  try {
    const data = await apiJson("/api/template/upload", { method: "POST", body: form });
    state.templateItems = data.items || [];
    state.sourceName = data.sourceName || file.name;
    updateTemplateStatus();
    renderTemplateTable();
    setMessage(`模板已导入：${state.templateItems.length} 行`);
  } catch (error) {
    setMessage(error.message, true);
  }
}

function addTemplateRow() {
  collectTemplateItems();
  const maxRow = state.templateItems.reduce((max, item) => Math.max(max, Number(item.row_number || 0)), 4);
  state.templateItems.unshift({
    row_number: maxRow + 1,
    owner: "",
    supplier: "",
    product: "",
    unit: "",
    quantity: "0",
    price: "",
    note: "",
    agreement_price: "",
  });
  el.templateSearch.value = "";
  renderTemplateTable();
}

async function saveTemplate() {
  collectTemplateItems();
  setMessage("正在保存模板...");
  try {
    const data = await apiJson("/api/template", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sourceName: state.sourceName || "手动模板", items: state.templateItems }),
    });
    state.templateItems = data.items || [];
    updateTemplateStatus();
    renderTemplateTable();
    setMessage(`模板已保存：${state.templateItems.length} 行`);
  } catch (error) {
    setMessage(error.message, true);
  }
}

function renderTemplateTable() {
  const filter = el.templateSearch.value.trim().toLowerCase();
  const rows = state.templateItems
    .map((item, index) => ({ item, index }))
    .filter(({ item }) => {
      if (!filter) return true;
      return fields.some((field) => String(item[field] ?? "").toLowerCase().includes(filter));
    });

  el.templateCount.textContent = `${state.templateItems.length} 行`;
  el.templateTableBody.innerHTML = "";

  if (!rows.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td class="empty-row" colspan="9">没有模板行</td>`;
    el.templateTableBody.appendChild(tr);
    return;
  }

  const fragment = document.createDocumentFragment();
  for (const { item, index } of rows) {
    const tr = document.createElement("tr");
    tr.dataset.index = String(index);
    tr.innerHTML = `
      ${inputCell("owner", item.owner)}
      ${inputCell("supplier", item.supplier)}
      ${inputCell("product", item.product)}
      ${inputCell("unit", item.unit)}
      ${inputCell("quantity", item.quantity)}
      ${inputCell("price", item.price)}
      ${inputCell("note", item.note)}
      ${inputCell("agreement_price", item.agreement_price)}
      <td><button class="row-delete" type="button" title="删除">×</button></td>
    `;
    tr.querySelector(".row-delete").addEventListener("click", () => {
      collectTemplateItems();
      state.templateItems.splice(index, 1);
      renderTemplateTable();
    });
    fragment.appendChild(tr);
  }
  el.templateTableBody.appendChild(fragment);
}

function inputCell(field, value) {
  const safeValue = escapeHtml(value ?? "");
  const type = field === "quantity" || field === "price" ? "text" : "text";
  return `<td><input data-field="${field}" type="${type}" value="${safeValue}" /></td>`;
}

function collectTemplateItems() {
  const rows = el.templateTableBody.querySelectorAll("tr[data-index]");
  for (const row of rows) {
    const index = Number(row.dataset.index);
    const item = state.templateItems[index];
    if (!item) continue;
    row.querySelectorAll("input[data-field]").forEach((input) => {
      item[input.dataset.field] = input.value.trim();
    });
  }
}

function updateTemplateStatus() {
  const name = state.sourceName || "当前模板";
  el.templateStatus.textContent = state.templateItems.length
    ? `${name} · ${state.templateItems.length} 行`
    : "未上传模板";
}

function renderOrderFiles() {
  const files = Array.from(el.orderFiles.files || []);
  if (!files.length) {
    el.orderFileList.textContent = "未选择订单";
    return;
  }
  el.orderFileList.innerHTML = files.map((file) => `<div>${escapeHtml(file.name)}</div>`).join("");
}

function renderSkipKeywords() {
  const values = state.skipKeywords.length ? state.skipKeywords : [""];
  el.skipKeywordList.innerHTML = "";
  const fragment = document.createDocumentFragment();

  values.forEach((value, index) => {
    const row = document.createElement("div");
    row.className = "skip-keyword-row";
    row.innerHTML = `
      <input class="skip-keyword-input" type="text" value="${escapeHtml(value)}" placeholder="例如：营养餐" />
      <button class="skip-keyword-delete" type="button" title="删除">×</button>
    `;
    row.querySelector(".skip-keyword-input").addEventListener("input", (event) => {
      state.skipKeywords[index] = event.target.value;
    });
    row.querySelector(".skip-keyword-delete").addEventListener("click", () => {
      const values = collectSkipKeywords({ keepEmpty: true });
      values.splice(index, 1);
      state.skipKeywords = values.filter(Boolean);
      renderSkipKeywords();
    });
    fragment.appendChild(row);
  });

  el.skipKeywordList.appendChild(fragment);
}

function addSkipKeyword() {
  state.skipKeywords = collectSkipKeywords({ keepEmpty: true });
  state.skipKeywords.push("");
  renderSkipKeywords();
  const inputs = el.skipKeywordList.querySelectorAll(".skip-keyword-input");
  inputs[inputs.length - 1]?.focus();
}

function collectSkipKeywords(options = {}) {
  const values = Array.from(el.skipKeywordList.querySelectorAll(".skip-keyword-input"))
    .map((input) => input.value.trim());
  if (options.keepEmpty) {
    return values;
  }
  state.skipKeywords = values.filter(Boolean);
  return state.skipKeywords;
}

async function processOrders(event) {
  event.preventDefault();
  collectTemplateItems();
  if (!state.templateItems.length) {
    setMessage("请先上传模板", true);
    return;
  }
  if (!el.orderFiles.files.length) {
    setMessage("请选择订单文件", true);
    return;
  }

  await saveTemplate();
  if (el.message.classList.contains("error")) {
    return;
  }

  const form = new FormData();
  Array.from(el.orderFiles.files).forEach((file) => form.append("orders", file));
  form.append("skipKeywords", collectSkipKeywords().join(","));
  form.append("fuzzyThreshold", el.fuzzyThreshold.value);
  form.append("includeTemplateRows", el.includeTemplateRows.checked ? "true" : "false");

  setMessage("正在匹配订单...");
  el.downloadLinks.innerHTML = "";
  try {
    const data = await apiJson("/api/process", { method: "POST", body: form });
    state.result = data;
    renderSummary();
    renderDownloads();
    renderResultTable();
    if ((data.summary?.unmatchedRows || 0) > 0) {
      state.activeTab = "unmatched";
      document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === "unmatched"));
      renderResultTable();
      setMessage(`还有 ${data.summary.unmatchedRows} 行未匹配，先补模板后再生成采购单`, true);
    } else {
      setMessage("已生成采购单");
    }
  } catch (error) {
    setMessage(error.message, true);
  }
}

function renderSummary() {
  const summary = state.result?.summary || {};
  const values = [
    [summary.purchaseRows || 0, "采购行"],
    [summary.unmatchedRows || 0, "未匹配"],
    [summary.skippedRows || 0, "跳过"],
    [summary.warningRows || 0, "警告"],
  ];
  el.summaryStrip.innerHTML = values
    .map(([value, label]) => `<div><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`)
    .join("");
}

function renderDownloads() {
  const downloads = state.result?.downloads;
  if (downloads?.debug) {
    el.debugExportLink.href = downloads.debug;
    el.debugExportLink.classList.remove("hidden");
  } else {
    el.debugExportLink.href = "#";
    el.debugExportLink.classList.add("hidden");
  }
  if (!downloads?.debug && !downloads?.purchase) {
    el.downloadLinks.innerHTML = "";
    return;
  }
  const links = [];
  if (downloads.debug) {
    links.push(`<a href="${downloads.debug}" class="debug-link">导出调试明细.xlsx</a>`);
  }
  if (downloads.purchase) {
    links.push(`<a href="${downloads.purchase}">下载采购单.xlsx</a>`);
  }
  el.downloadLinks.innerHTML = links.join("");
}

function renderResultTable() {
  const result = state.result;
  const tab = state.activeTab;
  if (!result) {
    renderSimpleTable(["状态"], [["等待生成"]]);
    return;
  }

  if (tab === "lines") {
    renderSimpleTable(
      ["供应商", "学校", "商品", "单位", "数量", "单价", "备注"],
      (result.lines || []).map((row) => [row.supplier, row.owner, row.product, row.unit, row.quantity, row.price, row.note]),
    );
    return;
  }
  if (tab === "unmatched") {
    renderSimpleTable(
      ["文件", "行", "订单号", "学校", "商品", "数量", "单位", "备注", "原因"],
      (result.unmatched || []).map((row) => [row.file, row.row, row.orderNo, row.customer, row.product, row.quantity, row.unit, row.note, row.reason]),
    );
    return;
  }
  if (tab === "warnings") {
    renderSimpleTable(["警告"], (result.warnings || []).map((warning) => [warning]));
    return;
  }
  renderSimpleTable(
    ["文件", "行", "订单号", "学校", "商品", "数量", "单位", "备注", "原因"],
    (result.skipped || []).map((row) => [row.file, row.row, row.orderNo, row.customer, row.product, row.quantity, row.unit, row.note, row.reason]),
  );
}

function renderSimpleTable(headers, rows) {
  el.resultHead.innerHTML = `<tr>${headers.map((header) => `<th>${escapeHtml(header)}</th>`).join("")}</tr>`;
  if (!rows.length) {
    el.resultBody.innerHTML = `<tr><td class="empty-row" colspan="${headers.length}">没有数据</td></tr>`;
    return;
  }
  el.resultBody.innerHTML = rows
    .map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell ?? "")}</td>`).join("")}</tr>`)
    .join("");
}

async function apiJson(url, options = {}) {
  const response = await fetch(url, options);
  const rawText = await response.text();
  let data = {};
  if (rawText) {
    try {
      data = JSON.parse(rawText);
    } catch {
      data = {};
    }
  }
  if (!response.ok) {
    const details = Array.isArray(data.details) && data.details.length ? `：${data.details.join("；")}` : "";
    const fallback = rawText ? rawText.slice(0, 200) : "请求失败";
    throw new Error(`${data.error || fallback}${details}`);
  }
  return data;
}

function setMessage(text, isError = false) {
  el.message.textContent = text;
  el.message.classList.toggle("error", isError);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
