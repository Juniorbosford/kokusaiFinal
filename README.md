# Kokusai

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
- use `GOOGLE_CREDENTIALS_JSON` no Railway


## Debug
- A rota `/api/debug-config` fica bloqueada por padrão. Ative somente temporariamente com `ENABLE_DEBUG_CONFIG=true`.
- Erros internos aparecem de forma resumida no navegador e detalhados apenas nos logs do Railway/terminal.

## Autenticação adicionada

Esta versão inclui dois níveis de acesso:

- `kokusai`: administrador com acesso total.
- `member`: contas individuais das Salas de Meta; cada pessoa vê apenas a própria sala e não acessa o painel operacional.

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

O cálculo é feito no navegador e não salva nada na planilha. O usuário `kokusai` pode preencher as quantidades e o campo **Tenho** para ver quanto falta.

## Pagamento de metas

A antiga lista de metas foi transformada em **Salas de Meta** semanais e privadas.

- Cada membro possui usuário e senha próprios e é redirecionado para `/minha-meta`.
- O membro vê somente a própria sala, envia fotos da semana e consulta seu histórico.
- O envio aceita JPG/JPEG, PNG e WEBP, inclusive fotos cujo navegador não informa o tipo MIME corretamente; basta clicar ou arrastar as imagens para a área de upload.
- O administrador vê todas as salas, abre os comprovantes e marca cada pessoa como `Pago` ou `Não pago`.
- A sala abre na sexta-feira, recebe comprovantes até quarta às 23:59 e fica disponível para conferência na quinta-feira.
- Ao finalizar a conferência, o resultado é bloqueado, fica salvo no PostgreSQL e um log TXT é baixado automaticamente no computador do admin.
- Na sexta-feira, a nova semana é criada automaticamente sem apagar o histórico anterior.
- Dados de usuários/status ficam no PostgreSQL e as imagens ficam em Bucket privado no Railway.
- Em desenvolvimento local, o módulo usa SQLite e `data/meta_uploads` automaticamente.

Consulte `RAILWAY_METAS.md` para configurar PostgreSQL e Bucket no Railway. As credenciais iniciais dos membros ficam em `CREDENCIAIS_METAS.txt`, arquivo ignorado pelo Git.

## Fluxo de encomendas e vendas

- Encomendas pendentes permanecem na aba **Encomendas**.
- Ao clicar em **Confirmar entrega**, o registro é criado na aba **Vendas** e removido de **Encomendas**.
- Uma encomenda cadastrada inicialmente como já entregue é registrada diretamente em **Vendas**.
- Pedidos escritos como `15 L85` ou `15x L85` são convertidos para produto `L85` e quantidade `15`. Sem quantidade explícita, o sistema usa quantidade `1`.
- A conversão usa um ID estável para evitar venda duplicada caso a exclusão da encomenda precise ser tentada novamente.
- O vínculo com a família é preservado quando a encomenda vira venda, inclusive em pedidos combinados com mais de um produto.

## Relatório mensal por gangue

- A aba **Relatórios** permite selecionar um mês e gera o ranking das famílias que mais compraram.
- Vendas diretas podem ser vinculadas a uma família cadastrada; compradores avulsos continuam permitidos.
- O ranking soma somente vendas concluídas e mostra total gasto, quantidade de compras, encomendas entregues, encomendas pendentes, valor ainda pendente e itens comprados.
- Uma encomenda com L85 e Seringa conta como uma única compra, embora os valores dos dois produtos sejam somados normalmente.
- Vendas sem família ficam fora do ranking e aparecem em um indicador separado para facilitar a correção dos próximos registros.
- O relatório exibido pode ser baixado como arquivo TXT pelo navegador.
- Registros antigos também entram no ranking quando o nome do comprador corresponde exatamente a uma família cadastrada.

## Dinheiro limpo e dinheiro sujo

- Compras, vendas e encomendas possuem a opção **Tipo de dinheiro**.
- **Dinheiro limpo** mantém o valor calculado normalmente.
- **Dinheiro sujo** acrescenta automaticamente **30%** sobre o valor base.
- A prévia mostra o valor base, o acréscimo e o total antes de salvar.
- A planilha guarda separadamente `tipo_dinheiro`, `valor_base` e `acrescimo_dinheiro_sujo`, enquanto `valor_total`/`valor` recebe o valor final.
- Quando uma encomenda em dinheiro sujo é entregue, os 30% são preservados ao converter os produtos em vendas.
- O histórico identifica visualmente o tipo de dinheiro usado em cada movimentação.

## Layout responsivo

Os formulários e históricos agora usam toda a largura disponível. Em telas menores, as linhas das tabelas viram cartões, evitando barras de rolagem horizontal nas abas Compras, Vendas, Encomendas, Relatórios, Metas e Craft.


## Segurança

Consulte `SECURITY_REVIEW.md` antes de publicar alterações no GitHub/Railway.

## Famílias e gangues

- A antiga área de **Flyers** foi reorganizada como **Famílias**.
- O cadastro permite informar nome, ícone, mercado aberto/fechado, preço de venda para a família, preço de compra da família, observações e um link opcional para a imagem do flyer.
- **Aura** e **Cartel** são incluídos automaticamente. Registros antigos chamados **Bandoleros** são exibidos e migrados como **Cartel**.
- Ao finalizar uma reunião, a gangue/família é incluída automaticamente na aba **Famílias**, sem duplicar cadastros.
- Caso exista uma aba antiga chamada `Flyers` na planilha, o sistema tenta importar os cadastros reconhecendo os cabeçalhos mais comuns.

## Cancelamento de encomendas

- Encomendas pendentes agora possuem o botão **Cancelar**.
- Ao confirmar o cancelamento, o registro é apagado imediatamente da aba `Encomendas` e não é enviado para `Vendas`.

## Pedidos combinados e gestão de famílias

- Uma única encomenda pode conter **L85** e **Seringa**, cada uma com quantidade e valor unitário próprios. O total é calculado pela soma dos dois produtos.
- Encomendas pendentes podem ser **editadas por completo** no mesmo formulário: cliente, produtos, quantidades, valores, prazo, negociador, status e observação.
- Toda encomenda nova ou editada fica vinculada a uma família cadastrada por ID e exibe o **emoji + nome da gangue** no histórico.
- Ao confirmar a entrega de um pedido combinado, cada produto é registrado corretamente na aba `Vendas`.
- Compras possuem **Justificativa (opcional)** e o texto aparece no histórico.
- Famílias possuem até **dois contatos**, mascarados por padrão, e até **dois flyers** exibidos lado a lado.
- O campo de venda para a família é exibido como **Nosso valor para esta família**, permitindo manter tabelas especiais como Aura e Distrito.
- Flyers podem ser substituídos por URL, ocultados e removidos pela própria aba de Famílias.
