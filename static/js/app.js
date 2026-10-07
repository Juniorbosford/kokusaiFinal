const navLinks = document.querySelectorAll(".nav-link");
const views = document.querySelectorAll(".view");
const canWrite = document.body.dataset.canWrite === "true";
const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";

const VIEW_META = {
  dashboard:{kicker:"Central operacional", title:"Visão geral", subtitle:"Indicadores essenciais da operação."},
  compras:{kicker:"Movimentações", title:"Compras", subtitle:"Entradas registradas e histórico de fornecedores."},
  vendas:{kicker:"Movimentações", title:"Vendas", subtitle:"Saídas, clientes e valores movimentados."},
  encomendas:{kicker:"Operação", title:"Encomendas", subtitle:"Prioridades, prazos e entregas pendentes."},
  relatorios:{kicker:"Inteligência comercial", title:"Relatórios", subtitle:"Desempenho mensal por família e gangue."},
  reunioes:{kicker:"Agenda", title:"Reuniões", subtitle:"Compromissos e alinhamentos externos."},
  familias:{kicker:"Relacionamento", title:"Famílias", subtitle:"Mercados, responsáveis e condições comerciais."},
  metas:{kicker:"Controle semanal", title:"Salas de Meta", subtitle:"Comprovantes, conferência e fechamento."},
  "registro-bau":{kicker:"Arquivo", title:"Registro Baú", subtitle:"Fotos do baú guardadas para consulta futura."},
  craft:{kicker:"Produção", title:"Craft", subtitle:"Cálculo objetivo de materiais e faltas."},
};

function csrfHeaders(headers = {}){
  return csrfToken ? {...headers, "X-CSRF-Token": csrfToken} : headers;
}

function activateView(target){
  navLinks.forEach(btn => btn.classList.toggle("active", btn.dataset.target === target));
  views.forEach(view => view.classList.toggle("active", view.id === target));
  const meta = VIEW_META[target] || VIEW_META.dashboard;
  const kicker = document.getElementById("topbarKicker");
  const title = document.getElementById("topbarTitle");
  const subtitle = document.getElementById("topbarSubtitle");
  if(kicker) kicker.textContent = meta.kicker;
  if(title) title.textContent = meta.title;
  if(subtitle) subtitle.textContent = meta.subtitle;
  document.title = `${meta.title} | Kokusai`;
  window.scrollTo({top:0, behavior:"smooth"});
}

function syncDisclosurePanel(panel, open){
  if(!panel) return;
  panel.classList.toggle("is-collapsed", !open);
  const button = panel.querySelector(":scope > .panel-head .panel-disclosure-toggle");
  if(!button) return;
  button.setAttribute("aria-expanded", String(open));
  button.classList.toggle("active", open);
  const label = button.querySelector(".panel-disclosure-label");
  if(label) label.textContent = open ? "Recolher" : (panel.dataset.disclosureLabel || "Abrir");
  const symbol = button.querySelector(".panel-disclosure-symbol");
  if(symbol) symbol.textContent = open ? "−" : "+";
}

function initializeDisclosurePanels(){
  document.querySelectorAll("[data-disclosure-panel]").forEach(panel => {
    const head = panel.querySelector(":scope > .panel-head");
    if(!head || head.querySelector(".panel-disclosure-toggle")) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "panel-disclosure-toggle";
    button.innerHTML = '<span class="panel-disclosure-symbol" aria-hidden="true">+</span><span class="panel-disclosure-label"></span>';
    head.appendChild(button);
    const startsOpen = panel.dataset.disclosureOpen === "true";
    syncDisclosurePanel(panel, startsOpen);
    button.addEventListener("click", () => syncDisclosurePanel(panel, panel.classList.contains("is-collapsed")));
  });
}

function setDisclosurePanelOpen(panelId, open = true, scroll = false){
  const panel = document.getElementById(panelId);
  if(!panel) return;
  syncDisclosurePanel(panel, open);
  if(scroll) requestAnimationFrame(() => panel.scrollIntoView({behavior:"smooth", block:"start"}));
}

navLinks.forEach(link => {
  link.addEventListener("click", () => activateView(link.dataset.target));
});

const refreshBtn = document.getElementById("refreshBtn");
const form = document.getElementById("compraForm");
const compraFamiliaSelect = document.getElementById("c_familia_id");
const compraVendedorInput = document.getElementById("quem_vendeu");
const compraVendedorManualField = document.getElementById("c_vendedor_manual_field");
const compraFamilySummary = document.getElementById("c_family_summary");
const vendaForm = document.getElementById("vendaForm");
const vendaFamiliaSelect = document.getElementById("v_familia_id");
const vendaFamilySummary = document.getElementById("v_family_summary");
const vendaCompradorInput = document.getElementById("quem_compra");
const vendaCompradorManualField = document.getElementById("v_comprador_manual_field");
const encomendaForm = document.getElementById("encomendaForm");
const encomendaFamiliaSelect = document.getElementById("e_familia_id");
const encomendaFamilySummary = document.getElementById("e_family_summary");
const encomendaSubmitBtn = document.getElementById("encomendaSubmitBtn");
const encomendaCancelEditBtn = document.getElementById("encomendaCancelEditBtn");
const reuniaoForm = document.getElementById("reuniaoForm");
const formFeedback = document.getElementById("formFeedback");
const vendaFeedback = document.getElementById("vendaFeedback");
const encomendaFeedback = document.getElementById("encomendaFeedback");
const reuniaoFeedback = document.getElementById("reuniaoFeedback");
const reuniaoSubmitBtn = document.getElementById("reuniaoSubmitBtn");
const reuniaoCancelEditBtn = document.getElementById("reuniaoCancelEditBtn");
let reuniaoEmEdicaoId = null;
let reunioesCache = [];
const familiaForm = document.getElementById("familiaForm");
const familiaFeedback = document.getElementById("familiaFeedback");
const familiaSubmitBtn = document.getElementById("familiaSubmitBtn");
const familiaCancelEditBtn = document.getElementById("familiaCancelEditBtn");
const toggleFamilyContactBtn = document.getElementById("toggleFamilyContact");
const toggleFamilyContact2Btn = document.getElementById("toggleFamilyContact2");
const familiasGrid = document.getElementById("familiasGrid");
const familiasDatalist = document.getElementById("familiasDatalist");
let familiaEmEdicaoId = null;
let familiasCache = [];
const comprasTable = document.getElementById("comprasTable");
const vendasTable = document.getElementById("vendasTable");
const encomendasTable = document.getElementById("encomendasTable");
const encomendasBusca = document.getElementById("encomendasBusca");
const encomendasOrdenacao = document.getElementById("encomendasOrdenacao");
const encomendasDataInicio = document.getElementById("encomendasDataInicio");
const encomendasDataFim = document.getElementById("encomendasDataFim");
const encomendasLimparFiltros = document.getElementById("encomendasLimparFiltros");
const encomendasFilterCount = document.getElementById("encomendasFilterCount");
const encomendasAdvancedToggle = document.getElementById("encomendasAdvancedToggle");
const encomendasAdvancedFilters = document.getElementById("encomendasAdvancedFilters");
const encomendasQuickFilters = document.querySelectorAll("[data-order-filter]");
const relatorioMes = document.getElementById("relatorioMes");
const relatorioGerarBtn = document.getElementById("relatorioGerarBtn");
const relatorioDownloadBtn = document.getElementById("relatorioDownloadBtn");
const relatorioFeedback = document.getElementById("relatorioFeedback");
const relatorioTable = document.getElementById("relatorioTable");
const relatorioPodio = document.getElementById("relatorioPodio");
let ultimoRelatorio = null;
let encomendaEmEdicaoId = null;
let encomendasCache = [];
let encomendasFiltroAtivo = "all";
const reunioesGrid = document.getElementById("reunioesGrid");
const metasFeedback = document.getElementById("metasFeedback");
const metaRoomsGrid = document.getElementById("metaRoomsGrid");
const metaRoomsSearch = document.getElementById("metaRoomsSearch");
const metaRoomDetail = document.getElementById("metaRoomDetail");
const finalizeMetaWeekBtn = document.getElementById("finalizeMetaWeekBtn");
const metaCycleStatus = document.getElementById("metaCycleStatus");
const metaCycleDeadline = document.getElementById("metaCycleDeadline");
const metaReviewConfirm = document.getElementById("metaReviewConfirm");
const metaReviewConfirmIcon = document.getElementById("metaReviewConfirmIcon");
const metaReviewConfirmTitle = document.getElementById("metaReviewConfirmTitle");
const metaReviewConfirmText = document.getElementById("metaReviewConfirmText");
const metaReviewConfirmCancel = document.getElementById("metaReviewConfirmCancel");
const metaReviewConfirmSubmit = document.getElementById("metaReviewConfirmSubmit");
const familyDeleteConfirm = document.getElementById("familyDeleteConfirm");
const familyDeleteConfirmTitle = document.getElementById("familyDeleteConfirmTitle");
const familyDeleteConfirmText = document.getElementById("familyDeleteConfirmText");
const familyDeleteConfirmName = document.getElementById("familyDeleteConfirmName");
const familyDeleteConfirmInput = document.getElementById("familyDeleteConfirmInput");
const familyDeleteConfirmCancel = document.getElementById("familyDeleteConfirmCancel");
const familyDeleteConfirmSubmit = document.getElementById("familyDeleteConfirmSubmit");
let metaRoomsCache = [];
let selectedMetaRoomUserId = null;
let activeMetaWeek = null;
let pendingMetaReview = null;
let metaConfirmPreviousFocus = null;
let pendingFamilyDelete = null;
let familyDeletePreviousFocus = null;
const craftForm = document.getElementById("craftForm");
const craftInputs = document.querySelectorAll("[data-craft-input]");
const craftTable = document.getElementById("craftTable");
const recipeGrid = document.getElementById("recipeGrid");
const craftFeedback = document.getElementById("craftFeedback");
const clearCraftBtn = document.getElementById("clearCraftBtn");

const CRAFT_RECIPES = [
  {
    id:"l85",
    inputId:"craft_l85",
    title:"Craft L85",
    helper:"Quantas armas quero fazer",
    materials:[
      ["FIOS DE COBRE", 3],
      ["TUBO DE PLÁSTICO", 3],
      ["PARAFUSOS PEQUENOS", 3],
      ["PEÇA DE ARMA PESADA", 2],
      ["DINHEIRO SUJO", 500],
    ],
  },
  {
    id:"peca_pesada",
    inputId:"craft_peca_pesada",
    title:"Caso falte peça de arma pesada",
    helper:"Quantas peças de arma pesada faltam",
    materials:[
      ["ALUMÍNIO", 75],
      ["COBRE", 75],
      ["PLÁSTICO", 125],
      ["BORRACHA", 125],
      ["CORPO DE RIFLE", 1],
      ["PEÇA DE ARMA", 2],
      ["DINHEIRO SUJO", 1000],
    ],
  },
  {
    id:"corpo_rifle",
    inputId:"craft_corpo_rifle",
    title:"Caso falte corpo de rifle",
    helper:"Quantos corpos de rifle faltam",
    materials:[
      ["PEÇA DE ARMA", 6],
      ["DINHEIRO SUJO", 1000],
    ],
  },
  {
    id:"seringa_crack",
    inputId:"craft_seringa_crack",
    title:"Craft seringa de crack",
    helper:"Quantas seringas quero fazer",
    materials:[
      ["COCAÍNA", 5],
      ["ACETONA", 1],
    ],
  },
  {
    id:"macarico",
    inputId:"craft_macarico",
    title:"Craft maçarico",
    helper:"Quantos maçaricos quero fazer",
    materials:[
      ["ALUMÍNIO", 5],
      ["COBRE", 5],
      ["CHAPA DE METAL", 1],
      ["DINHEIRO SUJO", 200],
    ],
  },
  {
    id:"rastreador",
    inputId:"craft_rastreador",
    title:"Craft rastreador ilegal",
    helper:"Quantos rastreadores quero fazer",
    materials:[
      ["ALUMÍNIO", 10],
      ["DINHEIRO SUJO", 200],
    ],
  },
  {
    id:"circuito_eletronico",
    inputId:"craft_circuito_eletronico",
    title:"Craft circuito eletrônico",
    helper:"Quantos circuitos eletrônicos quero fazer",
    materials:[
      ["ALUMÍNIO", 5],
      ["COBRE", 5],
      ["DINHEIRO SUJO", 200],
      ["PLÁSTICO", 10],
      ["CHAPA DE METAL", 1],
    ],
  },
];

const craftInventory = {};

function currency(value){
  return new Intl.NumberFormat("pt-BR", {style:"currency", currency:"BRL"}).format(Number(value || 0));
}

function dirtyMoneyPercentage(value){
  const parsed = Number(String(value ?? "").replace(",", "."));
  if(!Number.isFinite(parsed)) return 30;
  return Math.min(30, Math.max(1, parsed));
}

function percentLabel(value){
  return new Intl.NumberFormat("pt-BR", {maximumFractionDigits:2}).format(dirtyMoneyPercentage(value));
}

function moneyPricing(baseValue, moneyType, dirtyPercentage = 30){
  const base = Math.max(0, Number(baseValue || 0));
  const dirty = String(moneyType || "").trim().toLowerCase() === "dinheiro sujo";
  const percentage = dirty ? dirtyMoneyPercentage(dirtyPercentage) : 0;
  const surcharge = dirty ? Math.round((base * (percentage / 100) + Number.EPSILON) * 100) / 100 : 0;
  return {base, surcharge, total:Math.round((base + surcharge + Number.EPSILON) * 100) / 100, dirty, percentage};
}

function moneyTypeBadge(value, dirtyPercentage = 30){
  const dirty = String(value || "").trim().toLowerCase() === "dinheiro sujo";
  return `<span class="money-type-badge ${dirty ? "dirty" : ""}">${dirty ? `Dinheiro sujo +${percentLabel(dirtyPercentage)}%` : "Dinheiro limpo"}</span>`;
}

function renderMoneyPreview(totalId, detailId, baseValue, moneyType, dirtyPercentage = 30){
  const pricing = moneyPricing(baseValue, moneyType, dirtyPercentage);
  setText(totalId, currency(pricing.total));
  setText(detailId, pricing.dirty
    ? `${currency(pricing.base)} + ${currency(pricing.surcharge)} (${percentLabel(pricing.percentage)}%)`
    : "Dinheiro limpo — sem acréscimo");
  document.getElementById(totalId)?.closest(".money-calc-box")?.classList.toggle("dirty", pricing.dirty);
  return pricing;
}

function syncDirtyPercentageField(moneyTypeId, fieldId, percentageId){
  const dirty = inputValue(moneyTypeId).trim().toLowerCase() === "dinheiro sujo";
  const field = document.getElementById(fieldId);
  const input = document.getElementById(percentageId);
  if(field) field.hidden = !dirty;
  if(input){
    input.disabled = !dirty;
    input.required = dirty;
    if(dirty && String(input.value).trim() === "") input.value = "30";
  }
  return dirty ? dirtyMoneyPercentage(input?.value) : 0;
}

