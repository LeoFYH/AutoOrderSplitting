const state = {
  templateItems: [],
  sourceName: "",
  result: null,
  activeTab: "lines",
  skipKeywords: [],
  activeModule: "split",
  supplierMarkerResult: null,
};

const fields = ["owner", "supplier", "product", "unit", "quantity", "price", "note", "agreement_price"];

const el = {
  templateStatus: document.querySelector("#templateStatus"),
  templateForm: document.querySelector("#templateForm"),
  templateFile: document.querySelector("#templateFile"),
  templateFileName: document.querySelector("#templateFileName"),
  templateSearch: document.querySelector("#templateSearch"),
  templateCount: document.querySelector("#templateCount"),
  templateTableBody: document.querySelector("#templateTable tbody"),
  addTemplateRow: document.querySelector("#addTemplateRow"),
  saveTemplate: document.querySelector("#saveTemplate"),
  orderForm: document.querySelector("#orderForm"),
  orderFiles: document.querySelector("#orderFiles"),
  orderFileSummary: document.querySelector("#orderFileSummary"),
  orderFileList: document.querySelector("#orderFileList"),
  skipKeywordList: document.querySelector("#skipKeywordList"),
  addSkipKeyword: document.querySelector("#addSkipKeyword"),
  fuzzyThreshold: document.querySelector("#fuzzyThreshold"),
  message: document.querySelector("#message"),
  downloadLinks: document.querySelector("#downloadLinks"),
  debugExportLink: document.querySelector("#debugExportLink"),
  summaryStrip: document.querySelector("#summaryStrip"),
  resultHead: document.querySelector("#resultTable thead"),
  resultBody: document.querySelector("#resultTable tbody"),
  splitModule: document.querySelector("#splitModule"),
  supplierMarkerModule: document.querySelector("#supplierMarkerModule"),
  supplierMarkerForm: document.querySelector("#supplierMarkerForm"),
  supplierPurchaseFile: document.querySelector("#supplierPurchaseFile"),
  supplierPurchaseFileName: document.querySelector("#supplierPurchaseFileName"),
  supplierKeyword: document.querySelector("#supplierKeyword"),
  keepFirstCustomerUncolored: document.querySelector("#keepFirstCustomerUncolored"),
  supplierMarkerMessage: document.querySelector("#supplierMarkerMessage"),
  supplierMarkerSummary: document.querySelector("#supplierMarkerSummary"),
  supplierMarkerDownloads: document.querySelector("#supplierMarkerDownloads"),
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
  el.templateFile.addEventListener("change", renderTemplateFileName);
  el.templateSearch.addEventListener("input", renderTemplateTable);
  el.addTemplateRow.addEventListener("click", addTemplateRow);
  el.saveTemplate.addEventListener("click", saveTemplate);
  el.orderFiles.addEventListener("change", renderOrderFiles);
  el.orderForm.addEventListener("submit", processOrders);
  el.addSkipKeyword.addEventListener("click", addSkipKeyword);
  el.supplierMarkerForm.addEventListener("submit", processSupplierAnnotation);
  el.supplierPurchaseFile.addEventListener("change", renderSupplierPurchaseFileName);

  document.querySelectorAll(".module-tab").forEach((button) => {
    button.addEventListener("click", () => switchModule(button.dataset.module));
  });

  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeTab = button.dataset.tab;
      document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab === button));
      renderResultTable();
    });
  });
}

function switchModule(moduleName) {
  state.activeModule = moduleName;
  document.querySelectorAll(".module-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.module === moduleName);
  });
  el.splitModule.classList.toggle("hidden", moduleName !== "split");
  el.supplierMarkerModule.classList.toggle("hidden", moduleName !== "supplier-marker");
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

function renderTemplateFileName() {
  const file = el.templateFile.files[0];
  el.templateFileName.textContent = file ? file.name : "未选择采购总模板";
}

function renderOrderFiles() {
  const files = Array.from(el.orderFiles.files || []);
  if (!files.length) {
    el.orderFileSummary.textContent = "未选择订单";
    el.orderFileList.textContent = "未选择订单";
    return;
  }
  el.orderFileSummary.textContent = files.length === 1 ? files[0].name : `已选择 ${files.length} 个订单文件`;
  el.orderFileList.innerHTML = files.map((file) => `<div>${escapeHtml(file.name)}</div>`).join("");
}

