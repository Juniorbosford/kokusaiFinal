const navLinks = document.querySelectorAll(".nav-link");
const views = document.querySelectorAll(".view");
const canWrite = document.body.dataset.canWrite === "true";
const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";

function csrfHeaders(headers = {}){
  return csrfToken ? {...headers, "X-CSRF-Token": csrfToken} : headers;
}

function activateView(target){
  navLinks.forEach(btn => btn.classList.toggle("active", btn.dataset.target === target));
  views.forEach(view => view.classList.toggle("active", view.id === target));
  window.scrollTo({top:0, behavior:"smooth"});
}

navLinks.forEach(link => {
  link.addEventListener("click", () => activateView(link.dataset.target));
});

const refreshBtn = document.getElementById("refreshBtn");
const form = document.getElementById("compraForm");
const vendaForm = document.getElementById("vendaForm");
const encomendaForm = document.getElementById("encomendaForm");
const encomendaFamiliaSelect = document.getElementById("e_familia_id");
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
let encomendaEmEdicaoId = null;
let encomendasCache = [];
const reunioesGrid = document.getElementById("reunioesGrid");
const metasFeedback = document.getElementById("metasFeedback");
const metaRoomsGrid = document.getElementById("metaRoomsGrid");
const metaRoomsSearch = document.getElementById("metaRoomsSearch");
const metaRoomDetail = document.getElementById("metaRoomDetail");
const finalizeMetaWeekBtn = document.getElementById("finalizeMetaWeekBtn");
const metaCycleStatus = document.getElementById("metaCycleStatus");
const metaCycleDeadline = document.getElementById("metaCycleDeadline");
let metaRoomsCache = [];
let selectedMetaRoomUserId = null;
let activeMetaWeek = null;
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
];

const craftInventory = {};