function escapeHtml(value){
  return String(value ?? "")
    .replace(/&/g,"&amp;")
    .replace(/</g,"&lt;")
    .replace(/>/g,"&gt;")
    .replace(/\"/g,"&quot;")
    .replace(/'/g,"&#039;");
}

const LOCAL_FLYERS = {
  "ballas": "/static/images/flyers/ballas.png",
  "cartel": "/static/images/flyers/cartel.png",
  "distrito": "/static/images/flyers/distrito.png",
  "families": "/static/images/flyers/families.png",
  "the families": "/static/images/flyers/families.png",
  "hells": "/static/images/flyers/hells.png",
  "hells angels": "/static/images/flyers/hells.png",
  "hydra": "/static/images/flyers/hydra1.png",
  "la guardia": "/static/images/flyers/laguardia.png",
  "laguardia": "/static/images/flyers/laguardia.png",
  "legacy": "/static/images/flyers/legacy.png",
  "leviata": "/static/images/flyers/leviata.png",
  "vagos": "/static/images/flyers/vagos.png",
  "vendetta": "/static/images/flyers/vendetta.png",
  "los bandoleros": "/static/images/flyers/cartel.png",
  "bandoleros": "/static/images/flyers/cartel.png",
};

function normalizeFamilyFlyerKey(value){
  const key = String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[’']/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
  const aliases = {
    "caos":"chaos",
    "balaklava":"balaclava",
    "blackherts":"black hearts",
    "black heart":"black hearts",
    "the lost":"the lost mc",
    "lost mc":"the lost mc",
    "laguardia":"la guardia",
    "bandoleros":"cartel",
    "bandolero":"cartel",
    "los bandoleros":"cartel",
    "hells angels":"hells",
  };
  return aliases[key] || key;
}

function getLocalFamilyFlyers(item){
  const key = normalizeFamilyFlyerKey(item?.nome);
  if(key === "hydra") return ["/static/images/flyers/hydra1.png", "/static/images/flyers/hydra2.png"];
  const flyer = LOCAL_FLYERS[key] || "";
  return flyer ? [flyer] : [];
}

function setFeedback(el, msg, isError=false){
  if(!el) return;
  el.textContent = msg;
  el.classList.toggle("error", isError);
  el.classList.toggle("success", !isError);
}

function updateLastSync(){
  const lastSync = document.getElementById("lastSync");
  if(!lastSync) return;
  const now = new Date();
  lastSync.textContent = `Atualizado às ${now.toLocaleTimeString("pt-BR", {hour:"2-digit", minute:"2-digit"})}`;
}

function deliveryBadge(value){
  const normalized = String(value || "Não").trim().toLowerCase();
  const delivered = normalized === "sim";
  return `<span class="status-badge ${delivered ? "success" : "pending"}">${delivered ? "SIM" : "NÃO"}</span>`;
}

function deliveryControl(item){
  const delivered = String(item.entregue || "Não").trim().toLowerCase() === "sim";
  if(!canWrite) return delivered ? deliveryBadge("Sim") : deliveryBadge("Não");

  return `<div class="delivery-actions">
    <button type="button" class="delivery-edit-btn" data-editar-encomenda="${escapeHtml(item.id)}">Editar</button>
    <button type="button" class="delivery-confirm-btn" data-encomenda-entrega="${escapeHtml(item.id)}" data-encomenda-choice="Sim">
      ${delivered ? "Mover para Vendas" : "Confirmar entrega"}
    </button>
    <button type="button" class="delivery-cancel-btn" data-cancelar-encomenda="${escapeHtml(item.id)}">Cancelar encomenda</button>
  </div>`;
}

function paymentBadge(value){
  const normalized = String(value || "Não").trim().toLowerCase();
  const isPaid = normalized === "sim";
  return `<span class="status-badge ${isPaid ? "success" : "pending"}">${isPaid ? "SIM" : "NÃO"}</span>`;
}

function updateMetaCounters(total=0, pagos=0, pendentes=0, confirmados=0, semanaLabel="--", naoPagos=0){
  setText("metaTotal", integer(total));
  setText("metaPagas", integer(pagos));
  setText("metaPendentes", integer(pendentes));
  setText("metaNaoPagas", integer(naoPagos));
  setText("statMetasPagas", integer(pagos));
  setText("statMetasPendentes", integer(pendentes));
  setText("metaSemanaAtual", semanaLabel || "--");
  setText("metaProgresso", `${integer(confirmados)}/${integer(total)} pagos`);
}

async function parseResponse(res){
  const text = await res.text();
  if(!text) return {};
  try{
    return JSON.parse(text);
  }catch{
    return { error: text };
  }
}

async function fetchJson(url, options = {}){
  const res = await fetch(url, options);
  return { res, data: await parseResponse(res) };
}

function inputValue(id){
  return document.getElementById(id)?.value ?? "";
}

function setText(id, value){
  const el = document.getElementById(id);
  if(el) el.textContent = value;
}

function applyResponsiveTableLabels(tbody){
  const table = tbody?.closest("table");
  if(!table) return;

  const labels = Array.from(table.querySelectorAll("thead th"))
    .map(header => header.textContent.trim());

  tbody.querySelectorAll("tr").forEach(row => {
    const cells = Array.from(row.children).filter(cell => cell.tagName === "TD");
    if(cells.length === 1 && Number(cells[0].colSpan) > 1){
      cells[0].classList.add("table-message");
      return;
    }
    cells.forEach((cell, index) => {
      cell.dataset.label = labels[index] || "";
    });
  });
}

function setTableContent(tbody, html){
  if(!tbody) return;
  tbody.innerHTML = html;
  applyResponsiveTableLabels(tbody);
}

function onInput(id, handler){
  document.getElementById(id)?.addEventListener("input", handler);
}

onInput("valor_unitario", updatePreviewCompra);
onInput("quantidade", updatePreviewCompra);
onInput("c_tipo_dinheiro", updatePreviewCompra);
onInput("c_percentual_dinheiro_sujo", updatePreviewCompra);
onInput("v_valor_unitario", updatePreviewVenda);
onInput("v_quantidade", updatePreviewVenda);
onInput("v_tipo_dinheiro", updatePreviewVenda);
onInput("v_percentual_dinheiro_sujo", updatePreviewVenda);
onInput("e_l85_quantidade", updatePreviewEncomenda);
onInput("e_l85_valor", updatePreviewEncomenda);
onInput("e_seringa_quantidade", updatePreviewEncomenda);
onInput("e_seringa_valor", updatePreviewEncomenda);
onInput("e_circuito_quantidade", updatePreviewEncomenda);
onInput("e_circuito_valor", updatePreviewEncomenda);
onInput("e_tipo_dinheiro", updatePreviewEncomenda);
onInput("e_percentual_dinheiro_sujo", updatePreviewEncomenda);

function updatePreviewCompra(){
  const valor = Number(inputValue("valor_unitario") || 0);
  const qtd = Number(inputValue("quantidade") || 0);
  const moneyType = inputValue("c_tipo_dinheiro");
  const percentage = syncDirtyPercentageField("c_tipo_dinheiro", "c_percentual_field", "c_percentual_dinheiro_sujo");
  renderMoneyPreview("previewTotal", "previewCompraDetalhe", valor * qtd, moneyType, percentage);
}

function updatePreviewVenda(){
  const valor = Number(inputValue("v_valor_unitario") || 0);
  const qtd = Number(inputValue("v_quantidade") || 0);
  const moneyType = inputValue("v_tipo_dinheiro");
  const percentage = syncDirtyPercentageField("v_tipo_dinheiro", "v_percentual_field", "v_percentual_dinheiro_sujo");
  renderMoneyPreview("previewVendaTotal", "previewVendaDetalhe", valor * qtd, moneyType, percentage);
}

function familyMarketInfo(family){
  const status = String(family?.mercado || "Aberto").trim();
  if(status === "Sem mercado") return {open:false, className:"no-market", label:"Sem mercado", detail:"Compras, vendas e encomendas bloqueadas"};
  if(status === "Em negociação") return {open:false, className:"negotiating", label:"Em negociação", detail:"Mercado ainda não estabelecido"};
  if(status === "Fechado") return {open:false, className:"closed", label:"Mercado fechado", detail:"Movimentações bloqueadas"};
  return {open:true, className:"open", label:"Mercado aberto", detail:"Movimentações liberadas"};
}

function familyOptionLabel(family){
  const market = familyMarketInfo(family);
  const responsible = String(family?.responsavel_contato || "A definir").trim();
  return `${family?.icone || "🤝"} ${family?.nome || "Família"} — ${responsible} — ${market.label}`;
}

function renderFamilySelectionSummary(family, container){
  if(!container) return;
  if(!family){
    container.hidden = true;
    container.innerHTML = "";
    return;
  }
  const market = familyMarketInfo(family);
  container.hidden = false;
  container.className = `family-selection-summary field-full ${market.className}`;
  container.innerHTML = `
    <span class="family-selection-icon">${escapeHtml(family.icone || "🤝")}</span>
    <div><strong>${escapeHtml(family.nome || "Família")}</strong><small>Responsável pelo contato: ${escapeHtml(family.responsavel_contato || "A definir")}</small></div>
    <span class="family-selection-market">${escapeHtml(market.label)}</span>`;
}

function familyChipHtml(family, fallback = {}){
  const name = family?.nome || fallback.nome || "Família não vinculada";
  const icon = family?.icone || fallback.icone || "🤝";
  const responsible = family?.responsavel_contato || fallback.responsavel || "";
  const linked = Boolean(family?.id || fallback.linked);
  return `<span class="order-family-chip ${linked ? "" : "unlinked"}"><span class="order-family-icon">${escapeHtml(icon)}</span><span class="order-family-text"><strong>${escapeHtml(name)}</strong>${responsible ? `<small>Contato: ${escapeHtml(responsible)}</small>` : ""}</span></span>`;
}

function syncCompraFamilyField(){
  if(!compraFamiliaSelect || !compraVendedorInput) return;
  const wasLinked = compraVendedorInput.disabled;
  const family = familiasCache.find(item => item.id === compraFamiliaSelect.value);
  const linked = Boolean(family);
  if(linked) compraVendedorInput.value = family.nome || "";
  else if(wasLinked) compraVendedorInput.value = "";
  compraVendedorInput.required = !linked;
  compraVendedorInput.disabled = linked;
  if(compraVendedorManualField) compraVendedorManualField.hidden = linked;
  renderFamilySelectionSummary(family, compraFamilySummary);
}

function syncVendaFamilyField(){
  if(!vendaFamiliaSelect || !vendaCompradorInput) return;
  const wasLinked = vendaCompradorInput.disabled;
  const family = familiasCache.find(item => item.id === vendaFamiliaSelect.value);
  const linked = Boolean(family);
  if(linked) vendaCompradorInput.value = family.nome || "";
  else if(wasLinked) vendaCompradorInput.value = "";
  vendaCompradorInput.required = !linked;
  vendaCompradorInput.disabled = linked;
  if(vendaCompradorManualField) vendaCompradorManualField.hidden = linked;
  renderFamilySelectionSummary(family, vendaFamilySummary);
}

vendaFamiliaSelect?.addEventListener("change", syncVendaFamilyField);
compraFamiliaSelect?.addEventListener("change", syncCompraFamilyField);
encomendaFamiliaSelect?.addEventListener("change", () => {
  const family = familiasCache.find(item => item.id === encomendaFamiliaSelect.value);
  renderFamilySelectionSummary(family, encomendaFamilySummary);
});

function updatePreviewEncomenda(){
  const moneyType = inputValue("e_tipo_dinheiro");
  const percentage = syncDirtyPercentageField("e_tipo_dinheiro", "e_percentual_field", "e_percentual_dinheiro_sujo");
  const l85Base = Math.max(0, Number(inputValue("e_l85_quantidade") || 0)) * Math.max(0, Number(inputValue("e_l85_valor") || 0));
  const seringaBase = Math.max(0, Number(inputValue("e_seringa_quantidade") || 0)) * Math.max(0, Number(inputValue("e_seringa_valor") || 0));
  const circuitoBase = Math.max(0, Number(inputValue("e_circuito_quantidade") || 0)) * Math.max(0, Number(inputValue("e_circuito_valor") || 0));
  setText("e_l85_subtotal", currency(moneyPricing(l85Base, moneyType, percentage).total));
  setText("e_seringa_subtotal", currency(moneyPricing(seringaBase, moneyType, percentage).total));
  setText("e_circuito_subtotal", currency(moneyPricing(circuitoBase, moneyType, percentage).total));
  let tempBase = 0;
  tempOrderCards().forEach(card => {
    const base = Math.max(0, Number(card.querySelector("[data-temp-qty]")?.value || 0)) * Math.max(0, Number(card.querySelector("[data-temp-val]")?.value || 0));
    tempBase += base;
    const subtotal = card.querySelector("[data-temp-subtotal]");
    if(subtotal) subtotal.textContent = currency(moneyPricing(base, moneyType, percentage).total);
  });
  renderMoneyPreview("previewEncomendaValor", "previewEncomendaDetalhe", l85Base + seringaBase + circuitoBase + tempBase, moneyType, percentage);
}

function resetEncomendaForm(){
  encomendaEmEdicaoId = null;
  encomendaForm?.reset();
  renderFamilySelectionSummary(null, encomendaFamilySummary);
  renderTempOrderItems();
  updatePreviewEncomenda();
  if(encomendaSubmitBtn) encomendaSubmitBtn.textContent = "Salvar encomenda";
  if(encomendaCancelEditBtn) encomendaCancelEditBtn.hidden = true;
  setText("encomendaFormKicker", "Nova encomenda");
  setText("encomendaFormTitle", "Dados da encomenda");
}

function familyForOrder(item){
  const familyId = String(item?.familia_id || "").trim();
  if(familyId){
    const byId = familiasCache.find(family => family.id === familyId);
    if(byId) return byId;
  }
  const orderName = normalizeFamilyFlyerKey(item?.familia_nome || item?.quem_pediu);
  return familiasCache.find(family => normalizeFamilyFlyerKey(family.nome) === orderName) || null;
}

function orderDeadlineTimestamp(item){
  const rawValue = String(item?.prazo_iso || item?.para_quando || "").trim();
  if(!rawValue) return Number.NaN;
  const parsed = new Date(rawValue);
  return Number.isNaN(parsed.getTime()) ? Number.NaN : parsed.getTime();
}

function orderDeadlineInputValue(item){
  const rawValue = String(item?.prazo_iso || item?.para_quando || "").trim();
  const parsed = new Date(rawValue);
  if(!rawValue || Number.isNaN(parsed.getTime())) return "";
  const pad = value => String(value).padStart(2, "0");
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}T${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`;
}

function orderDeadlineHtml(item){
  const timestamp = orderDeadlineTimestamp(item);
  const fallback = item?.para_quando_exibicao || item?.para_quando || "Prazo não reconhecido";
  if(!Number.isFinite(timestamp)) return `<div class="order-deadline-cell"><strong>${escapeHtml(fallback)}</strong><small class="unknown">Sem ordenação automática</small></div>`;

  const deadline = new Date(timestamp);
  const label = item?.para_quando_exibicao || deadline.toLocaleString("pt-BR", {day:"2-digit", month:"2-digit", year:"numeric", hour:"2-digit", minute:"2-digit"});
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const deadlineDay = new Date(deadline.getFullYear(), deadline.getMonth(), deadline.getDate());
  const dayDifference = Math.round((deadlineDay - today) / 86400000);
  let stateClass = "scheduled";
  let stateLabel = "Agendada";
  if(timestamp < now.getTime()){
    stateClass = "overdue";
    stateLabel = "Prazo vencido";
  }else if(dayDifference === 0){
    stateClass = "today";
    stateLabel = "Entrega hoje";
  }else if(dayDifference === 1){
    stateClass = "soon";
    stateLabel = "Entrega amanhã";
  }else if(dayDifference <= 3){
    stateClass = "soon";
    stateLabel = `Faltam ${dayDifference} dias`;
  }
  return `<div class="order-deadline-cell"><strong>${escapeHtml(label)}</strong><small class="${stateClass}">${escapeHtml(stateLabel)}</small></div>`;
}

function orderPriorityBadge(item, nearestRegularDeadline){
  if(Boolean(item?.prioridade)) return '<span class="order-priority-badge high"><span>!</span> Prioridade</span>';
  const timestamp = orderDeadlineTimestamp(item);
  if(Number.isFinite(timestamp) && timestamp === nearestRegularDeadline){
    return timestamp < Date.now()
      ? '<span class="order-priority-badge deadline"><span>◆</span> Prazo vencido</span>'
      : '<span class="order-priority-badge deadline"><span>◆</span> Próximo prazo</span>';
  }
  return '<span class="order-priority-badge normal">Normal</span>';
}

function orderCreatedTimestamp(value){
  const rawValue = String(value || "").trim();
  const brMatch = rawValue.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?$/);
  if(brMatch){
    return new Date(
      Number(brMatch[3]),
      Number(brMatch[2]) - 1,
      Number(brMatch[1]),
      Number(brMatch[4] || 0),
      Number(brMatch[5] || 0),
      Number(brMatch[6] || 0),
    ).getTime();
  }
  const parsed = new Date(rawValue);
  return Number.isNaN(parsed.getTime()) ? Number.NaN : parsed.getTime();
}

function orderDateBoundary(value, endOfDay = false){
  if(!value) return Number.NaN;
  const parsed = new Date(`${value}T${endOfDay ? "23:59:59.999" : "00:00:00"}`);
  return Number.isNaN(parsed.getTime()) ? Number.NaN : parsed.getTime();
}

function compareOrderTimestamps(left, right, direction = 1){
  const leftValid = Number.isFinite(left);
  const rightValid = Number.isFinite(right);
  if(!leftValid && !rightValid) return 0;
  if(!leftValid) return 1;
  if(!rightValid) return -1;
  return (left - right) * direction;
}

function orderMatchesQuickFilter(item, nowTimestamp, todayStart, todayEnd){
  const deadline = orderDeadlineTimestamp(item);
  if(encomendasFiltroAtivo === "priority") return Boolean(item.prioridade);
  if(encomendasFiltroAtivo === "overdue") return Number.isFinite(deadline) && deadline < nowTimestamp;
  if(encomendasFiltroAtivo === "today") return Number.isFinite(deadline) && deadline >= todayStart && deadline <= todayEnd;
  if(encomendasFiltroAtivo === "next7"){
    const sevenDaysEnd = todayEnd + (6 * 86400000);
    return Number.isFinite(deadline) && deadline >= todayStart && deadline <= sevenDaysEnd;
  }
  if(encomendasFiltroAtivo === "undated") return !Number.isFinite(deadline);
  return true;
}

function filteredAndSortedOrders(){
  const searchTerm = normalizeFamilyFlyerKey(encomendasBusca?.value);
  const startDate = orderDateBoundary(encomendasDataInicio?.value);
  const endDate = orderDateBoundary(encomendasDataFim?.value, true);
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const todayEnd = todayStart + 86400000 - 1;

  const filtered = encomendasCache.filter(item => {
    const family = familyForOrder(item);
    const searchable = normalizeFamilyFlyerKey([
      family?.nome,
      family?.responsavel_contato,
      item.familia_nome,
      item.familia_responsavel,
      item.quem_pediu,
      item.o_que_pediu,
      item.quem_negociou,
      item.observacao,
    ].filter(Boolean).join(" "));
    if(searchTerm && !searchable.includes(searchTerm)) return false;
    if(!orderMatchesQuickFilter(item, now.getTime(), todayStart, todayEnd)) return false;

    const deadline = orderDeadlineTimestamp(item);
    if(Number.isFinite(startDate) && (!Number.isFinite(deadline) || deadline < startDate)) return false;
    if(Number.isFinite(endDate) && (!Number.isFinite(deadline) || deadline > endDate)) return false;
    return true;
  });

  const sorting = encomendasOrdenacao?.value || "priority-deadline";
  return filtered.sort((left, right) => {
    const leftDeadline = orderDeadlineTimestamp(left);
    const rightDeadline = orderDeadlineTimestamp(right);
    const leftCreated = orderCreatedTimestamp(left.data);
    const rightCreated = orderCreatedTimestamp(right.data);

    if(sorting === "deadline-asc") return compareOrderTimestamps(leftDeadline, rightDeadline, 1) || compareOrderTimestamps(leftCreated, rightCreated, 1);
    if(sorting === "deadline-desc") return compareOrderTimestamps(leftDeadline, rightDeadline, -1) || compareOrderTimestamps(leftCreated, rightCreated, 1);
    if(sorting === "created-desc") return compareOrderTimestamps(leftCreated, rightCreated, -1);
    if(sorting === "created-asc") return compareOrderTimestamps(leftCreated, rightCreated, 1);
    if(sorting === "family-asc"){
      const leftName = familyForOrder(left)?.nome || left.familia_nome || left.quem_pediu || "";
      const rightName = familyForOrder(right)?.nome || right.familia_nome || right.quem_pediu || "";
      return String(leftName).localeCompare(String(rightName), "pt-BR", {sensitivity:"base"});
    }

    const priorityDifference = Number(Boolean(right.prioridade)) - Number(Boolean(left.prioridade));
    return priorityDifference || compareOrderTimestamps(leftDeadline, rightDeadline, 1) || compareOrderTimestamps(leftCreated, rightCreated, 1);
  });
}

function updateOrderFilterCount(visible){
  if(!encomendasFilterCount) return;
  const total = encomendasCache.length;
  encomendasFilterCount.textContent = visible === total
    ? `${total} ${total === 1 ? "encomenda" : "encomendas"}`
    : `${visible} de ${total} encomendas`;
}

function renderEncomendas(){
  if(!encomendasTable) return;
  const colspan = 9;
  const items = filteredAndSortedOrders();
  updateOrderFilterCount(items.length);
  if(!encomendasCache.length){
    setTableContent(encomendasTable, `<tr><td colspan="${colspan}">Nenhuma encomenda pendente.</td></tr>`);
    return;
  }
  if(!items.length){
    setTableContent(encomendasTable, `<tr><td colspan="${colspan}">Nenhuma encomenda encontrada com os filtros selecionados.</td></tr>`);
    return;
  }

  const regularDeadlines = items
    .filter(item => !Boolean(item.prioridade))
    .map(orderDeadlineTimestamp)
    .filter(Number.isFinite);
  const nearestRegularDeadline = regularDeadlines.length ? Math.min(...regularDeadlines) : Number.NaN;
  setTableContent(encomendasTable, items.map(item => {
    const family = familyForOrder(item);
    const familyName = family?.nome || item.familia_nome || item.quem_pediu || "Família não vinculada";
    const familyIcon = family?.icone || item.familia_icone || "🤝";
    const familyResponsible = family?.responsavel_contato || item.familia_responsavel || "";
    const linked = Boolean(family?.id || item.familia_id);
    const priority = Boolean(item.prioridade);
    const nextByDeadline = !priority && orderDeadlineTimestamp(item) === nearestRegularDeadline;
    const observation = String(item.observacao || "").trim();
    const detailsId = `order-details-${item.id}`;
    const observationButton = observation ? `
      <button class="order-observation-toggle" type="button" data-toggle-order-details="${escapeHtml(item.id)}" aria-expanded="false" aria-controls="${escapeHtml(detailsId)}">
        <span class="order-observation-icon">📝</span>
        <span class="order-details-label">Ver observação</span>
        <span class="order-details-arrow" aria-hidden="true">⌄</span>
      </button>` : "";
    const detailsRow = observation ? `
      <tr class="order-details-row" id="${escapeHtml(detailsId)}" data-order-details-row="${escapeHtml(item.id)}" hidden>
        <td colspan="${colspan}">
          <div class="order-details-panel">
            <div class="order-details-heading">
              <span class="order-details-heading-icon">📝</span>
              <div><small>Observação da encomenda</small><strong>${escapeHtml(familyName)}</strong></div>
              <button class="order-details-close" type="button" data-close-order-details="${escapeHtml(item.id)}">Fechar</button>
            </div>
            <p>${escapeHtml(observation)}</p>
            <div class="order-details-meta">
              <span><small>Pedido</small><strong>${escapeHtml(item.o_que_pediu || "—")}</strong></span>
              <span><small>Negociou</small><strong>${escapeHtml(item.quem_negociou || "—")}</strong></span>
              <span><small>Prazo</small><strong>${escapeHtml(item.para_quando_exibicao || item.para_quando || "—")}</strong></span>
            </div>
          </div>
        </td>
      </tr>` : "";
    return `<tr class="order-main-row ${priority ? "order-row-priority" : (nextByDeadline ? "order-row-next" : "")}" data-order-main-row="${escapeHtml(item.id)}">
      <td>${orderPriorityBadge(item, nearestRegularDeadline)}</td>
      <td>${escapeHtml(item.data)}</td>
      <td>${familyChipHtml(family, {nome:familyName, icone:familyIcon, responsavel:familyResponsible, linked})}</td>
      <td><div class="order-product-cell"><span>${escapeHtml(item.o_que_pediu)}</span>${observationButton}</div></td>
      <td>${orderDeadlineHtml(item)}</td>
      <td>${escapeHtml(item.quem_negociou)}</td>
      <td>${moneyTypeBadge(item.tipo_dinheiro, item.percentual_dinheiro_sujo)}</td>
      <td>${currency(item.valor)}</td>
      <td>${deliveryControl(item)}</td>
    </tr>${detailsRow}`;
  }).join(""));
}

function toggleOrderDetails(orderId, forceOpen = null){
  if(!encomendasTable) return;
  const detailsRow = Array.from(encomendasTable.querySelectorAll("[data-order-details-row]"))
    .find(row => row.dataset.orderDetailsRow === orderId);
  const mainRow = Array.from(encomendasTable.querySelectorAll("[data-order-main-row]"))
    .find(row => row.dataset.orderMainRow === orderId);
  if(!detailsRow) return;

  const willOpen = forceOpen === null ? detailsRow.hidden : Boolean(forceOpen);
  detailsRow.hidden = !willOpen;
  mainRow?.classList.toggle("details-open", willOpen);
  encomendasTable.querySelectorAll("[data-toggle-order-details]").forEach(button => {
    if(button.dataset.toggleOrderDetails !== orderId) return;
    button.setAttribute("aria-expanded", String(willOpen));
    button.classList.toggle("active", willOpen);
    const label = button.querySelector(".order-details-label");
    if(label) label.textContent = willOpen ? "Ocultar observação" : "Ver observação";
  });
}

function setActiveOrderFilter(filterName){
  encomendasFiltroAtivo = filterName || "all";
  encomendasQuickFilters.forEach(button => {
    const active = button.dataset.orderFilter === encomendasFiltroAtivo;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  renderEncomendas();
}

function clearOrderFilters(){
  if(encomendasBusca) encomendasBusca.value = "";
  if(encomendasOrdenacao) encomendasOrdenacao.value = "priority-deadline";
  if(encomendasDataInicio) encomendasDataInicio.value = "";
  if(encomendasDataFim) encomendasDataFim.value = "";
  setActiveOrderFilter("all");
}

encomendasAdvancedToggle?.addEventListener("click", () => {
  const willOpen = Boolean(encomendasAdvancedFilters?.hidden);
  if(encomendasAdvancedFilters) encomendasAdvancedFilters.hidden = !willOpen;
  encomendasAdvancedToggle.setAttribute("aria-expanded", String(willOpen));
  encomendasAdvancedToggle.classList.toggle("active", willOpen);
  encomendasAdvancedToggle.textContent = willOpen ? "Ocultar filtros" : "Filtros avançados";
});

function iniciarEdicaoEncomenda(id){
  const item = encomendasCache.find(encomenda => encomenda.id === id);
  if(!item || !encomendaForm) return;

  const itens = Array.isArray(item.itens) ? item.itens : [];
  const l85 = itens.find(produto => String(produto.produto || "").trim().toLowerCase() === "l85");
  const seringa = itens.find(produto => String(produto.produto || "").trim().toLowerCase() === "seringa");
  const circuito = itens.find(produto => normalizeFamilyFlyerKey(produto.produto) === "circuito eletronico");
  const family = familyForOrder(item);

  encomendaEmEdicaoId = id;
  if(encomendaFamiliaSelect) encomendaFamiliaSelect.value = family?.id || item.familia_id || "";
  renderFamilySelectionSummary(family, encomendaFamilySummary);
  document.getElementById("e_l85_quantidade").value = l85?.quantidade || "";
  document.getElementById("e_l85_valor").value = l85?.valor_unitario ?? "";
  document.getElementById("e_seringa_quantidade").value = seringa?.quantidade || "";
  document.getElementById("e_seringa_valor").value = seringa?.valor_unitario ?? "";
  document.getElementById("e_circuito_quantidade").value = circuito?.quantidade || "";
  document.getElementById("e_circuito_valor").value = circuito?.valor_unitario ?? "";

  // Produtos adicionais (ex.: M16): o cartão aparece mesmo depois do prazo se a encomenda já o tinha.
  const extras = itens.filter(produto => !ORDER_FIXED_PRODUCT_KEYS.includes(normalizeFamilyFlyerKey(produto.produto)));
  renderTempOrderItems(extras.map(produto => produto.produto));
  tempOrderCards().forEach(card => {
    card.querySelector("[data-temp-qty]").value = "";
    card.querySelector("[data-temp-val]").value = "";
  });
  extras.forEach(produto => {
    const card = tempOrderCards().find(item => normalizeFamilyFlyerKey(item.dataset.tempOrderItem) === normalizeFamilyFlyerKey(produto.produto));
    if(!card) return;
    card.querySelector("[data-temp-qty]").value = produto.quantidade || "";
    card.querySelector("[data-temp-val]").value = produto.valor_unitario ?? "";
  });

  // Compatibilidade com encomendas antigas, anteriores ao campo itens_json.
  if(!itens.length){
    const texto = String(item.o_que_pediu || "");
    const match = texto.match(/^\s*(?:(\d+)\s*x?\s*)?(L85|Seringa|Circuito Eletr[oô]nico)\s*$/i);
    if(match){
      const quantidade = Number(match[1] || 1);
      const valorUnitario = quantidade > 0 ? Number(item.valor_base || item.valor || 0) / quantidade : 0;
      const produtoNormalizado = normalizeFamilyFlyerKey(match[2]);
      const prefixo = produtoNormalizado === "l85" ? "e_l85" : (produtoNormalizado === "seringa" ? "e_seringa" : "e_circuito");
      document.getElementById(`${prefixo}_quantidade`).value = quantidade;
      document.getElementById(`${prefixo}_valor`).value = Number(valorUnitario.toFixed(2));
    }
  }

  document.getElementById("e_para_quando").value = orderDeadlineInputValue(item);
  document.getElementById("e_quem_negociou").value = item.quem_negociou || "";
  document.getElementById("e_entregue").value = String(item.entregue || "Não").toLowerCase() === "sim" ? "Sim" : "Não";
  const dirtyMoney = String(item.tipo_dinheiro || "Dinheiro limpo").toLowerCase() === "dinheiro sujo";
  document.getElementById("e_tipo_dinheiro").value = dirtyMoney ? "Dinheiro sujo" : "Dinheiro limpo";
  document.getElementById("e_percentual_dinheiro_sujo").value = dirtyMoney
    ? dirtyMoneyPercentage(item.percentual_dinheiro_sujo ?? 30)
    : 30;
  document.getElementById("e_observacao").value = item.observacao || "";
  document.getElementById("e_prioridade").checked = Boolean(item.prioridade);
  updatePreviewEncomenda();

  if(encomendaSubmitBtn) encomendaSubmitBtn.textContent = "Salvar alterações";
  if(encomendaCancelEditBtn) encomendaCancelEditBtn.hidden = false;
  setText("encomendaFormKicker", "Editar encomenda");
  setText("encomendaFormTitle", family ? `${family.icone || "🤝"} ${family.nome}` : (item.familia_nome || item.quem_pediu || "Atualizar encomenda"));
  setFeedback(encomendaFeedback, "Edite os campos e clique em Salvar alterações.");
  setDisclosurePanelOpen("encomendaEntryPanel", true, true);
}

encomendaCancelEditBtn?.addEventListener("click", () => {
  resetEncomendaForm();
  setFeedback(encomendaFeedback, "Edição cancelada.");
});

async function sendPost(url, payload, feedbackEl, loadingMessage, successMessage){
  if(!canWrite){
    setFeedback(feedbackEl, "Seu usuário está em modo somente leitura.", true);
    return null;
  }

  try{
    setFeedback(feedbackEl, loadingMessage);
    const {res, data} = await fetchJson(url, {
      method:"POST",
      headers:csrfHeaders({"Content-Type":"application/json"}),
      body:JSON.stringify(payload)
    });
    if(!res.ok){
      setFeedback(feedbackEl, data.error || `Erro ${res.status} ao salvar registro.`, true);
      return null;
    }
    setFeedback(feedbackEl, data.message || successMessage);
    await loadAll();
    return data;
  }catch(error){
    setFeedback(feedbackEl, `Falha ao conectar com o servidor: ${error.message}`, true);
    return null;
  }
}

form?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const selectedFamily = familiasCache.find(item => item.id === inputValue("c_familia_id").trim());
  if(selectedFamily && !familyMarketInfo(selectedFamily).open){
    setFeedback(formFeedback, `${selectedFamily.nome}: ${familyMarketInfo(selectedFamily).detail}.`, true);
    return;
  }
  const payload = {
    produto: inputValue("produto").trim(),
    quem_pediu: inputValue("quem_pediu").trim(),
    quem_vendeu: inputValue("quem_vendeu").trim(),
    familia_id: inputValue("c_familia_id").trim(),
    valor_unitario: Number(inputValue("valor_unitario")),
    quantidade: Number(inputValue("quantidade")),
    tipo_dinheiro: inputValue("c_tipo_dinheiro"),
    percentual_dinheiro_sujo: dirtyMoneyPercentage(inputValue("c_percentual_dinheiro_sujo")),
    observacao: inputValue("observacao").trim(),
  };

  const ok = await sendPost("/api/compras", payload, formFeedback, "Salvando compra...", "Compra salva com sucesso.");
  if(ok){
    form.reset();
    syncCompraFamilyField();
    updatePreviewCompra();
  }
});

vendaForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const selectedFamily = familiasCache.find(item => item.id === inputValue("v_familia_id").trim());
  if(selectedFamily && !familyMarketInfo(selectedFamily).open){
    setFeedback(vendaFeedback, `${selectedFamily.nome}: ${familyMarketInfo(selectedFamily).detail}.`, true);
    return;
  }
  const payload = {
    produto: inputValue("v_produto").trim(),
    familia_id: inputValue("v_familia_id").trim(),
    quem_compra: inputValue("quem_compra").trim(),
    quem_vende: inputValue("quem_vende").trim(),
    valor_unitario: Number(inputValue("v_valor_unitario")),
    quantidade: Number(inputValue("v_quantidade")),
    tipo_dinheiro: inputValue("v_tipo_dinheiro"),
    percentual_dinheiro_sujo: dirtyMoneyPercentage(inputValue("v_percentual_dinheiro_sujo")),
    observacao: inputValue("v_observacao").trim(),
  };

  const ok = await sendPost("/api/vendas", payload, vendaFeedback, "Salvando venda...", "Venda salva com sucesso.");
  if(ok){
    vendaForm.reset();
    syncVendaFamilyField();
    updatePreviewVenda();
  }
});

encomendaForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const familiaId = inputValue("e_familia_id").trim();
  if(!familiaId){
    setFeedback(encomendaFeedback, "Selecione a família ou gangue responsável pela encomenda.", true);
    return;
  }
  const selectedFamily = familiasCache.find(item => item.id === familiaId);
  if(selectedFamily && !familyMarketInfo(selectedFamily).open){
    setFeedback(encomendaFeedback, `${selectedFamily.nome}: ${familyMarketInfo(selectedFamily).detail}.`, true);
    return;
  }
  const itens = [
    {
      produto:"L85",
      quantidade:Number(inputValue("e_l85_quantidade") || 0),
      valor_unitario:Number(inputValue("e_l85_valor") || 0),
    },
    {
      produto:"Seringa",
      quantidade:Number(inputValue("e_seringa_quantidade") || 0),
      valor_unitario:Number(inputValue("e_seringa_valor") || 0),
    },
    {
      produto:"Circuito Eletrônico",
      quantidade:Number(inputValue("e_circuito_quantidade") || 0),
      valor_unitario:Number(inputValue("e_circuito_valor") || 0),
    },
    ...tempOrderCards().map(card => ({
      produto:card.dataset.tempOrderItem,
      quantidade:Number(card.querySelector("[data-temp-qty]")?.value || 0),
      valor_unitario:Number(card.querySelector("[data-temp-val]")?.value || 0),
    })),
  ];

  if(!itens.some(item => Number.isInteger(item.quantidade) && item.quantidade > 0)){
    setFeedback(encomendaFeedback, "Informe a quantidade de pelo menos um produto do pedido.", true);
    return;
  }
  if(itens.some(item => item.quantidade < 0 || !Number.isInteger(item.quantidade))){
    setFeedback(encomendaFeedback, "As quantidades precisam ser números inteiros.", true);
    return;
  }
  if(itens.some(item => item.quantidade > 0 && (!Number.isFinite(item.valor_unitario) || item.valor_unitario < 0))){
    setFeedback(encomendaFeedback, "Informe um valor unitário válido para cada produto selecionado.", true);
    return;
  }

  const payload = {
    familia_id: familiaId,
    itens,
    para_quando: inputValue("e_para_quando").trim(),
    quem_negociou: inputValue("e_quem_negociou").trim(),
    entregue: inputValue("e_entregue"),
    tipo_dinheiro: inputValue("e_tipo_dinheiro"),
    percentual_dinheiro_sujo: dirtyMoneyPercentage(inputValue("e_percentual_dinheiro_sujo")),
    prioridade: Boolean(document.getElementById("e_prioridade")?.checked),
    observacao: inputValue("e_observacao").trim(),
  };

  if(encomendaEmEdicaoId){
    try{
      setFeedback(encomendaFeedback, "Salvando alterações...");
      const {res, data} = await fetchJson(`/api/encomendas/${encodeURIComponent(encomendaEmEdicaoId)}`, {
        method:"PUT",
        headers:csrfHeaders({"Content-Type":"application/json"}),
        body:JSON.stringify(payload)
      });
      setFeedback(encomendaFeedback, data.message || (res.ok ? "Encomenda atualizada." : "Erro ao atualizar encomenda."), !res.ok);
      if(res.ok){
        resetEncomendaForm();
        await Promise.all([loadEncomendas(), loadVendas(), loadResumo(), loadRelatorio()]);
        if(data.moved_to_vendas) activateView("vendas");
      }
    }catch(error){
      setFeedback(encomendaFeedback, `Falha ao atualizar encomenda: ${error.message}`, true);
    }
    return;
  }

  const result = await sendPost("/api/encomendas", payload, encomendaFeedback, "Salvando encomenda...", "Encomenda salva com sucesso.");
  if(result){
    resetEncomendaForm();
    if(result.moved_to_vendas){
      activateView("vendas");
    }
  }
});

function resetReuniaoForm(){
  reuniaoEmEdicaoId = null;
  reuniaoForm?.reset();
  if(reuniaoSubmitBtn) reuniaoSubmitBtn.textContent = "Agendar reunião";
  if(reuniaoCancelEditBtn) reuniaoCancelEditBtn.hidden = true;
  setText("reuniaoFormKicker", "Nova reunião");
  setText("reuniaoFormTitle", "Agendar compromisso");
}

function iniciarEdicaoReuniao(id){
  const item = reunioesCache.find(reuniao => reuniao.id === id);
  if(!item || !reuniaoForm) return;
  reuniaoEmEdicaoId = id;
  document.getElementById("r_titulo").value = item.titulo || "";
  document.getElementById("r_gangue").value = item.gangue || "";
  document.getElementById("r_icone").value = item.icone || "";
  document.getElementById("r_data").value = item.data || "";
  document.getElementById("r_horario").value = item.horario || "";
  document.getElementById("r_local").value = item.local || "";
  document.getElementById("r_pauta").value = item.pauta || "";
  if(reuniaoSubmitBtn) reuniaoSubmitBtn.textContent = "Salvar alterações";
  if(reuniaoCancelEditBtn) reuniaoCancelEditBtn.hidden = false;
  setText("reuniaoFormKicker", "Editar reunião");
  setText("reuniaoFormTitle", item.titulo || "Atualizar compromisso");
  setFeedback(reuniaoFeedback, "Edite os campos e clique em Salvar alterações.");
  setDisclosurePanelOpen("reuniaoEntryPanel", true, true);
}

reuniaoCancelEditBtn?.addEventListener("click", () => {
  resetReuniaoForm();
  setFeedback(reuniaoFeedback, "Edição cancelada.");
});

reuniaoForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    titulo: inputValue("r_titulo"), gangue: inputValue("r_gangue"), icone: inputValue("r_icone"),
    data: inputValue("r_data"), horario: inputValue("r_horario"), local: inputValue("r_local"), pauta: inputValue("r_pauta")
  };

  if(reuniaoEmEdicaoId){
    try{
      setFeedback(reuniaoFeedback, "Salvando alterações...");
      const {res, data} = await fetchJson(`/api/reunioes/${encodeURIComponent(reuniaoEmEdicaoId)}`, {
        method:"PUT",
        headers:csrfHeaders({"Content-Type":"application/json"}),
        body:JSON.stringify(payload)
      });
      setFeedback(reuniaoFeedback, data.message || (res.ok ? "Reunião atualizada." : "Erro ao atualizar reunião."), !res.ok);
      if(res.ok){ resetReuniaoForm(); await loadReunioes(); }
    }catch(error){ setFeedback(reuniaoFeedback, `Falha ao atualizar: ${error.message}`, true); }
    return;
  }

  const result = await sendPost("/api/reunioes", payload, reuniaoFeedback, "Agendando reunião...", "Reunião agendada com sucesso.");
  if(result){ resetReuniaoForm(); await loadReunioes(); }
});

reunioesGrid?.addEventListener("click", async (event) => {
  const editButton = event.target.closest("[data-editar-reuniao]");
  if(editButton){ iniciarEdicaoReuniao(editButton.dataset.editarReuniao); return; }

  const cancelButton = event.target.closest("[data-cancelar-reuniao]");
  if(cancelButton){
    if(!window.confirm("Marcar esta reunião como cancelada?")) return;
    cancelButton.disabled = true;
    try{
      const {res, data} = await fetchJson(`/api/reunioes/${encodeURIComponent(cancelButton.dataset.cancelarReuniao)}/cancelar`, {method:"POST", headers:csrfHeaders()});
      setFeedback(reuniaoFeedback, data.message || (res.ok ? "Reunião cancelada." : "Erro ao cancelar."), !res.ok);
      if(res.ok) await loadReunioes();
    }catch(error){ setFeedback(reuniaoFeedback, `Falha ao cancelar: ${error.message}`, true); }
    finally{ cancelButton.disabled = false; }
    return;
  }

  const button = event.target.closest("[data-finalizar-reuniao]");
  if(!button) return;
  if(!window.confirm("Marcar esta reunião como finalizada?")) return;
  button.disabled = true;
  try{
    const {res, data} = await fetchJson(`/api/reunioes/${encodeURIComponent(button.dataset.finalizarReuniao)}/finalizar`, {method:"POST", headers:csrfHeaders()});
    setFeedback(reuniaoFeedback, data.message || (res.ok ? "Reunião finalizada." : "Erro ao finalizar."), !res.ok);
    if(res.ok) await Promise.all([loadReunioes(), loadFamilias()]);
  }catch(error){ setFeedback(reuniaoFeedback, `Falha ao finalizar: ${error.message}`, true); }
  finally{ button.disabled = false; }
});

encomendasTable?.addEventListener("click", async (event) => {
  const detailsButton = event.target.closest("[data-toggle-order-details]");
  if(detailsButton){
    toggleOrderDetails(detailsButton.dataset.toggleOrderDetails);
    return;
  }

  const closeDetailsButton = event.target.closest("[data-close-order-details]");
  if(closeDetailsButton){
    toggleOrderDetails(closeDetailsButton.dataset.closeOrderDetails, false);
    return;
  }

  if(!canWrite) return;

  const editButton = event.target.closest("[data-editar-encomenda]");
  if(editButton){
    iniciarEdicaoEncomenda(editButton.dataset.editarEncomenda);
    return;
  }

  const cancelButton = event.target.closest("[data-cancelar-encomenda]");
  if(cancelButton){
    const id = cancelButton.dataset.cancelarEncomenda;
    if(!window.confirm("Cancelar esta encomenda? Ela será apagada imediatamente e não irá para Vendas.")) return;
    const row = cancelButton.closest("tr");
    const buttons = row ? row.querySelectorAll("button") : [cancelButton];
    buttons.forEach(btn => btn.disabled = true);
    setFeedback(encomendaFeedback, "Cancelando e apagando encomenda...");
    try{
      const {res, data} = await fetchJson(`/api/encomendas/${encodeURIComponent(id)}`, {
        method:"DELETE",
        headers:csrfHeaders()
      });
      setFeedback(encomendaFeedback, data.message || (res.ok ? "Encomenda cancelada." : "Erro ao cancelar encomenda."), !res.ok);
      if(res.ok) await Promise.all([loadEncomendas(), loadResumo(), loadRelatorio()]);
    }catch(error){
      setFeedback(encomendaFeedback, `Falha ao cancelar encomenda: ${error.message}`, true);
    }finally{
      buttons.forEach(btn => btn.disabled = false);
    }
    return;
  }

  const button = event.target.closest("[data-encomenda-entrega]");
  if(!button) return;

  const id = button.dataset.encomendaEntrega;
  const entregue = button.dataset.encomendaChoice;
  if(entregue === "Sim" && !window.confirm("Confirmar a entrega? A encomenda será removida daqui e registrada em Vendas.")) return;
  const row = button.closest("tr");
  const buttons = row ? row.querySelectorAll("button") : [button];
  buttons.forEach(btn => btn.disabled = true);
  setFeedback(encomendaFeedback, `Atualizando entrega para ${entregue.toUpperCase()}...`);

  try{
    const {res, data} = await fetchJson(`/api/encomendas/${encodeURIComponent(id)}/entrega`, {
      method:"POST",
      headers:csrfHeaders({"Content-Type":"application/json"}),
      body:JSON.stringify({entregue})
    });

    if(!res.ok){
      setFeedback(encomendaFeedback, data.error || "Erro ao atualizar entrega.", true);
      await loadEncomendas();
      return;
    }

    setFeedback(encomendaFeedback, data.message || "Status de entrega atualizado.");
    await Promise.all([loadEncomendas(), loadVendas(), loadResumo(), loadRelatorio()]);
    if(data.moved_to_vendas){
      activateView("vendas");
    }
  }catch(error){
    setFeedback(encomendaFeedback, `Falha ao atualizar entrega: ${error.message}`, true);
  }finally{
    buttons.forEach(btn => btn.disabled = false);
  }
});

function resetFamiliaForm(){
  familiaEmEdicaoId = null;
  familiaForm?.reset();
  const mercado = document.getElementById("f_mercado");
  if(mercado) mercado.value = "Aberto";
  const contato = document.getElementById("f_contato");
  if(contato) contato.type = "password";
  const contato2 = document.getElementById("f_contato_2");
  if(contato2) contato2.type = "password";
  if(toggleFamilyContactBtn) toggleFamilyContactBtn.textContent = "Mostrar";
  if(toggleFamilyContact2Btn) toggleFamilyContact2Btn.textContent = "Mostrar";
  const flyerUrl1 = document.getElementById("f_flyer_url");
  const flyerUrl2 = document.getElementById("f_flyer_url_2");
  if(flyerUrl1) flyerUrl1.placeholder = "Opcional: https://.../flyer-1.png";
  if(flyerUrl2) flyerUrl2.placeholder = "Opcional: https://.../flyer-2.png";
  if(familiaSubmitBtn) familiaSubmitBtn.textContent = "Adicionar Família/Gangue";
  if(familiaCancelEditBtn) familiaCancelEditBtn.hidden = true;
  const entryPanel = document.getElementById("familiaEntryPanel");
  if(entryPanel) entryPanel.dataset.disclosureLabel = "Adicionar família";
  setText("familiaFormKicker", "Novo cadastro");
  setText("familiaFormTitle", "Adicionar Família/Gangue");
}

function storedFamilyFlyer(item, slot){
  const field = slot === 1 ? "flyer_url" : "flyer_url_2";
  return String(item?.[`${field}_stored`] || item?.[field] || "").trim();
}

function isStoredBucketFlyer(value){
  return String(value || "").startsWith("kokusai-bucket://");
}

function iniciarEdicaoFamilia(id){
  const item = familiasCache.find(familia => familia.id === id);
  if(!item || !familiaForm) return;
  familiaEmEdicaoId = id;
  document.getElementById("f_nome").value = item.nome || "";
  document.getElementById("f_icone").value = item.icone || "";
  document.getElementById("f_responsavel_contato").value = item.responsavel_contato || "";
  document.getElementById("f_mercado").value = item.mercado || "Aberto";
  document.getElementById("f_preco_venda").value = item.preco_venda_para_familia || "";
  document.getElementById("f_preco_compra").value = item.preco_compra_da_familia || "";
  document.getElementById("f_contato").value = item.contato || "";
  document.getElementById("f_contato_2").value = item.contato_2 || "";
  const storedFlyer1 = storedFamilyFlyer(item, 1);
  const storedFlyer2 = storedFamilyFlyer(item, 2);
  const flyerUrl1 = document.getElementById("f_flyer_url");
  const flyerUrl2 = document.getElementById("f_flyer_url_2");
  flyerUrl1.value = isStoredBucketFlyer(storedFlyer1) ? "" : storedFlyer1;
  flyerUrl2.value = isStoredBucketFlyer(storedFlyer2) ? "" : storedFlyer2;
  flyerUrl1.placeholder = isStoredBucketFlyer(storedFlyer1) ? "Flyer 1 já armazenado no Bucket" : "Opcional: https://.../flyer-1.png";
  flyerUrl2.placeholder = isStoredBucketFlyer(storedFlyer2) ? "Flyer 2 já armazenado no Bucket" : "Opcional: https://.../flyer-2.png";
  document.getElementById("f_flyer_oculto").checked = Boolean(item.flyer_oculto);
  document.getElementById("f_observacao").value = item.observacao || "";
  if(familiaSubmitBtn) familiaSubmitBtn.textContent = "Salvar alterações";
  if(familiaCancelEditBtn) familiaCancelEditBtn.hidden = false;
  const entryPanel = document.getElementById("familiaEntryPanel");
  if(entryPanel) entryPanel.dataset.disclosureLabel = "Editar informações";
  setText("familiaFormKicker", "Editar cadastro");
  setText("familiaFormTitle", item.nome || "Atualizar família/gangue");
  setFeedback(familiaFeedback, "Edite os dados e clique em Salvar alterações.");
  setDisclosurePanelOpen("familiaEntryPanel", true, true);
}

familiaCancelEditBtn?.addEventListener("click", () => {
  resetFamiliaForm();
  setFeedback(familiaFeedback, "Edição cancelada.");
});

function toggleSecretFamilyInput(inputId, button){
  const input = document.getElementById(inputId);
  if(!input) return;
  const showing = input.type === "text";
  input.type = showing ? "password" : "text";
  if(button) button.textContent = showing ? "Mostrar" : "Esconder";
}

toggleFamilyContactBtn?.addEventListener("click", () => toggleSecretFamilyInput("f_contato", toggleFamilyContactBtn));
toggleFamilyContact2Btn?.addEventListener("click", () => toggleSecretFamilyInput("f_contato_2", toggleFamilyContact2Btn));

onInput("f_flyer_url", () => {
  const hidden = document.getElementById("f_flyer_oculto");
  if(hidden && inputValue("f_flyer_url").trim()) hidden.checked = false;
});
onInput("f_flyer_url_2", () => {
  const hidden = document.getElementById("f_flyer_oculto");
  if(hidden && inputValue("f_flyer_url_2").trim()) hidden.checked = false;
});

async function uploadFamilyFlyerFile(familyId, slot, file){
  if(!file) return null;
  const body = new FormData();
  body.append("slot", String(slot));
  body.append("flyer", file);
  const response = await fetch(`/api/familias/${encodeURIComponent(familyId)}/flyers`, {
    method:"POST",
    headers:csrfHeaders(),
    body,
  });
  const data = await parseResponse(response);
  if(!response.ok) throw new Error(data.error || `Não foi possível armazenar o Flyer ${slot}.`);
  return data;
}

familiaForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const editing = Boolean(familiaEmEdicaoId);
  const currentFamily = editing ? familiasCache.find(item => item.id === familiaEmEdicaoId) : null;
  const flyerFile1 = document.getElementById("f_flyer_file")?.files?.[0] || null;
  const flyerFile2 = document.getElementById("f_flyer_file_2")?.files?.[0] || null;
  const typedFlyerUrl1 = inputValue("f_flyer_url").trim();
  const typedFlyerUrl2 = inputValue("f_flyer_url_2").trim();
  const payload = {
    nome: inputValue("f_nome").trim(),
    icone: inputValue("f_icone").trim(),
    responsavel_contato: inputValue("f_responsavel_contato").trim(),
    mercado: inputValue("f_mercado"),
    preco_venda_para_familia: inputValue("f_preco_venda").trim(),
    preco_compra_da_familia: inputValue("f_preco_compra").trim(),
    contato: inputValue("f_contato").trim(),
    contato_2: inputValue("f_contato_2").trim(),
    flyer_url: typedFlyerUrl1 || (editing ? storedFamilyFlyer(currentFamily, 1) : ""),
    flyer_url_2: typedFlyerUrl2 || (editing ? storedFamilyFlyer(currentFamily, 2) : ""),
    flyer_oculto: Boolean(document.getElementById("f_flyer_oculto")?.checked),
    observacao: inputValue("f_observacao").trim(),
  };

  const url = editing ? `/api/familias/${encodeURIComponent(familiaEmEdicaoId)}` : "/api/familias";
  try{
    if(familiaSubmitBtn){
      familiaSubmitBtn.disabled = true;
      familiaSubmitBtn.textContent = editing ? "Salvando alterações..." : "Adicionando...";
    }
    setFeedback(familiaFeedback, editing ? "Salvando alterações..." : "Adicionando família/gangue...");
    const {res, data} = await fetchJson(url, {
      method:editing ? "PUT" : "POST",
      headers:csrfHeaders({"Content-Type":"application/json"}),
      body:JSON.stringify(payload)
    });
    setFeedback(familiaFeedback, data.message || (res.ok ? "Cadastro salvo." : "Erro ao salvar cadastro."), !res.ok);
    if(res.ok){
      const familyId = data.id || familiaEmEdicaoId;
      try{
        if(flyerFile1){
          setFeedback(familiaFeedback, "Cadastro salvo. Armazenando Flyer 1 no Bucket...");
          await uploadFamilyFlyerFile(familyId, 1, flyerFile1);
        }
        if(flyerFile2){
          setFeedback(familiaFeedback, `${flyerFile1 ? "Flyer 1 pronto. " : ""}Armazenando Flyer 2 no Bucket...`);
          await uploadFamilyFlyerFile(familyId, 2, flyerFile2);
        }
        setFeedback(familiaFeedback, flyerFile1 || flyerFile2 ? "Cadastro e flyers armazenados permanentemente." : (data.message || "Cadastro salvo."));
        resetFamiliaForm();
      }catch(uploadError){
        setFeedback(familiaFeedback, `O cadastro foi salvo, mas houve falha no upload: ${uploadError.message}`, true);
      }
      await loadFamilias();
    }
  }catch(error){
    setFeedback(familiaFeedback, `Falha ao salvar família/gangue: ${error.message}`, true);
  }finally{
    if(familiaSubmitBtn){
      familiaSubmitBtn.disabled = false;
      familiaSubmitBtn.textContent = familiaEmEdicaoId ? "Salvar alterações" : "Adicionar Família/Gangue";
    }
  }
});

function familyPayloadFromItem(item, overrides = {}){
  return {
    nome:item?.nome || "",
    icone:item?.icone || "",
    responsavel_contato:item?.responsavel_contato || "",
    mercado:item?.mercado || "Aberto",
    preco_venda_para_familia:item?.preco_venda_para_familia || "",
    preco_compra_da_familia:item?.preco_compra_da_familia || "",
    contato:item?.contato || "",
    contato_2:item?.contato_2 || "",
    flyer_url:storedFamilyFlyer(item, 1),
    flyer_url_2:storedFamilyFlyer(item, 2),
    flyer_oculto:Boolean(item?.flyer_oculto),
    observacao:item?.observacao || "",
    ...overrides,
  };
}

function closeFamilyDeleteConfirm(){
  if(!familyDeleteConfirm) return;
  familyDeleteConfirm.hidden = true;
  pendingFamilyDelete = null;
  if(familyDeleteConfirmInput){
    familyDeleteConfirmInput.value = "";
    familyDeleteConfirmInput.disabled = false;
  }
  if(familyDeleteConfirmSubmit){
    familyDeleteConfirmSubmit.disabled = true;
    familyDeleteConfirmSubmit.textContent = "Excluir definitivamente";
  }
  if(familyDeletePreviousFocus?.isConnected) familyDeletePreviousFocus.focus();
  familyDeletePreviousFocus = null;
}

function syncFamilyDeleteConfirmation(){
  if(!familyDeleteConfirmInput || !familyDeleteConfirmSubmit || !pendingFamilyDelete) return;
  familyDeleteConfirmSubmit.disabled = normalizeFamilyFlyerKey(familyDeleteConfirmInput.value) !== normalizeFamilyFlyerKey(pendingFamilyDelete.nome);
}

function openFamilyDeleteConfirm(item){
  if(!item || !familyDeleteConfirm){
    setFeedback(familiaFeedback, "Não foi possível abrir a confirmação de exclusão.", true);
    return;
  }
  pendingFamilyDelete = {id:item.id, nome:item.nome || "Família"};
  familyDeletePreviousFocus = document.activeElement;
  if(familyDeleteConfirmTitle) familyDeleteConfirmTitle.textContent = `Excluir ${pendingFamilyDelete.nome}?`;
  if(familyDeleteConfirmText) familyDeleteConfirmText.textContent = `${pendingFamilyDelete.nome} deixará de aparecer no cadastro e não poderá receber novas movimentações.`;
  if(familyDeleteConfirmName) familyDeleteConfirmName.textContent = pendingFamilyDelete.nome;
  if(familyDeleteConfirmInput){
    familyDeleteConfirmInput.value = "";
    familyDeleteConfirmInput.disabled = false;
  }
  if(familyDeleteConfirmSubmit){
    familyDeleteConfirmSubmit.disabled = true;
    familyDeleteConfirmSubmit.textContent = "Excluir definitivamente";
  }
  familyDeleteConfirm.hidden = false;
  requestAnimationFrame(() => familyDeleteConfirmInput?.focus());
}

async function submitFamilyDelete(){
  if(!pendingFamilyDelete || !familyDeleteConfirmSubmit || familyDeleteConfirmSubmit.disabled || !canWrite) return;
  const item = {...pendingFamilyDelete};
  familyDeleteConfirmSubmit.disabled = true;
  familyDeleteConfirmSubmit.textContent = "Excluindo...";
  if(familyDeleteConfirmInput) familyDeleteConfirmInput.disabled = true;
  try{
    const {res, data} = await fetchJson(`/api/familias/${encodeURIComponent(item.id)}`, {
      method:"DELETE",
      headers:csrfHeaders(),
    });
    setFeedback(familiaFeedback, data.message || (res.ok ? "Família excluída." : "Erro ao excluir família."), !res.ok);
    if(res.ok){
      closeFamilyDeleteConfirm();
      await loadFamilias();
      return;
    }
  }catch(error){
    setFeedback(familiaFeedback, `Falha ao excluir família: ${error.message}`, true);
  }
  if(familyDeleteConfirmInput) familyDeleteConfirmInput.disabled = false;
  familyDeleteConfirmSubmit.textContent = "Excluir definitivamente";
  syncFamilyDeleteConfirmation();
}

familiasGrid?.addEventListener("click", async (event) => {
  const contactButton = event.target.closest("[data-toggle-family-contact]");
  if(contactButton){
    const contact = contactButton.closest(".family-contact");
    const value = contact?.querySelector("[data-family-contact-value]");
    if(!value) return;
    const willShow = value.hidden;
    value.hidden = !willShow;
    contactButton.textContent = willShow ? "Esconder contato" : "Mostrar contato";
    return;
  }

  const editButton = event.target.closest("[data-editar-familia]");
  if(editButton){
    iniciarEdicaoFamilia(editButton.dataset.editarFamilia);
    return;
  }

  const flyerButton = event.target.closest("[data-remover-flyer]");
  if(flyerButton && canWrite){
    const id = flyerButton.dataset.removerFlyer;
    const item = familiasCache.find(familia => familia.id === id);
    if(!item || !window.confirm(`Remover os flyers de ${item.nome}? Você poderá adicionar outras imagens depois em Editar.`)) return;
    flyerButton.disabled = true;
    try{
      const {res, data} = await fetchJson(`/api/familias/${encodeURIComponent(id)}`, {
        method:"PUT",
        headers:csrfHeaders({"Content-Type":"application/json"}),
        body:JSON.stringify(familyPayloadFromItem(item, {flyer_url:"", flyer_url_2:"", flyer_oculto:true})),
      });
      setFeedback(familiaFeedback, data.message || (res.ok ? "Flyers removidos." : "Erro ao remover flyers."), !res.ok);
      if(res.ok) await loadFamilias();
    }catch(error){
      setFeedback(familiaFeedback, `Falha ao remover flyers: ${error.message}`, true);
    }finally{
      flyerButton.disabled = false;
    }
    return;
  }

  const deleteButton = event.target.closest("[data-apagar-familia]");
  if(!deleteButton || !canWrite) return;
  const id = deleteButton.dataset.apagarFamilia;
  const item = familiasCache.find(familia => familia.id === id);
  openFamilyDeleteConfirm(item);
});

function integer(value){
  return new Intl.NumberFormat("pt-BR", {maximumFractionDigits:0}).format(Number(value || 0));
}

function positiveIntegerFrom(id){
  const value = Math.floor(Number(inputValue(id) || 0));
  if(!Number.isFinite(value) || value < 0) return 0;
  return value;
}

function collectCraftTotals(){
  const totals = new Map();
  let totalItens = 0;

  CRAFT_RECIPES.forEach(recipe => {
    const quantity = positiveIntegerFrom(recipe.inputId);
    totalItens += quantity;
    if(quantity <= 0) return;

    recipe.materials.forEach(([material, amount]) => {
      totals.set(material, (totals.get(material) || 0) + (amount * quantity));
    });
  });

  return {totalItens, totals};
}

function bindInventoryInputs(){
  craftTable?.querySelectorAll("[data-have-material]").forEach(input => {
    input.addEventListener("change", () => {
      const material = input.dataset.haveMaterial;
      craftInventory[material] = Math.max(0, Math.floor(Number(input.value || 0)) || 0);
      renderCraft();
    });
  });
}

function renderCraft(){
  if(!craftTable) return;

  if(!canWrite){
    setTableContent(craftTable, `<tr><td colspan="4">Modo somente leitura. A tabela de receitas está disponível abaixo.</td></tr>`);
    return;
  }

  const {totalItens, totals} = collectCraftTotals();
  setText("craftTotalItens", integer(totalItens));

  if(totalItens <= 0 || totals.size === 0){
    setTableContent(craftTable, `<tr><td colspan="4">Informe uma quantidade para calcular.</td></tr>`);
    setFeedback(craftFeedback, "Informe uma quantidade para calcular os materiais.");
    return;
  }

  setTableContent(craftTable, Array.from(totals.entries()).map(([material, total]) => {
    const tenho = Math.max(0, Math.floor(Number(craftInventory[material] || 0)) || 0);
    const falta = Math.max(total - tenho, 0);
    return `
      <tr>
        <td><strong>${escapeHtml(material)}</strong></td>
        <td>${integer(total)}</td>
        <td>
          <input class="mini-input" type="number" min="0" step="1" value="${tenho || ""}" placeholder="0" data-have-material="${escapeHtml(material)}" />
        </td>
        <td><span class="missing-value ${falta > 0 ? "pending" : "success"}">${integer(falta)}</span></td>
      </tr>`;
  }).join(""));

  setFeedback(craftFeedback, `Cálculo pronto: ${integer(totalItens)} item(ns) selecionado(s).`);
  bindInventoryInputs();
}

function renderRecipes(){
  if(!recipeGrid) return;

  recipeGrid.innerHTML = CRAFT_RECIPES.map(recipe => `
    <details class="recipe-card">
      <summary class="recipe-head">
        <h4>${escapeHtml(recipe.title)}</h4>
        <span>${escapeHtml(recipe.helper)}</span>
        <b aria-hidden="true">+</b>
      </summary>
      <div class="recipe-list">
        ${recipe.materials.map(([material, amount]) => `
          <div>
            <span>${escapeHtml(material)}</span>
            <strong>${integer(amount)}</strong>
          </div>`).join("")}
      </div>
    </details>
  `).join("");
}

craftInputs.forEach(input => {
  input.addEventListener("input", renderCraft);
});

craftForm?.addEventListener("submit", (e) => {
  e.preventDefault();
  renderCraft();
});

clearCraftBtn?.addEventListener("click", () => {
  craftInputs.forEach(input => input.value = "");
  Object.keys(craftInventory).forEach(key => delete craftInventory[key]);
  renderCraft();
});

async function loadHealth(){
  try{
    const {data} = await fetchJson("/health");
    document.getElementById("systemStatus").textContent = data.ok ? "Operacional" : "Erro";
  }catch{
    document.getElementById("systemStatus").textContent = "Offline";
  }
}

async function loadResumo(){
  try{
    const [rc, rv, re, rm] = await Promise.all([
      fetch("/api/resumo"),
      fetch("/api/resumo-vendas"),
      fetch("/api/resumo-encomendas"),
      fetch("/api/resumo-metas")
    ]);
    const dc = await parseResponse(rc);
    const dv = await parseResponse(rv);
    const de = await parseResponse(re);
    const dm = await parseResponse(rm);
    document.getElementById("statCompras").textContent = dc.total_registros ?? 0;
    document.getElementById("statVendas").textContent = dv.total_registros ?? 0;
    document.getElementById("statEncomendas").textContent = de.total_registros ?? 0;
    document.getElementById("statValorCompras").textContent = currency(dc.valor_movimentado ?? 0);
    document.getElementById("statValorVendas").textContent = currency(dv.valor_movimentado ?? 0);
    document.getElementById("statValorEncomendas").textContent = currency(de.valor_movimentado ?? 0);
    updateMetaCounters(dm.total ?? 0, dm.pagos ?? 0, dm.faltam_confirmar ?? 0, dm.confirmados ?? 0, dm.semana_label ?? "--", dm.nao_pagos ?? 0);
  }catch{}
}

async function loadCompras(){
  const comprasColspan = canWrite ? 9 : 8;
  try{
    const {res, data} = await fetchJson("/api/compras");
    if(!res.ok){
      setTableContent(comprasTable, `<tr><td colspan="${comprasColspan}">${escapeHtml(data.error || "Erro ao carregar compras.")}</td></tr>`);
      return;
    }
    if(!Array.isArray(data) || !data.length){
      setTableContent(comprasTable, `<tr><td colspan="${comprasColspan}">Nenhuma compra registrada.</td></tr>`);
      return;
    }
    setTableContent(comprasTable, data.map(item => {
      const family = familyForOrder(item);
      const linked = Boolean(family?.id || item.familia_id);
      const seller = linked
        ? familyChipHtml(family, {nome:item.familia_nome || item.quem_vendeu, icone:item.familia_icone, responsavel:item.familia_responsavel, linked:true})
        : escapeHtml(item.quem_vendeu);
      return `<tr>
        <td>${escapeHtml(item.data)}</td>
        <td>${escapeHtml(item.produto)}</td>
        <td>${escapeHtml(item.quem_pediu)}</td>
        <td>${seller}</td>
        <td>${escapeHtml(item.quantidade)}</td>
        <td>${moneyTypeBadge(item.tipo_dinheiro, item.percentual_dinheiro_sujo)}</td>
        <td>${currency(item.valor_total)}</td>
        <td>${escapeHtml(item.observacao || "—")}</td>
        ${canWrite ? `<td><button type="button" class="danger-btn table-action-btn" data-remover-compra="${escapeHtml(item.id)}" data-compra-desc="${escapeHtml(`${item.quantidade}x ${item.produto} — ${currency(item.valor_total)} (${item.data})`)}">Remover</button></td>` : ""}
      </tr>`;
    }).join(""));
  }catch(error){
    setTableContent(comprasTable, `<tr><td colspan="${comprasColspan}">Falha ao carregar compras: ${escapeHtml(error.message)}</td></tr>`);
  }
}

async function loadVendas(){
  try{
    const {res, data} = await fetchJson("/api/vendas");
    if(!res.ok){
      setTableContent(vendasTable, `<tr><td colspan="7">${escapeHtml(data.error || "Erro ao carregar vendas.")}</td></tr>`);
      return;
    }
    if(!Array.isArray(data) || !data.length){
      setTableContent(vendasTable, `<tr><td colspan="7">Nenhuma venda registrada.</td></tr>`);
      return;
    }
    setTableContent(vendasTable, data.map(item => {
      const family = familyForOrder(item);
      const familyName = family?.nome || item.familia_nome || item.quem_compra || "Comprador não informado";
      const familyIcon = family?.icone || item.familia_icone || "🤝";
      const familyResponsible = family?.responsavel_contato || item.familia_responsavel || "";
      const linked = Boolean(family?.id || item.familia_id);
      return `<tr>
        <td>${escapeHtml(item.data)}</td>
        <td>${escapeHtml(item.produto)}</td>
        <td>${linked ? familyChipHtml(family, {nome:familyName, icone:familyIcon, responsavel:familyResponsible, linked:true}) : escapeHtml(item.quem_compra)}</td>
        <td>${escapeHtml(item.quem_vende)}</td>
        <td>${escapeHtml(item.quantidade)}</td>
        <td>${moneyTypeBadge(item.tipo_dinheiro, item.percentual_dinheiro_sujo)}</td>
        <td>${currency(item.valor_total)}</td>
      </tr>`;
    }).join(""));
  }catch(error){
    setTableContent(vendasTable, `<tr><td colspan="7">Falha ao carregar vendas: ${escapeHtml(error.message)}</td></tr>`);
  }
}

function reportMedal(position){
  if(position === 1) return "🥇";
  if(position === 2) return "🥈";
  if(position === 3) return "🥉";
  return `#${position}`;
}

function renderRelatorio(data){
  ultimoRelatorio = data;
  const summary = data?.resumo || {};
  const ranking = Array.isArray(data?.ranking) ? data.ranking : [];

  setText("relatorioTitulo", `Ranking de ${data?.mes_label || "mês selecionado"}`);
  setText("relatorioGangues", integer(summary.gangues || 0));
  setText("relatorioTotalGasto", currency(summary.total_gasto || 0));
  setText("relatorioCompras", integer(summary.compras || 0));
  setText("relatorioEncomendasPendentes", integer(summary.encomendas_pendentes || 0));
  setText("relatorioValorPendente", `${currency(summary.valor_pendente || 0)} em aberto`);
  setText("relatorioSemFamilia", integer(summary.vendas_sem_familia || 0));
  setText("relatorioValorSemFamilia", `${currency(summary.valor_sem_familia || 0)} fora do ranking`);

  if(relatorioDownloadBtn) relatorioDownloadBtn.disabled = false;
  if(relatorioPodio){
    const topThree = ranking.slice(0, 3);
    relatorioPodio.innerHTML = topThree.length ? topThree.map(item => `
      <article class="report-podium-card report-position-${item.posicao}">
        <span class="report-medal">${reportMedal(item.posicao)}</span>
        <div class="report-family-icon">${escapeHtml(item.icone || "🤝")}</div>
        <strong>${escapeHtml(item.nome)}</strong>
        <span class="report-family-owner">Contato: ${escapeHtml(item.responsavel_contato || "A definir")}</span>
        <p>${currency(item.total_gasto)}</p>
        <small>${integer(item.compras)} compra${Number(item.compras) === 1 ? "" : "s"}</small>
      </article>`).join("") : `<div class="report-empty">Nenhuma venda ou encomenda vinculada a uma família neste mês.</div>`;
  }

  if(!ranking.length){
    setTableContent(relatorioTable, `<tr><td colspan="8">Nenhuma gangue com movimentação no período selecionado.</td></tr>`);
    return;
  }

  setTableContent(relatorioTable, ranking.map(item => `
    <tr>
      <td><span class="report-rank">${reportMedal(item.posicao)}</span></td>
      <td>${familyChipHtml({id:item.familia_id, nome:item.nome, icone:item.icone, responsavel_contato:item.responsavel_contato})}</td>
      <td><strong class="report-money">${currency(item.total_gasto)}</strong></td>
      <td>${integer(item.compras)}</td>
      <td>${integer(item.encomendas_finalizadas)}</td>
      <td>${integer(item.encomendas_pendentes)}</td>
      <td>${currency(item.valor_pendente)}</td>
      <td>${integer(item.itens_comprados)}</td>
    </tr>`).join(""));
}

async function loadRelatorio(){
  if(!relatorioMes || !relatorioTable) return;
  const month = relatorioMes.value;
  if(!month) return;
  ultimoRelatorio = null;
  if(relatorioDownloadBtn) relatorioDownloadBtn.disabled = true;
  if(relatorioGerarBtn){
    relatorioGerarBtn.disabled = true;
    relatorioGerarBtn.textContent = "Gerando...";
  }
  setFeedback(relatorioFeedback, "Calculando vendas e encomendas do período...");
  try{
    const {res, data} = await fetchJson(`/api/relatorios/gangues?mes=${encodeURIComponent(month)}`);
    if(!res.ok){
      setFeedback(relatorioFeedback, data.error || "Não foi possível gerar o relatório.", true);
      return;
    }
    renderRelatorio(data);
    setFeedback(relatorioFeedback, `Relatório de ${data.mes_label} gerado em ${data.gerado_em}.`);
  }catch(error){
    setFeedback(relatorioFeedback, `Falha ao gerar relatório: ${error.message}`, true);
  }finally{
    if(relatorioGerarBtn){
      relatorioGerarBtn.disabled = false;
      relatorioGerarBtn.textContent = "Gerar relatório";
    }
  }
}

function reportTxt(data){
  const summary = data?.resumo || {};
  const ranking = Array.isArray(data?.ranking) ? data.ranking : [];
  const lines = [
    "KOKUSAI - RELATÓRIO MENSAL POR GANGUE",
    "============================================================",
    `Período: ${data?.mes_label || data?.mes || "Não informado"}`,
    `Gerado em: ${data?.gerado_em || "Não informado"}`,
    "",
    "RESUMO",
    `Gangues no ranking: ${summary.gangues || 0}`,
    `Total gasto: ${currency(summary.total_gasto || 0)}`,
    `Compras concluídas: ${summary.compras || 0}`,
    `Encomendas entregues: ${summary.encomendas_finalizadas || 0}`,
    `Encomendas pendentes: ${summary.encomendas_pendentes || 0}`,
    `Valor pendente: ${currency(summary.valor_pendente || 0)}`,
    `Vendas sem família: ${summary.vendas_sem_familia || 0} (${currency(summary.valor_sem_familia || 0)})`,
    "",
    "RANKING",
    "------------------------------------------------------------",
  ];

  if(!ranking.length) lines.push("Nenhuma gangue com movimentação no período.");
  ranking.forEach(item => {
    lines.push(
      `${item.posicao}. ${item.icone || "🤝"} ${item.nome}`,
      `   Responsável pelo contato: ${item.responsavel_contato || "A definir"}`,
      `   Total gasto: ${currency(item.total_gasto)}`,
      `   Compras concluídas: ${item.compras}`,
      `   Compras diretas: ${item.compras_diretas}`,
      `   Encomendas entregues: ${item.encomendas_finalizadas}`,
      `   Encomendas pendentes: ${item.encomendas_pendentes}`,
      `   Valor pendente: ${currency(item.valor_pendente)}`,
      `   Itens comprados: ${item.itens_comprados}`,
      ""
    );
  });
  return lines.join("\r\n").trimEnd() + "\r\n";
}

relatorioGerarBtn?.addEventListener("click", loadRelatorio);
relatorioMes?.addEventListener("change", loadRelatorio);
relatorioDownloadBtn?.addEventListener("click", () => {
  if(!ultimoRelatorio) return;
  const blob = new Blob(["\ufeff", reportTxt(ultimoRelatorio)], {type:"text/plain;charset=utf-8"});
  const downloadUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = downloadUrl;
  link.download = `kokusai-relatorio-gangues-${ultimoRelatorio.mes || "mensal"}.txt`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(downloadUrl);
});

async function loadEncomendas(){
  if(!encomendasTable) return;

  const colspan = 9;
  try{
    const {res, data} = await fetchJson("/api/encomendas");
    if(!res.ok){
      encomendasCache = [];
      updateOrderFilterCount(0);
      setTableContent(encomendasTable, `<tr><td colspan="${colspan}">${escapeHtml(data.error || "Erro ao carregar encomendas.")}</td></tr>`);
      return;
    }
    encomendasCache = Array.isArray(data) ? data : [];
    renderEncomendas();
  }catch(error){
    encomendasCache = [];
    updateOrderFilterCount(0);
    setTableContent(encomendasTable, `<tr><td colspan="${colspan}">Falha ao carregar encomendas: ${escapeHtml(error.message)}</td></tr>`);
  }
}

encomendasBusca?.addEventListener("input", renderEncomendas);
encomendasOrdenacao?.addEventListener("change", renderEncomendas);
encomendasDataInicio?.addEventListener("change", renderEncomendas);
encomendasDataFim?.addEventListener("change", renderEncomendas);
encomendasLimparFiltros?.addEventListener("click", clearOrderFilters);
encomendasQuickFilters.forEach(button => {
  button.addEventListener("click", () => setActiveOrderFilter(button.dataset.orderFilter));
});


async function loadFamilias(){
  if(!familiasGrid) return;
  try{
    const {res, data} = await fetchJson("/api/familias");
    if(!res.ok){
      familiasGrid.innerHTML = `<div class="family-empty">${escapeHtml(data.error || "Erro ao carregar famílias.")}</div>`;
      return;
    }

    const items = Array.isArray(data) ? data : [];
    familiasCache = items;
    const abertas = items.filter(item => item.mercado === "Aberto").length;
    setText("familiasTotal", integer(items.length));
    setText("familiasAbertas", integer(abertas));
    setText("familiasFechadas", integer(items.length - abertas));

    if(familiasDatalist){
      familiasDatalist.innerHTML = items.map(item => `<option value="${escapeHtml(item.nome)}"></option>`).join("");
    }
    const familyOptions = items.map(item => {
      const market = familyMarketInfo(item);
      return `<option value="${escapeHtml(item.id)}" ${market.open ? "" : "disabled"}>${escapeHtml(familyOptionLabel(item))}</option>`;
    }).join("");
    if(compraFamiliaSelect){
      const selectedFamilyId = compraFamiliaSelect.value;
      compraFamiliaSelect.innerHTML = `<option value="">Fornecedor sem família cadastrada</option>${familyOptions}`;
      if(items.some(item => item.id === selectedFamilyId)) compraFamiliaSelect.value = selectedFamilyId;
      syncCompraFamilyField();
    }
    if(encomendaFamiliaSelect){
      const selectedFamilyId = encomendaFamiliaSelect.value;
      encomendaFamiliaSelect.innerHTML = `<option value="">Selecione a família responsável</option>${familyOptions}`;
      if(items.some(item => item.id === selectedFamilyId)) encomendaFamiliaSelect.value = selectedFamilyId;
      renderFamilySelectionSummary(items.find(item => item.id === encomendaFamiliaSelect.value), encomendaFamilySummary);
    }
    if(vendaFamiliaSelect){
      const selectedFamilyId = vendaFamiliaSelect.value;
      vendaFamiliaSelect.innerHTML = `<option value="">Sem família cadastrada</option>${familyOptions}`;
      if(items.some(item => item.id === selectedFamilyId)) vendaFamiliaSelect.value = selectedFamilyId;
      syncVendaFamilyField();
    }

    if(!items.length){
      familiasGrid.innerHTML = '<div class="family-empty">Nenhuma família ou gangue cadastrada.</div>';
      return;
    }

    familiasGrid.innerHTML = items.map(item => {
      const market = familyMarketInfo(item);
      const localFlyers = getLocalFamilyFlyers(item);
      const configuredFlyers = [item.flyer_url, item.flyer_url_2].filter(Boolean);
      const flyerUrls = item.flyer_oculto ? [] : (configuredFlyers.length ? configuredFlyers : localFlyers);
      const flyer = flyerUrls.length
        ? `<div class="family-flyer ${flyerUrls.length > 1 ? "family-flyer-multiple" : ""}">${flyerUrls.map((url, index) => `<img data-family-flyer src="${escapeHtml(url)}" alt="Flyer ${index + 1} de ${escapeHtml(item.nome)}" referrerpolicy="no-referrer" />`).join("")}</div>`
        : `<div class="family-flyer family-flyer-empty"><span>${escapeHtml(item.icone || "🤝")}</span><small>Sem flyer vinculado</small></div>`;
      const contacts = [item.contato, item.contato_2].filter(Boolean);
      const contactsHtml = contacts.length ? `<div class="family-contacts">${contacts.map((contact, index) => `<div class="family-contact"><button type="button" class="family-contact-toggle" data-toggle-family-contact>Mostrar contato ${index + 1}</button><span data-family-contact-value hidden>${escapeHtml(contact)}</span></div>`).join("")}</div>` : "";
      return `<article class="family-card ${market.className}">
        <div class="family-card-content">
          <div class="family-card-top">
            <div><span class="family-icon">${escapeHtml(item.icone || "🤝")}</span><h4>${escapeHtml(item.nome)}</h4></div>
            <div class="family-card-controls">
              <span class="market-status ${market.className}">${escapeHtml(market.label)}</span>
              ${canWrite ? `<button type="button" class="family-quick-edit" data-editar-familia="${escapeHtml(item.id)}" aria-label="Editar informações de ${escapeHtml(item.nome)}">Editar</button>` : ""}
              ${canWrite ? `<button type="button" class="family-quick-delete" data-apagar-familia="${escapeHtml(item.id)}" aria-label="Excluir permanentemente ${escapeHtml(item.nome)}">Excluir</button>` : ""}
            </div>
          </div>
          <div class="family-responsible-card"><span>Responsável pelo contato</span><strong>${escapeHtml(item.responsavel_contato || "A definir")}</strong></div>
          <details class="entity-details family-card-details">
            <summary><span>Cadastro e condições</span><b aria-hidden="true">+</b></summary>
            <div class="entity-details-body">
              ${flyer}
              <div class="family-price-grid">
                <div><span>Nosso valor</span><p>${escapeHtml(item.preco_venda_para_familia || "Não informado")}</p></div>
                <div><span>Valor deles</span><p>${escapeHtml(item.preco_compra_da_familia || "Não informado")}</p></div>
              </div>
              ${contactsHtml}
              ${item.observacao ? `<p class="family-note">${escapeHtml(item.observacao)}</p>` : ""}
              ${canWrite && flyerUrls.length ? `<div class="family-actions"><button type="button" class="family-flyer-delete-btn" data-remover-flyer="${escapeHtml(item.id)}">Remover flyers</button></div>` : ""}
            </div>
          </details>
        </div>
      </article>`;
    }).join("");

    familiasGrid.querySelectorAll("img[data-family-flyer]").forEach(image => {
      image.addEventListener("error", () => {
        const container = image.closest(".family-flyer");
        image.remove();
        if(container && !container.querySelector("img[data-family-flyer]")){
          container.innerHTML = '<span>🖼️</span><small>Flyers indisponíveis</small>';
          container.classList.add("family-flyer-empty");
        }else{
          container?.classList.remove("family-flyer-multiple");
        }
      }, {once:true});
    });
  }catch(error){
    familiasGrid.innerHTML = `<div class="family-empty">Falha ao carregar famílias: ${escapeHtml(error.message)}</div>`;
  }
}

async function loadReunioes(){
  if(!reunioesGrid) return;
  try{
    const {res, data} = await fetchJson("/api/reunioes");
    if(!res.ok){ reunioesGrid.innerHTML = `<div class="meeting-empty">${escapeHtml(data.error || "Erro ao carregar reuniões.")}</div>`; return; }
    const items = Array.isArray(data) ? data : [];
    reunioesCache = items;
    const finalizadas = items.filter(item => item.status === "Finalizada").length;
    const canceladas = items.filter(item => item.status === "Cancelada").length;
    const agendadas = items.length - finalizadas - canceladas;
    setText("reunioesAgendadas", integer(agendadas));
    setText("reunioesFinalizadas", integer(finalizadas));
    setText("reunioesCanceladas", integer(canceladas));
    if(!items.length){ reunioesGrid.innerHTML = '<div class="meeting-empty">Nenhuma reunião agendada até o momento.</div>'; return; }
    reunioesGrid.innerHTML = items.map(item => {
      const done = item.status === "Finalizada";
      const canceled = item.status === "Cancelada";
      const pending = item.status === "Aguardando confirmação";
      const statusClass = done ? "finished" : (canceled ? "canceled" : (pending ? "pending" : "scheduled"));
      const statusLabel = done ? "Finalizada" : (canceled ? "Cancelada" : (pending ? "Aguardando confirmação" : "Agendada"));
      const date = item.data ? new Date(`${item.data}T12:00:00`) : null;
      const dateLabel = date && !Number.isNaN(date.getTime()) ? date.toLocaleDateString("pt-BR", {weekday:"short", day:"2-digit", month:"short"}) : item.data;
      const relationship = item.responsavel_contato
        ? `<div class="meeting-relationship"><span>Responsável pelo contato</span><strong>${escapeHtml(item.responsavel_contato)}</strong></div>`
        : "";
      const extraDetails = item.local || item.pauta || done || canceled || canWrite;
      return `<article class="meeting-card ${statusClass}">
        <div class="meeting-icon">${escapeHtml(item.icone || "🤝")}</div>
        <div class="meeting-card-content">
          <div class="meeting-card-top"><span class="meeting-status ${statusClass}">${statusLabel}</span><span class="meeting-gang">${escapeHtml(item.gangue)}</span></div>
          <h4>${escapeHtml(item.titulo)}</h4>
          ${relationship}
          <div class="meeting-details"><span>📆 ${escapeHtml(dateLabel || "--")}</span><span>🕒 ${escapeHtml(item.horario || "--")}</span></div>
          ${extraDetails ? `<details class="entity-details meeting-card-details">
            <summary><span>Ver detalhes</span><b aria-hidden="true">+</b></summary>
            <div class="entity-details-body">
              ${item.local ? `<div class="meeting-location">📍 ${escapeHtml(item.local)}</div>` : ""}
              ${item.pauta ? `<p>${escapeHtml(item.pauta)}</p>` : ""}
              ${done ? `<small>Concluída em ${escapeHtml(item.finalizada_em || "--")}</small>` : ""}
              ${canceled ? `<small class="meeting-canceled-at">Cancelada em ${escapeHtml(item.finalizada_em || "--")}</small>` : ""}
              ${canWrite ? `<div class="meeting-actions"><button class="meeting-edit-btn" type="button" data-editar-reuniao="${escapeHtml(item.id)}">Editar</button>${done || canceled ? "" : `<button class="meeting-cancel-btn" type="button" data-cancelar-reuniao="${escapeHtml(item.id)}">Cancelar</button><button class="meeting-finish-btn" type="button" data-finalizar-reuniao="${escapeHtml(item.id)}">Finalizar</button>`}</div>` : ""}
            </div>
          </details>` : ""}
        </div>
      </article>`;
    }).join("");
  }catch(error){ reunioesGrid.innerHTML = `<div class="meeting-empty">Falha ao carregar reuniões: ${escapeHtml(error.message)}</div>`; }
}

function metaStatusClass(status){
  const value = String(status || "Pendente").toLowerCase();
  if(value === "pago") return "paid";
  if(value === "enviado") return "sent";
  if(value === "recusado" || value === "não pago" || value === "nao pago") return "rejected";
  return "pending";
}

function renderMetaRooms(){
  if(!metaRoomsGrid) return;
  const term = String(metaRoomsSearch?.value || "").trim().toLocaleLowerCase("pt-BR");
  const rooms = metaRoomsCache.filter(room => !term || `${room.display_name} ${room.username}`.toLocaleLowerCase("pt-BR").includes(term));
  if(!rooms.length){
    metaRoomsGrid.innerHTML = '<div class="meta-empty-state">Nenhuma sala encontrada.</div>';
    return;
  }
  metaRoomsGrid.innerHTML = rooms.map(room => {
    const unpaidStreak = integer(room.consecutive_unpaid_weeks || 0);
    const paymentAlert = room.payment_warning
      ? `<small class="meta-payment-alert" title="${unpaidStreak} semanas consecutivas sem meta paga">! ${unpaidStreak} semanas</small>`
      : "";
    return `
    <button type="button" class="meta-room-list-item ${room.user_id === selectedMetaRoomUserId ? "active" : ""} ${room.payment_warning ? "has-payment-warning" : ""}" data-meta-room-user="${escapeHtml(room.user_id)}">
      <span class="meta-room-avatar">${escapeHtml(String(room.display_name || "?").slice(0, 1).toUpperCase())}</span>
      <span class="meta-room-person"><strong>${escapeHtml(room.display_name)}</strong><small>@${escapeHtml(room.username)}</small></span>
      <span class="meta-room-list-info"><span class="meta-status-badge ${metaStatusClass(room.status)}">${escapeHtml(room.status)}</span><small>${integer(room.photo_count || 0)} foto(s)</small>${paymentAlert}</span>
    </button>`;
  }).join("");
}

async function loadMetaRoomDetail(userId){
  if(!metaRoomDetail) return;
  selectedMetaRoomUserId = userId;
  renderMetaRooms();
  metaRoomDetail.innerHTML = '<div class="meta-empty-state">Carregando sala...</div>';
  try{
    const weekQuery = activeMetaWeek?.semana_inicio ? `?week_start=${encodeURIComponent(activeMetaWeek.semana_inicio)}` : "";
    const {res, data} = await fetchJson(`/api/meta-rooms/${encodeURIComponent(userId)}${weekQuery}`);
    if(!res.ok){ metaRoomDetail.innerHTML = `<div class="meta-empty-state">${escapeHtml(data.error || "Erro ao abrir sala.")}</div>`; return; }
    const submission = data.submission || {};
    const photos = Array.isArray(data.photos) ? data.photos : [];
    const history = Array.isArray(data.history) ? data.history : [];
    const photosHtml = photos.length
      ? `<div class="admin-meta-photo-grid">${photos.map((photo, index) => `<a href="${escapeHtml(photo.url)}" target="_blank" rel="noopener"><img src="${escapeHtml(photo.url)}" alt="Comprovante ${index + 1} de ${escapeHtml(data.member.display_name)}" /><span>Foto ${index + 1}</span></a>`).join("")}</div>`
      : '<div class="meta-empty-state compact">Nenhuma foto enviada nesta semana.</div>';
    const historyHtml = history.length
      ? history.map(item => `<tr><td>${escapeHtml(item.week_start)} até ${escapeHtml(item.week_end)}</td><td>${integer(item.photo_count || 0)}</td><td><span class="meta-status-badge ${metaStatusClass(item.status)}">${escapeHtml(item.status)}</span></td><td>${escapeHtml(item.reviewed_at || "—")}</td></tr>`).join("")
      : '<tr><td colspan="4">Nenhum histórico ainda.</td></tr>';
    const unpaidStreak = integer(data.payment_monitor?.consecutive_unpaid_weeks || 0);
    const paymentWarningHtml = data.payment_monitor?.warning
      ? `<aside class="meta-payment-warning admin-payment-warning"><span class="meta-payment-warning-icon" aria-hidden="true">!</span><div><strong>Atenção: ${unpaidStreak} semanas sem meta paga</strong><p>O aviso considera somente semanas já finalizadas e consecutivas.</p></div></aside>`
      : "";
    const reviewAllowed = Boolean(activeMetaWeek?.review_mode && !activeMetaWeek?.closed);
    const reviewPanel = reviewAllowed
      ? `<div class="meta-review-panel"><label for="metaAdminNote">Observação para o membro</label><textarea id="metaAdminNote" placeholder="Opcional: orientação ou justificativa">${escapeHtml(submission.admin_note || "")}</textarea><div class="meta-review-actions"><button type="button" class="meta-review-paid" data-meta-review="Pago" data-submission-id="${escapeHtml(submission.id)}">✓ Marcar pago</button><button type="button" class="meta-review-rejected" data-meta-review="Não pago" data-submission-id="${escapeHtml(submission.id)}">✕ Marcar não pago</button><button type="button" class="meta-review-pending" data-meta-review="Pendente" data-submission-id="${escapeHtml(submission.id)}">Voltar para pendente</button></div></div>`
      : `<div class="meta-empty-state compact">${activeMetaWeek?.closed ? "Esta semana já foi finalizada e está bloqueada." : "A conferência será liberada após quarta-feira às 23:59."}</div>`;

    metaRoomDetail.innerHTML = `
      <div class="meta-room-detail-head">
        <div><p class="panel-kicker">Sala individual</p><h3>${escapeHtml(data.member.display_name)}</h3><small>@${escapeHtml(data.member.username)}</small></div>
        <span class="meta-status-badge ${metaStatusClass(submission.status)}">${escapeHtml(submission.status || "Pendente")}</span>
      </div>
      ${paymentWarningHtml}
      <div class="meta-detail-week"><span>Semana</span><strong>${escapeHtml(submission.week_start)} até ${escapeHtml(submission.week_end)}</strong><small>${integer(photos.length)} foto(s) enviada(s)</small></div>
      ${photosHtml}
      ${canWrite ? reviewPanel : (submission.admin_note ? `<p class="family-note">Observação: ${escapeHtml(submission.admin_note)}</p>` : "")}
      <div class="meta-detail-history"><div class="panel-head"><div><p class="panel-kicker">Histórico</p><h3>Semanas anteriores</h3></div></div><div class="table-wrap"><table class="responsive-table"><thead><tr><th>Semana</th><th>Fotos</th><th>Status</th><th>Revisado</th></tr></thead><tbody>${historyHtml}</tbody></table></div></div>`;
  }catch(error){
    metaRoomDetail.innerHTML = `<div class="meta-empty-state">Falha ao abrir sala: ${escapeHtml(error.message)}</div>`;
  }
}

metaRoomsGrid?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-meta-room-user]");
  if(button) loadMetaRoomDetail(button.dataset.metaRoomUser);
});

