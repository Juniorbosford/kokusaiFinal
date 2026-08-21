# KOKUSAI

Painel interno para compras, vendas, encomendas, famílias, reuniões, relatórios, craft e salas semanais de meta.

## Estrutura do projeto

```text
kokusaiFinal/
├── main.py                 # Aplicação Flask, APIs e regras de negócio
├── meta_members.py         # Membros e hashes de acesso das salas de meta
├── KOKUSAI_PREVIEW_HUD.html # Prévia completa em um único arquivo
├── requirements.txt        # Dependências Python
├── Procfile                # Comando de inicialização do Railway
├── scripts/
│   ├── build_hud_preview.js
│   └── generate_password_hash.py
├── templates/
│   ├── index.html          # Painel do administrador
│   ├── login.html
│   └── meta_room.html      # Sala individual do membro
└── static/
    ├── css/
    │   ├── style.css       # Componentes e regras visuais de base
    │   └── hud.css         # Hierarquia e acabamento da interface atual
    ├── js/app.js
    ├── js/meta_room.js
    └── images/
```

Arquivos locais contendo credenciais, banco SQLite, fotos enviadas e cache não devem ser publicados. Eles já estão cobertos pelo `.gitignore`.

## Ver somente a interface

Para avaliar a HUD sem instalar Python, configurar banco ou conectar o Google Sheets:

1. Extraia todo o ZIP.
2. Abra `KOKUSAI_PREVIEW_HUD.html` com dois cliques.
3. Navegue pelas abas normalmente.

A prévia usa dados simulados, não envia informações e não altera a produção. CSS, JavaScript, logo e flyers de demonstração ficam embutidos no próprio HTML, então o arquivo pode ser aberto sozinho, mesmo fora da pasta do projeto. Quando a interface principal mudar, execute `node scripts/build_hud_preview.js` para regenerá-la.

## Interface e fluxo visual

- O cabeçalho muda conforme a área aberta e substitui títulos repetidos dentro das telas.
- Formulários de cadastro começam recolhidos e abrem somente quando o usuário solicita; ao editar um registro, o formulário correto é aberto automaticamente.
- Famílias, reuniões, observações de encomenda, ranking completo e receitas mostram primeiro apenas o resumo. Informações secundárias ficam em detalhes expansíveis.
- Os filtros rápidos de encomendas permanecem visíveis; busca, período e ordenações avançadas abrem sob demanda.
- `style.css` concentra a base funcional dos componentes e `hud.css` aplica o visual grafite/preto/vermelho de baixa densidade. Carregue sempre `hud.css` depois de `style.css`.
- A interface é responsiva: tabelas viram cartões, a navegação se torna horizontal e os painéis se reorganizam em telas menores.

## Onde os dados ficam

- **Google Sheets:** compras, vendas, encomendas, famílias e reuniões.
- **PostgreSQL:** usuários das metas, semanas, status, histórico e fechamentos.
- **Railway Bucket privado:** fotos das metas e flyers enviados pelo painel.
- **SQLite + `data/meta_uploads` e `data/flyer_uploads`:** alternativa automática somente para desenvolvimento local.

## Fluxo semanal das metas

- **Sexta-feira às 00:00:** abre uma nova semana.
- **Sexta até quarta-feira às 23:59:** membros podem enviar e remover suas fotos.
- **Quinta-feira:** somente o administrador `kokusai` confere e marca `Pago` ou `Não pago`.
- As fotos são comprovantes opcionais: o administrador pode marcar `Pago` mesmo quando o membro enviou 0 fotos.
- Depois que todos forem avaliados, o administrador finaliza a semana e recebe o log em TXT.
- **Sexta-feira seguinte:** a próxima semana abre automaticamente.
- Cada membro vê todas as próprias fotos; o administrador vê todas as salas.
- Ciclos antigos são migrados automaticamente para o calendário sexta–quarta sem apagar fotos.
- As fotos permanecem no Bucket após atualizações e deploys e continuam disponíveis no histórico semanal.
- Membros podem selecionar, arrastar ou colar imagens copiadas com `Ctrl + V`, conferindo as prévias antes do envio.
- Cada membro pode manter até **10 fotos por semana**.
- Depois de **3 semanas finalizadas consecutivas** com resultado `Não pago`, o sistema exibe um aviso na sala individual e no painel do administrador.
- Ao retirar alguém de `meta_members.py`, o acesso é desativado sem apagar o histórico antigo, as fotos ou os logs.

## Persistência dos flyers

- O formulário de Famílias aceita dois arquivos de imagem, além dos links externos opcionais.
- Imagens enviadas pelo formulário são convertidas para WEBP e armazenadas permanentemente no Bucket.
- O Google Sheets guarda uma referência estável; o próprio KOKUSAI entrega a imagem privada ao navegador, sem depender de links temporários que expiram.
- O upload só é confirmado no cadastro depois que o Bucket confirma a existência do arquivo.
- Links temporários antigos do Bucket são reconhecidos e recuperados automaticamente quando ainda contêm a chave do flyer.
- Substituir ou remover um flyer também remove do Bucket apenas o arquivo que deixou de ser usado.
- Flyers incluídos dentro de `static/images/flyers` continuam fazendo parte do próprio projeto.