function currency(value){
  return new Intl.NumberFormat("pt-BR", {style:"currency", currency:"BRL"}).format(Number(value || 0));
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
  return String(value || "")
    .normalize("NFD")
    .replace(/[\\u0300-\\u036f]/g, "")
    .toLowerCase()
    .replace(/[’']/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
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
onInput("v_valor_unitario", updatePreviewVenda);
onInput("v_quantidade", updatePreviewVenda);
onInput("e_l85_quantidade", updatePreviewEncomenda);
onInput("e_l85_valor", updatePreviewEncomenda);
onInput("e_seringa_quantidade", updatePreviewEncomenda);
onInput("e_seringa_valor", updatePreviewEncomenda);

function updatePreviewCompra(){
  const valor = Number(inputValue("valor_unitario") || 0);
  const qtd = Number(inputValue("quantidade") || 0);
  setText("previewTotal", currency(valor * qtd));
}

function updatePreviewVenda(){
  const valor = Number(inputValue("v_valor_unitario") || 0);
  const qtd = Number(inputValue("v_quantidade") || 0);
  setText("previewVendaTotal", currency(valor * qtd));
}

function updatePreviewEncomenda(){
  const l85 = Math.max(0, Number(inputValue("e_l85_quantidade") || 0)) * Math.max(0, Number(inputValue("e_l85_valor") || 0));
  const seringa = Math.max(0, Number(inputValue("e_seringa_quantidade") || 0)) * Math.max(0, Number(inputValue("e_seringa_valor") || 0));
  setText("e_l85_subtotal", currency(l85));
  setText("e_seringa_subtotal", currency(seringa));
  setText("previewEncomendaValor", currency(l85 + seringa));
}

function resetEncomendaForm(){
  encomendaEmEdicaoId = null;
  encomendaForm?.reset();
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

function iniciarEdicaoEncomenda(id){
  const item = encomendasCache.find(encomenda => encomenda.id === id);
  if(!item || !encomendaForm) return;

  const itens = Array.isArray(item.itens) ? item.itens : [];
  const l85 = itens.find(produto => String(produto.produto || "").trim().toLowerCase() === "l85");
  const seringa = itens.find(produto => String(produto.produto || "").trim().toLowerCase() === "seringa");
  const family = familyForOrder(item);

  encomendaEmEdicaoId = id;
  if(encomendaFamiliaSelect) encomendaFamiliaSelect.value = family?.id || item.familia_id || "";
  document.getElementById("e_l85_quantidade").value = l85?.quantidade || "";
  document.getElementById("e_l85_valor").value = l85?.valor_unitario ?? "";
  document.getElementById("e_seringa_quantidade").value = seringa?.quantidade || "";
  document.getElementById("e_seringa_valor").value = seringa?.valor_unitario ?? "";

  // Compatibilidade com encomendas antigas, anteriores ao campo itens_json.
  if(!itens.length){
    const texto = String(item.o_que_pediu || "");
    const match = texto.match(/^\s*(?:(\d+)\s*x?\s*)?(L85|Seringa)\s*$/i);
    if(match){
      const quantidade = Number(match[1] || 1);
      const valorUnitario = quantidade > 0 ? Number(item.valor || 0) / quantidade : 0;
      const prefixo = match[2].toLowerCase() === "l85" ? "e_l85" : "e_seringa";
      document.getElementById(`${prefixo}_quantidade`).value = quantidade;
      document.getElementById(`${prefixo}_valor`).value = Number(valorUnitario.toFixed(2));
    }
  }

  document.getElementById("e_para_quando").value = item.para_quando || "";
  document.getElementById("e_quem_negociou").value = item.quem_negociou || "";
  document.getElementById("e_entregue").value = String(item.entregue || "Não").toLowerCase() === "sim" ? "Sim" : "Não";
  document.getElementById("e_observacao").value = item.observacao || "";
  updatePreviewEncomenda();

  if(encomendaSubmitBtn) encomendaSubmitBtn.textContent = "Salvar alterações";
  if(encomendaCancelEditBtn) encomendaCancelEditBtn.hidden = false;
  setText("encomendaFormKicker", "Editar encomenda");
  setText("encomendaFormTitle", family ? `${family.icone || "🤝"} ${family.nome}` : (item.familia_nome || item.quem_pediu || "Atualizar encomenda"));
  setFeedback(encomendaFeedback, "Edite os campos e clique em Salvar alterações.");
  encomendaForm.scrollIntoView({behavior:"smooth", block:"start"});
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
  const payload = {
    produto: inputValue("produto").trim(),
    quem_pediu: inputValue("quem_pediu").trim(),
    quem_vendeu: inputValue("quem_vendeu").trim(),
    valor_unitario: Number(inputValue("valor_unitario")),
    quantidade: Number(inputValue("quantidade")),
    observacao: inputValue("observacao").trim(),
  };

  const ok = await sendPost("/api/compras", payload, formFeedback, "Salvando compra...", "Compra salva com sucesso.");
  if(ok){
    form.reset();
    updatePreviewCompra();
  }
});

vendaForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    produto: inputValue("v_produto").trim(),
    quem_compra: inputValue("quem_compra").trim(),
    quem_vende: inputValue("quem_vende").trim(),
    valor_unitario: Number(inputValue("v_valor_unitario")),
    quantidade: Number(inputValue("v_quantidade")),
    observacao: inputValue("v_observacao").trim(),
  };

  const ok = await sendPost("/api/vendas", payload, vendaFeedback, "Salvando venda...", "Venda salva com sucesso.");
  if(ok){
    vendaForm.reset();
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
  ];

  if(!itens.some(item => Number.isInteger(item.quantidade) && item.quantidade > 0)){
    setFeedback(encomendaFeedback, "Informe a quantidade de L85, Seringa ou dos dois produtos.", true);
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
        await Promise.all([loadEncomendas(), loadVendas(), loadResumo()]);
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
  reuniaoForm.scrollIntoView({behavior:"smooth", block:"start"});
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
      if(res.ok) await Promise.all([loadEncomendas(), loadResumo()]);
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
    await Promise.all([loadEncomendas(), loadVendas(), loadResumo()]);
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
  if(familiaSubmitBtn) familiaSubmitBtn.textContent = "Adicionar Família/Gangue";
  if(familiaCancelEditBtn) familiaCancelEditBtn.hidden = true;
  setText("familiaFormKicker", "Novo cadastro");
  setText("familiaFormTitle", "Adicionar Família/Gangue");
}

function iniciarEdicaoFamilia(id){
  const item = familiasCache.find(familia => familia.id === id);
  if(!item || !familiaForm) return;
  familiaEmEdicaoId = id;
  document.getElementById("f_nome").value = item.nome || "";
  document.getElementById("f_icone").value = item.icone || "";
  document.getElementById("f_mercado").value = item.mercado || "Aberto";
  document.getElementById("f_preco_venda").value = item.preco_venda_para_familia || "";
  document.getElementById("f_preco_compra").value = item.preco_compra_da_familia || "";
  document.getElementById("f_contato").value = item.contato || "";
  document.getElementById("f_contato_2").value = item.contato_2 || "";
  document.getElementById("f_flyer_url").value = item.flyer_url || "";
  document.getElementById("f_flyer_url_2").value = item.flyer_url_2 || "";
  document.getElementById("f_flyer_oculto").checked = Boolean(item.flyer_oculto);
  document.getElementById("f_observacao").value = item.observacao || "";
  if(familiaSubmitBtn) familiaSubmitBtn.textContent = "Salvar alterações";
  if(familiaCancelEditBtn) familiaCancelEditBtn.hidden = false;
  setText("familiaFormKicker", "Editar cadastro");
  setText("familiaFormTitle", item.nome || "Atualizar família/gangue");
  setFeedback(familiaFeedback, "Edite os dados e clique em Salvar alterações.");
  familiaForm.scrollIntoView({behavior:"smooth", block:"start"});
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

familiaForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    nome: inputValue("f_nome").trim(),
    icone: inputValue("f_icone").trim(),
    mercado: inputValue("f_mercado"),
    preco_venda_para_familia: inputValue("f_preco_venda").trim(),
    preco_compra_da_familia: inputValue("f_preco_compra").trim(),
    contato: inputValue("f_contato").trim(),
    contato_2: inputValue("f_contato_2").trim(),
    flyer_url: inputValue("f_flyer_url").trim(),
    flyer_url_2: inputValue("f_flyer_url_2").trim(),
    flyer_oculto: Boolean(document.getElementById("f_flyer_oculto")?.checked),
    observacao: inputValue("f_observacao").trim(),
  };

  const editing = Boolean(familiaEmEdicaoId);
  const url = editing ? `/api/familias/${encodeURIComponent(familiaEmEdicaoId)}` : "/api/familias";
  try{
    setFeedback(familiaFeedback, editing ? "Salvando alterações..." : "Adicionando família/gangue...");
    const {res, data} = await fetchJson(url, {
      method:editing ? "PUT" : "POST",
      headers:csrfHeaders({"Content-Type":"application/json"}),
      body:JSON.stringify(payload)
    });
    setFeedback(familiaFeedback, data.message || (res.ok ? "Cadastro salvo." : "Erro ao salvar cadastro."), !res.ok);
    if(res.ok){
      resetFamiliaForm();
      await loadFamilias();
    }
  }catch(error){
    setFeedback(familiaFeedback, `Falha ao salvar família/gangue: ${error.message}`, true);
  }
});

