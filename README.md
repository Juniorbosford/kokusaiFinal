# Kokusai System - pacote corrigido

## Estrutura correta
- main.py
- requirements.txt
- templates/index.html
- static/css/style.css
- static/js/app.js
- static/images/kokusai-logo.webp

## Como rodar localmente
```bash
pip install -r requirements.txt
python main.py
```

## Como publicar
- não envie `service_account.json` para o GitHub
- use `GOOGLE_CREDENTIALS_JSON` no Render


## Debug
- A rota `/api/debug-config` mostra se as variáveis do Google Sheets foram lidas.
- Os erros agora aparecem melhor no front e nos logs do Railway.

## Autenticação adicionada

Esta versão inclui login com dois perfis:

- `kokusai`: administrador com acesso total.
- `nekutai`: leitor com acesso somente para visualização.

As senhas são validadas por hash PBKDF2-SHA256. Consulte `LOGIN_RAILWAY.md` para configurar `SECRET_KEY`, cookies seguros no Railway e troca de senha.

## Sistema de craft

A aba **Craft** foi adicionada abaixo de **Encomendas**.

Ela calcula automaticamente os materiais necessários para:

- L85
- Peça de arma pesada
- Corpo de rifle
- Seringa de crack
- Maçarico
- Rastreador ilegal

O cálculo é feito no navegador e não salva nada na planilha. O usuário `kokusai` pode preencher as quantidades e o campo **Tenho** para ver quanto falta. O usuário `nekutai` visualiza apenas as receitas em modo somente leitura.

## Pagamento de metas

A aba **Metas** foi adicionada abaixo de **Encomendas**.

Ela usa a aba `Pagamento de Metas` no Google Sheets e mantém apenas:

- nome da pessoa;
- status de pagamento: `Sim` ou `Não`;
- data da última atualização.

A lista inicial foi transcrita da planilha **NKT - CONTROLE DE META FINANCEIRA.xlsx**, aba `Meta Semanal Padrao`. O usuário `kokusai` pode alterar o status, adicionar nomes e apagar nomes. O usuário `nekutai` apenas visualiza.

Variável opcional no Railway:

```txt
METAS_WORKSHEET_NAME=Pagamento de Metas
```
