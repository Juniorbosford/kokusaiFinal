const memberCsrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
const photoInput = document.getElementById("memberPhotoInput");
const uploadBtn = document.getElementById("memberUploadBtn");
const uploadZone = document.getElementById("memberUploadZone");
const selectedPhotosLabel = document.getElementById("memberSelectedPhotos");
const selectionPreview = document.getElementById("memberSelectionPreview");
const photoGrid = document.getElementById("memberPhotoGrid");
const historyTable = document.getElementById("memberHistoryTable");
const feedback = document.getElementById("memberMetaFeedback");
const paymentWarning = document.getElementById("memberPaymentWarning");
const paymentWarningTitle = document.getElementById("memberPaymentWarningTitle");
const paymentWarningText = document.getElementById("memberPaymentWarningText");
const lateBanner = document.getElementById("memberLateBanner");
const lateBannerTitle = document.getElementById("memberLateBannerTitle");
const lateBannerText = document.getElementById("memberLateBannerText");
const lateBannerBtn = document.getElementById("memberLateBannerBtn");
const lateBadge = document.getElementById("memberLateBadge");
let currentRoom = null;
let viewingWeekStart = "";
let selectedPhotos = [];
let selectedPreviewUrls = [];

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

function selectedPhotoSignature(file){
  return [file?.name, file?.size, file?.type, file?.lastModified].join(":");
}

function syncMemberPhotoInput(){
  try{
    const transfer = new DataTransfer();
    selectedPhotos.forEach(file => transfer.items.add(file));
    photoInput.files = transfer.files;
  }catch{
    // O envio usa selectedPhotos quando o navegador não permite alterar FileList.
  }
}

function clearSelectedPreviewUrls(){
  selectedPreviewUrls.forEach(url => URL.revokeObjectURL(url));
  selectedPreviewUrls = [];
}

function renderSelectedPhotos(){
  if(!selectionPreview) return;
  clearSelectedPreviewUrls();
  selectionPreview.hidden = selectedPhotos.length === 0;
  if(!selectedPhotos.length){
    selectionPreview.innerHTML = "";
    return;
  }
  selectionPreview.innerHTML = selectedPhotos.map((file, index) => {
    const previewUrl = URL.createObjectURL(file);
    selectedPreviewUrls.push(previewUrl);
    return `<article class="member-selected-photo">
      <img src="${memberEscape(previewUrl)}" alt="Prévia da foto ${index + 1}" />
      <div><strong>Foto ${index + 1}</strong><small>${memberEscape(file.name || "Imagem colada")}</small></div>
      <button type="button" data-remove-selected-photo="${index}" aria-label="Remover foto ${index + 1} da seleção">×</button>
    </article>`;
  }).join("");
}

function updateSelectedPhotos(files, {append=false} = {}){
  const previousCount = selectedPhotos.length;
  const incoming = Array.from(files || []).filter(Boolean);
  const supported = incoming.filter(isSupportedMemberImage);
  const rejected = incoming.length - supported.length;
  const maxBytes = (currentRoom?.limits?.max_file_mb || 10) * 1024 * 1024;
  const accepted = supported.filter(file => file.size <= maxBytes);
  const oversized = supported.length - accepted.length;
  const candidates = append ? [...selectedPhotos, ...accepted] : accepted;
  const signatures = new Set();
  const unique = candidates.filter(file => {
    const signature = selectedPhotoSignature(file);
    if(signatures.has(signature)) return false;
    signatures.add(signature);
    return true;
  });
  const remaining = Math.max((currentRoom?.limits?.max_photos || 10) - (currentRoom?.photos?.length || 0), 0);
  const excess = Math.max(unique.length - remaining, 0);
  selectedPhotos = unique.slice(0, remaining);
  if(uploadZone) uploadZone.classList.toggle("has-files", selectedPhotos.length > 0);
  if(selectedPhotosLabel){
    selectedPhotosLabel.textContent = selectedPhotos.length
      ? `${selectedPhotos.length} foto${selectedPhotos.length === 1 ? " selecionada" : "s selecionadas"}`
      : "Nenhuma foto selecionada";
  }
  syncMemberPhotoInput();
  renderSelectedPhotos();

  const warnings = [];
  if(rejected) warnings.push("Use somente imagens JPG, JPEG, PNG ou WEBP.");
  if(oversized) warnings.push(`Cada foto deve ter no máximo ${currentRoom?.limits?.max_file_mb || 10} MB.`);
  if(excess) warnings.push(`O limite permite manter no máximo ${remaining} nova(s) foto(s) nesta semana.`);
  if(warnings.length){
    memberFeedback(warnings.join(" "), true);
  }
  return {added: Math.max(selectedPhotos.length - previousCount, 0), hasWarnings: warnings.length > 0};
}

