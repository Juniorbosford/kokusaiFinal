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
const familiasGrid = document.getElementById("familiasGrid");
const familiasDatalist = document.getElementById("familiasDatalist");
let familiaEmEdicaoId = null;
let familiasCache = [];
const comprasTable = document.getElementById("comprasTable");
const vendasTable = document.getElementById("vendasTable");
const encomendasTable = document.getElementById("encomendasTable");
const reunioesGrid = document.getElementById("reunioesGrid");
const metasTable = document.getElementById("metasTable");
const metaForm = document.getElementById("metaForm");
const metasFeedback = document.getElementById("metasFeedback");
const fecharSemanaBtn = document.getElementById("fecharSemanaBtn");
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
    <button type="button" class="delivery-confirm-btn" data-encomenda-entrega="${escapeHtml(item.id)}" data-encomenda-choice="Sim">
      ${delivered ? "Mover para Vendas" : "Confirmar entrega"}
    </button>
    <button type="button" class="delivery-cancel-btn" data-cancelar-encomenda="${escapeHtml(item.id)}">Cancelar</button>
  </div>`;
}

function paymentBadge(value){
  const normalized = String(value || "Não").trim().toLowerCase();
  const isPaid = normalized === "sim";
  return `<span class="status-badge ${isPaid ? "success" : "pending"}">${isPaid ? "SIM" : "NÃO"}</span>`;
}

function updateMetaCounters(total=0, pagos=0, pendentes=0, confirmados=0, semanaLabel="--"){
  setText("metaTotal", integer(total));
  setText("metaPagas", integer(pagos));
  setText("metaPendentes", integer(pendentes));
  setText("statMetasPagas", integer(pagos));
  setText("statMetasPendentes", integer(pendentes));
  setText("metaSemanaAtual", semanaLabel || "--");
  setText("metaProgresso", `${integer(confirmados)}/${integer(total)} marcados`);
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
onInput("e_valor", updatePreviewEncomenda);

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
  const valor = Number(inputValue("e_valor") || 0);
  setText("previewEncomendaValor", currency(valor));
}

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
  const payload = {
    quem_pediu: inputValue("e_quem_pediu").trim(),
    o_que_pediu: inputValue("e_o_que_pediu").trim(),
    valor: Number(inputValue("e_valor")),
    para_quando: inputValue("e_para_quando").trim(),
    quem_negociou: inputValue("e_quem_negociou").trim(),
    entregue: inputValue("e_entregue"),
    observacao: inputValue("e_observacao").trim(),
  };

  const result = await sendPost("/api/encomendas", payload, encomendaFeedback, "Salvando encomenda...", "Encomenda salva com sucesso.");
  if(result){
    encomendaForm.reset();
    updatePreviewEncomenda();
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
  document.getElementById("f_flyer_url").value = item.flyer_url || "";
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

familiaForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    nome: inputValue("f_nome").trim(),
    icone: inputValue("f_icone").trim(),
    mercado: inputValue("f_mercado"),
    preco_venda_para_familia: inputValue("f_preco_venda").trim(),
    preco_compra_da_familia: inputValue("f_preco_compra").trim(),
    flyer_url: inputValue("f_flyer_url").trim(),
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

familiasGrid?.addEventListener("click", async (event) => {
  const editButton = event.target.closest("[data-editar-familia]");
  if(editButton){
    iniciarEdicaoFamilia(editButton.dataset.editarFamilia);
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

metaForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    nome: inputValue("meta_nome").trim(),
    pago: inputValue("meta_pago") || "Não",
  };

  const ok = await sendPost("/api/metas", payload, metasFeedback, "Adicionando nome...", "Nome adicionado na lista de metas.");
  if(ok){
    metaForm.reset();
    const status = document.getElementById("meta_pago");
    if(status) status.value = "Não";
  }
});

metasTable?.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-meta-choice]");
  if(!button || !canWrite) return;

  const id = button.dataset.metaStatus;
  const pago = button.dataset.metaChoice;
  const row = button.closest("tr");
  const buttons = row ? row.querySelectorAll("[data-meta-choice]") : [button];
  buttons.forEach(btn => btn.disabled = true);
  setFeedback(metasFeedback, `Marcando ${pago.toUpperCase()}...`);

  try{
    const {res, data} = await fetchJson(`/api/metas/${encodeURIComponent(id)}/status`, {
      method:"POST",
      headers:csrfHeaders({"Content-Type":"application/json"}),
      body:JSON.stringify({pago})
    });
    if(!res.ok){
      setFeedback(metasFeedback, data.error || "Erro ao atualizar status.", true);
      await loadMetas();
      return;
    }

    const message = data.week_closed
      ? `${data.message} Nova semana: ${data.next_week?.semana_label || "--"}.`
      : (data.message || "Status atualizado.");
    setFeedback(metasFeedback, message);
    await Promise.all([loadMetas(), loadResumo()]);
  }catch(error){
    setFeedback(metasFeedback, `Falha ao atualizar status: ${error.message}`, true);
  }finally{
    buttons.forEach(btn => btn.disabled = false);
  }
});

metasTable?.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-delete-meta]");
  if(!button || !canWrite) return;

  const id = button.dataset.deleteMeta;
  const name = button.dataset.name || "essa pessoa";
  if(!window.confirm(`Apagar ${name} da lista de metas?`)) return;

  button.disabled = true;
  setFeedback(metasFeedback, "Apagando nome da planilha...");

  try{
    const {res, data} = await fetchJson(`/api/metas/${encodeURIComponent(id)}`, {method:"DELETE", headers:csrfHeaders()});
    if(!res.ok){
      setFeedback(metasFeedback, data.error || "Erro ao apagar nome.", true);
      return;
    }
    setFeedback(metasFeedback, data.message || "Nome removido.");
    await Promise.all([loadMetas(), loadResumo()]);
  }catch(error){
    setFeedback(metasFeedback, `Falha ao apagar nome: ${error.message}`, true);
  }finally{
    button.disabled = false;
  }
});

fecharSemanaBtn?.addEventListener("click", async () => {
  if(!canWrite) return;
  if(!window.confirm("Fechar a semana atual, salvar no histórico e abrir a próxima zerada?")) return;

  fecharSemanaBtn.disabled = true;
  setFeedback(metasFeedback, "Fechando semana e abrindo a próxima...");

  try{
    const {res, data} = await fetchJson("/api/metas/fechar-semana", {method:"POST", headers:csrfHeaders()});
    if(!res.ok){
      setFeedback(metasFeedback, data.error || "Erro ao fechar semana.", true);
      return;
    }
    setFeedback(metasFeedback, `${data.message} Nova semana: ${data.next_week?.semana_label || "--"}.`);
    await Promise.all([loadMetas(), loadResumo()]);
  }catch(error){
    setFeedback(metasFeedback, `Falha ao fechar semana: ${error.message}`, true);
  }finally{
    fecharSemanaBtn.disabled = false;
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
    updateMetaCounters(dm.total ?? 0, dm.pagos ?? 0, dm.pendentes ?? 0, dm.confirmados ?? 0, dm.semana_label ?? "--");
  }catch{}
}

async function loadCompras(){
  try{
    const {res, data} = await fetchJson("/api/compras");
    if(!res.ok){
      setTableContent(comprasTable, `<tr><td colspan="6">${escapeHtml(data.error || "Erro ao carregar compras.")}</td></tr>`);
      return;
    }
    if(!Array.isArray(data) || !data.length){
      setTableContent(comprasTable, `<tr><td colspan="6">Nenhuma compra registrada.</td></tr>`);
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
      </tr>`).join(""));
  }catch(error){
    setTableContent(comprasTable, `<tr><td colspan="6">Falha ao carregar compras: ${escapeHtml(error.message)}</td></tr>`);
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
      setTableContent(encomendasTable, `<tr><td colspan="${colspan}">${escapeHtml(data.error || "Erro ao carregar encomendas.")}</td></tr>`);
      return;
    }
    if(!Array.isArray(data) || !data.length){
      setTableContent(encomendasTable, `<tr><td colspan="${colspan}">Nenhuma encomenda pendente.</td></tr>`);
      return;
    }
    setTableContent(encomendasTable, data.map(item => `
      <tr>
        <td>${escapeHtml(item.data)}</td>
        <td>${escapeHtml(item.quem_pediu)}</td>
        <td>${escapeHtml(item.o_que_pediu)}</td>
        <td>${escapeHtml(item.para_quando)}</td>
        <td>${escapeHtml(item.quem_negociou)}</td>
        <td>${currency(item.valor)}</td>
        <td>${deliveryControl(item)}</td>
      </tr>`).join(""));
  }catch(error){
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

    if(!items.length){
      familiasGrid.innerHTML = '<div class="family-empty">Nenhuma família ou gangue cadastrada.</div>';
      return;
    }

    familiasGrid.innerHTML = items.map(item => {
      const closed = item.mercado === "Fechado";
      const flyer = item.flyer_url
        ? `<div class="family-flyer"><img data-family-flyer src="${escapeHtml(item.flyer_url)}" alt="Flyer de ${escapeHtml(item.nome)}" referrerpolicy="no-referrer" /></div>`
        : `<div class="family-flyer family-flyer-empty"><span>${escapeHtml(item.icone || "🤝")}</span><small>Sem flyer vinculado</small></div>`;
      return `<article class="family-card ${closed ? "closed" : "open"}">
        ${flyer}
        <div class="family-card-content">
          <div class="family-card-top">
            <div><span class="family-icon">${escapeHtml(item.icone || "🤝")}</span><h4>${escapeHtml(item.nome)}</h4></div>
            <span class="market-status ${closed ? "closed" : "open"}">${closed ? "Mercado fechado" : "Mercado aberto"}</span>
          </div>
          <div class="family-price-grid">
            <div><span>Venda para eles</span><p>${escapeHtml(item.preco_venda_para_familia || "Não informado")}</p></div>
            <div><span>Compra deles</span><p>${escapeHtml(item.preco_compra_da_familia || "Não informado")}</p></div>
          </div>
          ${item.observacao ? `<p class="family-note">${escapeHtml(item.observacao)}</p>` : ""}
          ${canWrite ? `<div class="family-actions"><button type="button" class="family-edit-btn" data-editar-familia="${escapeHtml(item.id)}">✏️ Editar</button><button type="button" class="family-delete-btn" data-apagar-familia="${escapeHtml(item.id)}">Remover</button></div>` : ""}
        </div>
      </article>`;
    }).join("");

    familiasGrid.querySelectorAll("img[data-family-flyer]").forEach(image => {
      image.addEventListener("error", () => {
        const container = image.closest(".family-flyer");
        if(container) container.innerHTML = '<span>🖼️</span><small>Flyer indisponível</small>';
        container?.classList.add("family-flyer-empty");
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

async function loadMetas(){
  if(!metasTable) return;

  const colspan = canWrite ? 5 : 4;
  try{
    const {res, data} = await fetchJson("/api/metas");
    if(!res.ok){
      setTableContent(metasTable, `<tr><td colspan="${colspan}">${escapeHtml(data.error || "Erro ao carregar metas.")}</td></tr>`);
      return;
    }
    if(!Array.isArray(data) || !data.length){
      setTableContent(metasTable, `<tr><td colspan="${colspan}">Nenhum nome cadastrado na lista de metas.</td></tr>`);
      updateMetaCounters(0, 0, 0, 0, "--");
      return;
    }

    const pagos = data.filter(item => String(item.pago || "").trim().toLowerCase() === "sim").length;
    const confirmados = data.filter(item => Boolean(item.confirmado)).length;
    const first = data[0] || {};
    const semanaLabel = first.semana_inicio && first.semana_fim ? `${first.semana_inicio} até ${first.semana_fim}` : "--";
    updateMetaCounters(data.length, pagos, data.length - pagos, confirmados, semanaLabel);

    setTableContent(metasTable, data.map((item, index) => {
      const pago = String(item.pago || "Não").trim().toLowerCase() === "sim" ? "Sim" : "Não";
      const confirmado = Boolean(item.confirmado);
      const statusCell = canWrite
        ? `<div class="payment-toggle-group" aria-label="Pagamento de ${escapeHtml(item.nome)}">
            <button type="button" class="payment-choice ${pago === "Sim" ? "active success" : ""}" data-meta-status="${escapeHtml(item.id)}" data-meta-choice="Sim">SIM</button>
            <button type="button" class="payment-choice ${pago === "Não" ? "active pending" : ""}" data-meta-status="${escapeHtml(item.id)}" data-meta-choice="Não">NÃO</button>
          </div>`
        : paymentBadge(pago);
      const actionCell = canWrite
        ? `<td><button class="danger-btn small-btn" type="button" data-delete-meta="${escapeHtml(item.id)}" data-name="${escapeHtml(item.nome)}">Apagar</button></td>`
        : "";

      return `
        <tr class="${confirmado ? "meta-confirmed" : "meta-unconfirmed"}">
          <td class="sheet-index">${index + 1}</td>
          <td class="meta-name-cell"><strong>${escapeHtml(item.nome)}</strong>${confirmado ? "" : `<small>Aguardando clique</small>`}</td>
          <td>${statusCell}</td>
          <td>${confirmado ? escapeHtml(item.atualizado_em || "--") : "--"}</td>
          ${actionCell}
        </tr>`;
    }).join(""));
  }catch(error){
    setTableContent(metasTable, `<tr><td colspan="${colspan}">Falha ao carregar metas: ${escapeHtml(error.message)}</td></tr>`);
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
