# KOKUSAI — Revisão de segurança 2026.10.24

Identificador: `2026.10.24-seguranca`

Nenhuma tela ou funcionalidade muda. Esta versão corrige:

- **Imagens gigantes derrubavam o servidor:** um PNG de poucos KB pode declarar 12000x12000 pixels e ocupar centenas de MB ao abrir. Agora fotos de meta, do baú, de perfil e flyers com mais de 50 milhões de pixels são recusadas (`META_IMAGE_MAX_PIXELS`), e fotos JPG de celular são decodificadas já reduzidas.
- **Redirecionamento externo no login:** `/login?next=/\site.com` levava para outro site depois do login. Endereços com barra invertida ou caracteres de controle passam a voltar para a página inicial.
- **Teste de senha em vários usuários:** o limite de tentativas era por IP+usuário, então um IP podia testar uma senha em todos os usuários. Agora também há um limite de 30 falhas por IP a cada 15 minutos (`LOGIN_MAX_ATTEMPTS_PER_IP`).
- **Descobrir quais usuários existem:** usuário inexistente respondia na hora e o existente demorava (cálculo do hash). Agora os dois levam o mesmo tempo.
- **Valores NaN/Infinity:** compras, vendas e encomendas recusam esses valores em vez de gravá-los na planilha.

Depois do deploy, abra `/health` e confirme `"version": "2026.10.24-seguranca"`.

---

# Versão anterior — Pagamento de meta com atraso (`2026.10.15-meta-atrasada`)

Identificador: `2026.10.15-meta-atrasada`

Esta versão inclui:

- Membros podem pagar a meta mesmo depois do prazo de quarta-feira às 23:59, enquanto o `kokusai` não finalizar a semana. Na quinta a sala aceita o envio direto; a partir de sexta aparece o aviso vermelho **Meta em atraso** com o botão **Pagar com atraso**.
- Na hora de fechar a semana, quem pagou com atraso aparece com o selo vermelho **ATRASADA** na lista de salas e um aviso vermelho dentro da sala, com quantos comprovantes chegaram depois do prazo. O resumo da conferência mostra quantas metas estão atrasadas.
- Novo botão **Pago com atraso** na conferência (também serve para pagamento confirmado sem foto).
- O log TXT do fechamento mostra "PAGO COM ATRASO", a linha "Atrasada" de cada pessoa e o total "Pagaram com atraso".
- Banco: `meta_submissions` ganha `paid_late` e `meta_photos` ganha `late` (as duas com padrão 0), criadas sozinhas no primeiro start. Nada existente é alterado.

Depois do deploy, abra `/health` e confirme `"version": "2026.10.15-meta-atrasada"`.

---

# Versão anterior — Fotos de perfil no painel (`2026.10.07-fotos-perfil`)

Identificador: `2026.10.07-fotos-perfil`

Esta versão inclui:

- A foto que cada membro coloca no perfil agora aparece para a administração em **Salas de Meta**: na lista de salas, no topo da sala aberta (foto maior, para conferir na hora de fechar a meta) e em **Gerenciar membros**.
- A própria sala do membro mostra a foto dele no topo.
- **Em todo o painel:** quando um nome escrito nas tabelas e cartões bate com o nome, apelido ou usuário de um membro com foto, a foto aparece ao lado (Compras "quem pediu", Vendas "quem vende", Encomendas "negociou", responsável das Famílias e Reuniões, "registrado por" do Baú). Nomes que não são de membros (ex.: "Estoque") continuam só texto.
- As fotos são entregues por `/avatar/<id>` com cache: carregam uma vez e só são baixadas de novo quando a pessoa troca a foto. A equipe vê a foto de todos; cada membro vê apenas a própria.
- Nova rota `GET /api/pessoas` (equipe) com os membros ativos e o endereço da foto.

Depois do deploy, abra `/health` e confirme `"version": "2026.10.07-fotos-perfil"`.

---

# Versão anterior — Registro Baú protegido (`2026.10.07-bau-arquivo`)

Identificador: `2026.10.07-bau-arquivo`

Esta versão inclui:

