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
const comprasTable = document.getElementById("comprasTable");
const vendasTable = document.getElementById("vendasTable");
const encomendasTable = document.getElementById("encomendasTable");
let encomendasCache = [];
const deliveryModal = document.getElementById("deliveryModal");
const deliveryForm = document.getElementById("deliveryForm");
const deliveryFeedback = document.getElementById("deliveryFeedback");
const deliveryConfirmBtn = document.getElementById("deliveryConfirmBtn");
const encomendaEditModal = document.getElementById("encomendaEditModal");
const encomendaEditForm = document.getElementById("encomendaEditForm");
const encomendaEditFeedback = document.getElementById("encomendaEditFeedback");
const encomendaEditSaveBtn = document.getElementById("encomendaEditSaveBtn");
let activeDeliveryEncomendaId = null;
let activeEditEncomendaId = null;
const reunioesGrid = document.getElementById("reunioesGrid");
const flyersGrid = document.getElementById("flyersGrid");
const flyerSearch = document.getElementById("flyerSearch");
const reuniaoOrganizationSelect = document.getElementById("r_organizacao");
const reuniaoOrganizationFilter = document.getElementById("reuniaoOrganizationFilter");
const reuniaoCustomOrganizationWrap = document.getElementById("r_gangue_wrap");
const flyerModal = document.getElementById("flyerModal");
const flyerModalImage = document.getElementById("flyerModalImage");
const flyerModalPrevious = document.getElementById("flyerModalPrevious");
const flyerModalNext = document.getElementById("flyerModalNext");
const flyerModalMeetings = document.getElementById("flyerModalMeetings");
let organizacoesCache = [];
let activeFlyerOrganizationId = null;
let activeFlyerIndex = 0;
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

function moneyTypeBadge(value){
  const normalized = String(value || "").trim().toLowerCase();
  if(normalized === "sujo") return `<span class="money-type-badge dirty">SUJO +30%</span>`;
  if(normalized === "limpo") return `<span class="money-type-badge clean">LIMPO</span>`;
  return `<span class="money-type-badge neutral">NÃO INFORMADO</span>`;
}

