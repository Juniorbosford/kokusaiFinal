const memberCsrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
const photoInput = document.getElementById("memberPhotoInput");
const uploadBtn = document.getElementById("memberUploadBtn");
const photoGrid = document.getElementById("memberPhotoGrid");
const historyTable = document.getElementById("memberHistoryTable");
const feedback = document.getElementById("memberMetaFeedback");
let currentRoom = null;

function memberEscape(value){
  return String(value ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#039;");
}

function memberFeedback(message, error=false){
  if(!feedback) return;
  feedback.textContent = message;
  feedback.classList.toggle("error", error);
  feedback.classList.toggle("success", !error);
}

function setMemberStatus(status){
  const badge = document.getElementById("memberMetaStatus");
  if(!badge) return;
  const normalized = String(status || "Pendente").toLowerCase();
  badge.textContent = status || "Pendente";
  badge.className = `meta-status-badge ${normalized === "pago" ? "paid" : normalized === "enviado" ? "sent" : normalized === "recusado" ? "rejected" : "pending"}`;
}

function renderCurrentPhotos(room){
  const photos = room.photos || [];
  const locked = room.submission?.status === "Pago";
  document.getElementById("memberPhotoCounter").textContent = `${photos.length}/${room.limits?.max_photos || 5} fotos enviadas`;
  if(!photos.length){
    photoGrid.innerHTML = '<div class="meta-empty-state">Você ainda não enviou fotos nesta semana.</div>';
    return;
  }
  photoGrid.innerHTML = photos.map((photo, index) => `
    <article class="member-photo-card">
      <a href="${memberEscape(photo.url)}" target="_blank" rel="noopener"><img src="${memberEscape(photo.url)}" alt="Comprovante ${index + 1}" /></a>
      <div><span>Foto ${index + 1}</span><small>${memberEscape(photo.created_at || "")}</small></div>
      ${locked ? '<span class="photo-locked">Meta paga</span>' : `<button type="button" data-delete-member-photo="${memberEscape(photo.id)}">Remover</button>`}
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
      <td><span class="history-status status-${memberEscape(String(item.status || "").toLowerCase())}">${memberEscape(item.status)}</span></td>
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
    const locked = data.submission.status === "Pago";
    photoInput.disabled = locked;
    uploadBtn.disabled = locked;
    if(locked) memberFeedback("Meta confirmada como paga. Esta semana está encerrada para novos envios.");
  }catch(error){
    memberFeedback(error.message, true);
  }
}

uploadBtn?.addEventListener("click", async () => {
  const files = Array.from(photoInput.files || []);
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
    memberFeedback("Fotos enviadas. Sua meta está aguardando conferência.");
    await loadMemberRoom();
  }catch(error){
    memberFeedback(error.message, true);
  }finally{
    if(currentRoom?.submission?.status !== "Pago"){
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
