# Flyers e organizações

A aba **Flyers** usa um cadastro central em `main.py`, na constante `ORGANIZACOES`.

## Como funciona

- Cada organização possui um `id`, nome, ícone, aliases e uma lista de flyers.
- As imagens ficam em `static/images/flyers/`.
- A API `/api/organizacoes` entrega os dados para a interface.
- A aba **Reuniões** salva também o campo `organizacao_id` na planilha `Reunioes`.
- Reuniões antigas são associadas automaticamente pelo nome da organização, mesmo antes de serem editadas.
- Hydra possui dois flyers e o visualizador permite avançar entre eles.

## Adicionar um novo flyer

1. Coloque a imagem otimizada em `static/images/flyers/`.
2. Abra `main.py` e encontre `ORGANIZACOES`.
3. Adicione o arquivo na lista `flyers` da organização correspondente.
4. Para uma organização nova, crie um novo item com `id`, `nome`, `icone`, `aliases` e `flyers`.

Organizações já existentes na agenda, mas sem imagem, aparecem como **Flyer pendente**.