function deliveryControl(item){
  const delivered = String(item.entregue || "Não").trim().toLowerCase() === "sim";
  if(!canWrite) return delivered ? deliveryBadge("Sim") : deliveryBadge("Não");

  return `<div class="encomenda-action-group">
    <button type="button" class="delivery-confirm-btn" data-open-delivery="${escapeHtml(item.id)}">
      ${delivered ? "Mover para Vendas" : "Confirmar entrega"}
    </button>
    <button type="button" class="encomenda-edit-btn" data-edit-encomenda="${escapeHtml(item.id)}">Editar</button>
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
onInput("edit_e_valor", updateEditEncomendaPreview);
document.getElementById("e_entregue")?.addEventListener("change", updateEncomendaPaymentField);

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
  setText("previewEncomendaSujo", `No sujo (+30%): ${currency(valor * 1.30)}`);
}

function updateEncomendaPaymentField(){
  const delivered = inputValue("e_entregue") === "Sim";
  const wrap = document.getElementById("e_tipo_dinheiro_wrap");
  const select = document.getElementById("e_tipo_dinheiro");
  if(wrap) wrap.hidden = !delivered;
  if(select){
    select.required = delivered;
    if(!delivered) select.value = "";
  }
}

function updateEditEncomendaPreview(){
  const valor = Number(inputValue("edit_e_valor") || 0);
  setText("editEncomendaDirtyPreview", `No sujo (+30%): ${currency(valor * 1.30)}`);
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
    tipo_dinheiro: inputValue("e_tipo_dinheiro"),
    observacao: inputValue("e_observacao").trim(),
  };

  const result = await sendPost("/api/encomendas", payload, encomendaFeedback, "Salvando encomenda...", "Encomenda salva com sucesso.");
  if(result){
    encomendaForm.reset();
    updatePreviewEncomenda();
    updateEncomendaPaymentField();
    if(result.moved_to_vendas){
      activateView("vendas");
    }
  }
});


function organizationById(id){
  return organizacoesCache.find(item => item.id === id) || null;
}

function meetingOrganization(item){
  return item?.organizacao || organizationById(item?.organizacao_id) || null;
}

function setMeetingOrganizationPreview(organization, custom=false){
  const icon = document.getElementById("r_icone");
  const customName = document.getElementById("r_gangue");
  if(icon){
    icon.readOnly = !custom;
    if(organization) icon.value = organization.icone || "🤝";
    else if(!custom) icon.value = "";
  }
  if(reuniaoCustomOrganizationWrap) reuniaoCustomOrganizationWrap.hidden = !custom;
  if(custom && customName) customName.required = true;
  else if(customName) customName.required = false;

  setText("reuniaoOrgPreviewIcon", organization?.icone || (custom ? icon?.value || "🤝" : "🤝"));
  setText("reuniaoOrgPreviewName", organization?.nome || (custom ? customName?.value || "Nova organização" : "Nenhuma organização"));
  setText(
    "reuniaoOrgPreviewStatus",
    organization
      ? (organization.tem_flyer ? `${organization.flyers.length} flyer${organization.flyers.length > 1 ? "s" : ""} vinculado${organization.flyers.length > 1 ? "s" : ""}.` : "Flyer ainda não enviado.")
      : (custom ? "A reunião ficará sem flyer até esta organização ser cadastrada." : "Selecione um parceiro para relacionar.")
  );
}

function updateMeetingOrganizationSelection(){
  if(!reuniaoOrganizationSelect) return;
  const selectedId = reuniaoOrganizationSelect.value;
  const isCustom = selectedId === "__custom__";
  setMeetingOrganizationPreview(isCustom ? null : organizationById(selectedId), isCustom);
}

function populateOrganizationControls(){
  const sorted = [...organizacoesCache].sort((a,b) => a.nome.localeCompare(b.nome, "pt-BR"));

  if(reuniaoOrganizationSelect){
    const previous = reuniaoOrganizationSelect.value;
    reuniaoOrganizationSelect.innerHTML = [
      '<option value="">Selecione uma organização</option>',
      ...sorted.map(item => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.icone || "🤝")} ${escapeHtml(item.nome)}${item.tem_flyer ? "" : " — flyer pendente"}</option>`),
      '<option value="__custom__">＋ Outra organização</option>'
    ].join("");
    if([...reuniaoOrganizationSelect.options].some(option => option.value === previous)) reuniaoOrganizationSelect.value = previous;
    updateMeetingOrganizationSelection();
  }

  if(reuniaoOrganizationFilter){
    const previous = reuniaoOrganizationFilter.value;
    reuniaoOrganizationFilter.innerHTML = [
      '<option value="">Todas as organizações</option>',
      ...sorted.map(item => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.nome)}</option>`),
      '<option value="__custom__">Sem organização cadastrada</option>'
    ].join("");
    if([...reuniaoOrganizationFilter.options].some(option => option.value === previous)) reuniaoOrganizationFilter.value = previous;
  }
}

function renderFlyers(){
  if(!flyersGrid) return;
  const query = String(flyerSearch?.value || "").trim().toLocaleLowerCase("pt-BR");
  const items = organizacoesCache.filter(item => !query || item.nome.toLocaleLowerCase("pt-BR").includes(query));

  if(!items.length){
    flyersGrid.innerHTML = '<div class="flyer-empty">Nenhuma organização encontrada para esta pesquisa.</div>';
    return;
  }

  flyersGrid.innerHTML = items.map(organization => {
    const flyers = Array.isArray(organization.flyers) ? organization.flyers : [];
    const hasFlyer = flyers.length > 0;
    const preview = hasFlyer
      ? `<button class="flyer-preview-button" type="button" data-open-flyer="${escapeHtml(organization.id)}" data-flyer-index="0" aria-label="Abrir flyer de ${escapeHtml(organization.nome)}">
          <img src="${escapeHtml(flyers[0].url)}" alt="${escapeHtml(flyers[0].titulo)} — ${escapeHtml(organization.nome)}" loading="lazy" />
          ${flyers.length > 1 ? `<span class="flyer-stack-badge">+${flyers.length - 1}</span>` : ""}
        </button>`
      : `<div class="flyer-missing-preview"><span>${escapeHtml(organization.icone || "🤝")}</span><strong>Flyer pendente</strong><small>A imagem ainda não foi enviada.</small></div>`;

    return `<article class="flyer-card ${hasFlyer ? "has-flyer" : "missing-flyer"}">
      <div class="flyer-card-media">${preview}</div>
      <div class="flyer-card-content">
        <div class="flyer-card-heading">
          <span class="flyer-organization-icon">${escapeHtml(organization.icone || "🤝")}</span>
          <div><p>Organização</p><h4>${escapeHtml(organization.nome)}</h4></div>
          <span class="flyer-status-badge ${hasFlyer ? "available" : "pending"}">${hasFlyer ? `${flyers.length} flyer${flyers.length > 1 ? "s" : ""}` : "Pendente"}</span>
        </div>
        ${hasFlyer ? `<div class="flyer-title-list">${flyers.map((flyer,index) => `<button type="button" data-open-flyer="${escapeHtml(organization.id)}" data-flyer-index="${index}">${escapeHtml(flyer.titulo)}</button>`).join("")}</div>` : '<p class="flyer-pending-copy">Esta organização já pode ser relacionada às reuniões. O flyer aparecerá aqui quando for adicionado.</p>'}
        <div class="flyer-card-actions">
          ${hasFlyer ? `<button class="primary-btn flyer-open-btn" type="button" data-open-flyer="${escapeHtml(organization.id)}" data-flyer-index="0">Abrir flyer</button>` : ""}
          <button class="ghost-btn flyer-meetings-btn" type="button" data-org-meetings="${escapeHtml(organization.id)}">Ver reuniões</button>
        </div>
      </div>
    </article>`;
  }).join("");
}

function updateOrganizationStats(){
  const flyerCount = organizacoesCache.reduce((total,item) => total + (Array.isArray(item.flyers) ? item.flyers.length : 0), 0);
  const pending = organizacoesCache.filter(item => !item.tem_flyer).length;
  setText("statOrganizacoes", integer(organizacoesCache.length));
  setText("statFlyers", integer(flyerCount));
  setText("flyerOrganizationCount", integer(organizacoesCache.length));
  setText("flyerAssetCount", integer(flyerCount));
  setText("flyerPendingCount", integer(pending));
}

async function loadOrganizacoes(){
  try{
    const {res, data} = await fetchJson("/api/organizacoes");
    if(!res.ok) throw new Error(data.error || "Erro ao carregar organizações.");
    organizacoesCache = Array.isArray(data) ? data : [];
    updateOrganizationStats();
    populateOrganizationControls();
    renderFlyers();
    renderReunioes();
  }catch(error){
    if(flyersGrid) flyersGrid.innerHTML = `<div class="flyer-empty">Falha ao carregar organizações: ${escapeHtml(error.message)}</div>`;
  }
}

function updateFlyerModal(){
  const organization = organizationById(activeFlyerOrganizationId);
  const flyers = organization?.flyers || [];
  if(!organization || !flyers.length) return closeFlyerModal();
  activeFlyerIndex = (activeFlyerIndex + flyers.length) % flyers.length;
  const flyer = flyers[activeFlyerIndex];
  setText("flyerModalOrganization", organization.nome);
  setText("flyerModalTitle", flyer.titulo);
  setText("flyerModalCounter", `${activeFlyerIndex + 1} de ${flyers.length}`);
  if(flyerModalImage){
    flyerModalImage.src = flyer.url;
    flyerModalImage.alt = `${flyer.titulo} — ${organization.nome}`;
  }
  if(flyerModalPrevious) flyerModalPrevious.hidden = flyers.length <= 1;
  if(flyerModalNext) flyerModalNext.hidden = flyers.length <= 1;
}

function openFlyerModal(organizationId, index=0){
  const organization = organizationById(organizationId);
  if(!flyerModal || !organization?.flyers?.length) return;
  activeFlyerOrganizationId = organizationId;
  activeFlyerIndex = Number(index) || 0;
  flyerModal.hidden = false;
  flyerModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
  updateFlyerModal();
  flyerModal.querySelector(".flyer-modal-close")?.focus();
}

function closeFlyerModal(){
  if(!flyerModal) return;
  flyerModal.hidden = true;
  flyerModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");
}

function openOrganizationMeetings(organizationId){
  closeFlyerModal();
  activateView("reunioes");
  if(reuniaoOrganizationFilter){
    reuniaoOrganizationFilter.value = organizationId || "";
    renderReunioes();
  }
  document.getElementById("reunioesGrid")?.scrollIntoView({behavior:"smooth", block:"start"});
}

reuniaoOrganizationSelect?.addEventListener("change", updateMeetingOrganizationSelection);
document.getElementById("r_gangue")?.addEventListener("input", () => setMeetingOrganizationPreview(null, true));
document.getElementById("r_icone")?.addEventListener("input", () => setMeetingOrganizationPreview(null, reuniaoOrganizationSelect?.value === "__custom__"));
reuniaoOrganizationFilter?.addEventListener("change", renderReunioes);
flyerSearch?.addEventListener("input", renderFlyers);
flyersGrid?.addEventListener("click", event => {
  const openButton = event.target.closest("[data-open-flyer]");
  if(openButton){ openFlyerModal(openButton.dataset.openFlyer, openButton.dataset.flyerIndex); return; }
  const meetingButton = event.target.closest("[data-org-meetings]");
  if(meetingButton) openOrganizationMeetings(meetingButton.dataset.orgMeetings);
});
flyerModal?.addEventListener("click", event => {
  if(event.target.closest("[data-close-flyer]")) closeFlyerModal();
});
flyerModalPrevious?.addEventListener("click", () => { activeFlyerIndex -= 1; updateFlyerModal(); });
flyerModalNext?.addEventListener("click", () => { activeFlyerIndex += 1; updateFlyerModal(); });
flyerModalMeetings?.addEventListener("click", () => openOrganizationMeetings(activeFlyerOrganizationId));
document.addEventListener("keydown", event => {
  if(flyerModal?.hidden !== false) return;
  if(event.key === "Escape") closeFlyerModal();
  if(event.key === "ArrowLeft"){ activeFlyerIndex -= 1; updateFlyerModal(); }
  if(event.key === "ArrowRight"){ activeFlyerIndex += 1; updateFlyerModal(); }
});

function resetReuniaoForm(){
  reuniaoEmEdicaoId = null;
  reuniaoForm?.reset();
  if(reuniaoSubmitBtn) reuniaoSubmitBtn.textContent = "Agendar reunião";
  if(reuniaoCancelEditBtn) reuniaoCancelEditBtn.hidden = true;
  setText("reuniaoFormKicker", "Nova reunião");
  setText("reuniaoFormTitle", "Agendar compromisso");
  updateMeetingOrganizationSelection();
}

function iniciarEdicaoReuniao(id){
  const item = reunioesCache.find(reuniao => reuniao.id === id);
  if(!item || !reuniaoForm) return;
  reuniaoEmEdicaoId = id;
  document.getElementById("r_titulo").value = item.titulo || "";
  const hasKnownOrganization = item.organizacao_id && organizationById(item.organizacao_id);
  if(reuniaoOrganizationSelect) reuniaoOrganizationSelect.value = hasKnownOrganization ? item.organizacao_id : "__custom__";
  document.getElementById("r_gangue").value = hasKnownOrganization ? "" : (item.gangue || "");
  document.getElementById("r_icone").value = item.icone || item.organizacao?.icone || "🤝";
  updateMeetingOrganizationSelection();
  if(!hasKnownOrganization){
    document.getElementById("r_icone").value = item.icone || "🤝";
    setMeetingOrganizationPreview(null, true);
  }
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
  const selectedOrganizationId = inputValue("r_organizacao");
  const organization = organizationById(selectedOrganizationId);
  const payload = {
    titulo: inputValue("r_titulo").trim(),
    organizacao_id: organization?.id || "",
    gangue: organization?.nome || inputValue("r_gangue").trim(),
    icone: organization?.icone || inputValue("r_icone").trim(),
    data: inputValue("r_data"),
    horario: inputValue("r_horario"),
    local: inputValue("r_local").trim(),
    pauta: inputValue("r_pauta").trim()
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
  const flyerButton = event.target.closest("[data-open-flyer]");
  if(flyerButton){ openFlyerModal(flyerButton.dataset.openFlyer, flyerButton.dataset.flyerIndex); return; }
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
    if(res.ok) await loadReunioes();
  }catch(error){ setFeedback(reuniaoFeedback, `Falha ao finalizar: ${error.message}`, true); }
  finally{ button.disabled = false; }
});

function encomendaById(id){
  return encomendasCache.find(item => String(item.id) === String(id)) || null;
}

function setInputValue(id, value){
  const element = document.getElementById(id);
  if(element) element.value = value ?? "";
}

function openDeliveryModal(id){
  const item = encomendaById(id);
  if(!deliveryModal || !item || !canWrite) return;

  activeDeliveryEncomendaId = item.id;
  deliveryForm?.reset();
  setText("deliveryOrderName", item.o_que_pediu || "Encomenda");
  setText("deliveryOrderCustomer", `${item.quem_pediu || "--"} • valor base ${currency(item.valor)}`);
  setText("deliveryCleanValue", currency(item.valor));
  setText("deliveryDirtyValue", currency(Number(item.valor || 0) * 1.30));
  setText("deliverySelectedValue", "Escolha uma opção");
  setFeedback(deliveryFeedback, "Selecione dinheiro limpo ou sujo.");
  deliveryModal.hidden = false;
  deliveryModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
  deliveryModal.querySelector('input[name="delivery_money_type"]')?.focus();
}

function closeDeliveryModal(){
  if(!deliveryModal) return;
  deliveryModal.hidden = true;
  deliveryModal.setAttribute("aria-hidden", "true");
  activeDeliveryEncomendaId = null;
  document.body.classList.remove("modal-open");
}

function updateDeliverySelectedValue(){
  const item = encomendaById(activeDeliveryEncomendaId);
  const selected = deliveryForm?.querySelector('input[name="delivery_money_type"]:checked')?.value;
  if(!item || !selected){
    setText("deliverySelectedValue", "Escolha uma opção");
    return;
  }
  const total = Number(item.valor || 0) * (selected === "Sujo" ? 1.30 : 1);
  setText("deliverySelectedValue", `${selected}: ${currency(total)}`);
}

function openEncomendaEditModal(id){
  const item = encomendaById(id);
  if(!encomendaEditModal || !item || !canWrite) return;
  activeEditEncomendaId = item.id;
  setInputValue("edit_e_quem_pediu", item.quem_pediu);
  setInputValue("edit_e_o_que_pediu", item.o_que_pediu);
  setInputValue("edit_e_valor", item.valor);
  setInputValue("edit_e_para_quando", item.para_quando);
  setInputValue("edit_e_quem_negociou", item.quem_negociou);
  setInputValue("edit_e_observacao", item.observacao);
  updateEditEncomendaPreview();
  setFeedback(encomendaEditFeedback, "Edite os campos e salve.");
  encomendaEditModal.hidden = false;
  encomendaEditModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
  document.getElementById("edit_e_quem_pediu")?.focus();
}

function closeEncomendaEditModal(){
  if(!encomendaEditModal) return;
  encomendaEditModal.hidden = true;
  encomendaEditModal.setAttribute("aria-hidden", "true");
  activeEditEncomendaId = null;
  document.body.classList.remove("modal-open");
}

encomendasTable?.addEventListener("click", event => {
  if(!canWrite) return;
  const deliveryButton = event.target.closest("[data-open-delivery]");
  if(deliveryButton){
    openDeliveryModal(deliveryButton.dataset.openDelivery);
    return;
  }
  const editButton = event.target.closest("[data-edit-encomenda]");
  if(editButton) openEncomendaEditModal(editButton.dataset.editEncomenda);
});

deliveryModal?.addEventListener("click", event => {
  if(event.target.closest("[data-close-delivery]")) closeDeliveryModal();
});

deliveryForm?.addEventListener("change", updateDeliverySelectedValue);

deliveryForm?.addEventListener("submit", async event => {
  event.preventDefault();
  const id = activeDeliveryEncomendaId;
  const tipoDinheiro = deliveryForm.querySelector('input[name="delivery_money_type"]:checked')?.value;
  if(!id || !tipoDinheiro){
    setFeedback(deliveryFeedback, "Escolha dinheiro limpo ou sujo antes de confirmar.", true);
    return;
  }

  deliveryConfirmBtn.disabled = true;
  setFeedback(deliveryFeedback, "Confirmando entrega e calculando o valor...");
  try{
    const {res, data} = await fetchJson(`/api/encomendas/${encodeURIComponent(id)}/entrega`, {
      method:"POST",
      headers:csrfHeaders({"Content-Type":"application/json"}),
      body:JSON.stringify({entregue:"Sim", tipo_dinheiro:tipoDinheiro})
    });
    if(!res.ok){
      setFeedback(deliveryFeedback, data.error || "Erro ao confirmar a entrega.", true);
      return;
    }

    closeDeliveryModal();
    setFeedback(encomendaFeedback, `${data.message || "Entrega confirmada."} ${data.tipo_dinheiro || tipoDinheiro}: ${currency(data.valor_total)}.`);
    await Promise.all([loadEncomendas(), loadVendas(), loadResumo()]);
    activateView("vendas");
  }catch(error){
    setFeedback(deliveryFeedback, `Falha ao atualizar a entrega: ${error.message}`, true);
  }finally{
    deliveryConfirmBtn.disabled = false;
  }
});

encomendaEditModal?.addEventListener("click", event => {
  if(event.target.closest("[data-close-encomenda-edit]")) closeEncomendaEditModal();
});

encomendaEditForm?.addEventListener("submit", async event => {
  event.preventDefault();
  const id = activeEditEncomendaId;
  if(!id) return;

  const payload = {
    quem_pediu: inputValue("edit_e_quem_pediu").trim(),
    o_que_pediu: inputValue("edit_e_o_que_pediu").trim(),
    valor: Number(inputValue("edit_e_valor")),
    para_quando: inputValue("edit_e_para_quando").trim(),
    quem_negociou: inputValue("edit_e_quem_negociou").trim(),
    observacao: inputValue("edit_e_observacao").trim(),
  };

  encomendaEditSaveBtn.disabled = true;
  setFeedback(encomendaEditFeedback, "Salvando alterações...");
  try{
    const {res, data} = await fetchJson(`/api/encomendas/${encodeURIComponent(id)}`, {
      method:"PUT",
      headers:csrfHeaders({"Content-Type":"application/json"}),
      body:JSON.stringify(payload)
    });
    if(!res.ok){
      setFeedback(encomendaEditFeedback, data.error || "Erro ao editar a encomenda.", true);
      return;
    }
    closeEncomendaEditModal();
    setFeedback(encomendaFeedback, data.message || "Encomenda atualizada com sucesso.");
    await Promise.all([loadEncomendas(), loadResumo()]);
  }catch(error){
    setFeedback(encomendaEditFeedback, `Falha ao editar a encomenda: ${error.message}`, true);
  }finally{
    encomendaEditSaveBtn.disabled = false;
  }
});

document.addEventListener("keydown", event => {
  if(event.key !== "Escape") return;
  if(deliveryModal?.hidden === false) closeDeliveryModal();
  if(encomendaEditModal?.hidden === false) closeEncomendaEditModal();
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

comprasTable?.addEventListener("click", event => {
  const button = event.target.closest("[data-toggle-purchase-details]");
  if(!button) return;
  const id = button.dataset.togglePurchaseDetails;
  const detailRow = Array.from(comprasTable.querySelectorAll("[data-purchase-detail-row]"))
    .find(row => row.dataset.purchaseDetailRow === id);
  if(!detailRow) return;
  const willOpen = detailRow.hidden;
  detailRow.hidden = !willOpen;
  button.setAttribute("aria-expanded", String(willOpen));
  button.textContent = willOpen ? "Ocultar justificativa" : "Ver justificativa";
});

async function loadCompras(){
  const colspan = 7;
  try{
    const {res, data} = await fetchJson("/api/compras");
    if(!res.ok){
      setTableContent(comprasTable, `<tr><td colspan="${colspan}">${escapeHtml(data.error || "Erro ao carregar compras.")}</td></tr>`);
      return;
    }
    if(!Array.isArray(data) || !data.length){
      setTableContent(comprasTable, `<tr><td colspan="${colspan}">Nenhuma compra registrada.</td></tr>`);
      return;
    }
    setTableContent(comprasTable, data.map(item => {
      const observation = String(item.observacao || "").trim();
      const detailButton = observation
        ? `<button type="button" class="purchase-details-btn" data-toggle-purchase-details="${escapeHtml(item.id)}" aria-expanded="false">Ver justificativa</button>`
        : `<span class="purchase-no-details">Sem justificativa</span>`;
      const detailRow = observation
        ? `<tr class="purchase-detail-row" data-purchase-detail-row="${escapeHtml(item.id)}" hidden>
            <td colspan="${colspan}">
              <div class="purchase-detail-content"><strong>Justificativa da compra</strong><p>${escapeHtml(observation)}</p></div>
            </td>
          </tr>`
        : "";
      return `<tr class="purchase-main-row">
        <td>${escapeHtml(item.data)}</td>
        <td>${escapeHtml(item.produto)}</td>
        <td>${escapeHtml(item.quem_pediu)}</td>
        <td>${escapeHtml(item.quem_vendeu)}</td>
        <td>${escapeHtml(item.quantidade)}</td>
        <td>${currency(item.valor_total)}</td>
        <td>${detailButton}</td>
      </tr>${detailRow}`;
    }).join(""));
  }catch(error){
    setTableContent(comprasTable, `<tr><td colspan="${colspan}">Falha ao carregar compras: ${escapeHtml(error.message)}</td></tr>`);
  }
}

async function loadVendas(){
  const colspan = 7;
  try{
    const {res, data} = await fetchJson("/api/vendas");
    if(!res.ok){
      setTableContent(vendasTable, `<tr><td colspan="${colspan}">${escapeHtml(data.error || "Erro ao carregar vendas.")}</td></tr>`);
      return;
    }
    if(!Array.isArray(data) || !data.length){
      setTableContent(vendasTable, `<tr><td colspan="${colspan}">Nenhuma venda registrada.</td></tr>`);
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
        <td>${moneyTypeBadge(item.tipo_dinheiro)}</td>
      </tr>`).join(""));
  }catch(error){
    setTableContent(vendasTable, `<tr><td colspan="${colspan}">Falha ao carregar vendas: ${escapeHtml(error.message)}</td></tr>`);
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
    if(!Array.isArray(data) || !data.length){
      encomendasCache = [];
      setTableContent(encomendasTable, `<tr><td colspan="${colspan}">Nenhuma encomenda pendente.</td></tr>`);
      return;
    }
    encomendasCache = data;
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
    encomendasCache = [];
    setTableContent(encomendasTable, `<tr><td colspan="${colspan}">Falha ao carregar encomendas: ${escapeHtml(error.message)}</td></tr>`);
  }
}