- **Quem registrou:** o envio de fotos do baú pede o nome de quem está registrando (a conta kokusai é compartilhada). O nome fica gravado junto da foto e aparece no cartão e na foto ampliada. O aparelho lembra o último nome usado.
- **Data e hora automáticas:** continuam sendo gravadas pelo servidor (horário de Brasília) no momento do envio; o navegador não consegue alterar. O formulário agora avisa isso.
- **Excluir virou Arquivar:** nenhuma foto é apagada de verdade. Ao arquivar, o site pede quem está arquivando; a foto sai da galeria e vai para **Arquivadas** (com data, hora e quem arquivou), continua no Bucket e pode ser restaurada.
- Fotos arquivadas não podem ter a legenda editada (restaure antes).
- Banco: a tabela `bau_registros` ganha as colunas `responsavel`, `arquivado`, `arquivado_em` e `arquivado_por` automaticamente no primeiro start; registros antigos continuam iguais (o "registrado por" deles mostra a conta, já que não tinham o nome).
- Rotas: `GET /api/bau?arquivadas=1`, `DELETE /api/bau/photos/<id>` agora arquiva (exige `responsavel`), novo `POST /api/bau/photos/<id>/restaurar`.

Depois do deploy, abra `/health` e confirme `"version": "2026.10.07-bau-arquivo"`.

---

# Versão anterior — Usuário kiyotaka (`2026.10.07-kiyotaka`)

Identificador: `2026.10.07-kiyotaka`

Esta versão inclui:

- O usuário de acesso **kyotaka** passa a se chamar **kiyotaka**. É a mesma conta: semanas, fotos, perfil, apelido e senha continuam iguais. A troca acontece sozinha no primeiro start depois do deploy.
- O nome antigo ainda é aceito no login (entra como kiyotaka) e na variável `META_MEMBERS_JSON`, então não precisa mexer no Railway. Quem estava conectado como kyotaka precisa entrar de novo uma vez.
- Novo mecanismo `MEMBER_USERNAME_RENAMES` no `main.py` para futuras trocas de usuário de acesso.
- Proteção: o painel não deixa criar um membro novo com um nome que foi renomeado ou que gere conflito de id.

Depois do deploy, abra `/health` e confirme `"version": "2026.10.07-kiyotaka"`.

---

# Versão anterior — Conta por aba (`2026.10.07-conta-por-aba`)

Identificador: `2026.10.07-conta-por-aba`

Esta versão inclui:

- **Correção:** com duas contas abertas no mesmo navegador (ex.: `kokusai` e a conta pessoal), trocar de conta numa aba fazia as outras abas passarem a agir com a nova conta. Na sala de metas isso aparecia como "Esta ação é exclusiva dos membros das salas de meta." ao enviar fotos. Agora cada aba continua com a conta em que foi aberta.
- Se a conta da aba não estiver mais conectada (saiu ou caiu a sessão), o site pede para recarregar a página em vez de usar outra conta.
- "Sair" e "Sair de todos os aparelhos" agem sobre a conta da página onde foram clicados.

Depois do deploy, abra `/health` e confirme `"version": "2026.10.07-conta-por-aba"`. Recarregue as abas abertas (Ctrl+F5) para pegar o novo `account.js`.

---

# Versão anterior — Visual "Laca" (`2026.10.07-visual-laca`)

Identificador: `2026.10.07-visual-laca`

Esta versão inclui:

- **Nova identidade visual** em todo o site (painel, login, sala de metas e perfil): preto quente, cinzas quentes e vermelho-laca, com degradê só nos pontos de destaque. Títulos em Shippori Mincho e interface em Hanken Grotesk. Carimbo 国際 no destaque da visão geral e no login.
- **Visão geral:** os 8 cartões do resumo viraram um quadro único (colunas Compras, Vendas, Encomendas e Metas; linhas de registros e valores). No celular, uma linha por assunto.
- Saíram os rótulos em caixa alta acima dos títulos, os ícones do menu cada um de uma cor, o roxo dos cartões e as caixas dentro de caixas. Status agora são ponto + texto.
- **Correções:** no celular a página não estica mais para os lados (o painel ficava cortado e o botão Atualizar sumia); na tabela de Encomendas os botões e as datas não quebram mais letra por letra; em Famílias os nomes não aparecem mais cortados; o menu lateral rola quando a tela é baixa; a sala aberta em Salas de Meta não fica mais centralizada; no celular o menu centraliza a aba ativa.
- `hud.css` consolidado numa folha só (as 4 camadas antigas foram unificadas).

