# Salas de Meta no Railway

O módulo novo foi preparado para usar **PostgreSQL** para usuários/status/histórico e um **Bucket privado** para as fotos.

## 1. Criar o PostgreSQL

No projeto do Kokusai no Railway, adicione um serviço PostgreSQL. No serviço web do Kokusai, crie uma variável de referência apontando para a URL do banco:

```txt
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

Se o seu serviço PostgreSQL tiver outro nome, troque `Postgres` pelo nome correspondente.

As tabelas `meta_users`, `meta_submissions` e `meta_photos` são criadas automaticamente no primeiro acesso ao módulo. Os 30 membros iniciais também são inseridos automaticamente.

## 2. Criar o Bucket das fotos

No mesmo projeto, adicione um **Bucket** e passe as credenciais dele ao serviço web usando referências de variáveis:

```txt
BUCKET=${{Bucket.BUCKET}}
ENDPOINT=${{Bucket.ENDPOINT}}
REGION=${{Bucket.REGION}}
ACCESS_KEY_ID=${{Bucket.ACCESS_KEY_ID}}
SECRET_ACCESS_KEY=${{Bucket.SECRET_ACCESS_KEY}}
```

Troque `Bucket` caso você dê outro nome ao recurso.

O bucket permanece privado. O backend gera links temporários somente depois de verificar se quem pediu a foto é o próprio membro ou o administrador.

## 3. Dependências e deploy

O `requirements.txt` já inclui `psycopg`, `boto3` e `Pillow`. O deploy normal instala essas dependências.

Mantenha também as variáveis que o Kokusai já utilizava, principalmente `SECRET_KEY`, `SPREADSHEET_ID`, `GOOGLE_CREDENTIALS_JSON` e os hashes dos usuários administrativos.

Não configure `service_account.json` como arquivo publicado. Continue usando `GOOGLE_CREDENTIALS_JSON` no Railway.

## 4. Credenciais dos membros

O arquivo local `CREDENCIAIS_METAS.txt` contém os usuários e senhas iniciais. Ele está no `.gitignore` e não deve ser enviado ao GitHub.

Cada pessoa deve receber somente a própria linha. No banco ficam apenas hashes PBKDF2-SHA256 das senhas.

## 5. Funcionamento semanal

- Quarta-feira é o início da semana por padrão (`META_RESET_WEEKDAY=2`).
- Ao iniciar uma nova semana, o sistema cria uma nova sala semanal para cada membro.
- Fotos e status das semanas anteriores continuam no histórico.
- Uma semana marcada `Pago` fica bloqueada para alteração de fotos pelo membro.
- Fotos aceitas: JPG, PNG e WEBP, até 10 MB por arquivo.
- O sistema redimensiona imagens grandes e armazena em WEBP para economizar espaço.
- O limite padrão é de até 5 fotos por pessoa/semana, embora o fluxo normal seja 1 ou 2.

## Desenvolvimento local

Sem `DATABASE_URL`, o projeto usa automaticamente:

```txt
data/kokusai_metas.db
data/meta_uploads/
```

Esses arquivos já ficam fora do Git pela regra `data/` do `.gitignore`. No Railway, o módulo exige PostgreSQL e Bucket para não depender do disco efêmero do serviço.
