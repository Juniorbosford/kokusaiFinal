# Revisão de qualidade - Kokusai

## Ajustes desta versão

- Removida a limitação de largura do conteúdo principal.
- Formulários e históricos passam a ocupar toda a largura disponível.
- Todas as tabelas ficam responsivas e viram cartões em telas menores, sem rolagem horizontal.
- A tabela de encomendas foi simplificada para exibir apenas os dados necessários e a ação de confirmar entrega.
- Ao confirmar uma entrega, a encomenda é convertida em venda e removida da aba de encomendas.
- Encomendas cadastradas como já entregues vão diretamente para vendas.
- A conversão reconhece quantidade em textos como `15 L85` e `15x L85`.
- O fluxo é idempotente: uma repetição após falha parcial não duplica a venda.
- IDs novos receberam milissegundos e sufixo aleatório para reduzir colisões.

## Mapeamento da encomenda para venda

- `O que pediu` → produto; quando começa com quantidade, ela é separada automaticamente.
- `Quem pediu` → quem compra.
- `Quem negociou` → quem vende.
- `Valor` → valor total; o valor unitário é calculado pela quantidade.
- O prazo e o ID original são preservados na observação da venda.

## Validação executada

- `python -m py_compile main.py`
- `node --check static/js/app.js`
- renderização do template Flask
- testes do fluxo de conversão com planilhas simuladas
- teste do fluxo no frontend com navegador headless
- verificação em larguras de 1440 px, 600 px e 390 px sem overflow horizontal

## Itens preservados

- Login, perfis administrador/leitor e proteção CSRF.
- Cache e integração com Google Sheets.
- Compras, vendas manuais, metas e craft.
- Nomes das abas e cabeçalhos atuais da planilha.
