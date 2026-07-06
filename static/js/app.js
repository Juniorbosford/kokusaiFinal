const navLinks = document.querySelectorAll(".nav-link");
const views = document.querySelectorAll(".view");
const canWrite = document.body.dataset.canWrite === "true";
const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";

function csrfHeaders(headers = {}){
  return csrfToken ? {...headers, "X-CSRF-Token": csrfToken} : headers;
}

navLinks.forEach(link => {
  link.addEventListener("click", () => {
    navLinks.forEach(btn => btn.classList.remove("active"));
    views.forEach(view => view.classList.remove("active"));
    link.classList.add("active");
    document.getElementById(link.dataset.target)?.classList.add("active");
  });
});

const refreshBtn = document.getElementById("refreshBtn");
const form = document.getElementById("compraForm");
const vendaForm = document.getElementById("vendaForm");
const encomendaForm = document.getElementById("encomendaForm");
const formFeedback = document.getElementById("formFeedback");
const vendaFeedback = document.getElementById("vendaFeedback");
const encomendaFeedback = document.getElementById("encomendaFeedback");
const comprasTable = document.getElementById("comprasTable");
const vendasTable = document.getElementById("vendasTable");
const encomendasTable = document.getElementById("encomendasTable");
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
  const label = escapeHtml(value || "Não informado");
  const normalized = String(value || "").trim().toLowerCase();
  const cls = normalized === "sim" ? "success" : "pending";
  return `<span class="status-badge ${cls}">${label}</span>`;
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

function inputValue(id){
  return document.getElementById(id)?.value ?? "";
}

function setText(id, value){
  const el = document.getElementById(id);
  if(el) el.textContent = value;
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
    return false;
  }

  try{
    setFeedback(feedbackEl, loadingMessage);
    const res = await fetch(url, {
      method:"POST",
      headers:csrfHeaders({"Content-Type":"application/json"}),
      body:JSON.stringify(payload)
    });
    const data = await parseResponse(res);
    if(!res.ok){
      setFeedback(feedbackEl, data.error || `Erro ${res.status} ao salvar registro.`, true);
      return false;
    }
    setFeedback(feedbackEl, data.message || successMessage);
    await loadAll();
    return true;
  }catch(error){
    setFeedback(feedbackEl, `Falha ao conectar com o servidor: ${error.message}`, true);
    return false;
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

  const ok = await sendPost("/api/encomendas", payload, encomendaFeedback, "Salvando encomenda...", "Encomenda salva com sucesso.");
  if(ok){
    encomendaForm.reset();
    updatePreviewEncomenda();
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
    const res = await fetch(`/api/metas/${encodeURIComponent(id)}/status`, {
      method:"POST",
      headers:csrfHeaders({"Content-Type":"application/json"}),
      body:JSON.stringify({pago})
    });
    const data = await parseResponse(res);
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
    const res = await fetch(`/api/metas/${encodeURIComponent(id)}`, {method:"DELETE", headers:csrfHeaders()});
    const data = await parseResponse(res);
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
    const res = await fetch("/api/metas/fechar-semana", {method:"POST", headers:csrfHeaders()});
    const data = await parseResponse(res);
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
    craftTable.innerHTML = `<tr><td colspan="4">Modo somente leitura. A tabela de receitas está disponível abaixo.</td></tr>`;
    return;
  }

  const {totalItens, totals} = collectCraftTotals();
  setText("craftTotalItens", integer(totalItens));

  if(totalItens <= 0 || totals.size === 0){
    craftTable.innerHTML = `<tr><td colspan="4">Informe uma quantidade para calcular.</td></tr>`;
    setFeedback(craftFeedback, "Informe uma quantidade para calcular os materiais.");
    return;
  }

  craftTable.innerHTML = Array.from(totals.entries()).map(([material, total]) => {
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
  }).join("");

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
    const res = await fetch("/health");
    const data = await parseResponse(res);
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
    const res = await fetch("/api/compras");
    const data = await parseResponse(res);
    if(!res.ok){
      comprasTable.innerHTML = `<tr><td colspan="6">${escapeHtml(data.error || "Erro ao carregar compras.")}</td></tr>`;
      return;
    }
    if(!Array.isArray(data) || !data.length){
      comprasTable.innerHTML = `<tr><td colspan="6">Nenhuma compra registrada.</td></tr>`;
      return;
    }
    comprasTable.innerHTML = data.map(item => `
      <tr>
        <td>${escapeHtml(item.data)}</td>
        <td>${escapeHtml(item.produto)}</td>
        <td>${escapeHtml(item.quem_pediu)}</td>
        <td>${escapeHtml(item.quem_vendeu)}</td>
        <td>${escapeHtml(item.quantidade)}</td>
        <td>${currency(item.valor_total)}</td>
      </tr>`).join("");
  }catch(error){
    comprasTable.innerHTML = `<tr><td colspan="6">Falha ao carregar compras: ${escapeHtml(error.message)}</td></tr>`;
  }
}

