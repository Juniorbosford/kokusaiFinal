const navLinks = document.querySelectorAll(".nav-link");
const views = document.querySelectorAll(".view");
navLinks.forEach(link => {
  link.addEventListener("click", () => {
    navLinks.forEach(btn => btn.classList.remove("active"));
    views.forEach(view => view.classList.remove("active"));
    link.classList.add("active");
    document.getElementById(link.dataset.target).classList.add("active");
  });
});

const refreshBtn = document.getElementById("refreshBtn");
const form = document.getElementById("compraForm");
const vendaForm = document.getElementById("vendaForm");
const formFeedback = document.getElementById("formFeedback");
const vendaFeedback = document.getElementById("vendaFeedback");
const comprasTable = document.getElementById("comprasTable");
const vendasTable = document.getElementById("vendasTable");

function currency(value){
  return new Intl.NumberFormat("pt-BR",{style:"currency",currency:"BRL"}).format(Number(value||0));
}
function escapeHtml(value){
  return String(value ?? "")
    .replace(/&/g,"&amp;")
    .replace(/</g,"&lt;")
    .replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;")
    .replace(/'/g,"&#039;");
}
function setFeedback(el, msg, isError=false){
  el.textContent=msg;
  el.classList.toggle("error",isError);
  el.classList.toggle("success",!isError);
}

async function parseResponse(res){
  const text = await res.text();
  if(!text){
    return {};
  }
  try{
    return JSON.parse(text);
  }catch{
    return { error: text };
  }
}

document.getElementById("valor_unitario").addEventListener("input", updatePreviewCompra);
document.getElementById("quantidade").addEventListener("input", updatePreviewCompra);
document.getElementById("v_valor_unitario").addEventListener("input", updatePreviewVenda);
document.getElementById("v_quantidade").addEventListener("input", updatePreviewVenda);

function updatePreviewCompra(){
  const valor = Number(document.getElementById("valor_unitario").value||0);
  const qtd = Number(document.getElementById("quantidade").value||0);
  document.getElementById("previewTotal").textContent = currency(valor*qtd);
}
function updatePreviewVenda(){
  const valor = Number(document.getElementById("v_valor_unitario").value||0);
  const qtd = Number(document.getElementById("v_quantidade").value||0);
  document.getElementById("previewVendaTotal").textContent = currency(valor*qtd);
}

form.addEventListener("submit", async (e)=>{
  e.preventDefault();
  const payload = {
    produto: document.getElementById("produto").value.trim(),
    quem_pediu: document.getElementById("quem_pediu").value.trim(),
    quem_vendeu: document.getElementById("quem_vendeu").value.trim(),
    valor_unitario: Number(document.getElementById("valor_unitario").value),
    quantidade: Number(document.getElementById("quantidade").value),
    observacao: document.getElementById("observacao").value.trim(),
  };
  try{
    setFeedback(formFeedback, "Salvando compra...");
    const res = await fetch("/api/compras",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    const data = await parseResponse(res);
    if(!res.ok){
      setFeedback(formFeedback, data.error || `Erro ${res.status} ao salvar compra.`, true);
      return;
    }
    setFeedback(formFeedback, data.message || "Compra salva com sucesso.");
    form.reset();
    updatePreviewCompra();
    await loadAll();
  }catch(error){
    setFeedback(formFeedback, `Falha ao conectar com o servidor: ${error.message}`, true);
  }
});

vendaForm.addEventListener("submit", async (e)=>{
  e.preventDefault();
  const payload = {
    produto: document.getElementById("v_produto").value.trim(),
    quem_compra: document.getElementById("quem_compra").value.trim(),
    quem_vende: document.getElementById("quem_vende").value.trim(),
    valor_unitario: Number(document.getElementById("v_valor_unitario").value),
    quantidade: Number(document.getElementById("v_quantidade").value),
    observacao: document.getElementById("v_observacao").value.trim(),
  };
  try{
    setFeedback(vendaFeedback, "Salvando venda...");
    const res = await fetch("/api/vendas",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    const data = await parseResponse(res);
    if(!res.ok){
      setFeedback(vendaFeedback, data.error || `Erro ${res.status} ao salvar venda.`, true);
      return;
    }
    setFeedback(vendaFeedback, data.message || "Venda salva com sucesso.");
    vendaForm.reset();
    updatePreviewVenda();
    await loadAll();
  }catch(error){
    setFeedback(vendaFeedback, `Falha ao conectar com o servidor: ${error.message}`, true);
  }
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
    const [rc, rv] = await Promise.all([fetch("/api/resumo"), fetch("/api/resumo-vendas")]);
    const dc = await parseResponse(rc);
    const dv = await parseResponse(rv);
    document.getElementById("statCompras").textContent = dc.total_registros ?? 0;
    document.getElementById("statVendas").textContent = dv.total_registros ?? 0;
    document.getElementById("statValorCompras").textContent = currency(dc.valor_movimentado ?? 0);
    document.getElementById("statValorVendas").textContent = currency(dv.valor_movimentado ?? 0);
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

async function loadAll(){
  await Promise.all([loadHealth(), loadResumo(), loadCompras(), loadVendas()]);
}

refreshBtn.addEventListener("click", loadAll);
updatePreviewCompra();
updatePreviewVenda();
loadAll();