Depois do deploy, abra `/health` e confirme `"version": "2026.10.07-visual-laca"`. Se o navegador mostrar o visual antigo, recarregue com Ctrl+F5.

---

# Versão anterior — Gerenciar membros das metas (`2026.10.07-gerenciar-membros`)

Identificador: `2026.10.07-gerenciar-membros`

Esta versão inclui:

- Na aba **Salas de Meta**, novo painel recolhível **Gerenciar membros** (somente o usuário `kokusai`).
- **Adicionar** uma pessoa: usuário de acesso, nome no painel e senha inicial opcional. Em branco, o sistema gera uma senha provisória que aparece **uma única vez** na tela para você repassar; a pessoa troca depois no próprio perfil. A sala dela já nasce na semana atual.
- **Remover** uma pessoa que saiu: o acesso é bloqueado na hora e as sessões abertas caem. Semanas, fotos e logs antigos continuam guardados e ela some dos totais e do painel.
- **Reativar** quem voltou (a senha antiga continua valendo, mas sessões de antes da remoção não voltam) e **Nova senha** para quem esqueceu.
- **Mudança importante:** `META_MEMBERS_JSON` agora só **cadastra** quem ainda não existe. Quem entra e quem sai é decidido pelo painel: tirar alguém da variável não desativa a pessoa, quem foi removido pelo painel não é reativado por um deploy, e quem foi adicionado pelo painel não precisa estar na variável.
- Novas rotas (admin): `GET|POST /api/meta-members`, `DELETE /api/meta-members/<id>`, `POST /api/meta-members/<id>/reativar` e `/redefinir-senha`.

Depois do deploy, abra `/health` e confirme `"version": "2026.10.07-gerenciar-membros"`.

---

# Versão anterior — Produtos de linha + M16 (`2026.10.07-produtos-m16`)

Identificador: `2026.10.07-produtos-m16`

Esta versão inclui:

- **Vendas:** atalhos de produto para **L85, Seringa e Circuito Eletrônico** (sempre disponíveis) e, além deles, o **M16** até 13/10/2026, com selo "até 13/10".
- **Encomendas:** os cartões L85, Seringa e Circuito Eletrônico continuam como sempre, e agora existe um cartão adicional de **M16** (quantidade e valor unitário) durante a mesma semana. O M16 entra no total, no resumo da encomenda e na conversão para Vendas.
- Editar uma encomenda que já tinha M16 continua funcionando depois do dia 13/10 (o cartão aparece como "período encerrado" só nessa edição).
- Nova rota `GET /api/produtos-venda` (equipe autenticada) com `fixos` e `temporarios`. A lista de linha está em `PERMANENT_SALE_PRODUCTS` e a de temporários em `TEMPORARY_SALE_PRODUCTS`, ambas no `main.py`.
- Correção: a função que normaliza nomes no navegador apagava letras maiúsculas e números (expressão regular com erro). Isso impedia carregar o Circuito Eletrônico ao editar uma encomenda.

Depois do deploy, abra `/health` e confirme `"version": "2026.10.07-produtos-m16"`.

---

# Versão anterior — Contas e perfil (`2026.10.07-contas-perfil`)

Identificador: `2026.10.07-contas-perfil`

Esta versão inclui:

- **Login estilo Steam:** ao abrir o site aparece "Quem está entrando?" com as contas salvas no aparelho e a opção "Outra conta". Contas salvas pedem sempre a senha.
- **Até 2 contas abertas ao mesmo tempo** (ex.: `kokusai` + conta pessoal), com troca sem senha enquanto a sessão durar. Atalhos no menu lateral, na sala de metas e no perfil.
- **Página de perfil (`/perfil`):** foto, apelido, trocar senha e "Sair de todos os aparelhos". O nome continua fixo (afeta o painel de metas). A conta `kokusai` tem perfil somente leitura.
- Trocar a senha ou sair de todos derruba as sessões dos outros aparelhos (nova coluna de versão de sessão em `user_profiles`).
- **Deploys não sobrescrevem mais senhas trocadas pelo perfil.** `META_MEMBERS_JSON` é a senha inicial; para redefinir a senha de alguém, troque o hash dele nessa variável.
- No celular/tablet o avatar no topo do painel abre o perfil (onde ficam "Trocar de conta" e "Sair").
- Tabela nova `user_profiles`, criada automaticamente no primeiro start.