function clipboardImageFiles(event){
  const itemFiles = Array.from(event.clipboardData?.items || [])
    .filter(item => item.kind === "file" && String(item.type || "").toLowerCase().startsWith("image/"))
    .map(item => item.getAsFile())
    .filter(Boolean);
  if(itemFiles.length) return itemFiles;
  return Array.from(event.clipboardData?.files || []).filter(file => String(file.type || "").toLowerCase().startsWith("image/"));
}

function memberCanUpload(room){
  if(room?.schedule?.envio_atrasado) return true;
  return Boolean(room?.schedule?.envios_abertos) && !["Pago", "Não pago"].includes(room?.submission?.status);
}

function memberStatusLabel(item){
  return item?.status === "Pago" && item?.atrasado ? "Pago com atraso" : (item?.status || "Pendente");
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
  const locked = !memberCanUpload(room);
  const lateMode = Boolean(room.schedule?.envio_atrasado);
  document.getElementById("memberPhotoCounter").textContent = `${photos.length}/${room.limits?.max_photos || 10} fotos enviadas`;
  if(!photos.length){
    photoGrid.innerHTML = '<div class="meta-empty-state">Você ainda não enviou fotos nesta semana.</div>';
    return;
  }
  photoGrid.innerHTML = photos.map((photo, index) => `
    <article class="member-photo-card">
      <a href="${memberEscape(photo.url)}" target="_blank" rel="noopener"><img src="${memberEscape(photo.url)}" alt="Comprovante ${index + 1}" /></a>
      <div><span>Foto ${index + 1}${photo.atrasada ? ' <em class="meta-late-tag">Atrasada</em>' : ""}</span><small>${memberEscape(photo.created_at || "")}</small></div>
      ${locked || (lateMode && !photo.atrasada) ? '<span class="photo-locked">Envios encerrados</span>' : `<button type="button" data-delete-member-photo="${memberEscape(photo.id)}">Remover</button>`}
    </article>`).join("");
}