function familyPayloadFromItem(item, overrides = {}){
  return {
    nome:item?.nome || "",
    icone:item?.icone || "",
    mercado:item?.mercado || "Aberto",
    preco_venda_para_familia:item?.preco_venda_para_familia || "",
    preco_compra_da_familia:item?.preco_compra_da_familia || "",
    contato:item?.contato || "",
    contato_2:item?.contato_2 || "",
    flyer_url:item?.flyer_url || "",
    flyer_url_2:item?.flyer_url_2 || "",
    flyer_oculto:Boolean(item?.flyer_oculto),
    observacao:item?.observacao || "",
    ...overrides,
  };
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
  if(!window.confirm(`Remover ${item?.nome || "esta família"} da aba Famílias?`)) return;
  deleteButton.disabled = true;
  try{
    const {res, data} = await fetchJson(`/api/familias/${encodeURIComponent(id)}`, {
      method:"DELETE",
      headers:csrfHeaders()
    });
    setFeedback(familiaFeedback, data.message || (res.ok ? "Família removida." : "Erro ao remover família."), !res.ok);
    if(res.ok) await loadFamilias();
  }catch(error){
    setFeedback(familiaFeedback, `Falha ao remover família: ${error.message}`, true);
  }finally{
    deleteButton.disabled = false;
  }
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
    <article class="recipe-card">
      <div class="recipe-head">
        <h4>${escapeHtml(recipe.title)}</h4>
        <span>${escapeHtml(recipe.helper)}</span>
      </div>
      <div class="recipe-list">
        ${recipe.materials.map(([material, amount]) => `
          <div>
            <span>${escapeHtml(material)}</span>
            <strong>${integer(amount)}</strong>
          </div>`).join("")}
      </div>
    </article>
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
  try{
    const {res, data} = await fetchJson("/api/compras");
    if(!res.ok){
      setTableContent(comprasTable, `<tr><td colspan="7">${escapeHtml(data.error || "Erro ao carregar compras.")}</td></tr>`);
      return;
    }
    if(!Array.isArray(data) || !data.length){
      setTableContent(comprasTable, `<tr><td colspan="7">Nenhuma compra registrada.</td></tr>`);
      return;
    }
    setTableContent(comprasTable, data.map(item => `
      <tr>
        <td>${escapeHtml(item.data)}</td>
        <td>${escapeHtml(item.produto)}</td>
        <td>${escapeHtml(item.quem_pediu)}</td>
        <td>${escapeHtml(item.quem_vendeu)}</td>
        <td>${escapeHtml(item.quantidade)}</td>
        <td>${currency(item.valor_total)}</td>
        <td>${escapeHtml(item.observacao || "—")}</td>
      </tr>`).join(""));
  }catch(error){
    setTableContent(comprasTable, `<tr><td colspan="7">Falha ao carregar compras: ${escapeHtml(error.message)}</td></tr>`);
  }
}