async function loadVendas(){
  try{
    const res = await fetch("/api/vendas");
    const data = await parseResponse(res);
    if(!res.ok){
      vendasTable.innerHTML = `<tr><td colspan="6">${escapeHtml(data.error || "Erro ao carregar vendas.")}</td></tr>`;
      return;
    }
    if(!Array.isArray(data) || !data.length){
      vendasTable.innerHTML = `<tr><td colspan="6">Nenhuma venda registrada.</td></tr>`;
      return;
    }
    vendasTable.innerHTML = data.map(item => `
      <tr>
        <td>${escapeHtml(item.data)}</td>
        <td>${escapeHtml(item.produto)}</td>
        <td>${escapeHtml(item.quem_compra)}</td>
        <td>${escapeHtml(item.quem_vende)}</td>
        <td>${escapeHtml(item.quantidade)}</td>
        <td>${currency(item.valor_total)}</td>
      </tr>`).join("");
  }catch(error){
    vendasTable.innerHTML = `<tr><td colspan="6">Falha ao carregar vendas: ${escapeHtml(error.message)}</td></tr>`;
  }
}

async function loadEncomendas(){
  try{
    const res = await fetch("/api/encomendas");
    const data = await parseResponse(res);
    if(!res.ok){
      encomendasTable.innerHTML = `<tr><td colspan="7">${escapeHtml(data.error || "Erro ao carregar encomendas.")}</td></tr>`;
      return;
    }
    if(!Array.isArray(data) || !data.length){
      encomendasTable.innerHTML = `<tr><td colspan="7">Nenhuma encomenda registrada.</td></tr>`;
      return;
    }
    encomendasTable.innerHTML = data.map(item => `
      <tr>
        <td>${escapeHtml(item.data)}</td>
        <td>${escapeHtml(item.quem_pediu)}</td>
        <td>${escapeHtml(item.o_que_pediu)}</td>
        <td>${escapeHtml(item.para_quando)}</td>
        <td>${escapeHtml(item.quem_negociou)}</td>
        <td>${deliveryBadge(item.entregue)}</td>
        <td>${currency(item.valor)}</td>
      </tr>`).join("");
  }catch(error){
    encomendasTable.innerHTML = `<tr><td colspan="7">Falha ao carregar encomendas: ${escapeHtml(error.message)}</td></tr>`;
  }
}

async function loadMetas(){
  if(!metasTable) return;

  const colspan = canWrite ? 5 : 4;
  try{
    const res = await fetch("/api/metas");
    const data = await parseResponse(res);
    if(!res.ok){
      metasTable.innerHTML = `<tr><td colspan="${colspan}">${escapeHtml(data.error || "Erro ao carregar metas.")}</td></tr>`;
      return;
    }
    if(!Array.isArray(data) || !data.length){
      metasTable.innerHTML = `<tr><td colspan="${colspan}">Nenhum nome cadastrado na lista de metas.</td></tr>`;
      updateMetaCounters(0, 0, 0, 0, "--");
      return;
    }

    const pagos = data.filter(item => String(item.pago || "").trim().toLowerCase() === "sim").length;
    const confirmados = data.filter(item => Boolean(item.confirmado)).length;
    const first = data[0] || {};
    const semanaLabel = first.semana_inicio && first.semana_fim ? `${first.semana_inicio} até ${first.semana_fim}` : "--";
    updateMetaCounters(data.length, pagos, data.length - pagos, confirmados, semanaLabel);

    metasTable.innerHTML = data.map((item, index) => {
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
    }).join("");
  }catch(error){
    metasTable.innerHTML = `<tr><td colspan="${colspan}">Falha ao carregar metas: ${escapeHtml(error.message)}</td></tr>`;
  }
}

async function loadAll(){
  if(refreshBtn){
    refreshBtn.disabled = true;
    refreshBtn.textContent = "Atualizando...";
  }
  try{
    await Promise.all([loadHealth(), loadResumo(), loadCompras(), loadVendas(), loadEncomendas(), loadMetas()]);
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
renderRecipes();
renderCraft();
loadAll();
