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