metaRoomsSearch?.addEventListener("input", renderMetaRooms);

function closeMetaReviewConfirm(){
  if(!metaReviewConfirm) return;
  metaReviewConfirm.hidden = true;
  metaReviewConfirm.dataset.status = "";
  pendingMetaReview = null;
  if(metaConfirmPreviousFocus?.isConnected) metaConfirmPreviousFocus.focus();
  metaConfirmPreviousFocus = null;
}

function openMetaReviewConfirm(button, status){
  if(!metaReviewConfirm || !metaReviewConfirmTitle || !metaReviewConfirmText || !metaReviewConfirmSubmit){
    submitMetaReview(button, status);
    return;
  }
  const member = metaRoomsCache.find(room => room.user_id === selectedMetaRoomUserId);
  const memberName = member?.display_name || "esta pessoa";
  const isPaid = status === "Pago";
  pendingMetaReview = {button, status};
  metaConfirmPreviousFocus = document.activeElement;
  metaReviewConfirm.dataset.status = isPaid ? "paid" : "unpaid";
  if(metaReviewConfirmIcon) metaReviewConfirmIcon.textContent = isPaid ? "✓" : "!";
  metaReviewConfirmTitle.textContent = isPaid ? "Confirmar meta paga?" : "Confirmar meta não paga?";
  metaReviewConfirmText.textContent = isPaid
    ? `${memberName} ficará como pago nesta semana.`
    : `${memberName} ficará como não pago nesta semana.`;
  metaReviewConfirmSubmit.textContent = isPaid ? "Confirmar pagamento" : "Confirmar não pagamento";
  metaReviewConfirm.hidden = false;
  requestAnimationFrame(() => metaReviewConfirmSubmit.focus());
}

