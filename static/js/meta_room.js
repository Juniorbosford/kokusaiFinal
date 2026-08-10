const memberCsrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
const photoInput = document.getElementById("memberPhotoInput");
const uploadBtn = document.getElementById("memberUploadBtn");
const uploadZone = document.getElementById("memberUploadZone");
const selectedPhotosLabel = document.getElementById("memberSelectedPhotos");
const photoGrid = document.getElementById("memberPhotoGrid");
const historyTable = document.getElementById("memberHistoryTable");
const feedback = document.getElementById("memberMetaFeedback");
let currentRoom = null;
let selectedPhotos = [];

function memberEscape(value){
  return String(value ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#039;");
}

function memberFeedback(message, error=false){
  if(!feedback) return;
  feedback.textContent = message;
  feedback.classList.toggle("error", error);
  feedback.classList.toggle("success", !error);
}

function isSupportedMemberImage(file){
  const name = String(file?.name || "").toLowerCase();
  const mime = String(file?.type || "").toLowerCase();
  return /\.(jpe?g|png|webp)$/.test(name) || ["image/jpeg", "image/jpg", "image/png", "image/webp"].includes(mime);
}

function updateSelectedPhotos(files){
  selectedPhotos = Array.from(files || []).filter(Boolean);
  const accepted = selectedPhotos.filter(isSupportedMemberImage);
  const rejected = selectedPhotos.length - accepted.length;
  selectedPhotos = accepted;
  if(uploadZone) uploadZone.classList.toggle("has-files", selectedPhotos.length > 0);
  if(selectedPhotosLabel){
    selectedPhotosLabel.textContent = selectedPhotos.length
      ? `${selectedPhotos.length} foto${selectedPhotos.length === 1 ? " selecionada" : "s selecionadas"}`
      : "Nenhuma foto selecionada";
  }
  if(rejected){
    memberFeedback("Use somente imagens JPG, JPEG, PNG ou WEBP.", true);
  }
}

function setMemberStatus(status){
  const badge = document.getElementById("memberMetaStatus");
  if(!badge) return;
  const normalized = String(status || "Pendente").toLowerCase();
  badge.textContent = status || "Pendente";
  badge.className = `meta-status-badge ${normalized === "pago" ? "paid" : normalized === "enviado" ? "sent" : ["recusado", "não pago", "nao pago"].includes(normalized) ? "rejected" : "pending"}`;
}

function memberStatusClass(status){
  const normalized = String(status || "").toLowerCase();
  if(normalized === "pago") return "pago";
  if(["recusado", "não pago", "nao pago"].includes(normalized)) return "recusado";
  if(normalized === "enviado") return "enviado";
  return "pendente";
}

function renderCurrentPhotos(room){
  const photos = room.photos || [];
  const locked = !room.schedule?.envios_abertos || ["Pago", "Não pago"].includes(room.submission?.status);
  document.getElementById("memberPhotoCounter").textContent = `${photos.length}/${room.limits?.max_photos || 5} fotos enviadas`;
  if(!photos.length){
    photoGrid.innerHTML = '<div class="meta-empty-state">Você ainda não enviou fotos nesta semana.</div>';
    return;
  }
  photoGrid.innerHTML = photos.map((photo, index) => `
    <article class="member-photo-card">
      <a href="${memberEscape(photo.url)}" target="_blank" rel="noopener"><img src="${memberEscape(photo.url)}" alt="Comprovante ${index + 1}" /></a>
      <div><span>Foto ${index + 1}</span><small>${memberEscape(photo.created_at || "")}</small></div>
      ${locked ? '<span class="photo-locked">Envios encerrados</span>' : `<button type="button" data-delete-member-photo="${memberEscape(photo.id)}">Remover</button>`}
    </article>`).join("");
}

function renderHistory(history){
  if(!Array.isArray(history) || !history.length){
    historyTable.innerHTML = '<tr><td colspan="4">Nenhuma semana registrada ainda.</td></tr>';
    return;
  }
  historyTable.innerHTML = history.map(item => `
    <tr>
      <td>${memberEscape(item.week_start)} até ${memberEscape(item.week_end)}</td>
      <td>${Number(item.photo_count || 0)}</td>
      <td><span class="history-status status-${memberStatusClass(item.status)}">${memberEscape(item.status)}</span></td>
      <td>${memberEscape(item.reviewed_at || "—")}</td>
    </tr>`).join("");
}

async function loadMemberRoom(){
  try{
    const response = await fetch("/api/meta-room");
    const data = await response.json();
    if(!response.ok) throw new Error(data.error || "Não foi possível carregar sua sala.");
    currentRoom = data;
    const weekLabel = `${data.submission.week_start} até ${data.submission.week_end}`;
    document.getElementById("memberRoomTitle").textContent = `Meta de ${data.member.display_name}`;
    document.getElementById("memberWeekLabel").textContent = weekLabel;
    document.getElementById("memberWeekMini").textContent = weekLabel;
    setMemberStatus(data.submission.status);
    renderCurrentPhotos(data);
    renderHistory(data.history);
    const noteBox = document.getElementById("memberAdminNote");
    if(data.submission.admin_note){
      noteBox.hidden = false;
      noteBox.innerHTML = `<strong>Observação da administração</strong><p>${memberEscape(data.submission.admin_note)}</p>`;
    }else{
      noteBox.hidden = true;
      noteBox.textContent = "";
    }
    const locked = !data.schedule?.envios_abertos || ["Pago", "Não pago"].includes(data.submission.status);
    photoInput.disabled = locked;
    uploadBtn.disabled = locked;
    if(locked) updateSelectedPhotos([]);
    if(locked){
      if(data.schedule?.closed){
        memberFeedback("Esta semana foi finalizada pela administração.");
      }else{
        memberFeedback(`Envios encerrados em ${data.schedule?.prazo_pagamento || "quarta-feira às 23:59"}. A meta está em conferência.`);
      }
    }else{
      memberFeedback(`Envios abertos até ${data.schedule?.prazo_pagamento || "quarta-feira às 23:59"}.`);
    }
  }catch(error){
    memberFeedback(error.message, true);
  }
}

photoInput?.addEventListener("change", () => updateSelectedPhotos(photoInput.files));

["dragenter", "dragover"].forEach(eventName => {
  uploadZone?.addEventListener(eventName, event => {
    event.preventDefault();
    if(!photoInput?.disabled) uploadZone.classList.add("drag-over");
  });
});

uploadZone?.addEventListener("dragleave", event => {
  if(!uploadZone.contains(event.relatedTarget)) uploadZone.classList.remove("drag-over");
});

uploadZone?.addEventListener("drop", event => {
  event.preventDefault();
  uploadZone.classList.remove("drag-over");
  if(photoInput?.disabled) return;
  const files = Array.from(event.dataTransfer?.files || []);
  updateSelectedPhotos(files);
  try{
    const transfer = new DataTransfer();
    selectedPhotos.forEach(file => transfer.items.add(file));
    photoInput.files = transfer.files;
  }catch{
    // O envio usa selectedPhotos, então navegadores que bloqueiam essa atribuição continuam funcionando.
  }
});

uploadZone?.addEventListener("keydown", event => {
  if(photoInput?.disabled || !["Enter", " "].includes(event.key)) return;
  event.preventDefault();
  photoInput?.click();
});

uploadBtn?.addEventListener("click", async () => {
  const files = selectedPhotos.length ? selectedPhotos : Array.from(photoInput.files || []);
  if(!files.length){ memberFeedback("Selecione pelo menos uma foto.", true); return; }
  const remaining = Math.max((currentRoom?.limits?.max_photos || 5) - (currentRoom?.photos?.length || 0), 0);
  if(files.length > remaining){ memberFeedback(`Você pode enviar mais ${remaining} foto(s) nesta semana.`, true); return; }
  const maxBytes = (currentRoom?.limits?.max_file_mb || 10) * 1024 * 1024;
  if(files.some(file => file.size > maxBytes)){ memberFeedback(`Cada foto deve ter no máximo ${currentRoom?.limits?.max_file_mb || 10} MB.`, true); return; }

  uploadBtn.disabled = true;
  photoInput.disabled = true;
  try{
    for(let index = 0; index < files.length; index++){
      memberFeedback(`Enviando foto ${index + 1} de ${files.length}...`);
      const body = new FormData();
      body.append("photo", files[index]);
      const response = await fetch("/api/meta-room/photos", {method:"POST", headers:{"X-CSRF-Token":memberCsrfToken}, body});
      const data = await response.json();
      if(!response.ok) throw new Error(data.error || "Falha ao enviar uma das fotos.");
    }
    photoInput.value = "";
    updateSelectedPhotos([]);
    memberFeedback("Fotos enviadas. Sua meta está aguardando conferência.");
    await loadMemberRoom();
  }catch(error){
    memberFeedback(error.message, true);
  }finally{
    if(currentRoom?.schedule?.envios_abertos && !["Pago", "Não pago"].includes(currentRoom?.submission?.status)){
      uploadBtn.disabled = false;
      photoInput.disabled = false;
    }
  }
});

photoGrid?.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-delete-member-photo]");
  if(!button) return;
  if(!window.confirm("Remover esta foto da meta desta semana?")) return;
  button.disabled = true;
  try{
    const response = await fetch(`/api/meta-room/photos/${encodeURIComponent(button.dataset.deleteMemberPhoto)}`, {method:"DELETE", headers:{"X-CSRF-Token":memberCsrfToken}});
    const data = await response.json();
    if(!response.ok) throw new Error(data.error || "Não foi possível remover a foto.");
    memberFeedback(data.message || "Foto removida.");
    await loadMemberRoom();
  }catch(error){ memberFeedback(error.message, true); }
  finally{ button.disabled = false; }
});

loadMemberRoom();