function renderReunioes(){
  if(!reunioesGrid) return;
  const selectedOrganization = reuniaoOrganizationFilter?.value || "";
  const items = reunioesCache.filter(item => {
    if(!selectedOrganization) return true;
    if(selectedOrganization === "__custom__") return !item.organizacao_id;
    return item.organizacao_id === selectedOrganization;
  });

  const finalizadas = items.filter(item => item.status === "Finalizada").length;
  const canceladas = items.filter(item => item.status === "Cancelada").length;
  const agendadas = items.length - finalizadas - canceladas;
  setText("reunioesAgendadas", integer(agendadas));
  setText("reunioesFinalizadas", integer(finalizadas));
  setText("reunioesCanceladas", integer(canceladas));

  if(!items.length){
    reunioesGrid.innerHTML = `<div class="meeting-empty">${selectedOrganization ? "Nenhuma reunião encontrada para esta organização." : "Nenhuma reunião agendada até o momento."}</div>`;
    return;
  }

  reunioesGrid.innerHTML = items.map(item => {
    const done = item.status === "Finalizada";
    const canceled = item.status === "Cancelada";
    const pending = item.status === "Aguardando confirmação";
    const statusClass = done ? "finished" : (canceled ? "canceled" : (pending ? "pending" : "scheduled"));
    const statusLabel = done ? "Finalizada" : (canceled ? "Cancelada" : (pending ? "Aguardando confirmação" : "Agendada"));
    const date = item.data ? new Date(`${item.data}T12:00:00`) : null;
    const dateLabel = date && !Number.isNaN(date.getTime()) ? date.toLocaleDateString("pt-BR", {weekday:"short", day:"2-digit", month:"short"}) : item.data;
    const organization = meetingOrganization(item);
    const firstFlyer = organization?.flyers?.[0];
    const linkedFlyer = firstFlyer
      ? `<button class="meeting-flyer-link" type="button" data-open-flyer="${escapeHtml(organization.id)}" data-flyer-index="0">
          <img src="${escapeHtml(firstFlyer.url)}" alt="Flyer de ${escapeHtml(organization.nome)}" loading="lazy" />
          <span><strong>Flyer vinculado</strong><small>Abrir material da organização</small></span>
        </button>`
      : `<div class="meeting-flyer-link unavailable"><span class="meeting-no-flyer-icon">${escapeHtml(organization?.icone || item.icone || "🤝")}</span><span><strong>Sem flyer</strong><small>${organization ? "Imagem ainda não enviada" : "Organização personalizada"}</small></span></div>`;

    return `<article class="meeting-card ${statusClass}">
      <div class="meeting-icon">${escapeHtml(organization?.icone || item.icone || "🤝")}</div>
      <div class="meeting-card-content">
        <div class="meeting-card-top"><span class="meeting-status ${statusClass}">${statusLabel}</span><span class="meeting-gang">${escapeHtml(organization?.nome || item.gangue)}</span></div>
        <h4>${escapeHtml(item.titulo)}</h4>
        <div class="meeting-details"><span>📆 ${escapeHtml(dateLabel || "--")}</span><span>🕒 ${escapeHtml(item.horario || "--")}</span>${item.local ? `<span>📍 ${escapeHtml(item.local)}</span>` : ""}</div>
        ${linkedFlyer}
        ${item.pauta ? `<p>${escapeHtml(item.pauta)}</p>` : ""}
        ${done ? `<small>Concluída em ${escapeHtml(item.finalizada_em || "--")}</small>` : ""}
        ${canceled ? `<small class="meeting-canceled-at">Cancelada em ${escapeHtml(item.finalizada_em || "--")}</small>` : ""}
        ${canWrite ? `<div class="meeting-actions"><button class="meeting-edit-btn" type="button" data-editar-reuniao="${escapeHtml(item.id)}">✏️ Editar</button>${done || canceled ? "" : `<button class="meeting-cancel-btn" type="button" data-cancelar-reuniao="${escapeHtml(item.id)}">Cancelar reunião</button><button class="meeting-finish-btn" type="button" data-finalizar-reuniao="${escapeHtml(item.id)}">Marcar como finalizada</button>`}</div>` : ""}
      </div>
    </article>`;
  }).join("");
}

async function loadReunioes(){
  if(!reunioesGrid) return;
  try{
    const {res, data} = await fetchJson("/api/reunioes");
    if(!res.ok){ reunioesGrid.innerHTML = `<div class="meeting-empty">${escapeHtml(data.error || "Erro ao carregar reuniões.")}</div>`; return; }
    reunioesCache = Array.isArray(data) ? data : [];
    renderReunioes();
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
    await Promise.all([loadHealth(), loadResumo(), loadCompras(), loadVendas(), loadEncomendas(), loadOrganizacoes(), loadReunioes(), loadMetas()]);
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
updateEncomendaPaymentField();
renderRecipes();
renderCraft();
loadAll();