async function submitMetaReview(button, status){
  if(!button?.isConnected || !canWrite) return;
  const buttons = metaRoomDetail.querySelectorAll("[data-meta-review]");
  buttons.forEach(item => item.disabled = true);
  try{
    const {res, data} = await fetchJson(`/api/meta-rooms/${encodeURIComponent(button.dataset.submissionId)}/status`, {
      method:"POST",
      headers:csrfHeaders({"Content-Type":"application/json"}),
      body:JSON.stringify({status, admin_note:inputValue("metaAdminNote").trim()}),
    });
    setFeedback(metasFeedback, data.message || (res.ok ? "Status atualizado." : "Erro ao revisar meta."), !res.ok);
    if(res.ok){
      await Promise.all([loadMetas(), loadResumo()]);
    }
  }catch(error){ setFeedback(metasFeedback, `Falha ao revisar meta: ${error.message}`, true); }
  finally{ buttons.forEach(item => item.disabled = false); }
}

metaRoomDetail?.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-meta-review]");
  if(!button || !canWrite) return;
  const status = button.dataset.metaReview;
  if(["Pago", "Não pago"].includes(status)){
    openMetaReviewConfirm(button, status);
    return;
  }
  await submitMetaReview(button, status);
});

metaReviewConfirmCancel?.addEventListener("click", closeMetaReviewConfirm);
metaReviewConfirmSubmit?.addEventListener("click", async () => {
  const review = pendingMetaReview;
  if(!review) return;
  closeMetaReviewConfirm();
  await submitMetaReview(review.button, review.status);
});
metaReviewConfirm?.addEventListener("click", event => {
  if(event.target === metaReviewConfirm) closeMetaReviewConfirm();
});
familyDeleteConfirmInput?.addEventListener("input", syncFamilyDeleteConfirmation);
familyDeleteConfirmCancel?.addEventListener("click", closeFamilyDeleteConfirm);
familyDeleteConfirmSubmit?.addEventListener("click", submitFamilyDelete);
familyDeleteConfirm?.addEventListener("click", event => {
  if(event.target === familyDeleteConfirm) closeFamilyDeleteConfirm();
});
document.addEventListener("keydown", event => {
  if(event.key === "Escape" && metaReviewConfirm && !metaReviewConfirm.hidden) closeMetaReviewConfirm();
  if(event.key === "Escape" && familyDeleteConfirm && !familyDeleteConfirm.hidden) closeFamilyDeleteConfirm();
  if(event.key === "Enter" && familyDeleteConfirm && !familyDeleteConfirm.hidden && !familyDeleteConfirmSubmit?.disabled){
    event.preventDefault();
    submitFamilyDelete();
  }
});