function renderSupplierPurchaseFileName() {
  const file = el.supplierPurchaseFile.files[0];
  el.supplierPurchaseFileName.textContent = file ? file.name : "未选择采购单";
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
  const templateFile = el.templateFile.files[0];
  if (!templateFile && !state.templateItems.length) {
    setMessage("请选择采购总模板", true);
    return;
  }
  if (!el.orderFiles.files.length) {
    setMessage("请选择订单文件", true);
    return;
  }

  if (!templateFile) {
    await saveTemplate();
    if (el.message.classList.contains("error")) {
      return;
    }
  }

  const form = new FormData();
  if (templateFile) {
    form.append("template", templateFile);
  }
  Array.from(el.orderFiles.files).forEach((file) => form.append("orders", file));
  form.append("skipKeywords", collectSkipKeywords().join(","));
  form.append("fuzzyThreshold", el.fuzzyThreshold.value);

  setMessage("正在合并订单并匹配模板...");
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

async function processSupplierAnnotation(event) {
  event.preventDefault();
  const file = el.supplierPurchaseFile.files[0];
  if (!file) {
    setSupplierMarkerMessage("请选择蔬东坡采购单文件", true);
    return;
  }

  const form = new FormData();
  form.append("purchase", file);
  form.append("supplierKeyword", el.supplierKeyword.value.trim());
  form.append("keepFirstCustomerUncolored", el.keepFirstCustomerUncolored.checked ? "true" : "false");

  setSupplierMarkerMessage("正在按供应商客户标注...");
  el.supplierMarkerDownloads.innerHTML = "";
  el.supplierMarkerSummary.innerHTML = "";
  try {
    const data = await apiJson("/api/supplier-annotate", { method: "POST", body: form });
    state.supplierMarkerResult = data;
    renderSupplierMarkerResult();
    setSupplierMarkerMessage("已生成供应商采购单标注");
  } catch (error) {
    setSupplierMarkerMessage(error.message, true);
  }
}

function renderSupplierMarkerResult() {
  const result = state.supplierMarkerResult || {};
  const summary = result.summary || {};
  const supplierText = (result.suppliers || []).slice(0, 6).join("、") || "无";
  const customerText = (result.customers || []).slice(0, 10).join("、") || "无";
  el.supplierMarkerSummary.innerHTML = `
    <div><strong>${escapeHtml(summary.matchedRows || 0)}</strong><span>标注行</span></div>
    <div><strong>${escapeHtml(summary.supplierCount || 0)}</strong><span>供应商</span></div>
    <div><strong>${escapeHtml(summary.customerCount || 0)}</strong><span>客户</span></div>
    <p>供应商：${escapeHtml(supplierText)}</p>
    <p>客户：${escapeHtml(customerText)}</p>
  `;
  const download = result.downloads?.annotated;
  el.supplierMarkerDownloads.innerHTML = download
    ? `<a href="${download}">下载供应商采购单标注.xlsx</a>`
    : "";
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
      ["供应商", "学校", "商品", "单位", "数量", "单价", "商品备注", "订单备注", "备注"],
      (result.lines || []).map((row) => [row.supplier, row.owner, row.product, row.unit, row.quantity, row.price, row.productNote, row.orderNote, row.note]),
    );
    return;
  }
  if (tab === "unmatched") {
    renderSimpleTable(
      ["文件", "行", "订单号", "学校", "商品", "数量", "单位", "商品备注", "订单备注", "备注", "原因"],
      (result.unmatched || []).map((row) => [row.file, row.row, row.orderNo, row.customer, row.product, row.quantity, row.unit, row.productNote, row.orderNote, row.note, row.reason]),
    );
    return;
  }
  if (tab === "warnings") {
    renderSimpleTable(["警告"], (result.warnings || []).map((warning) => [warning]));
    return;
  }
  renderSimpleTable(
    ["文件", "行", "订单号", "学校", "商品", "数量", "单位", "商品备注", "订单备注", "备注", "原因"],
    (result.skipped || []).map((row) => [row.file, row.row, row.orderNo, row.customer, row.product, row.quantity, row.unit, row.productNote, row.orderNote, row.note, row.reason]),
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
  let response;
  try {
    response = await fetch(url, options);
  } catch (error) {
    throw new Error("请求没有连到服务器，可能是服务重启、处理超时或上传文件过大。请刷新页面重试；如果连续出现，请检查服务器日志。");
  }
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

function setSupplierMarkerMessage(text, isError = false) {
  el.supplierMarkerMessage.textContent = text;
  el.supplierMarkerMessage.classList.toggle("error", isError);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
