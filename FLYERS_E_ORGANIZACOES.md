# Flyers e organizações

A aba **Flyers** combina os flyers originais do projeto com imagens enviadas pelo próprio painel.

## Permissões

- Qualquer usuário autenticado pode enviar um flyer em PNG, JPG/JPEG ou WEBP.
- A conta **Kokusai** publica o próprio upload imediatamente.
- Uploads de outros usuários ficam aguardando aprovação.
- Somente a conta **Kokusai** pode:
  - publicar ou retirar um flyer;
  - excluir um flyer enviado;
  - editar as descrições de preço de cada organização.

## Descrições comerciais

Cada organização possui dois campos independentes:

1. **Preço da Kokusai para a organização** — quanto eles pagam ao comprar da Kokusai.
2. **Preço da organização para a Kokusai** — quanto a Kokusai paga ao comprar deles.

## Onde os dados ficam

- Os flyers originais continuam em `static/images/flyers/` e no cadastro `ORGANIZACOES` de `main.py`.
- Os novos uploads ficam em `KOKUSAI_DATA_DIR/flyers/`.
- Preços, aprovação e visibilidade ficam em `KOKUSAI_DATA_DIR/flyers_metadata.json`.

No Railway, monte um Volume e configure, por exemplo:

```txt
KOKUSAI_DATA_DIR=/data/kokusai
```

Sem um Volume, uploads e descrições podem ser perdidos quando o container for recriado.

## Cadastro de uma organização nova

Para incluir uma organização que ainda não aparece no painel, adicione um item à constante `ORGANIZACOES` em `main.py`, informando `id`, `nome`, `icone`, `aliases` e uma lista `flyers` — que pode começar vazia.