finalizeMetaWeekBtn?.addEventListener("click", async () => {
  if(!activeMetaWeek?.semana_inicio || !activeMetaWeek?.can_finalize) return;
  if(!window.confirm(`Finalizar a semana ${activeMetaWeek.semana_label}? Os resultados serão bloqueados e um TXT será baixado neste computador.`)) return;
  finalizeMetaWeekBtn.disabled = true;
  finalizeMetaWeekBtn.textContent = "Gerando log...";
  try{
    const response = await fetch("/api/meta-weeks/finalize", {
      method:"POST",
      headers:csrfHeaders({"Content-Type":"application/json"}),
      body:JSON.stringify({week_start:activeMetaWeek.semana_inicio}),
    });
    if(!response.ok){
      const data = await parseResponse(response);
      throw new Error(data.error || "Não foi possível finalizar a semana.");
    }
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const filenameMatch = disposition.match(/filename="?([^";]+)"?/i);
    const filename = filenameMatch?.[1] || `kokusai-metas-${activeMetaWeek.semana_inicio.replaceAll("/", "-")}.txt`;
    const downloadUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(downloadUrl);
    setFeedback(metasFeedback, "Semana finalizada. O log TXT foi baixado neste computador.");
    selectedMetaRoomUserId = null;
    await Promise.all([loadMetas(), loadResumo()]);
  }catch(error){
    setFeedback(metasFeedback, error.message, true);
    finalizeMetaWeekBtn.disabled = false;
    finalizeMetaWeekBtn.textContent = "Finalizar semana e baixar TXT";
  }
});

