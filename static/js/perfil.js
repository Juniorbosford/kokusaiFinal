/* Página de perfil: foto, apelido, senha e "sair de todos os aparelhos". */
(function () {
  "use strict";

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
  const $ = (id) => document.getElementById(id);
  const Accounts = window.KokusaiAccounts;

  const avatarNode = $("profileAvatar");
  const nameNode = $("profileName");
  const userNode = $("profileUser");
  const roleNode = $("profileRole");
  const photoActions = $("photoActions");
  const photoInput = $("photoInput");
  const photoPick = $("photoPickBtn");
  const photoRemove = $("photoRemoveBtn");
  const photoStatus = $("photoStatus");
  const sharedNote = $("sharedNote");
  const formsBox = $("profileForms");
  const aliasForm = $("aliasForm");
  const aliasInput = $("aliasInput");
  const aliasHelp = $("aliasHelp");
  const aliasStatus = $("aliasStatus");
  const passwordForm = $("passwordForm");
  const passwordHelp = $("passwordHelp");
  const passwordStatus = $("passwordStatus");
  const signOutButton = $("signOutAllBtn");
  const signOutStatus = $("signOutStatus");

  let profile = null;

  function say(node, text, kind) {
    node.textContent = text || "";
    node.dataset.kind = kind || "";
    node.classList.toggle("login-error", kind === "error");
  }

  async function api(url, options = {}) {
    const headers = Object.assign({ Accept: "application/json", "X-CSRF-Token": csrfToken }, options.headers || {});
    const response = await fetch(url, Object.assign({ credentials: "same-origin" }, options, { headers }));
    let data = {};
    try {
      data = await response.json();
    } catch (error) {
      data = {};
    }
    if (!response.ok || data.ok === false) {
      const message = data.error || "Não foi possível concluir. Tente novamente.";
      const failure = new Error(message);
      failure.status = response.status;
      throw failure;
    }
    return data;
  }

  function render(data) {
    profile = data;
    nameNode.textContent = data.display_name;
    userNode.textContent = "@" + data.username + (data.apelido ? " · " + data.apelido : "");
    roleNode.textContent = data.role_label;
    Accounts.fillAvatar(avatarNode, {
      username: data.username,
      display_name: data.display_name,
      apelido: data.apelido,
      role: data.role,
      thumb: "",
    });
    if (data.avatar && data.can_edit) {
      avatarNode.classList.remove("account-avatar-logo");
      avatarNode.textContent = "";
      const image = document.createElement("img");
      image.src = data.avatar;
      image.alt = "";
      avatarNode.appendChild(image);
    }

    const editable = Boolean(data.can_edit);
    sharedNote.hidden = editable;
    formsBox.hidden = !editable;
    photoActions.hidden = !editable;
    photoRemove.hidden = !data.avatar;
    if (editable) {
      aliasInput.value = data.apelido || "";
      aliasInput.maxLength = data.limits.apelido_max;
      aliasHelp.textContent = "Até " + data.limits.apelido_max + " caracteres. Deixe vazio para remover.";
      passwordHelp.textContent = "Entre " + data.limits.senha_min + " e " + data.limits.senha_max + " caracteres.";
    }
  }

  async function load() {
    try {
      const data = await api("/api/perfil");
      render(data.perfil);
    } catch (error) {
      roleNode.textContent = "Não foi possível carregar o perfil.";
    }
  }

  /* ---------- foto ---------- */
  photoPick.addEventListener("click", () => photoInput.click());

  photoInput.addEventListener("change", async () => {
    const file = photoInput.files && photoInput.files[0];
    photoInput.value = "";
    if (!file) return;
    const maxMb = profile ? profile.limits.foto_max_mb : 10;
    if (file.size > maxMb * 1024 * 1024) {
      say(photoStatus, "A foto ultrapassa o limite de " + maxMb + " MB.", "error");
      return;
    }
    const body = new FormData();
    body.append("photo", file);
    photoPick.disabled = true;
    say(photoStatus, "Enviando foto...", "");
    try {
      const data = await api("/api/perfil/foto", { method: "POST", body });
      render(data.perfil);
      say(photoStatus, data.message, "ok");
    } catch (error) {
      say(photoStatus, error.message, "error");
    } finally {
      photoPick.disabled = false;
    }
  });

  photoRemove.addEventListener("click", async () => {
    photoRemove.disabled = true;
    try {
      const data = await api("/api/perfil/foto", { method: "DELETE" });
      render(data.perfil);
      say(photoStatus, data.message, "ok");
    } catch (error) {
      say(photoStatus, error.message, "error");
    } finally {
      photoRemove.disabled = false;
    }
  });

  /* ---------- apelido ---------- */
  aliasForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    say(aliasStatus, "Salvando...", "");
    try {
      const data = await api("/api/perfil", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ apelido: aliasInput.value.trim() }),
      });
      render(data.perfil);
      say(aliasStatus, data.message, "ok");
    } catch (error) {
      say(aliasStatus, error.message, "error");
    }
  });

  /* ---------- senha ---------- */
  passwordForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(passwordForm);
    const atual = String(form.get("atual") || "");
    const nova = String(form.get("nova") || "");
    const confirmar = String(form.get("confirmar") || "");

    if (nova !== confirmar) {
      say(passwordStatus, "A confirmação não confere com a nova senha.", "error");
      return;
    }
    say(passwordStatus, "Alterando senha...", "");
    try {
      const data = await api("/api/perfil/senha", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ atual, nova, confirmar }),
      });
      passwordForm.reset();
      say(passwordStatus, data.message, "ok");
    } catch (error) {
      say(passwordStatus, error.message, "error");
    }
  });

  /* ---------- sair de todos os aparelhos ---------- */
  signOutButton.addEventListener("click", async () => {
    if (!window.confirm("Sair de todos os aparelhos, inclusive deste? Você precisará entrar de novo.")) return;
    signOutButton.disabled = true;
    say(signOutStatus, "Saindo...", "");
    try {
      const data = await api("/api/perfil/sair-todos", { method: "POST" });
      window.location.assign(data.redirect || "/login");
    } catch (error) {
      signOutButton.disabled = false;
      say(signOutStatus, error.message, "error");
    }
  });

  load();
})();
