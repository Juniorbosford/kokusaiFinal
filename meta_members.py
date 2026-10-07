"""Membros das salas de meta.

Os hashes de senha NÃO ficam mais no código nem no repositório. Eles são lidos de:

1. variável de ambiente META_MEMBERS_JSON (produção / Railway); ou
2. arquivo local meta_members.local.json (desenvolvimento; ignorado pelo Git).

Formato esperado (lista JSON):

    [{"username": "ana", "display_name": "Ana", "password_hash": "pbkdf2_sha256$..."}]

Para gerar um hash novo, use: python scripts/generate_password_hash.py
"""
import json
import os

LOCAL_MEMBERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "meta_members.local.json")
_REQUIRED_FIELDS = ("username", "display_name", "password_hash")


def _running_on_railway():
    return bool(
        os.getenv("RAILWAY_ENVIRONMENT")
        or os.getenv("RAILWAY_ENVIRONMENT_NAME")
        or os.getenv("RAILWAY_PROJECT_ID")
    )


def _load_members():
    raw = os.getenv("META_MEMBERS_JSON", "").strip()
    source = "META_MEMBERS_JSON"

    if not raw and os.path.isfile(LOCAL_MEMBERS_FILE):
        with open(LOCAL_MEMBERS_FILE, encoding="utf-8") as file_handle:
            raw = file_handle.read().strip()
        source = "meta_members.local.json"

    if not raw:
        if _running_on_railway():
            raise RuntimeError(
                "META_MEMBERS_JSON não configurada. Cole a variável do arquivo railway-variaveis.txt "
                "nas variáveis do Railway antes de publicar."
            )
        print(
            "[KOKUSAI][AVISO] Nenhum membro de meta carregado. Crie meta_members.local.json "
            "ou defina META_MEMBERS_JSON para habilitar as salas individuais.",
            flush=True,
        )
        return []

    try:
        data = json.loads(raw)
    except ValueError as error:
        raise RuntimeError(f"{source} não contém um JSON válido.") from error
    if not isinstance(data, list):
        raise RuntimeError(f"{source} deve ser uma lista de membros.")

    members = []
    seen = set()
    for index, entry in enumerate(data, start=1):
        if not isinstance(entry, dict) or any(not str(entry.get(field) or "").strip() for field in _REQUIRED_FIELDS):
            raise RuntimeError(f"{source}: o membro nº {index} precisa de username, display_name e password_hash.")
        username = str(entry["username"]).strip().lower()
        if username in seen:
            continue
        seen.add(username)
        members.append({
            "username": username,
            "display_name": str(entry["display_name"]).strip(),
            "password_hash": str(entry["password_hash"]).strip(),
        })
    return members


META_MEMBERS = _load_members()