async function loadMetas(){
  if(!metaRoomsGrid) return;
  try{
    const {res, data} = await fetchJson("/api/meta-rooms");
    if(!res.ok){
      metaRoomsGrid.innerHTML = `<div class="meta-empty-state">${escapeHtml(data.error || "Erro ao carregar salas de meta.")}</div>`;
      setFeedback(metasFeedback, data.error || "Erro ao carregar salas de meta.", true);
      return;
    }
    metaRoomsCache = Array.isArray(data.rooms) ? data.rooms : [];
    activeMetaWeek = data.week || null;
    const pagos = metaRoomsCache.filter(room => room.status === "Pago").length;
    const naoPagos = metaRoomsCache.filter(room => room.status === "Não pago").length;
    const pendingReviews = metaRoomsCache.filter(room => !["Pago", "Não pago"].includes(room.status)).length;
    updateMetaCounters(metaRoomsCache.length, pagos, pendingReviews, pagos, data.week?.semana_label || "--", naoPagos);
    if(metaCycleDeadline) metaCycleDeadline.textContent = `Pagamento até ${data.week?.prazo_pagamento || "quarta-feira às 23:59"} • conferência em ${data.week?.data_conferencia || "quinta-feira"}`;
    if(metaCycleStatus){
      if(data.week?.closed){
        metaCycleStatus.textContent = `Semana finalizada em ${data.week.closure?.closed_at || "--"} por ${data.week.closure?.closed_by || "admin"}`;
      }else if(data.week?.review_mode){
        metaCycleStatus.textContent = pendingReviews ? `Conferência aberta: faltam revisar ${pendingReviews} pessoa(s)` : "Conferência concluída: semana pronta para finalizar";
      }else{
        metaCycleStatus.textContent = "Período aberto para envio dos comprovantes";
      }
    }
    if(finalizeMetaWeekBtn){
      finalizeMetaWeekBtn.disabled = !data.week?.can_finalize;
      finalizeMetaWeekBtn.textContent = data.week?.closed
        ? "Semana finalizada"
        : data.week?.review_mode && pendingReviews
          ? `Revise ${pendingReviews} pessoa(s)`
          : data.week?.review_mode
            ? "Finalizar semana e baixar TXT"
            : "Fechamento disponível na quinta";
    }
    renderMetaRooms();
    if(selectedMetaRoomUserId && metaRoomsCache.some(room => room.user_id === selectedMetaRoomUserId)){
      await loadMetaRoomDetail(selectedMetaRoomUserId);
    }
  }catch(error){
    metaRoomsGrid.innerHTML = `<div class="meta-empty-state">Falha ao carregar salas: ${escapeHtml(error.message)}</div>`;
  }
}

