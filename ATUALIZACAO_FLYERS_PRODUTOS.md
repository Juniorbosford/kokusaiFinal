# Atualização — flyers, preços e itens separados

## Flyers e organizações

- Qualquer usuário autenticado pode enviar um flyer em PNG, JPG/JPEG ou WEBP.
- Upload feito pela conta **Kokusai** é publicado imediatamente.
- Upload feito por outro usuário entra como **aguardando aprovação**.
- Somente a conta Kokusai pode:
  - colocar/publicar um flyer;
  - retirar/ocultar um flyer;
  - excluir um flyer enviado;
  - editar as descrições comerciais de cada organização.
- Cada organização possui duas descrições independentes:
  - **Preço da Kokusai para a organização**;
  - **Preço da organização para a Kokusai**.

### Persistência no Railway

Os uploads e as descrições ficam no diretório configurado em `KOKUSAI_DATA_DIR`.
Para não perder os arquivos em um novo deploy, monte um **Railway Volume** e configure, por exemplo:

```txt
KOKUSAI_DATA_DIR=/data/kokusai
```

Sem Volume, a funcionalidade funciona, mas os uploads podem desaparecer após um redeploy do container.

## Vendas e encomendas

- L85 e Seringa agora possuem campos distintos de:
  - quantidade;
  - valor unitário.
- Os dois produtos podem ser usados no mesmo registro.
- O sistema soma automaticamente:
  - quantidade total;
  - valor total dos dois produtos.
- Venda ainda aceita um terceiro produto opcional.
- Encomenda ainda aceita uma descrição adicional opcional.
- As abas `Vendas` e `Encomendas` recebem automaticamente as colunas:
  - `quantidade_l85`;
  - `valor_unitario_l85`;
  - `quantidade_seringa`;
  - `valor_unitario_seringa`.

## Entrega em dinheiro limpo ou sujo

- O botão **Confirmar entrega** mostra os valores limpo e sujo.
- Dinheiro sujo acrescenta 30% automaticamente.
- A edição da encomenda agora também permite:
  - salvar e manter pendente;
  - salvar, escolher limpo/sujo e mover diretamente para Vendas.
