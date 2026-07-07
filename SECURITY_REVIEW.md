# Revisão de segurança - Kokusai

## Pontos corrigidos nesta versão

- Adicionado token CSRF nas ações que alteram dados (`POST`/`DELETE`).
- Adicionado limite básico de tentativas de login para reduzir força bruta.
- Adicionados cabeçalhos de segurança: CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy e Permissions-Policy.
- Reduzido vazamento de informações em erros 500 exibidos no navegador.
- Simplificada a rota `/health` para não expor nomes de abas/configurações internas.
- Rota `/api/debug-config` agora fica desativada por padrão; só funciona com `ENABLE_DEBUG_CONFIG=true`.
- Limitado tamanho do corpo da requisição e tamanho de textos enviados pelo usuário.
- Adicionada proteção contra formula injection no Google Sheets.
- Escritas principais na planilha agora usam `RAW` quando possível.
- O escopo do Google Drive só é usado quando o app precisa abrir/criar planilha por nome. Em produção, prefira `SPREADSHEET_ID` para usar apenas o escopo do Sheets.

## Variáveis recomendadas no Railway

Configure no Railway:

```txt
SECRET_KEY=uma_chave_grande_e_aleatoria
SESSION_COOKIE_SECURE=true
SPREADSHEET_ID=id_da_sua_planilha
GOOGLE_CREDENTIALS_JSON={...json completo da service account...}
KOKUSAI_PASSWORD_HASH=hash_gerado
NEKUTAI_PASSWORD_HASH=hash_gerado
```

Para gerar uma chave forte de sessão no Windows:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Para gerar hash de senha:

```bash
python scripts/generate_password_hash.py
```

## Ação urgente

A chave `GOOGLE_CREDENTIALS_JSON`/`service_account.json` apareceu em print durante a configuração. Gere uma nova chave no Google Cloud, troque no Railway e apague a chave antiga.

Também confirme antes de dar commit:

```bash
git status
git rm --cached service_account.json
```

O `.gitignore` já ignora `service_account.json`, mas se o arquivo já tiver sido adicionado ao Git antes, precisa remover do índice com `git rm --cached`.