## Executar localmente

Requer Python 3.11 ou superior.

```bash
python -m venv .venv
```

No Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Abra `http://localhost:5000`.

Sem `DATABASE_URL`, o projeto cria automaticamente:

```text
data/kokusai_metas.db
data/meta_uploads/
data/flyer_uploads/
```

## Publicar no Railway

O Railway usa o `Procfile` da raiz para iniciar o Gunicorn. Não é necessário Replit, Nix ou Dockerfile.

### Variáveis obrigatórias

```text
SECRET_KEY=chave_grande_e_aleatoria
SESSION_COOKIE_SECURE=true
SPREADSHEET_ID=id_da_planilha
GOOGLE_CREDENTIALS_JSON=json_completo_da_service_account
DATABASE_URL=${{Postgres.DATABASE_URL}}
BUCKET=${{Bucket.BUCKET}}
ENDPOINT=${{Bucket.ENDPOINT}}
REGION=${{Bucket.REGION}}
ACCESS_KEY_ID=${{Bucket.ACCESS_KEY_ID}}
SECRET_ACCESS_KEY=${{Bucket.SECRET_ACCESS_KEY}}
```

Troque `Postgres` e `Bucket` se os serviços tiverem outros nomes no projeto Railway.

### Variáveis opcionais

```text
KOKUSAI_PASSWORD_HASH=hash_do_administrador
APP_TIMEZONE=America/Sao_Paulo
META_MAX_FILE_BYTES=10485760
SHEETS_CACHE_SECONDS=45
SHEETS_MAINTENANCE_SECONDS=300
```

O ciclo da meta é fixo em sexta–quarta e não depende mais de variável de dia da semana.

## Trocar a senha do administrador

Execute:

```bash
python scripts/generate_password_hash.py
```

Copie o hash gerado para `KOKUSAI_PASSWORD_HASH` no Railway e faça um novo deploy. Nunca salve a senha em texto puro no GitHub.

## Regras principais

- Encomendas pendentes permanecem em **Encomendas**.
- Ao confirmar a entrega, cada produto é registrado em **Vendas** e a encomenda sai da lista ativa.
- A conversão usa IDs estáveis para não duplicar vendas após uma falha parcial.
- Toda encomenda é vinculada a uma família cadastrada.
- O ranking mensal aceita somente famílias existentes no cadastro atual.
- Dinheiro sujo permite escolher o acréscimo de 1% a 30% em cada compra, venda ou encomenda; 30% continua sendo o valor inicial.
- Uma encomenda pode combinar L85 e Seringa, preservando quantidade e valor de cada produto.
- Encomendas aceitam prioridade manual com destaque vermelho e são ordenadas automaticamente pelo prazo mais próximo.
- A lista de encomendas possui busca, filtros rápidos de prazo/prioridade, período personalizado e diferentes ordenações.
- Encomendas com observação exibem um botão discreto **Ver observação**; ele abre um painel com o texto, pedido, negociador e prazo sem ocupar espaço permanente na tabela.
- Famílias aceitam dois contatos ocultos e dois flyers.
- Cada família possui um responsável interno pelo contato, exibido em Famílias, Compras, Vendas, Encomendas, Reuniões e Relatórios.
- Ruptura/Leviatã ficam com Larissa; Distrito/Black Hearts com Wanda; The Lost MC com Kiyotaka; Ballas/Legacy com Matheus; Aura/La Guardia com Gohan; Vendetta/Cartel com Max; Hells com Theo.
- Nox, Void e Meraki ficam como **Sem mercado** e têm o bloqueio preservado. Chaos e Balaclava começam **Em negociação**, mas o administrador pode alterar para **Mercado aberto** quando as negociações forem liberadas. Enquanto uma família não estiver aberta, compras, vendas e encomendas ficam bloqueadas, inclusive pelo campo manual.
- Responsabilidades internas: Kiyotaka controla o baú, Lipe responde pela abertura/deep e Wanda responde por compra de material/controle de estoque.
- Variações de nomes são unificadas automaticamente, como Caos/Chaos e Balaklava/Balaclava. Ao remover a duplicata, o sistema preserva até dois flyers, dois contatos, valores, responsável e a situação comercial já liberada.

## Segurança

- Não publique `service_account.json`, `.env`, `CREDENCIAIS_METAS.txt` ou a pasta `data`.
- Use uma `SECRET_KEY` forte no Railway.
- O Bucket deve continuar privado; o sistema gera links temporários após validar o usuário.
- A rota `/api/debug-config` permanece desligada, salvo quando `ENABLE_DEBUG_CONFIG=true` for configurado temporariamente.
- Se uma chave da conta de serviço Google tiver sido exposta, revogue-a no Google Cloud e crie outra.

## Verificação rápida antes do deploy

```bash
python -m py_compile main.py meta_members.py
```

Se o Node.js estiver instalado:

```bash
node --check static/js/app.js
node --check static/js/meta_room.js
```