async function loadVendas(){
  try{
    const {res, data} = await fetchJson("/api/vendas");
    if(!res.ok){
      setTableContent(vendasTable, `<tr><td colspan="6">${escapeHtml(data.error || "Erro ao carregar vendas.")}</td></tr>`);
      return;
    }
    if(!Array.isArray(data) || !data.length){
      setTableContent(vendasTable, `<tr><td colspan="6">Nenhuma venda registrada.</td></tr>`);
      return;
    }
    setTableContent(vendasTable, data.map(item => `
      <tr>
        <td>${escapeHtml(item.data)}</td>
        <td>${escapeHtml(item.produto)}</td>
        <td>${escapeHtml(item.quem_compra)}</td>
        <td>${escapeHtml(item.quem_vende)}</td>
        <td>${escapeHtml(item.quantidade)}</td>
        <td>${currency(item.valor_total)}</td>
      </tr>`).join(""));
  }catch(error){
    setTableContent(vendasTable, `<tr><td colspan="6">Falha ao carregar vendas: ${escapeHtml(error.message)}</td></tr>`);
  }
}

async function loadEncomendas(){
  if(!encomendasTable) return;

  const colspan = 7;
  try{
    const {res, data} = await fetchJson("/api/encomendas");
    if(!res.ok){
      encomendasCache = [];
      setTableContent(encomendasTable, `<tr><td colspan="${colspan}">${escapeHtml(data.error || "Erro ao carregar encomendas.")}</td></tr>`);
      return;
    }
    encomendasCache = Array.isArray(data) ? data : [];
    if(!Array.isArray(data) || !data.length){
      setTableContent(encomendasTable, `<tr><td colspan="${colspan}">Nenhuma encomenda pendente.</td></tr>`);
      return;
    }
    setTableContent(encomendasTable, data.map(item => {
      const family = familyForOrder(item);
      const familyName = family?.nome || item.familia_nome || item.quem_pediu || "Família não vinculada";
      const familyIcon = family?.icone || item.familia_icone || "🤝";
      const linked = Boolean(family?.id || item.familia_id);
      return `<tr>
        <td>${escapeHtml(item.data)}</td>
        <td><span class="order-family-chip ${linked ? "" : "unlinked"}"><span>${escapeHtml(familyIcon)}</span><strong>${escapeHtml(familyName)}</strong></span></td>
        <td>${escapeHtml(item.o_que_pediu)}</td>
        <td>${escapeHtml(item.para_quando)}</td>
        <td>${escapeHtml(item.quem_negociou)}</td>
        <td>${currency(item.valor)}</td>
        <td>${deliveryControl(item)}</td>
      </tr>`;
    }).join(""));
  }catch(error){
    encomendasCache = [];
    setTableContent(encomendasTable, `<tr><td colspan="${colspan}">Falha ao carregar encomendas: ${escapeHtml(error.message)}</td></tr>`);
  }
}


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
    if(encomendaFamiliaSelect){
      const selectedFamilyId = encomendaFamiliaSelect.value;
      encomendaFamiliaSelect.innerHTML = `<option value="">Selecione a família responsável</option>${items.map(item => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.icone || "🤝")} ${escapeHtml(item.nome)}</option>`).join("")}`;
      if(items.some(item => item.id === selectedFamilyId)) encomendaFamiliaSelect.value = selectedFamilyId;
    }

    if(!items.length){
      familiasGrid.innerHTML = '<div class="family-empty">Nenhuma família ou gangue cadastrada.</div>';
      return;
    }

    familiasGrid.innerHTML = items.map(item => {
      const closed = item.mercado === "Fechado";
      const localFlyers = getLocalFamilyFlyers(item);
      const configuredFlyers = [item.flyer_url, item.flyer_url_2].filter(Boolean);
      const flyerUrls = item.flyer_oculto ? [] : (configuredFlyers.length ? configuredFlyers : localFlyers);
      const flyer = flyerUrls.length
        ? `<div class="family-flyer ${flyerUrls.length > 1 ? "family-flyer-multiple" : ""}">${flyerUrls.map((url, index) => `<img data-family-flyer src="${escapeHtml(url)}" alt="Flyer ${index + 1} de ${escapeHtml(item.nome)}" referrerpolicy="no-referrer" />`).join("")}</div>`
        : `<div class="family-flyer family-flyer-empty"><span>${escapeHtml(item.icone || "🤝")}</span><small>Sem flyer vinculado</small></div>`;
      const contacts = [item.contato, item.contato_2].filter(Boolean);
      const contactsHtml = contacts.length ? `<div class="family-contacts">${contacts.map((contact, index) => `<div class="family-contact"><button type="button" class="family-contact-toggle" data-toggle-family-contact>Mostrar contato ${index + 1}</button><span data-family-contact-value hidden>${escapeHtml(contact)}</span></div>`).join("")}</div>` : "";
      return `<article class="family-card ${closed ? "closed" : "open"}">
        ${flyer}
        <div class="family-card-content">
          <div class="family-card-top">
            <div><span class="family-icon">${escapeHtml(item.icone || "🤝")}</span><h4>${escapeHtml(item.nome)}</h4></div>
            <span class="market-status ${closed ? "closed" : "open"}">${closed ? "Mercado fechado" : "Mercado aberto"}</span>
          </div>
          <div class="family-price-grid">
            <div><span>Nosso valor para a família</span><p>${escapeHtml(item.preco_venda_para_familia || "Não informado")}</p></div>
            <div><span>Valor deles para a Kokusai</span><p>${escapeHtml(item.preco_compra_da_familia || "Não informado")}</p></div>
          </div>
          ${contactsHtml}
          ${item.observacao ? `<p class="family-note">${escapeHtml(item.observacao)}</p>` : ""}
          ${canWrite ? `<div class="family-actions"><button type="button" class="family-edit-btn" data-editar-familia="${escapeHtml(item.id)}">✏️ Editar dados/flyers</button>${flyerUrls.length ? `<button type="button" class="family-flyer-delete-btn" data-remover-flyer="${escapeHtml(item.id)}">Remover flyers</button>` : ""}<button type="button" class="family-delete-btn" data-apagar-familia="${escapeHtml(item.id)}">Remover família</button></div>` : ""}
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
      return `<article class="meeting-card ${statusClass}">
        <div class="meeting-icon">${escapeHtml(item.icone || "🤝")}</div>
        <div class="meeting-card-content">
          <div class="meeting-card-top"><span class="meeting-status ${statusClass}">${statusLabel}</span><span class="meeting-gang">${escapeHtml(item.gangue)}</span></div>
          <h4>${escapeHtml(item.titulo)}</h4>
          <div class="meeting-details"><span>📆 ${escapeHtml(dateLabel || "--")}</span><span>🕒 ${escapeHtml(item.horario || "--")}</span>${item.local ? `<span>📍 ${escapeHtml(item.local)}</span>` : ""}</div>
          ${item.pauta ? `<p>${escapeHtml(item.pauta)}</p>` : ""}
          ${done ? `<small>Concluída em ${escapeHtml(item.finalizada_em || "--")}</small>` : ""}
          ${canceled ? `<small class="meeting-canceled-at">Cancelada em ${escapeHtml(item.finalizada_em || "--")}</small>` : ""}
          ${canWrite ? `<div class="meeting-actions"><button class="meeting-edit-btn" type="button" data-editar-reuniao="${escapeHtml(item.id)}">✏️ Editar</button>${done || canceled ? "" : `<button class="meeting-cancel-btn" type="button" data-cancelar-reuniao="${escapeHtml(item.id)}">Cancelar reunião</button><button class="meeting-finish-btn" type="button" data-finalizar-reuniao="${escapeHtml(item.id)}">Marcar como finalizada</button>`}</div>` : ""}
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
  metaRoomsGrid.innerHTML = rooms.map(room => `
    <button type="button" class="meta-room-list-item ${room.user_id === selectedMetaRoomUserId ? "active" : ""}" data-meta-room-user="${escapeHtml(room.user_id)}">
      <span class="meta-room-avatar">${escapeHtml(String(room.display_name || "?").slice(0, 1).toUpperCase())}</span>
      <span class="meta-room-person"><strong>${escapeHtml(room.display_name)}</strong><small>@${escapeHtml(room.username)}</small></span>
      <span class="meta-room-list-info"><span class="meta-status-badge ${metaStatusClass(room.status)}">${escapeHtml(room.status)}</span><small>${integer(room.photo_count || 0)} foto(s)</small></span>
    </button>`).join("");
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
    const reviewAllowed = Boolean(activeMetaWeek?.review_mode && !activeMetaWeek?.closed);
    const reviewPanel = reviewAllowed
      ? `<div class="meta-review-panel"><label for="metaAdminNote">Observação para o membro</label><textarea id="metaAdminNote" placeholder="Opcional: orientação ou justificativa">${escapeHtml(submission.admin_note || "")}</textarea><div class="meta-review-actions"><button type="button" class="meta-review-paid" data-meta-review="Pago" data-submission-id="${escapeHtml(submission.id)}">✓ Marcar pago</button><button type="button" class="meta-review-rejected" data-meta-review="Não pago" data-submission-id="${escapeHtml(submission.id)}">✕ Marcar não pago</button><button type="button" class="meta-review-pending" data-meta-review="Pendente" data-submission-id="${escapeHtml(submission.id)}">Voltar para pendente</button></div></div>`
      : `<div class="meta-empty-state compact">${activeMetaWeek?.closed ? "Esta semana já foi finalizada e está bloqueada." : "A conferência será liberada após quarta-feira às 23:59."}</div>`;

    metaRoomDetail.innerHTML = `
      <div class="meta-room-detail-head">
        <div><p class="panel-kicker">Sala individual</p><h3>${escapeHtml(data.member.display_name)}</h3><small>@${escapeHtml(data.member.username)}</small></div>
        <span class="meta-status-badge ${metaStatusClass(submission.status)}">${escapeHtml(submission.status || "Pendente")}</span>
      </div>
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

metaRoomDetail?.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-meta-review]");
  if(!button || !canWrite) return;
  const status = button.dataset.metaReview;
  if(status === "Pago" && !window.confirm("Confirmar que esta pessoa pagou a meta da semana?")) return;
  if(status === "Não pago" && !window.confirm("Confirmar que esta pessoa não pagou a meta da semana?")) return;
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

async function loadAll(){
  if(refreshBtn){
    refreshBtn.disabled = true;
    refreshBtn.textContent = "Atualizando...";
  }
  try{
    await Promise.all([loadHealth(), loadResumo(), loadCompras(), loadVendas(), loadEncomendas(), loadReunioes(), loadFamilias(), loadMetas()]);
    updateLastSync();
  }finally{
    if(refreshBtn){
      refreshBtn.disabled = false;
      refreshBtn.textContent = "Atualizar dados";
    }
  }
}

refreshBtn?.addEventListener("click", loadAll);
updatePreviewCompra();
updatePreviewVenda();
updatePreviewEncomenda();
resetFamiliaForm();
renderRecipes();
renderCraft();
loadAll();