/* ===== Registro Baú ===== */
const BAU_PAGE_SIZE = 24;
const BAU_MAX_FILE_BYTES = 10 * 1024 * 1024;
const bauView = document.getElementById("registro-bau");
const bauUploadZone = document.getElementById("bauUploadZone");
const bauPhotoInput = document.getElementById("bauPhotoInput");
const bauSelectionPreview = document.getElementById("bauSelectionPreview");
const bauLegendaInput = document.getElementById("bauLegenda");
const bauSelectedCounter = document.getElementById("bauSelectedCounter");
const bauUploadBtn = document.getElementById("bauUploadBtn");
const bauFeedback = document.getElementById("bauFeedback");
const bauGrid = document.getElementById("bauGrid");
const bauCount = document.getElementById("bauCount");
const bauMonthFilter = document.getElementById("bauMonthFilter");
const bauLoadMore = document.getElementById("bauLoadMore");
const bauLightbox = document.getElementById("bauLightbox");
const bauLightboxImg = document.getElementById("bauLightboxImg");
const bauLightboxCaption = document.getElementById("bauLightboxCaption");
const bauLightboxClose = document.getElementById("bauLightboxClose");

const bauState = {items: [], total: 0, month: "", loading: false, uploading: false};
let bauSelected = []; // [{file, previewUrl}]

function isBauImage(file){
  return /^image\/(jpeg|jpg|png|webp)$/i.test(file.type || "") || /\.(jpe?g|png|webp)$/i.test(file.name || "");
}

function bauSignature(file){
  return `${file.name}|${file.size}|${file.lastModified}`;
}

