# Atualização — entregas e justificativas de compras

## Encomendas

- Ao confirmar uma entrega, o sistema abre uma janela com duas opções:
  - **Dinheiro limpo:** mantém o valor original.
  - **Dinheiro sujo:** acrescenta automaticamente **30%**.
- O valor escolhido é mostrado antes da confirmação.
- A venda criada registra o tipo de dinheiro, o valor base e o valor final.
- Também foi adicionado o botão **Editar** nas encomendas pendentes.
- Ao cadastrar uma encomenda como já entregue, o formulário também exige a escolha entre limpo e sujo.

## Compras

- O histórico agora mostra um botão **Ver justificativa** quando a compra possui observação.
- Ao clicar, a justificativa abre logo abaixo do pedido, sem precisar arrastar a tabela para o lado.

## Google Sheets

A aba `Vendas` recebe automaticamente duas colunas novas ao abrir o sistema:

- `tipo_dinheiro`
- `valor_base`

Os registros antigos continuam funcionando e aparecem como pagamento não informado.
