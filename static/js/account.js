/* Contas do aparelho: lista de contas salvas (somente neste navegador), avatar e atalhos de conta.
 * Nenhuma senha ou token é guardado aqui: só usuário, nome, apelido e a miniatura da foto.
 * Carregado nas telas de login, painel, sala de metas e perfil. */
(function () {
  "use strict";

  const STORE_KEY = "kokusai.savedAccounts.v1";
  const PENDING_KEY = "kokusai.rememberPending.v1";
  const MAX_SAVED = 6;
  const THUMB_PREFIX = "data:image/webp;base64,";
  // O ícone da aba é o próprio logo da Kokusai; assim a tela não depende de caminho fixo.
  const logoUrl = () => document.querySelector('link[rel="icon"]')?.href || "";

  const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || "";

  /* ---------- conta da aba ----------
   * Cada página sabe em qual conta foi aberta. Todo pedido ao servidor leva essa conta,
   * então trocar de conta em outra aba não faz esta aba agir com a conta errada
   * (ex.: enviar a meta do Gohan enquanto outra aba está na conta Kokusai). */
  const TAB_ACCOUNT_HEADER = "X-Kokusai-Conta";
  const tabAccount = document.querySelector('meta[name="kokusai-account"]')?.content?.trim() || "";

  function withTabAccount(headers) {
    if (headers && typeof Headers !== "undefined" && headers instanceof Headers) {
      if (!headers.has(TAB_ACCOUNT_HEADER)) headers.set(TAB_ACCOUNT_HEADER, tabAccount);
      return headers;
    }
    if (Array.isArray(headers)) {
      return headers.some(([name]) => String(name).toLowerCase() === TAB_ACCOUNT_HEADER.toLowerCase())
        ? headers
        : headers.concat([[TAB_ACCOUNT_HEADER, tabAccount]]);
    }
    return Object.assign({ [TAB_ACCOUNT_HEADER]: tabAccount }, headers || {});
  }

  if (tabAccount && typeof window.fetch === "function") {
    const originalFetch = window.fetch;
    window.fetch = function kokusaiFetch(input, init) {
      try {
        const rawUrl = typeof input === "string" || input instanceof URL ? String(input) : input.url;
        if (new URL(rawUrl, window.location.href).origin === window.location.origin) {
          init = Object.assign({}, init || {});
          init.headers = withTabAccount(init.headers);
        }
      } catch (error) {
        /* URL estranha: segue sem o cabeçalho */
      }
      return originalFetch.call(window, input, init);
    };
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  /* ---------- armazenamento local ---------- */
  function normalize(account) {
    if (!account || typeof account.username !== "string") return null;
    const username = account.username.trim().toLowerCase();
    if (!username || username.length > 64) return null;
    const thumb = typeof account.thumb === "string" && account.thumb.startsWith(THUMB_PREFIX) ? account.thumb : "";
    return {
      username,
      display_name: String(account.display_name || username).slice(0, 80),
      apelido: String(account.apelido || "").slice(0, 40),
      role: account.role === "admin" ? "admin" : "member",
      thumb,
    };
  }

  function readSaved() {
    try {
      const raw = JSON.parse(localStorage.getItem(STORE_KEY) || "[]");
      if (!Array.isArray(raw)) return [];
      const seen = new Set();
      const list = [];
      raw.forEach((item) => {
        const account = normalize(item);
        if (account && !seen.has(account.username)) {
          seen.add(account.username);
          list.push(account);
        }
      });
      return list.slice(0, MAX_SAVED);
    } catch (error) {
      return [];
    }
  }

  function writeSaved(list) {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(list.slice(0, MAX_SAVED)));
    } catch (error) {
      /* navegador sem armazenamento: o site funciona igual, só não lembra a conta */
    }
  }

  function saveAccount(account) {
    const clean = normalize(account);
    if (!clean) return;
    const list = readSaved().filter((item) => item.username !== clean.username);
    list.unshift(clean);
    writeSaved(list);
  }

  function refreshSaved(account) {
    const clean = normalize(account);
    if (!clean) return;
    const list = readSaved();
    const index = list.findIndex((item) => item.username === clean.username);
    if (index < 0) return;
    list[index] = clean;
    writeSaved(list);
  }

  function forgetAccount(username) {
    writeSaved(readSaved().filter((item) => item.username !== String(username || "").toLowerCase()));
  }

  function forgetAll() {
    try {
      localStorage.removeItem(STORE_KEY);
    } catch (error) {
      /* ignora */
    }
  }

  function setPending(username) {
    try {
      if (username) sessionStorage.setItem(PENDING_KEY, String(username).toLowerCase());
      else sessionStorage.removeItem(PENDING_KEY);
    } catch (error) {
      /* ignora */
    }
  }

  function takePending() {
    try {
      const value = sessionStorage.getItem(PENDING_KEY) || "";
      sessionStorage.removeItem(PENDING_KEY);
      return value;
    } catch (error) {
      return "";
    }
  }

  /* ---------- apresentação ---------- */
  function labelOf(account) {
    return account.apelido || account.display_name || account.username;
  }

  function initialsOf(account) {
    const text = labelOf(account).trim();
    return (text ? text.charAt(0) : "?").toUpperCase();
  }

  function fillAvatar(node, account) {
    node.textContent = "";
    node.classList.toggle("account-avatar-logo", account.role === "admin");
    if (account.role === "admin") {
      const source = logoUrl();
      if (source) {
        const logo = el("img");
        logo.src = source;
        logo.alt = "";
        node.appendChild(logo);
      } else {
        node.textContent = initialsOf(account);
      }
      return node;
    }
    if (account.thumb && account.thumb.startsWith(THUMB_PREFIX)) {
      const photo = el("img");
      photo.src = account.thumb;
      photo.alt = "";
      node.appendChild(photo);
      return node;
    }
    node.textContent = initialsOf(account);
    return node;
  }

  function avatarNode(account, sizeClass) {
    const node = el("span", "account-avatar" + (sizeClass ? " " + sizeClass : ""));
    node.setAttribute("aria-hidden", "true");
    return fillAvatar(node, account);
  }

  function postForm(action, fields) {
    const form = el("form");
    form.method = "post";
    form.action = action;
    form.className = "account-inline-form";
    Object.entries(Object.assign({ csrf_token: csrfToken() }, fields || {})).forEach(([name, value]) => {
      const input = el("input");
      input.type = "hidden";
      input.name = name;
      input.value = value;
      form.appendChild(input);
    });
    return form;
  }

  /* ---------- atalhos de conta no painel ---------- */
  function renderLinks(container, data) {
    container.textContent = "";
    const profile = el("a", "account-link", "Meu perfil");
    profile.href = "/perfil";
    container.appendChild(profile);

    (data.others || []).forEach((other) => {
      const form = postForm("/conta/trocar", { username: other.username });
      const button = el("button", "account-link", "Entrar como " + labelOf(other));
      button.type = "submit";
      form.appendChild(button);
      container.appendChild(form);
    });

    const switcher = el("a", "account-link", "Trocar ou adicionar conta");
    switcher.href = "/login?trocar=1";
    container.appendChild(switcher);
  }

  async function initPanels() {
    const links = document.querySelectorAll("[data-account-links]");
    const avatars = document.querySelectorAll("[data-account-avatar]");
    const profileLinks = document.querySelectorAll("[data-profile-link]");
    if (!links.length && !avatars.length && !profileLinks.length) return;

    let data;
    try {
      const response = await fetch("/api/auth/accounts", {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) return;
      data = await response.json();
    } catch (error) {
      return;
    }
    if (!data || !data.ok || !data.active) return;

    const active = normalize(data.active);
    if (active) {
      const pending = takePending();
      if (pending && pending === active.username) saveAccount(active);
      else refreshSaved(active);
      (data.others || []).forEach(refreshSaved);
    }

    if (active) avatars.forEach((node) => fillAvatar(node, active));
    profileLinks.forEach((node) => {
      node.hidden = false;
      if (active) node.setAttribute("aria-label", "Meu perfil (" + labelOf(active) + ")");
    });
    links.forEach((node) => renderLinks(node, data));
  }

  window.KokusaiAccounts = {
    readSaved,
    saveAccount,
    forgetAccount,
    forgetAll,
    setPending,
    labelOf,
    fillAvatar,
    avatarNode,
    postForm,
    el,
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initPanels);
  else initPanels();
})();
