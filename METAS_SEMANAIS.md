# Pagamento de metas semanal

A aba **Metas** agora trabalha por semana.

## Como funciona

- A semana de metas começa na quarta-feira.
- Cada nome precisa receber um clique em **SIM** ou **NÃO**.
- Quando todos os nomes forem marcados, o sistema salva a semana na aba **Historico Metas** e abre automaticamente a próxima semana zerada.
- Ao virar quarta-feira, se a semana anterior ainda estiver aberta, o sistema salva o histórico e reseta a lista no próximo carregamento.
- O botão **Fechar semana agora** permite salvar e resetar manualmente.

## Abas usadas no Google Sheets

- `Pagamento de Metas`: semana atual.
- `Historico Metas`: histórico das semanas fechadas.

## Variáveis opcionais

```txt
METAS_WORKSHEET_NAME=Pagamento de Metas
HISTORICO_METAS_WORKSHEET_NAME=Historico Metas
APP_TIMEZONE=America/Sao_Paulo
META_RESET_WEEKDAY=2
```

`META_RESET_WEEKDAY=2` significa quarta-feira. Segunda é `0`, terça é `1`, quarta é `2`.