function renderPaymentWarning(monitor){
  if(!paymentWarning) return;
  const weeks = Number(monitor?.consecutive_unpaid_weeks || 0);
  const showWarning = Boolean(monitor?.warning && weeks >= 3);
  paymentWarning.hidden = !showWarning;
  if(!showWarning) return;
  paymentWarningTitle.textContent = `Atenção: ${weeks} semanas sem meta paga`;
  paymentWarningText.textContent = "Este aviso considera semanas finalizadas e consecutivas. Procure a administração para regularizar sua situação.";
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
      <td><span class="history-status status-${memberStatusClass(item.status)}">${memberEscape(memberStatusLabel(item))}</span>${item.atrasado ? ' <em class="meta-late-tag">Atrasada</em>' : ""}</td>
      <td>${memberEscape(item.reviewed_at || "—")}</td>
    </tr>`).join("");
}

function renderLateBanner(room){
  if(!lateBanner) return;
  const viewingLateWeek = Boolean(room.current_week_start && room.submission.week_start !== room.current_week_start);
  const pending = room.late_week;
  lateBanner.hidden = !pending && !viewingLateWeek;
  if(viewingLateWeek){
    lateBannerTitle.textContent = `Pagando com atraso a semana ${room.submission.week_start} até ${room.submission.week_end}`;
    lateBannerText.textContent = "O comprovante enviado aqui aparece como ATRASADO para a administração no fechamento desta semana.";
    lateBannerBtn.textContent = "Voltar para a semana atual";
    lateBannerBtn.dataset.week = "";
  }else if(pending){
    lateBannerTitle.textContent = `Meta em atraso: semana ${pending.week_start} até ${pending.week_end}`;
    lateBannerText.textContent = "O prazo terminou, mas a semana ainda não foi fechada. Você pode pagar agora: vai aparecer como ATRASADO para a administração.";
    lateBannerBtn.textContent = "Pagar com atraso";
    lateBannerBtn.dataset.week = pending.week_start;
  }
}

async function loadMemberRoom(weekStart = viewingWeekStart){
  try{
    const weekQuery = weekStart ? `&week_start=${encodeURIComponent(weekStart)}` : "";
    const response = await fetch(`/api/meta-room?at=${Date.now()}${weekQuery}`, {cache:"no-store"});
    const data = await response.json();
    if(!response.ok){
      if(weekStart){
        // A semana atrasada foi fechada ou paga nesse meio-tempo: volta para a semana atual.
        viewingWeekStart = "";
        return loadMemberRoom("");
      }
      throw new Error(data.error || "Não foi possível carregar sua sala.");
    }
    currentRoom = data;
    viewingWeekStart = weekStart || "";
    const viewingLateWeek = Boolean(data.current_week_start && data.submission.week_start !== data.current_week_start);
    const weekLabel = `${data.submission.week_start} até ${data.submission.week_end}`;
    document.getElementById("memberRoomTitle").textContent = `Meta de ${data.member.display_name}`;
    const avatarBox = document.getElementById("memberRoomAvatar");
    if(avatarBox){
      avatarBox.textContent = "";
      if(data.member.avatar){
        const photo = document.createElement("img");
        photo.src = data.member.avatar;
        photo.alt = "";
        avatarBox.appendChild(photo);
      }
      avatarBox.hidden = !data.member.avatar;
    }
    document.getElementById("memberWeekLabel").textContent = weekLabel;
    const weekKicker = document.getElementById("memberWeekKicker");
    if(weekKicker) weekKicker.textContent = viewingLateWeek ? "Semana em atraso" : "Semana atual";
    if(!viewingLateWeek) document.getElementById("memberWeekMini").textContent = weekLabel;
    setMemberStatus(memberStatusLabel(data.submission));
    if(data.submission.status === "Pago" && data.submission.atrasado){
      document.getElementById("memberMetaStatus")?.classList.replace("paid", "paid-late");
    }
    if(lateBadge) lateBadge.hidden = !data.submission.atrasado;
    renderLateBanner(data);
    renderCurrentPhotos(data);
    renderPaymentWarning(data.payment_monitor);
    renderHistory(data.history);
    const noteBox = document.getElementById("memberAdminNote");
    if(data.submission.admin_note){
      noteBox.hidden = false;
      noteBox.innerHTML = `<strong>Observação da administração</strong><p>${memberEscape(data.submission.admin_note)}</p>`;
    }else{
      noteBox.hidden = true;
      noteBox.textContent = "";
    }
    const locked = !memberCanUpload(data);
    photoInput.disabled = locked;
    uploadBtn.disabled = locked;
    uploadZone?.classList.toggle("late-mode", Boolean(data.schedule?.envio_atrasado));
    if(locked) updateSelectedPhotos([]);
    if(data.schedule?.envio_atrasado){
      memberFeedback(`Prazo encerrado em ${data.schedule?.prazo_pagamento || "quarta-feira às 23:59"}. Você ainda pode pagar com atraso: o comprovante vai aparecer como ATRASADO para a administração.`, true);
    }else if(locked){
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

photoInput?.addEventListener("change", () => updateSelectedPhotos(photoInput.files, {append:true}));

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
  updateSelectedPhotos(files, {append:true});
});

document.addEventListener("paste", event => {
  const files = clipboardImageFiles(event);
  if(!files.length) return;
  event.preventDefault();
  if(photoInput?.disabled){
    memberFeedback("O envio de fotos está fechado nesta semana.", true);
    return;
  }
  const result = updateSelectedPhotos(files, {append:true});
  if(result.added && !result.hasWarnings){
    memberFeedback(`${result.added} imagem${result.added === 1 ? " colada" : "s coladas"}. Confira a prévia e clique em Enviar fotos.`);
  }
  uploadZone?.classList.add("paste-success");
  window.setTimeout(() => uploadZone?.classList.remove("paste-success"), 700);
});

uploadZone?.addEventListener("keydown", event => {
  if(photoInput?.disabled || !["Enter", " "].includes(event.key)) return;
  event.preventDefault();
  photoInput?.click();
});

selectionPreview?.addEventListener("click", event => {
  const button = event.target.closest("[data-remove-selected-photo]");
  if(!button) return;
  const index = Number(button.dataset.removeSelectedPhoto);
  if(!Number.isInteger(index) || index < 0 || index >= selectedPhotos.length) return;
  const remainingSelection = selectedPhotos.filter((_, photoIndex) => photoIndex !== index);
  updateSelectedPhotos(remainingSelection);
  memberFeedback("Foto removida da seleção.");
});

uploadBtn?.addEventListener("click", async () => {
  const files = selectedPhotos.length ? selectedPhotos : Array.from(photoInput.files || []);
  if(!files.length){ memberFeedback("Selecione pelo menos uma foto.", true); return; }
  const remaining = Math.max((currentRoom?.limits?.max_photos || 10) - (currentRoom?.photos?.length || 0), 0);
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
      if(currentRoom?.submission?.week_start) body.append("week_start", currentRoom.submission.week_start);
      const response = await fetch("/api/meta-room/photos", {method:"POST", headers:{"X-CSRF-Token":memberCsrfToken}, body});
      const data = await response.json();
      if(!response.ok) throw new Error(data.error || "Falha ao enviar uma das fotos.");
      if(Array.isArray(data.photos) && currentRoom){
        currentRoom.photos = data.photos;
        renderCurrentPhotos(currentRoom);
      }
    }
    photoInput.value = "";
    updateSelectedPhotos([]);
    const sentLate = Boolean(currentRoom?.schedule?.envio_atrasado);
    await loadMemberRoom();
    memberFeedback(sentLate
      ? "Comprovante enviado com atraso. A administração verá esta meta marcada como ATRASADA."
      : "Fotos enviadas. Sua meta está aguardando conferência.", sentLate);
  }catch(error){
    memberFeedback(error.message, true);
  }finally{
    if(memberCanUpload(currentRoom)){
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

lateBannerBtn?.addEventListener("click", () => {
  updateSelectedPhotos([]);
  loadMemberRoom(lateBannerBtn.dataset.week || "");
});

loadMemberRoom();
