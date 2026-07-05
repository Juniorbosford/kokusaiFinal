# Login e permissões

O sistema agora tem autenticação por sessão Flask e dois perfis:

- `kokusai`: administrador, com acesso total para visualizar e registrar compras, vendas e encomendas.
- `nekutai`: leitor, com acesso somente para visualização.

As senhas não estão salvas em texto puro no código. O arquivo `main.py` usa hashes PBKDF2-SHA256 na constante `AUTH_USERS`.

## Variáveis recomendadas no Railway

Configure no Railway:

```txt
SECRET_KEY=gere_uma_chave_grande_e_aleatoria
SESSION_COOKIE_SECURE=true
# Opcional, apenas se quiser trocar os hashes sem mexer no código:
KOKUSAI_PASSWORD_HASH=hash_do_usuario_kokusai
NEKUTAI_PASSWORD_HASH=hash_do_usuario_nekutai
```

A `SECRET_KEY` mantém as sessões assinadas corretamente entre reinícios do app. Em produção com HTTPS, `SESSION_COOKIE_SECURE=true` faz o navegador enviar o cookie apenas por conexão segura.

## Como trocar uma senha depois

Rode localmente:

```bash
python scripts/generate_password_hash.py
```

Copie o hash gerado e faça uma destas opções:

1. Substitua o campo `password_hash` do usuário desejado em `main.py`; ou
2. Configure `KOKUSAI_PASSWORD_HASH` / `NEKUTAI_PASSWORD_HASH` no Railway.

## Usar planilha para login

Dá para usar uma planilha como fonte de usuários, mas o ideal é guardar senha em hash, não em texto puro. Para apenas 2 usuários fixos, manter hashes no backend ou em variáveis de ambiente costuma ser mais simples e seguro. Se você quiser editar usuários sem mexer no código, o próximo passo seria criar uma aba `Usuarios` na planilha com colunas como `usuario`, `nome`, `perfil`, `senha_hash` e `ativo`.
