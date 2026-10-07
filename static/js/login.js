/* Tela de login estilo "quem está entrando?": contas abertas (troca sem senha) e contas salvas (pedem senha). */
(function () {
  "use strict";

  const Accounts = window.KokusaiAccounts;
  if (!Accounts) return;
  const { el } = Accounts;

  const body = document.body;
  const grid = document.getElementById("accountGrid");
  const form = document.getElementById("loginForm");
  if (!grid || !form) return;

  const usernameField = document.getElementById("usernameField");
  const usernameInput = document.getElementById("username");
  const passwordInput = document.getElementById("password");
  const rememberInput = document.getElementById("rememberAccount");
  const head = document.getElementById("accountLoginHead");
  const headAvatar = document.getElementById("loginHeadAvatar");
  const headName = document.getElementById("loginHeadName");
  const headUser = document.getElementById("loginHeadUser");
  const backButton = document.getElementById("loginBackBtn");
  const forgetBox = document.getElementById("accountForget");
  const forgetAllButton = document.getElementById("forgetAllBtn");
  const title = document.getElementById("loginTitle");
  const subtitle = document.getElementById("loginSubtitle");

  const TEXT = {
    pick: ["Quem está entrando?", "Escolha uma conta para continuar."],
    saved: ["Bem-vindo de volta", "Digite a senha para entrar nesta conta."],
    other: ["Entrar com outra conta", "Digite o usuário e a senha."],
    plain: ["Acesso restrito", "Entre para consultar ou administrar o painel."],
  };

  function readOpenAccounts() {
    try {
      const raw = JSON.parse(document.getElementById("openAccountsData")?.textContent || "[]");
      return Array.isArray(raw) ? raw : [];
    } catch (error) {
      return [];
    }
  }

  function setTitle(key) {
    const [heading, text] = TEXT[key];
    title.textContent = heading;
    subtitle.textContent = text;
  }

  function showPicker() {
    body.classList.remove("is-entering");
    form.classList.remove("is-visible");
    passwordInput.value = "";
    setTitle("pick");
  }

  function showForm(account) {
    body.classList.add("is-entering");
    form.classList.add("is-visible");
    passwordInput.value = "";
    if (account) {
      usernameInput.value = account.username;
      usernameField.hidden = true;
      head.hidden = false;
      Accounts.fillAvatar(headAvatar, account);
      headName.textContent = Accounts.labelOf(account);
      headUser.textContent = "@" + account.username;
      setTitle("saved");
      passwordInput.focus();
    } else {
      usernameField.hidden = false;
      head.hidden = true;
      setTitle("other");
      (usernameInput.value ? passwordInput : usernameInput).focus();
    }
  }

  function tileBody(tile, account, statusText) {
    tile.appendChild(Accounts.avatarNode(account));
    tile.appendChild(el("strong", "", Accounts.labelOf(account)));
    tile.appendChild(el("small", "", statusText));
  }

  function buildGrid(openAccounts, savedAccounts) {
    grid.textContent = "";

    openAccounts.forEach((account) => {
      const wrap = el("div", "account-tile-wrap");
      const switchForm = Accounts.postForm("/conta/trocar", { username: account.username });
      switchForm.className = "";
      const button = el("button", "account-tile is-open");
      button.type = "submit";
      button.appendChild(el("span", "account-badge", "Conectada"));
      tileBody(button, account, "@" + account.username);
      switchForm.appendChild(button);
      wrap.appendChild(switchForm);
      grid.appendChild(wrap);
    });

    savedAccounts.forEach((account) => {
      const wrap = el("div", "account-tile-wrap");
      const button = el("button", "account-tile");
      button.type = "button";
      button.dataset.username = account.username;
      tileBody(button, account, "@" + account.username);
      button.addEventListener("click", () => showForm(account));
      wrap.appendChild(button);

      const remove = el("button", "account-tile-remove", "×");
      remove.type = "button";
      remove.title = "Esquecer esta conta neste aparelho";
      remove.setAttribute("aria-label", "Esquecer " + Accounts.labelOf(account));
      remove.addEventListener("click", () => {
        Accounts.forgetAccount(account.username);
        init();
      });
      wrap.appendChild(remove);
      grid.appendChild(wrap);
    });

    const other = el("div", "account-tile-wrap");
    const otherButton = el("button", "account-tile");
    otherButton.type = "button";
    otherButton.id = "otherAccountBtn";
    otherButton.appendChild(el("span", "account-avatar account-avatar-plus", "+"));
    otherButton.appendChild(el("strong", "", "Outra conta"));
    otherButton.appendChild(el("small", "", "Digitar usuário"));
    otherButton.addEventListener("click", () => {
      usernameInput.value = "";
      showForm(null);
    });
    other.appendChild(otherButton);
    grid.appendChild(other);
  }

  function init() {
    const open = readOpenAccounts().map((item) => ({
      username: String(item.username || "").toLowerCase(),
      display_name: item.display_name,
      apelido: item.apelido,
      role: item.role === "admin" ? "admin" : "member",
      thumb: item.thumb,
    }));
    const openNames = new Set(open.map((item) => item.username));
    const saved = Accounts.readSaved().filter((item) => !openNames.has(item.username));

    if (!open.length && !saved.length) {
      // Primeiro acesso neste aparelho: só o formulário normal, com o campo de usuário.
      body.classList.remove("js-picker");
      usernameField.hidden = false;
      head.hidden = true;
      setTitle("plain");
      forgetBox.hidden = true;
      return { open, saved };
    }

    body.classList.add("js-picker");
    buildGrid(open, saved);
    forgetBox.hidden = saved.length === 0;
    showPicker();
    return { open, saved };
  }

  const state = init();

  // Depois de errar a senha a página recarrega: reabre direto a conta que estava sendo usada.
  const selected = (form.dataset.selected || "").trim().toLowerCase();
  if (selected && body.classList.contains("js-picker")) {
    const match = state.saved.find((item) => item.username === selected) || state.open.find((item) => item.username === selected);
    if (match && !state.open.includes(match)) {
      showForm(match);
    } else {
      usernameInput.value = selected;
      showForm(null);
    }
  } else if (selected) {
    usernameInput.value = selected;
  }

  backButton.addEventListener("click", showPicker);

  forgetAllButton.addEventListener("click", () => {
    Accounts.forgetAll();
    init();
  });

  form.addEventListener("submit", () => {
    const username = usernameInput.value.trim().toLowerCase();
    Accounts.setPending(rememberInput.checked ? username : "");
  });
})();