function bauMonthLabel(value){
  const [year, month] = String(value || "").split("-").map(Number);
  if(!year || !month) return String(value || "");
  const label = new Date(year, month - 1, 1).toLocaleDateString("pt-BR", {month:"long", year:"numeric"});
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function clearBauSelection(){
  bauSelected.forEach(item => URL.revokeObjectURL(item.previewUrl));
  bauSelected = [];
  renderBauSelection();
}

function renderBauSelection(){
  if(!bauSelectionPreview) return;
  bauSelectionPreview.textContent = "";
  bauSelectionPreview.hidden = bauSelected.length === 0;
  bauSelected.forEach((item, index) => {
    const card = document.createElement("article");
    card.className = "member-selected-photo";
    const img = document.createElement("img");
    img.src = item.previewUrl;
    img.alt = `Prévia da foto ${index + 1}`;
    const info = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = `Foto ${index + 1}`;
    const name = document.createElement("small");
    name.textContent = item.file.name || "Imagem colada";
    info.append(title, name);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.dataset.bauRemove = String(index);
    remove.setAttribute("aria-label", `Remover foto ${index + 1} da seleção`);
    remove.textContent = "×";
    card.append(img, info, remove);
    bauSelectionPreview.append(card);
  });
  const total = bauSelected.length;
  if(bauSelectedCounter){
    bauSelectedCounter.textContent = total
      ? `${total} foto${total === 1 ? " selecionada" : "s selecionadas"}`
      : "Nenhuma foto selecionada";
  }
  bauUploadZone?.classList.toggle("has-files", total > 0);
  if(bauUploadBtn) bauUploadBtn.disabled = total === 0 || bauState.uploading;
}

function addBauFiles(fileList){
  const incoming = Array.from(fileList || []).filter(Boolean);
  if(!incoming.length) return;
  const known = new Set(bauSelected.map(item => bauSignature(item.file)));
  let rejectedType = 0, rejectedSize = 0;
  incoming.forEach(file => {
    if(!isBauImage(file)){ rejectedType += 1; return; }
    if(file.size > BAU_MAX_FILE_BYTES){ rejectedSize += 1; return; }
    const signature = bauSignature(file);
    if(known.has(signature)) return;
    known.add(signature);
    bauSelected.push({file, previewUrl: URL.createObjectURL(file)});
  });
  renderBauSelection();
  const warnings = [];
  if(rejectedType) warnings.push("Use somente imagens JPG, PNG ou WEBP.");
  if(rejectedSize) warnings.push("Cada foto deve ter no máximo 10 MB.");
  if(warnings.length) setFeedback(bauFeedback, warnings.join(" "), true);
}

function bauCardHtml(item){
  const id = escapeHtml(item.id);
  const caption = item.legenda
    ? `<p class="bau-caption">${escapeHtml(item.legenda)}</p>`
    : '<p class="bau-caption bau-no-caption">Sem legenda</p>';
  const actions = canWrite
    ? `<div class="bau-card-actions"><button type="button" class="ghost-btn" data-bau-edit="${id}">Editar legenda</button><button type="button" class="danger-btn" data-bau-delete="${id}">Excluir</button></div>`
    : "";
  return `<article class="bau-card">
    <button type="button" class="bau-thumb" data-bau-open="${id}" aria-label="Ampliar foto">
      <img src="${escapeHtml(item.url)}" alt="${escapeHtml(item.legenda || "Foto do baú")}" loading="lazy" />
    </button>
    <div class="bau-card-body">
      ${caption}
      <small>${escapeHtml(item.created_at)} · ${escapeHtml(item.registrado_por || "—")}</small>
    </div>
    ${actions}
  </article>`;
}

function renderBauMonths(months){
  if(!bauMonthFilter) return;
  const current = bauState.month;
  const options = ['<option value="">Todos os meses</option>']
    .concat((months || []).map(item => `<option value="${escapeHtml(item.mes)}">${escapeHtml(bauMonthLabel(item.mes))} (${integer(item.total)})</option>`));
  bauMonthFilter.innerHTML = options.join("");
  bauMonthFilter.value = (months || []).some(item => item.mes === current) ? current : "";
  bauState.month = bauMonthFilter.value;
}

function renderBauGrid(hasMore){
  if(!bauGrid) return;
  if(bauCount) bauCount.textContent = `${bauState.total} foto${bauState.total === 1 ? "" : "s"}`;
  bauGrid.innerHTML = bauState.items.length
    ? bauState.items.map(bauCardHtml).join("")
    : '<div class="meta-empty-state">Nenhuma foto registrada ainda.</div>';
  if(bauLoadMore){
    bauLoadMore.hidden = !hasMore;
    bauLoadMore.disabled = false;
  }
}

async function loadBau({append = false} = {}){
  if(!bauGrid || bauState.loading) return;
  bauState.loading = true;
  try{
    const params = new URLSearchParams({offset: String(append ? bauState.items.length : 0), limit: String(BAU_PAGE_SIZE)});
    if(bauState.month) params.set("mes", bauState.month);
    const {res, data} = await fetchJson(`/api/bau?${params.toString()}`);
    if(!res.ok){
      bauGrid.innerHTML = `<div class="meta-empty-state">${escapeHtml(data.error || "Erro ao carregar o registro do baú.")}</div>`;
      if(bauLoadMore) bauLoadMore.hidden = true;
      return;
    }
    bauState.items = append ? bauState.items.concat(data.items || []) : (data.items || []);
    bauState.total = data.total || 0;
    renderBauMonths(data.months);
    renderBauGrid(Boolean(data.has_more));
  }catch(error){
    bauGrid.innerHTML = `<div class="meta-empty-state">Falha ao carregar o registro do baú: ${escapeHtml(error.message)}</div>`;
  }finally{
    bauState.loading = false;
  }
}

async function uploadBauSelection(){
  if(!bauSelected.length || bauState.uploading) return;
  bauState.uploading = true;
  if(bauUploadBtn) bauUploadBtn.disabled = true;
  const legenda = (bauLegendaInput?.value || "").trim();
  const queue = [...bauSelected];
  const failed = [];
  let sent = 0;
  for(const item of queue){
    setFeedback(bauFeedback, `Enviando foto ${sent + failed.length + 1} de ${queue.length}...`);
    try{
      const body = new FormData();
      body.append("photo", item.file, item.file.name || "imagem.png");
      body.append("legenda", legenda);
      const {res, data} = await fetchJson("/api/bau/photos", {method:"POST", headers: csrfHeaders(), body});
      if(!res.ok) throw new Error(data.error || "Falha ao enviar a foto.");
      sent += 1;
      URL.revokeObjectURL(item.previewUrl);
      bauSelected = bauSelected.filter(selected => selected !== item);
    }catch(error){
      failed.push(`${item.file.name || "Imagem colada"}: ${error.message}`);
    }
  }
  bauState.uploading = false;
  renderBauSelection();
  if(sent && bauLegendaInput && !failed.length) bauLegendaInput.value = "";
  if(failed.length){
    setFeedback(bauFeedback, `${sent} enviada(s). Não foi possível enviar: ${failed.join(" | ")}`, true);
  }else{
    setFeedback(bauFeedback, `${sent} foto${sent === 1 ? "" : "s"} registrada${sent === 1 ? "" : "s"} com sucesso.`);
  }
  if(sent) await loadBau();
}

function openBauLightbox(item){
  if(!bauLightbox || !item) return;
  bauLightboxImg.src = item.url;
  bauLightboxImg.alt = item.legenda || "Foto do baú";
  bauLightboxCaption.textContent = [item.legenda, `${item.created_at} · ${item.registrado_por || "—"}`].filter(Boolean).join(" — ");
  bauLightbox.hidden = false;
  bauLightboxClose?.focus();
}

function closeBauLightbox(){
  if(!bauLightbox || bauLightbox.hidden) return;
  bauLightbox.hidden = true;
  bauLightboxImg.removeAttribute("src");
}

async function editBauCaption(item){
  if(!canWrite || !item) return;
  const next = window.prompt("Legenda da foto (até 200 caracteres):", item.legenda || "");
  if(next === null) return;
  const {res, data} = await fetchJson(`/api/bau/photos/${encodeURIComponent(item.id)}`, {
    method:"PUT",
    headers: csrfHeaders({"Content-Type":"application/json"}),
    body: JSON.stringify({legenda: next}),
  });
  if(!res.ok){ window.alert(data.error || "Não foi possível atualizar a legenda."); return; }
  item.legenda = data.legenda ?? next.trim();
  renderBauGrid(!bauLoadMore?.hidden);
}

async function deleteBauPhoto(item){
  if(!canWrite || !item) return;
  if(!window.confirm("Excluir esta foto do registro? Essa ação não pode ser desfeita.")) return;
  const {res, data} = await fetchJson(`/api/bau/photos/${encodeURIComponent(item.id)}`, {method:"DELETE", headers: csrfHeaders()});
  if(!res.ok){ window.alert(data.error || "Não foi possível excluir a foto."); return; }
  await loadBau();
}

bauPhotoInput?.addEventListener("change", () => {
  addBauFiles(bauPhotoInput.files);
  bauPhotoInput.value = "";
});
["dragenter", "dragover"].forEach(name => {
  bauUploadZone?.addEventListener(name, event => { event.preventDefault(); bauUploadZone.classList.add("drag-over"); });
});
bauUploadZone?.addEventListener("dragleave", event => {
  if(!bauUploadZone.contains(event.relatedTarget)) bauUploadZone.classList.remove("drag-over");
});
bauUploadZone?.addEventListener("drop", event => {
  event.preventDefault();
  bauUploadZone.classList.remove("drag-over");
  addBauFiles(event.dataTransfer?.files);
});
bauUploadZone?.addEventListener("keydown", event => {
  if(event.key === "Enter" || event.key === " "){ event.preventDefault(); bauPhotoInput?.click(); }
});
document.addEventListener("paste", event => {
  if(!bauUploadZone || !bauView?.classList.contains("active")) return;
  const files = Array.from(event.clipboardData?.files || []).filter(file => String(file.type || "").toLowerCase().startsWith("image/"));
  if(!files.length) return;
  event.preventDefault();
  addBauFiles(files);
  bauUploadZone.classList.add("paste-success");
  window.setTimeout(() => bauUploadZone.classList.remove("paste-success"), 700);
});
bauSelectionPreview?.addEventListener("click", event => {
  const button = event.target.closest("[data-bau-remove]");
  if(!button) return;
  const [removed] = bauSelected.splice(Number(button.dataset.bauRemove), 1);
  if(removed) URL.revokeObjectURL(removed.previewUrl);
  renderBauSelection();
});
bauUploadBtn?.addEventListener("click", uploadBauSelection);
bauMonthFilter?.addEventListener("change", () => { bauState.month = bauMonthFilter.value; loadBau(); });
bauLoadMore?.addEventListener("click", () => { bauLoadMore.disabled = true; loadBau({append: true}); });
bauGrid?.addEventListener("click", event => {
  const findItem = id => bauState.items.find(item => item.id === id);
  const open = event.target.closest("[data-bau-open]");
  if(open){ openBauLightbox(findItem(open.dataset.bauOpen)); return; }
  const edit = event.target.closest("[data-bau-edit]");
  if(edit){ editBauCaption(findItem(edit.dataset.bauEdit)); return; }
  const remove = event.target.closest("[data-bau-delete]");
  if(remove){ deleteBauPhoto(findItem(remove.dataset.bauDelete)); }
});
bauLightbox?.addEventListener("click", event => { if(event.target === bauLightbox) closeBauLightbox(); });
bauLightboxClose?.addEventListener("click", closeBauLightbox);
document.addEventListener("keydown", event => { if(event.key === "Escape") closeBauLightbox(); });

/* ===== Remover compra ===== */
comprasTable?.addEventListener("click", async event => {
  const button = event.target.closest("[data-remover-compra]");
  if(!button || !canWrite) return;
  const description = button.dataset.compraDesc || "esta compra";
  if(!window.confirm(`Remover esta compra?\n\n${description}\n\nEla será apagada da planilha e deixará de entrar nos totais e no ranking. Essa ação não pode ser desfeita.`)) return;
  button.disabled = true;
  try{
    const {res, data} = await fetchJson(`/api/compras/${encodeURIComponent(button.dataset.removerCompra)}`, {
      method:"DELETE",
      headers: csrfHeaders()
    });
    if(!res.ok){
      window.alert(data.error || "Não foi possível remover a compra.");
      button.disabled = false;
      return;
    }
    setFeedback(document.getElementById("formFeedback"), data.message || "Compra removida com sucesso.");
    await Promise.all([loadCompras(), loadResumo(), loadRelatorio()]);
  }catch(error){
    window.alert(`Falha ao remover a compra: ${error.message}`);
    button.disabled = false;
  }
});

/* ===== Produtos de venda: de linha (L85, Seringa, Circuito) + temporários (ex.: M16) ===== */
const vendaQuickProducts = document.getElementById("v_quick_products");
const ORDER_FIXED_PRODUCT_KEYS = ["l85", "seringa", "circuito eletronico"];
let produtosFixosVenda = ["L85", "Seringa", "Circuito Eletrônico"];
let produtosTemporariosAtivos = [];

function tempOrderCards(){
  return Array.from(document.querySelectorAll("#e_temp_items [data-temp-order-item]"));
}

function tempItemSlug(nome){
  return normalizeFamilyFlyerKey(nome).replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "item";
}

// Monta os cartões de produtos adicionais do formulário de Encomendas, sem perder o que já foi digitado.
function renderTempOrderItems(extraNames = []){
  const box = document.getElementById("e_temp_items");
  if(!box) return;
  const typed = new Map(tempOrderCards().map(card => [
    normalizeFamilyFlyerKey(card.dataset.tempOrderItem),
    {quantidade:card.querySelector("[data-temp-qty]")?.value || "", valor:card.querySelector("[data-temp-val]")?.value || ""},
  ]));
  const entries = produtosTemporariosAtivos.map(item => ({nome:item.nome, ate:item.ate}));
  extraNames.forEach(nome => {
    if(!entries.some(entry => normalizeFamilyFlyerKey(entry.nome) === normalizeFamilyFlyerKey(nome))){
      entries.push({nome, ate:""});
    }
  });
  box.innerHTML = entries.map(({nome, ate}) => {
    const slug = tempItemSlug(nome);
    const note = ate ? `até ${escapeHtml(String(ate).slice(0, 5))}` : "período encerrado";
    return `<div class="order-item-card" data-temp-order-item="${escapeHtml(nome)}">
      <div class="order-item-title">
        <strong>${escapeHtml(nome)} <small class="order-item-note">${note}</small></strong>
        <span data-temp-subtotal>R$ 0,00</span>
      </div>
      <div class="order-item-fields">
        <label for="e_temp_${slug}_quantidade">Quantidade
          <input id="e_temp_${slug}_quantidade" data-temp-qty type="number" min="0" step="1" placeholder="0" />
        </label>
        <label for="e_temp_${slug}_valor">Valor unitário
          <input id="e_temp_${slug}_valor" data-temp-val type="number" min="0" step="0.01" placeholder="0,00" />
        </label>
      </div>
    </div>`;
  }).join("");
  tempOrderCards().forEach(card => {
    const old = typed.get(normalizeFamilyFlyerKey(card.dataset.tempOrderItem));
    if(!old) return;
    card.querySelector("[data-temp-qty]").value = old.quantidade;
    card.querySelector("[data-temp-val]").value = old.valor;
  });
  updatePreviewEncomenda();
}

document.getElementById("e_temp_items")?.addEventListener("input", updatePreviewEncomenda);

function renderVendaQuickProducts(){
  if(!vendaQuickProducts) return;
  const fixos = produtosFixosVenda.map(nome => `<button type="button" class="quick-product-btn" data-quick-produto="${escapeHtml(nome)}">${escapeHtml(nome)}</button>`);
  const temporarios = produtosTemporariosAtivos.map(item => `<button type="button" class="quick-product-btn is-temporary" data-quick-produto="${escapeHtml(item.nome)}" title="Disponível até ${escapeHtml(item.ate)}">${escapeHtml(item.nome)} <small>até ${escapeHtml(String(item.ate).slice(0, 5))}</small></button>`);
  vendaQuickProducts.innerHTML = [...fixos, ...temporarios].join("");
  vendaQuickProducts.hidden = fixos.length + temporarios.length === 0;
}

async function loadProdutosVenda(){
  try{
    const {res, data} = await fetchJson("/api/produtos-venda");
    if(res.ok){
      if(Array.isArray(data.fixos) && data.fixos.length) produtosFixosVenda = data.fixos.map(String);
      produtosTemporariosAtivos = Array.isArray(data.temporarios) ? data.temporarios : [];
    }
  }catch{
    /* mantém os produtos de linha já conhecidos */
  }
  renderVendaQuickProducts();
  renderTempOrderItems();
}

vendaQuickProducts?.addEventListener("click", event => {
  const button = event.target.closest("[data-quick-produto]");
  if(!button) return;
  const produto = document.getElementById("v_produto");
  if(produto) produto.value = button.dataset.quickProduto;
  document.getElementById("v_valor_unitario")?.focus();
});

async function loadAll(){
  if(refreshBtn){
    refreshBtn.disabled = true;
    refreshBtn.textContent = "Atualizando...";
  }
  try{
    await Promise.all([loadHealth(), loadResumo(), loadCompras(), loadVendas(), loadEncomendas(), loadRelatorio(), loadReunioes(), loadFamilias(), loadMetas(), loadBau(), loadProdutosVenda()]);
    updateLastSync();
  }finally{
    if(refreshBtn){
      refreshBtn.disabled = false;
      refreshBtn.textContent = "Atualizar";
    }
  }
}

refreshBtn?.addEventListener("click", loadAll);
initializeDisclosurePanels();
updatePreviewCompra();
updatePreviewVenda();
updatePreviewEncomenda();
if(relatorioMes && !relatorioMes.value){
  const now = new Date();
  relatorioMes.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}
resetFamiliaForm();
renderRecipes();
renderCraft();
loadAll();