Antes de publicar, confirme no Railway que `KOKUSAI_PASSWORD_HASH`, `META_MEMBERS_JSON` e `SECRET_KEY` existem. Depois do deploy, abra `/health` e confirme `"version": "2026.10.07-contas-perfil"`.

---

# Versão anterior — Remover compra e M16 2026.10.07 (`2026.10.07-remover-compra-m16`)

Identificador: `2026.10.07-remover-compra-m16`

Esta versão inclui:

- Botão **Remover** em cada compra (somente administrador), com confirmação mostrando a compra e rota `DELETE /api/compras/<id>`. A remoção é registrada no log do servidor.
- Atalho de venda do **M16**, disponível por 7 dias (07/10/2026 a 13/10/2026). Some automaticamente depois da data final, sem precisar publicar de novo.
- Novo mecanismo `TEMPORARY_SALE_PRODUCTS` no `main.py` para liberar outros produtos por período.
- Nova rota `GET /api/produtos-temporarios` (equipe autenticada) com os produtos ativos no dia.

Depois do deploy, abra `/health` e confirme `"version": "2026.10.07-remover-compra-m16"`.

---

# Versão anterior — Registro Baú e segurança 2026.10.01

Identificador: `2026.10.01-registro-bau`

Esta versão inclui:

- Nova aba **Registro Baú**: envio de fotos (arrastar, selecionar ou colar), legenda opcional, galeria por mês, ampliação da foto, edição de legenda e exclusão (somente administrador).
- Fotos do baú armazenadas no Bucket privado, com índice permanente no banco (`bau_registros`).
- O app não inicia no Railway sem `SECRET_KEY` (antes subia com a chave padrão do código).
- Limite de tentativas de login passou a usar o IP real do proxy (`ProxyFix`) e ignora `X-Forwarded-For` forjado; novo limite por usuário.
- Hash do administrador e hashes dos membros saíram do código: agora vêm de `KOKUSAI_PASSWORD_HASH` e `META_MEMBERS_JSON`.
- `scripts/generate_password_hash.py` gera hashes com 600 mil iterações.
- Se a lista de membros vier vazia, o sistema não desativa os membros existentes.

**Antes de publicar:** cadastre `KOKUSAI_PASSWORD_HASH` e `META_MEMBERS_JSON` no Railway (valores no arquivo `railway-variaveis.txt`) e confirme que `SECRET_KEY` existe.

Depois do deploy, abra `/health` e confirme `"version": "2026.10.01-registro-bau"`.

---

# Versão anterior — HUD Natural V2 2026.09.03

Identificador: `2026.09.03-hud-natural-v2`

Incluía:

- Correção automática de fotos antigas vinculadas à semana atual.
- Reassociação das fotos à semana correta pela data real do envio.
- Circuito Eletrônico na calculadora de craft.
- Craft por unidade: 5 Alumínios, 5 Cobres, 200 Dinheiro Sujo, 10 Plásticos e 1 Chapa de Metal.
- Botão Editar visível nos cartões das famílias.
- Formulário preenchido com opção Salvar alterações.
- Botão Excluir visível nos cartões das famílias.
- Confirmação segura digitando o nome antes da exclusão permanente.
- Exclusão remove somente o cadastro e seus flyers; transações anteriores permanecem.
- Famílias apagadas não são recriadas pela manutenção automática.
- Circuito Eletrônico disponível também nas Encomendas, com quantidade, valor unitário e subtotal.
- Nova identidade visual em vermelho profundo, preto e cinza metálico.
- Navegação com nove ícones vetoriais exclusivos e consistentes.
- Destaque vermelho mais forte para a aba ativa e ações principais.
- Cartões, tabelas, filtros, formulários e modais com acabamento premium.
- Login e sala individual de metas integrados à mesma identidade.
- Tipografia Manrope nos títulos, botões e navegação para uma leitura mais autoral.
- Responsividade preservada para desktop, notebook e celular.
- Vermelho reduzido nos grandes preenchimentos e mantido como assinatura visual.
- Sidebar, cartões, resumo e sala de metas com acabamento grafite mais natural.
- Ícones identificados por cores discretas específicas para cada área.
- Navegação com cor visível no ícone, indicador lateral e seleção da aba.
- Vermelho removido dos grandes cartões, cabeçalhos de tabelas e sidebar.
- Fundo geral preservado conforme a direção aprovada.
