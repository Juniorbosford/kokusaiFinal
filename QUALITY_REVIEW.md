# Revisão de qualidade - Kokusai

Esta versão recebeu uma limpeza conservadora para reduzir repetição sem alterar o comportamento do site.

## Ajustes feitos

- Centralizados os cabeçalhos das abas do Google Sheets em constantes.
- Criados helpers para normalizar linhas, gerar IDs, limitar listas e calcular resumos financeiros.
- Reduzida repetição nos endpoints de listagem e resumo de compras/vendas/encomendas.
- Removida uma leitura duplicada da aba de metas ao adicionar novo nome.
- Mantida a proteção de login, CSRF, modo leitura e cache de planilha.
- Reduzidos logs sensíveis/desnecessários da autenticação com Google Sheets.
- Corrigido `.replit`, que ainda apontava para `app.py`.
- Removidos arquivos gerados automaticamente (`__pycache__`/`.pyc`) do pacote.

## O que não foi alterado

- Rotas públicas e endpoints da API.
- Estrutura visual do painel.
- Nomes das abas do Google Sheets.
- Regras de permissão dos usuários.
- Fluxo semanal da aba Metas.
- Sistema de Craft no navegador.

## Validação feita

- `python -m py_compile main.py`
- validação sintática dos templates Jinja
- `node --check static/js/app.js`
- checagem do pacote para não incluir `service_account.json`
