import os
import json
import traceback
import base64
import hashlib
import hmac
import re
import time
import threading
import secrets
import sqlite3
import uuid
from io import BytesIO
from copy import deepcopy
from datetime import datetime, timedelta, date, timezone
from functools import wraps
import unicodedata
from urllib.parse import urlparse
from flask import Flask, jsonify, render_template, request, redirect, session, url_for, g, send_file
import gspread
from google.oauth2.service_account import Credentials
from meta_members import META_MEMBERS

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

app = Flask(__name__)
DEFAULT_SECRET_KEY = "kokusai-dev-secret-change-this"
IS_RAILWAY = bool(
    os.getenv("RAILWAY_ENVIRONMENT")
    or os.getenv("RAILWAY_ENVIRONMENT_NAME")
    or os.getenv("RAILWAY_PROJECT_ID")
)
app.secret_key = os.getenv("SECRET_KEY", DEFAULT_SECRET_KEY)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=12)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv(
    "SESSION_COOKIE_SECURE",
    "true" if IS_RAILWAY else "false",
).lower() == "true"
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", str(12 * 1024 * 1024)))


SHEET_NAME = os.getenv("SHEET_NAME", "KokusaiDB")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "").strip()
COMPRAS_WORKSHEET_NAME = os.getenv("COMPRAS_WORKSHEET_NAME", "Compras")
VENDAS_WORKSHEET_NAME = os.getenv("VENDAS_WORKSHEET_NAME", "Vendas")
ENCOMENDAS_WORKSHEET_NAME = os.getenv("ENCOMENDAS_WORKSHEET_NAME", "Encomendas")
METAS_WORKSHEET_NAME = os.getenv("METAS_WORKSHEET_NAME", "Pagamento de Metas")
HISTORICO_METAS_WORKSHEET_NAME = os.getenv("HISTORICO_METAS_WORKSHEET_NAME", "Historico Metas")
REUNIOES_WORKSHEET_NAME = os.getenv("REUNIOES_WORKSHEET_NAME", "Reunioes")
FAMILIAS_WORKSHEET_NAME = os.getenv("FAMILIAS_WORKSHEET_NAME", "Familias")
LEGACY_FLYERS_WORKSHEET_NAME = os.getenv("FLYERS_WORKSHEET_NAME", "Flyers")
META_RESET_WEEKDAY = int(os.getenv("META_RESET_WEEKDAY", "2"))  # 0=segunda, 2=quarta
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "America/Sao_Paulo")
APP_UTC_OFFSET_HOURS = int(os.getenv("APP_UTC_OFFSET_HOURS", "-3"))

# Salas semanais de meta: PostgreSQL + Bucket no Railway em produção.
# Localmente, SQLite e a pasta data/meta_uploads permitem testar sem infraestrutura externa.
META_DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
META_DB_LOCAL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "kokusai_metas.db")
META_BUCKET_NAME = (os.getenv("BUCKET") or os.getenv("AWS_S3_BUCKET_NAME") or "").strip()
META_BUCKET_ENDPOINT = (os.getenv("ENDPOINT") or os.getenv("AWS_ENDPOINT_URL") or "").strip()
META_BUCKET_REGION = (os.getenv("REGION") or os.getenv("AWS_DEFAULT_REGION") or "auto").strip()
META_BUCKET_ACCESS_KEY = (os.getenv("ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID") or "").strip()
META_BUCKET_SECRET_KEY = (os.getenv("SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY") or "").strip()
META_LOCAL_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "meta_uploads")
META_MAX_FILE_BYTES = int(os.getenv("META_MAX_FILE_BYTES", str(10 * 1024 * 1024)))
META_MAX_PHOTOS_PER_WEEK = int(os.getenv("META_MAX_PHOTOS_PER_WEEK", "5"))
META_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
META_IMAGE_MAX_SIDE = int(os.getenv("META_IMAGE_MAX_SIDE", "2200"))
META_IMAGE_WEBP_QUALITY = int(os.getenv("META_IMAGE_WEBP_QUALITY", "88"))

_meta_db_lock = threading.RLock()
_meta_db_ready = False
_meta_storage_client_cache = {"client": None}

# Cache simples para não estourar a quota do Google Sheets.
# O Google Sheets cobra cada leitura da API; antes o painel fazia várias leituras
# ao mesmo tempo ao abrir a tela. Com cache, a tela reaproveita os dados por alguns segundos.
SHEETS_CACHE_SECONDS = int(os.getenv("SHEETS_CACHE_SECONDS", "45"))
SHEETS_META_MAINTENANCE_SECONDS = int(os.getenv("SHEETS_META_MAINTENANCE_SECONDS", "300"))
_sheets_lock = threading.RLock()
_gsheet_client_cache = {"client": None}
_spreadsheet_cache = {"spreadsheet": None}
_worksheet_cache = {}
_values_cache = {}
_meta_maintenance_cache = {"checked_at": 0}
_familias_maintenance_cache = {"checked_at": 0}

# Proteções simples contra abuso. Como o app roda em poucos usuários,
# limites curtos já reduzem bastante risco de força bruta e payload gigante.
LOGIN_ATTEMPTS = {}
LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_WINDOW_SECONDS = int(os.getenv("LOGIN_WINDOW_SECONDS", "900"))
MAX_TEXT_LENGTH = int(os.getenv("MAX_TEXT_LENGTH", "120"))
MAX_OBSERVATION_LENGTH = int(os.getenv("MAX_OBSERVATION_LENGTH", "500"))
MAX_QUANTITY = int(os.getenv("MAX_QUANTITY", "1000000"))
MAX_MONEY_VALUE = float(os.getenv("MAX_MONEY_VALUE", "1000000000"))
SHEET_FORMULA_PREFIXES = ("=", "+", "-", "@")


# Usuários do sistema. As senhas não ficam salvas em texto puro: são hashes PBKDF2-SHA256.
# Para trocar senha depois, gere um novo hash e substitua o valor correspondente.
AUTH_USERS = {
    "kokusai": {
        "display_name": "Kokusai",
        "role": "admin",
        "password_hash": os.getenv(
            "KOKUSAI_PASSWORD_HASH",
            "pbkdf2_sha256$260000$zqJoxGpMrsecY1W5QaTi8g==$GdZg+UENu9jEfCZqybyt2+VFpZ25GtfFW3DzyYMetAo="
        ),
    },
    "nekutai": {
        "display_name": "Nekutai",
        "role": "viewer",
        "password_hash": os.getenv(
            "NEKUTAI_PASSWORD_HASH",
            "pbkdf2_sha256$260000$ADKx8F6jvODIGc5PijE9Fw==$tP2F34N+nyRT7/SspPQ108lAcJ/gQ3jD/manX3XLLsg="
        ),
    },
}


DEFAULT_META_NAMES = [
    "Astrid",
    "Ayanna",
    "Cecilia",
    "Dulce",
    "GB",
    "Gohan",
    "Harper",
    "Hinata",
    "João",
    "Junior (Azulzin)",
    "Kyotaka",
    "Lara Salles",
    "Larissa",
    "Liam",
    "Lipe",
    "Lucas Diaz",
    "Lucas Ricci",
    "Matheus",
    "Max",
    "Mia",
    "Mina",
    "Morgan",
    "Nanami",
    "Ricardo",
    "Semente",
    "Viny",
    "Yan (Gordin)",
    "Yara",
    "Yori",
    "Wanda",
]

COMPRAS_HEADERS = ["id", "data", "produto", "quem_pediu", "quem_vendeu", "valor_unitario", "quantidade", "valor_total", "observacao"]
VENDAS_HEADERS = ["id", "data", "produto", "quem_compra", "quem_vende", "valor_unitario", "quantidade", "valor_total", "observacao"]
ENCOMENDAS_HEADERS = [
    "id",
    "data",
    "quem_pediu",
    "o_que_pediu",
    "valor",
    "para_quando",
    "quem_negociou",
    "entregue",
    "observacao",
    "entregue_em",
    "itens_json",
]
META_HEADERS = ["id", "nome", "pago", "atualizado_em", "semana_inicio", "semana_fim", "confirmado"]
META_HISTORY_HEADERS = ["semana_inicio", "semana_fim", "fechado_em", "id", "nome", "pago", "atualizado_em"]
REUNIOES_HEADERS = ["id", "criado_em", "titulo", "gangue", "icone", "data", "horario", "local", "pauta", "status", "finalizada_em"]
FAMILIAS_HEADERS = [
    "id",
    "criado_em",
    "nome",
    "icone",
    "mercado",
    "preco_venda_para_familia",
    "preco_compra_da_familia",
    "flyer_url",
    "observacao",
    "atualizado_em",
    "contato",
    "flyer_oculto",
]
DEFAULT_FAMILIAS = [
    {
        "nome": "Aura",
        "icone": "✨",
        "mercado": "Aberto",
        "preco_venda_para_familia": "",
        "preco_compra_da_familia": "",
        "flyer_url": "",
        "observacao": "Cadastro padrão para garantir que a Aura apareça nas opções de facções.",
    },
    {
        "nome": "Distrito",
        "icone": "🏙️",
        "mercado": "Aberto",
        "preco_venda_para_familia": "",
        "preco_compra_da_familia": "",
        "flyer_url": "",
        "observacao": "Cadastro padrão para permitir uma tabela especial de valores para o Distrito.",
    },
    {
        "nome": "Cartel",
        "icone": "🦂",
        "mercado": "Aberto",
        "preco_venda_para_familia": "",
        "preco_compra_da_familia": "",
        "flyer_url": "",
        "observacao": "Nome corrigido de Bandoleros para Cartel.",
    },
]
LIST_LIMIT = int(os.getenv("LIST_LIMIT", "100"))


def now_local():
    """Retorna o horário local usado nas metas semanais.

    No Windows, o Python pode não ter a base de fusos IANA instalada e
    ZoneInfo("America/Sao_Paulo") gera o erro "No time zone found".
    Para não quebrar o site localmente, tentamos ZoneInfo e caímos para
    UTC-3, que é o fuso atual de São Paulo/Brasília.
    """
    if ZoneInfo:
        try:
            return datetime.now(ZoneInfo(APP_TIMEZONE))
        except Exception:
            pass

    return datetime.now(timezone(timedelta(hours=APP_UTC_OFFSET_HOURS)))


def format_timestamp(dt=None):
    return (dt or now_local()).strftime("%d/%m/%Y %H:%M:%S")


def format_date_br(value):
    return value.strftime("%d/%m/%Y")


def parse_date_br(value):
    try:
        return datetime.strptime(str(value or "").strip(), "%d/%m/%Y").date()
    except Exception:
        return None


def meta_week_start(today=None):
    today = today or now_local().date()
    days_since_reset = (today.weekday() - META_RESET_WEEKDAY) % 7
    return today - timedelta(days=days_since_reset)


def meta_week_end(start_date):
    return start_date + timedelta(days=6)


def meta_week_payload(start_date=None):
    start_date = start_date or meta_week_start()
    end_date = meta_week_end(start_date)
    return {
        "semana_inicio": format_date_br(start_date),
        "semana_fim": format_date_br(end_date),
        "semana_label": f"{format_date_br(start_date)} até {format_date_br(end_date)}",
    }


def verify_password(password, password_hash):
    try:
        algorithm, iterations, salt_b64, expected_b64 = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False

        salt = base64.b64decode(salt_b64.encode("utf-8"))
        expected = base64.b64decode(expected_b64.encode("utf-8"))
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            str(password).encode("utf-8"),
            salt,
            int(iterations),
        )
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def meta_db_uses_postgres():
    return bool(META_DATABASE_URL)


def meta_db_connect():
    if META_DATABASE_URL:
        try:
            import psycopg
        except ImportError as error:
            raise RuntimeError("Dependência psycopg não instalada. Execute pip install -r requirements.txt.") from error
        return psycopg.connect(META_DATABASE_URL)

    if IS_RAILWAY:
        raise RuntimeError("DATABASE_URL não configurada. Adicione um PostgreSQL ao projeto no Railway.")

    os.makedirs(os.path.dirname(META_DB_LOCAL_PATH), exist_ok=True)
    connection = sqlite3.connect(META_DB_LOCAL_PATH, timeout=20)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def meta_sql(query):
    return query.replace("?", "%s") if meta_db_uses_postgres() else query


def meta_rows_from_cursor(cursor):
    if not cursor.description:
        return []
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def meta_query_all(query, params=()):
    ensure_meta_database_ready()
    connection = meta_db_connect()
    try:
        cursor = connection.cursor()
        cursor.execute(meta_sql(query), tuple(params))
        return meta_rows_from_cursor(cursor)
    finally:
        connection.close()


def meta_query_one(query, params=()):
    rows = meta_query_all(query, params)
    return rows[0] if rows else None


def meta_execute(query, params=()):
    ensure_meta_database_ready()
    connection = meta_db_connect()
    try:
        cursor = connection.cursor()
        cursor.execute(meta_sql(query), tuple(params))
        connection.commit()
        return cursor.rowcount
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def meta_member_id(username):
    digest = hashlib.sha1(str(username).encode("utf-8")).hexdigest()[:20]
    return f"META-USER-{digest}"


def ensure_meta_database_ready():
    global _meta_db_ready
    if _meta_db_ready:
        return

    with _meta_db_lock:
        if _meta_db_ready:
            return
        connection = meta_db_connect()
        try:
            cursor = connection.cursor()
            statements = [
                """
                CREATE TABLE IF NOT EXISTS meta_users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'member',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS meta_submissions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    week_start TEXT NOT NULL,
                    week_end TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Pendente',
                    admin_note TEXT NOT NULL DEFAULT '',
                    submitted_at TEXT,
                    reviewed_at TEXT,
                    reviewed_by TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(user_id, week_start),
                    FOREIGN KEY(user_id) REFERENCES meta_users(id)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS meta_photos (
                    id TEXT PRIMARY KEY,
                    submission_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    object_key TEXT NOT NULL,
                    original_name TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(submission_id) REFERENCES meta_submissions(id),
                    FOREIGN KEY(user_id) REFERENCES meta_users(id)
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_meta_submissions_week ON meta_submissions(week_start)",
                "CREATE INDEX IF NOT EXISTS idx_meta_photos_submission ON meta_photos(submission_id)",
            ]
            for statement in statements:
                cursor.execute(statement)

            created_at = format_timestamp()
            seed_query = meta_sql(
                """
                INSERT INTO meta_users (id, username, display_name, password_hash, role, active, created_at)
                VALUES (?, ?, ?, ?, 'member', 1, ?)
                ON CONFLICT(username) DO NOTHING
                """
            )
            for member in META_MEMBERS:
                cursor.execute(seed_query, (
                    meta_member_id(member["username"]),
                    member["username"],
                    member["display_name"],
                    member["password_hash"],
                    created_at,
                ))
            connection.commit()
            _meta_db_ready = True
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def get_meta_member_by_username(username):
    try:
        return meta_query_one(
            "SELECT id, username, display_name, password_hash, role, active FROM meta_users WHERE username = ?",
            (str(username or "").strip().lower(),),
        )
    except Exception as error:
        log_error("Falha ao consultar usuário da sala de meta", error)
        return None


def get_meta_member_by_id(user_id):
    return meta_query_one(
        "SELECT id, username, display_name, role, active FROM meta_users WHERE id = ? AND active = 1",
        (user_id,),
    )


def ensure_current_meta_submissions():
    ensure_meta_database_ready()
    week = meta_week_payload()
    members = meta_query_all(
        "SELECT id FROM meta_users WHERE role = 'member' AND active = 1 ORDER BY display_name"
    )
    connection = meta_db_connect()
    try:
        cursor = connection.cursor()
        query = meta_sql(
            """
            INSERT INTO meta_submissions (id, user_id, week_start, week_end, status, created_at)
            VALUES (?, ?, ?, ?, 'Pendente', ?)
            ON CONFLICT(user_id, week_start) DO NOTHING
            """
        )
        created_at = format_timestamp()
        for member in members:
            cursor.execute(query, (
                f"META-SUB-{uuid.uuid4().hex}", member["id"], week["semana_inicio"], week["semana_fim"], created_at,
            ))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return week


def get_current_meta_submission(user_id):
    week = ensure_current_meta_submissions()
    return meta_query_one(
        """
        SELECT id, user_id, week_start, week_end, status, admin_note, submitted_at, reviewed_at, reviewed_by, created_at
        FROM meta_submissions WHERE user_id = ? AND week_start = ?
        """,
        (user_id, week["semana_inicio"]),
    )


def get_meta_photos(submission_id):
    return meta_query_all(
        """
        SELECT id, submission_id, user_id, object_key, original_name, content_type, size_bytes, created_at
        FROM meta_photos WHERE submission_id = ? ORDER BY created_at ASC
        """,
        (submission_id,),
    )


def get_meta_room_history(user_id, limit=12):
    current_week = meta_week_payload()["semana_inicio"]
    return meta_query_all(
        """
        SELECT s.id, s.week_start, s.week_end, s.status, s.admin_note, s.submitted_at, s.reviewed_at,
               (SELECT COUNT(*) FROM meta_photos p WHERE p.submission_id = s.id) AS photo_count
        FROM meta_submissions s
        WHERE s.user_id = ? AND s.week_start <> ?
        ORDER BY substr(s.week_start, 7, 4) || substr(s.week_start, 4, 2) || substr(s.week_start, 1, 2) DESC
        LIMIT ?
        """,
        (user_id, current_week, int(limit)),
    )


def meta_bucket_configured():
    return all([META_BUCKET_NAME, META_BUCKET_ENDPOINT, META_BUCKET_ACCESS_KEY, META_BUCKET_SECRET_KEY])


def get_meta_storage_client():
    if not meta_bucket_configured():
        return None
    if _meta_storage_client_cache.get("client") is not None:
        return _meta_storage_client_cache["client"]
    try:
        import boto3
    except ImportError as error:
        raise RuntimeError("Dependência boto3 não instalada. Execute pip install -r requirements.txt.") from error
    client = boto3.client(
        "s3",
        endpoint_url=META_BUCKET_ENDPOINT,
        region_name=META_BUCKET_REGION,
        aws_access_key_id=META_BUCKET_ACCESS_KEY,
        aws_secret_access_key=META_BUCKET_SECRET_KEY,
    )
    _meta_storage_client_cache["client"] = client
    return client


def prepare_meta_image(upload):
    if not upload or not upload.filename:
        raise ValueError("Selecione uma foto para enviar.")
    if upload.mimetype not in META_ALLOWED_IMAGE_TYPES:
        raise ValueError("Envie somente imagens JPG, PNG ou WEBP.")

    raw = upload.stream.read(META_MAX_FILE_BYTES + 1)
    if len(raw) > META_MAX_FILE_BYTES:
        raise ValueError("A foto ultrapassa o limite de 10 MB.")
    if not raw:
        raise ValueError("A foto enviada está vazia.")

    try:
        from PIL import Image, ImageOps
    except ImportError as error:
        raise RuntimeError("Dependência Pillow não instalada. Execute pip install -r requirements.txt.") from error

    try:
        image = Image.open(BytesIO(raw))
        image = ImageOps.exif_transpose(image)
        image.thumbnail((META_IMAGE_MAX_SIDE, META_IMAGE_MAX_SIDE))
        if image.mode not in {"RGB", "L"}:
            background = Image.new("RGB", image.size, (255, 255, 255))
            if "A" in image.getbands():
                background.paste(image, mask=image.getchannel("A"))
            else:
                background.paste(image)
            image = background
        elif image.mode == "L":
            image = image.convert("RGB")
        output = BytesIO()
        image.save(output, format="WEBP", quality=META_IMAGE_WEBP_QUALITY, method=6)
        return output.getvalue()
    except Exception as error:
        raise ValueError("Não foi possível ler essa imagem. Tente enviar outra foto.") from error


def store_meta_photo(upload, user_id, week_start):
    image_bytes = prepare_meta_image(upload)
    object_key = f"metas/{user_id}/{week_start.replace('/', '-')}/{uuid.uuid4().hex}.webp"
    client = get_meta_storage_client()
    if client:
        client.put_object(Bucket=META_BUCKET_NAME, Key=object_key, Body=image_bytes, ContentType="image/webp")
    else:
        if IS_RAILWAY:
            raise RuntimeError("Bucket de fotos não configurado no Railway.")
        local_path = os.path.join(META_LOCAL_UPLOAD_DIR, *object_key.split("/"))
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as file_handle:
            file_handle.write(image_bytes)
    return {
        "object_key": object_key,
        "original_name": os.path.basename(upload.filename)[:180],
        "content_type": "image/webp",
        "size_bytes": len(image_bytes),
    }


def delete_meta_photo_object(object_key):
    client = get_meta_storage_client()
    if client:
        client.delete_object(Bucket=META_BUCKET_NAME, Key=object_key)
        return
    local_path = os.path.join(META_LOCAL_UPLOAD_DIR, *str(object_key).split("/"))
    if os.path.isfile(local_path):
        os.remove(local_path)


def meta_photo_access_url(photo):
    client = get_meta_storage_client()
    if client:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": META_BUCKET_NAME, "Key": photo["object_key"]},
            ExpiresIn=300,
        )
    return url_for("meta_photo_file", photo_id=photo["id"])


def serialize_meta_photo(photo):
    return {
        "id": photo["id"],
        "original_name": photo["original_name"],
        "content_type": photo["content_type"],
        "size_bytes": int(photo["size_bytes"] or 0),
        "created_at": photo["created_at"],
        "url": meta_photo_access_url(photo),
    }


def get_current_user():
    username = session.get("username")
    if not username:
        return None

    user = AUTH_USERS.get(username)
    if not user:
        user = get_meta_member_by_username(username)
        if not user or not int(user.get("active") or 0):
            session.clear()
            return None

    return {
        "username": username,
        "display_name": user["display_name"],
        "role": user["role"],
        "can_write": user["role"] == "admin",
        "user_id": user.get("id") if isinstance(user, dict) else None,
    }


def wants_json_response():
    return request.path.startswith("/api/") or "application/json" in request.headers.get("Accept", "")


def safe_next_url(target):
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("home")


def get_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def csrf_error_if_invalid():
    sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
    expected = session.get("csrf_token")
    if not sent or not expected or not hmac.compare_digest(str(sent), str(expected)):
        return error_response("Token de segurança inválido. Atualize a página e tente novamente.", 403)
    return None


def get_client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.remote_addr or "unknown"


def login_attempt_key(username):
    return f"{get_client_ip()}:{str(username or '').lower()}"


def is_login_limited(key):
    now = time.time()
    with _sheets_lock:
        attempts = [ts for ts in LOGIN_ATTEMPTS.get(key, []) if now - ts < LOGIN_WINDOW_SECONDS]
        LOGIN_ATTEMPTS[key] = attempts
        return len(attempts) >= LOGIN_MAX_ATTEMPTS


def record_failed_login(key):
    now = time.time()
    with _sheets_lock:
        attempts = [ts for ts in LOGIN_ATTEMPTS.get(key, []) if now - ts < LOGIN_WINDOW_SECONDS]
        attempts.append(now)
        LOGIN_ATTEMPTS[key] = attempts


def clear_login_attempts(key):
    with _sheets_lock:
        LOGIN_ATTEMPTS.pop(key, None)


def clean_text(value, field_name="Campo", max_length=MAX_TEXT_LENGTH, required=False):
    text = str(value or "").replace("\x00", "").strip()
    text = "".join(ch for ch in text if ch in "\n\t" or ord(ch) >= 32)

    if required and not text:
        raise ValueError(f"{field_name} é obrigatório.")
    if len(text) > max_length:
        raise ValueError(f"{field_name} deve ter no máximo {max_length} caracteres.")
    if text.startswith(SHEET_FORMULA_PREFIXES):
        # Evita que dados digitados por usuário virem fórmula no Google Sheets.
        return "'" + text
    return text


def clean_text_field(data, key, label=None, max_length=MAX_TEXT_LENGTH, required=True):
    return clean_text(data.get(key, ""), label or key, max_length=max_length, required=required)


def require_login(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not get_current_user():
            if wants_json_response():
                return error_response("Login necessário para acessar o sistema.", 401)
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def require_staff(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if not user:
            if wants_json_response():
                return error_response("Login necessário para acessar o sistema.", 401)
            return redirect(url_for("login", next=request.path))
        if user["role"] not in {"admin", "viewer"}:
            if wants_json_response():
                return error_response("Esta área é restrita à equipe Kokusai.", 403)
            return redirect(url_for("meta_room"))
        return view(*args, **kwargs)

    return wrapped


def require_member(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if not user:
            if wants_json_response():
                return error_response("Login necessário para acessar sua sala.", 401)
            return redirect(url_for("login", next=request.path))
        if user["role"] != "member":
            if wants_json_response():
                return error_response("Esta ação é exclusiva dos membros das salas de meta.", 403)
            return redirect(url_for("home"))
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            csrf_error = csrf_error_if_invalid()
            if csrf_error:
                return csrf_error
        return view(*args, **kwargs)

    return wrapped


def require_admin(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if not user:
            if wants_json_response():
                return error_response("Login necessário para acessar o sistema.", 401)
            return redirect(url_for("login", next=request.path))
        if user["role"] != "admin":
            return error_response("Seu usuário tem acesso somente para visualização.", 403)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            csrf_error = csrf_error_if_invalid()
            if csrf_error:
                return csrf_error
        return view(*args, **kwargs)

    return wrapped


@app.before_request
def load_logged_user():
    g.current_user = get_current_user()


@app.context_processor
def inject_auth_context():
    user = getattr(g, "current_user", None)
    return {
        "current_user": user,
        "is_admin": bool(user and user.get("role") == "admin"),
        "is_member": bool(user and user.get("role") == "member"),
        "csrf_token": get_csrf_token(),
    }


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(), payment=()",
    )
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self' data: https: http:; "
        "connect-src 'self'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'",
    )
    if app.config.get("SESSION_COOKIE_SECURE"):
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


def log_info(message):
    print(f"[KOKUSAI][INFO] {message}", flush=True)


def log_error(context, error):
    print(f"[KOKUSAI][ERROR] {context}: {repr(error)}", flush=True)
    traceback.print_exc()


def error_response(message, status=500, details=None):
    if status >= 500:
        message = "Erro interno no servidor. Confira os logs do Railway ou do terminal local."
        details = None
    payload = {"ok": False, "error": message}
    if details:
        payload["details"] = details
    return jsonify(payload), status


def invalidate_values_cache(*worksheet_names):
    with _sheets_lock:
        if not worksheet_names:
            _values_cache.clear()
            return
        for name in worksheet_names:
            _values_cache.pop(name, None)


def cached_get_all_values(worksheet_name, worksheet, max_age=None, force=False):
    max_age = SHEETS_CACHE_SECONDS if max_age is None else max_age
    now = time.time()

    with _sheets_lock:
        cached = _values_cache.get(worksheet_name)
        if cached and not force and now - cached["time"] < max_age:
            return deepcopy(cached["rows"])

    # Leitura real no Google Sheets.
    # Importante: não chamar cached_get_all_values aqui, senão cria recursão infinita.
    rows = worksheet.get_all_values()

    with _sheets_lock:
        _values_cache[worksheet_name] = {"time": time.time(), "rows": deepcopy(rows)}

    return rows


def get_gsheet_client():
    with _sheets_lock:
        if _gsheet_client_cache.get("client") is not None:
            return _gsheet_client_cache["client"]

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    # Escopo do Drive só é necessário quando o app abre/cria planilha pelo nome.
    # Em produção, prefira SPREADSHEET_ID para reduzir permissões da service account.
    if not SPREADSHEET_ID:
        scopes.append("https://www.googleapis.com/auth/drive")

    credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
    log_info(
        "Preparando conexão com Google Sheets "
        f"({'SPREADSHEET_ID' if SPREADSHEET_ID else 'nome da planilha'})."
    )

    try:
        if credentials_json:
            creds_dict = json.loads(credentials_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            cred_path = os.path.join(base_dir, "service_account.json")
            log_info(f"Fallback para arquivo local: {cred_path}")

            if not os.path.exists(cred_path):
                raise FileNotFoundError(
                    "Credenciais não encontradas. Defina GOOGLE_CREDENTIALS_JSON "
                    "no Railway ou coloque service_account.json na raiz do projeto."
                )

            creds = Credentials.from_service_account_file(cred_path, scopes=scopes)

        client = gspread.authorize(creds)
        with _sheets_lock:
            _gsheet_client_cache["client"] = client
        log_info("Autenticação com Google Sheets concluída com sucesso.")
        return client

    except json.JSONDecodeError as e:
        log_error("GOOGLE_CREDENTIALS_JSON inválido", e)
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON está com JSON inválido.")
    except Exception as e:
        log_error("Falha ao autenticar no Google Sheets", e)
        raise RuntimeError(f"Erro ao autenticar no Google Sheets: {str(e)}")


def get_or_create_spreadsheet():
    with _sheets_lock:
        if _spreadsheet_cache.get("spreadsheet") is not None:
            return _spreadsheet_cache["spreadsheet"]

        client = get_gsheet_client()

        try:
            if SPREADSHEET_ID:
                log_info(f"Abrindo planilha pelo ID: {SPREADSHEET_ID}")
                spreadsheet = client.open_by_key(SPREADSHEET_ID)
            else:
                try:
                    log_info(f"Abrindo planilha pelo nome: {SHEET_NAME}")
                    spreadsheet = client.open(SHEET_NAME)
                except gspread.SpreadsheetNotFound:
                    log_info(f"Planilha '{SHEET_NAME}' não encontrada. Criando automaticamente.")
                    spreadsheet = client.create(SHEET_NAME)

            _spreadsheet_cache["spreadsheet"] = spreadsheet
            log_info(f"Planilha aberta com sucesso: {spreadsheet.title}")
            return spreadsheet

        except Exception as e:
            log_error("Erro ao abrir/criar planilha", e)
            if SPREADSHEET_ID:
                raise RuntimeError(
                    "Não foi possível abrir a planilha pelo SPREADSHEET_ID. "
                    "Verifique se o ID está correto e se a service account tem acesso de editor."
                )
            raise RuntimeError(f"Erro ao abrir/criar planilha: {str(e)}")


def ensure_headers(worksheet, headers):
    current_headers = worksheet.row_values(1)
    if not current_headers:
        worksheet.append_row(headers)
        invalidate_values_cache(worksheet.title)
        log_info(f"Cabeçalho criado na aba {worksheet.title}")
    elif current_headers[:len(headers)] != headers:
        end_col = chr(ord("A") + len(headers) - 1)
        worksheet.update(f"A1:{end_col}1", [headers], value_input_option="USER_ENTERED")
        invalidate_values_cache(worksheet.title)
        log_info(f"Cabeçalho atualizado na aba {worksheet.title}")


def get_or_create_worksheet(name, headers):
    with _sheets_lock:
        cached = _worksheet_cache.get(name)
        if cached is not None:
            return cached

        spreadsheet = get_or_create_spreadsheet()

        try:
            worksheet = spreadsheet.worksheet(name)
            log_info(f"Aba encontrada: {name}")
            ensure_headers(worksheet, headers)
        except gspread.WorksheetNotFound:
            log_info(f"Aba '{name}' não encontrada. Criando automaticamente.")
            worksheet = spreadsheet.add_worksheet(title=name, rows=1000, cols=20)
            worksheet.append_row(headers)
            invalidate_values_cache(name)
        except Exception as e:
            log_error(f"Erro ao abrir/criar aba {name}", e)
            raise RuntimeError(f"Erro ao abrir/criar aba '{name}': {str(e)}")

        _worksheet_cache[name] = worksheet
        return worksheet


def get_compras_worksheet():
    return get_or_create_worksheet(COMPRAS_WORKSHEET_NAME, COMPRAS_HEADERS)


def get_vendas_worksheet():
    return get_or_create_worksheet(VENDAS_WORKSHEET_NAME, VENDAS_HEADERS)


def get_encomendas_worksheet():
    return get_or_create_worksheet(ENCOMENDAS_WORKSHEET_NAME, ENCOMENDAS_HEADERS)


def normalized_lookup_key(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def canonical_family_name(value):
    name = str(value or "").strip()
    if normalized_lookup_key(name) in {"bandoleros", "bandolero"}:
        return "Cartel"
    return name


def normalize_market_status(value):
    normalized = normalized_lookup_key(value)
    if normalized in {"fechado", "fechada", "mercado fechado", "nao", "n"}:
        return "Fechado"
    return "Aberto"


def normalize_flag(value):
    if isinstance(value, bool):
        return value
    return normalized_lookup_key(value) in {"1", "true", "sim", "yes", "on"}


def family_id_from_name(name):
    digest = hashlib.sha1(normalized_lookup_key(name).encode("utf-8")).hexdigest()[:12].upper()
    return f"KKSF-{digest}"


def clean_optional_http_url(value, field_name="Link do flyer"):
    url = clean_text(value, field_name, max_length=1000, required=False)
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field_name} deve ser um link http ou https válido.")
    return url


def get_familias_worksheet(ensure_ready=True):
    worksheet = get_or_create_worksheet(FAMILIAS_WORKSHEET_NAME, FAMILIAS_HEADERS)
    if ensure_ready:
        ensure_familias_ready(worksheet)
    return worksheet


DEFAULT_REUNIOES = [
    ["KKSR-REUNIAO-BALLAS-20260714", "13/07/2026 20:00:00", "Apresentar produtos", "Ballas", "🟣", "2026-07-14", "21:00", "", "Trocou 01", "Agendada", ""],
    ["KKSR-REUNIAO-LEGACY-20260713", "13/07/2026 19:00:00", "Apresentar produtos", "Legacy", "👑", "2026-07-13", "20:30", "", "Família Nova", "Finalizada", "13/07/2026 20:30:00"],
    ["KKSR-REUNIAO-BLACKHERTS-20260715", "13/07/2026 20:00:00", "Trocar contatos", "Blackherts", "🖤", "2026-07-15", "20:30", "", "Reunião rápida", "Agendada", ""],
    ["KKSR-REUNIAO-LEVIATA-20260714", "13/07/2026 20:00:00", "Trocar contatos", "Leviatã", "🐉", "2026-07-14", "21:30", "", "Reunião rápida — horário aguardando confirmação", "Aguardando confirmação", ""],
    ["KKSR-REUNIAO-FAMILIES-20260714", "13/07/2026 20:00:00", "Trocar contatos", "Families", "💚", "2026-07-14", "21:00", "", "Reunião rápida", "Agendada", ""],
    ["KKSR-REUNIAO-THELOST-20260714", "13/07/2026 20:00:00", "Trocar contatos", "The Lost", "🏍️", "2026-07-14", "20:30", "", "Reunião rápida", "Agendada", ""],
    ["KKSR-REUNIAO-VAGOS-20260713", "13/07/2026 20:00:00", "Apresentar produtos", "Vagos", "💛", "2026-07-13", "21:30", "", "", "Agendada", ""],
    ["KKSR-REUNIAO-DISTRITO-20260715", "13/07/2026 20:00:00", "Apresentar produtos", "Distrito", "🏙️", "2026-07-15", "21:30", "", "Família Nova", "Agendada", ""],
]


def seed_default_reunioes(worksheet):
    """Adiciona a agenda inicial sem duplicar reuniões já cadastradas."""
    rows = cached_get_all_values(REUNIOES_WORKSHEET_NAME, worksheet, force=True)
    existing_ids = {sheet_cell(row, 0) for row in rows[1:]}
    missing = [row for row in DEFAULT_REUNIOES if row[0] not in existing_ids]
    if missing:
        worksheet.append_rows(missing, value_input_option="RAW")
        invalidate_values_cache(REUNIOES_WORKSHEET_NAME)


def get_reunioes_worksheet():
    worksheet = get_or_create_worksheet(REUNIOES_WORKSHEET_NAME, REUNIOES_HEADERS)
    seed_default_reunioes(worksheet)
    return worksheet


def legacy_flyers_payloads():
    """Lê uma aba antiga chamada Flyers, quando existir, sem exigir um esquema rígido."""
    if normalized_lookup_key(FAMILIAS_WORKSHEET_NAME) == normalized_lookup_key(LEGACY_FLYERS_WORKSHEET_NAME):
        return []

    try:
        spreadsheet = get_or_create_spreadsheet()
        worksheet = spreadsheet.worksheet(LEGACY_FLYERS_WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        return []
    except Exception as error:
        log_info(f"Não foi possível verificar a aba antiga de Flyers: {error}")
        return []

    rows = cached_get_all_values(LEGACY_FLYERS_WORKSHEET_NAME, worksheet)
    if len(rows) <= 1:
        return []

    normalized_headers = [normalized_lookup_key(header) for header in rows[0]]

    def find_column(*aliases):
        alias_keys = {normalized_lookup_key(alias) for alias in aliases}
        for index, header in enumerate(normalized_headers):
            if header in alias_keys:
                return index
        return None

    name_index = find_column("nome", "organização", "organizacao", "facção", "faccao", "família", "familia", "gangue", "fac")
    if name_index is None:
        return []

    icon_index = find_column("icone", "ícone", "emoji")
    market_index = find_column("mercado", "status", "situação", "situacao")
    sale_index = find_column("preco_venda_para_familia", "preço de venda", "preco de venda", "valor venda", "venda para eles")
    purchase_index = find_column("preco_compra_da_familia", "preço de compra", "preco de compra", "valor compra", "compra deles")
    flyer_index = find_column("flyer_url", "flyer", "imagem", "imagem_url", "url")
    contact_index = find_column("contato", "telefone", "discord", "responsavel", "responsável")
    observation_index = find_column("observacao", "observação", "descricao", "descrição")

    payloads = []
    for row in rows[1:]:
        name = canonical_family_name(sheet_cell(row, name_index))
        if not normalized_lookup_key(name):
            continue
        payloads.append({
            "nome": name,
            "icone": sheet_cell(row, icon_index) if icon_index is not None else "",
            "mercado": sheet_cell(row, market_index) if market_index is not None else "Aberto",
            "preco_venda_para_familia": sheet_cell(row, sale_index) if sale_index is not None else "",
            "preco_compra_da_familia": sheet_cell(row, purchase_index) if purchase_index is not None else "",
            "flyer_url": sheet_cell(row, flyer_index) if flyer_index is not None else "",
            "contato": sheet_cell(row, contact_index) if contact_index is not None else "",
            "observacao": sheet_cell(row, observation_index) if observation_index is not None else "Importada da antiga aba Flyers.",
        })
    return payloads


def build_family_row(data, registro_id=None, criado_em=None):
    now = format_timestamp()
    name = canonical_family_name(data.get("nome"))
    return [
        registro_id or family_id_from_name(name),
        criado_em or now,
        name,
        str(data.get("icone") or "").strip(),
        normalize_market_status(data.get("mercado")),
        str(data.get("preco_venda_para_familia") or "").strip(),
        str(data.get("preco_compra_da_familia") or "").strip(),
        str(data.get("flyer_url") or "").strip(),
        str(data.get("observacao") or "").strip(),
        now,
        str(data.get("contato") or "").strip(),
        "Sim" if normalize_flag(data.get("flyer_oculto")) else "Não",
    ]


def ensure_familias_ready(worksheet, force=False):
    # Serializa a manutenção para impedir cadastros duplicados em acessos simultâneos.
    with _sheets_lock:
        return _ensure_familias_ready_locked(worksheet, force=force)


def _ensure_familias_ready_locked(worksheet, force=False):
    now = time.time()
    with _sheets_lock:
        if not force and now - _familias_maintenance_cache.get("checked_at", 0) < SHEETS_META_MAINTENANCE_SECONDS:
            return

    rows = cached_get_all_values(FAMILIAS_WORKSHEET_NAME, worksheet, force=True)
    existing = {}
    duplicate_indexes = []
    changed = False

    for row_index, row in enumerate(rows[1:], start=2):
        name = canonical_family_name(sheet_cell(row, 2))
        key = normalized_lookup_key(name)
        if not key:
            continue
        if key in existing:
            duplicate_indexes.append(row_index)
            continue
        existing[key] = (row_index, row)
        if name != sheet_cell(row, 2):
            worksheet.update_cell(row_index, 3, name)
            changed = True

    # Remove duplicatas antigas, como Bandoleros + Cartel, preservando o primeiro cadastro.
    for row_index in reversed(duplicate_indexes):
        worksheet.delete_rows(row_index)
        changed = True

    additions = []

    # Importa cadastros da antiga aba Flyers quando ela existir.
    for legacy in legacy_flyers_payloads():
        key = normalized_lookup_key(legacy.get("nome"))
        if not key or key in existing:
            continue
        additions.append(build_family_row(legacy))
        existing[key] = (None, additions[-1])

    for default in DEFAULT_FAMILIAS:
        key = normalized_lookup_key(default["nome"])
        if key not in existing:
            additions.append(build_family_row(default))
            existing[key] = (None, additions[-1])

    # Toda reunião já finalizada também deve aparecer em Famílias.
    reunioes_worksheet = get_reunioes_worksheet()
    reunioes_rows = cached_get_all_values(REUNIOES_WORKSHEET_NAME, reunioes_worksheet)
    for reuniao_row in reunioes_rows[1:]:
        if str(sheet_cell(reuniao_row, 9)).strip().lower() != "finalizada":
            continue
        name = canonical_family_name(sheet_cell(reuniao_row, 3))
        key = normalized_lookup_key(name)
        if not key or key in existing:
            continue
        additions.append(build_family_row({
            "nome": name,
            "icone": sheet_cell(reuniao_row, 4),
            "mercado": "Aberto",
            "observacao": "Incluída automaticamente após a finalização de uma reunião.",
        }))
        existing[key] = (None, additions[-1])

    if additions:
        worksheet.append_rows(additions, value_input_option="RAW")
        changed = True

    if changed:
        invalidate_values_cache(FAMILIAS_WORKSHEET_NAME)

    with _sheets_lock:
        _familias_maintenance_cache["checked_at"] = time.time()


def upsert_family_from_meeting(name, icon=""):
    canonical_name = canonical_family_name(name)
    key = normalized_lookup_key(canonical_name)
    if not key:
        return None, False

    with _sheets_lock:
        worksheet = get_familias_worksheet(ensure_ready=False)
        rows = cached_get_all_values(FAMILIAS_WORKSHEET_NAME, worksheet, force=True)
        for row_index, row in enumerate(rows[1:], start=2):
            if normalized_lookup_key(canonical_family_name(sheet_cell(row, 2))) != key:
                continue
            padded = list(row[:len(FAMILIAS_HEADERS)]) + [""] * max(0, len(FAMILIAS_HEADERS) - len(row))
            changed = False
            if padded[2] != canonical_name:
                padded[2] = canonical_name
                changed = True
            if icon and not str(padded[3]).strip():
                padded[3] = str(icon).strip()
                changed = True
            if changed:
                padded[9] = format_timestamp()
                worksheet.update(f"A{row_index}:L{row_index}", [padded[:len(FAMILIAS_HEADERS)]], value_input_option="RAW")
                invalidate_values_cache(FAMILIAS_WORKSHEET_NAME)
            return padded[0] or family_id_from_name(canonical_name), False

        row = build_family_row({
            "nome": canonical_name,
            "icone": icon,
            "mercado": "Aberto",
            "observacao": "Incluída automaticamente após a finalização de uma reunião.",
        })
        worksheet.append_row(row, value_input_option="RAW")
        invalidate_values_cache(FAMILIAS_WORKSHEET_NAME)
        return row[0], True


def get_metas_worksheet():
    worksheet = get_or_create_worksheet(METAS_WORKSHEET_NAME, META_HEADERS)
    ensure_metas_ready(worksheet)
    return worksheet


def get_historico_metas_worksheet():
    return get_or_create_worksheet(HISTORICO_METAS_WORKSHEET_NAME, META_HISTORY_HEADERS)


def ensure_metas_ready(worksheet, force=False):
    now = time.time()
    with _sheets_lock:
        if not force and now - _meta_maintenance_cache.get("checked_at", 0) < SHEETS_META_MAINTENANCE_SECONDS:
            return
        _meta_maintenance_cache["checked_at"] = now

    seed_metas_if_empty(worksheet)
    ensure_metas_schema(worksheet)
    ensure_current_meta_week(worksheet)


def seed_metas_if_empty(worksheet):
    try:
        rows = cached_get_all_values(worksheet.title, worksheet, force=True)
        if len(rows) > 1:
            return

        agora = format_timestamp()
        week = meta_week_payload()
        seed_rows = [
            [f"META-{index:03d}", nome, "Não", agora, week["semana_inicio"], week["semana_fim"], "Não"]
            for index, nome in enumerate(DEFAULT_META_NAMES, start=1)
        ]
        if seed_rows:
            worksheet.append_rows(seed_rows, value_input_option="RAW")
            invalidate_values_cache(worksheet.title)
            log_info(f"Aba de metas populada com {len(seed_rows)} nomes iniciais.")
    except Exception as e:
        log_error("Erro ao popular aba de metas", e)
        raise


def ensure_metas_schema(worksheet):
    rows = cached_get_all_values(worksheet.title, worksheet, force=True)
    if len(rows) <= 1:
        return

    week = meta_week_payload()
    updated_rows = []
    changed = False

    for index, row in enumerate(rows[1:], start=1):
        padded = list(row[:len(META_HEADERS)]) + [""] * max(0, len(META_HEADERS) - len(row))
        nome = str(padded[1] or "").strip() if len(padded) > 1 else ""
        if not nome:
            updated_rows.append(padded[:len(META_HEADERS)])
            continue

        if not str(padded[0] or "").strip():
            padded[0] = f"META-{index:03d}"
            changed = True
        if validate_yes_no(padded[2]) is None:
            padded[2] = "Não"
            changed = True
        else:
            normalized = validate_yes_no(padded[2])
            if padded[2] != normalized:
                padded[2] = normalized
                changed = True
        if not str(padded[3] or "").strip():
            padded[3] = format_timestamp()
            changed = True
        if not str(padded[4] or "").strip():
            padded[4] = week["semana_inicio"]
            changed = True
        if not str(padded[5] or "").strip():
            padded[5] = week["semana_fim"]
            changed = True
        if validate_yes_no(padded[6]) is None:
            padded[6] = "Não"
            changed = True

        updated_rows.append(padded[:len(META_HEADERS)])

    if changed and updated_rows:
        worksheet.update(f"A2:G{len(updated_rows) + 1}", updated_rows, value_input_option="RAW")
        invalidate_values_cache(worksheet.title)
        log_info("Aba de metas atualizada para o formato semanal.")


def ensure_current_meta_week(worksheet):
    rows = cached_get_all_values(worksheet.title, worksheet, force=True)
    registros = active_meta_rows(rows)
    if not registros:
        return

    stored_start = parse_date_br(registros[0][4] if len(registros[0]) > 4 else "")
    current_start = meta_week_start()

    if stored_start and stored_start < current_start:
        log_info("Virada semanal detectada. Salvando histórico e resetando metas.")
        archive_and_reset_metas(worksheet, target_start_date=current_start)


def archive_and_reset_metas(worksheet, target_start_date=None):
    rows = cached_get_all_values(worksheet.title, worksheet, force=True)
    registros = active_meta_rows(rows)
    if not registros:
        return meta_week_payload(target_start_date or meta_week_start())

    fechado_em = format_timestamp()
    history_rows = []
    for row in registros:
        semana_inicio = row[4] if len(row) > 4 and row[4] else meta_week_payload()["semana_inicio"]
        semana_fim = row[5] if len(row) > 5 and row[5] else meta_week_payload()["semana_fim"]
        history_rows.append([
            semana_inicio,
            semana_fim,
            fechado_em,
            row[0] if len(row) > 0 else "",
            row[1] if len(row) > 1 else "",
            validate_yes_no(row[2] if len(row) > 2 else "Não") or "Não",
            row[3] if len(row) > 3 else "",
        ])

    if history_rows:
        historico = get_historico_metas_worksheet()
        historico.append_rows(history_rows, value_input_option="RAW")
        invalidate_values_cache(historico.title)

    if target_start_date is None:
        current_stored_start = parse_date_br(registros[0][4] if len(registros[0]) > 4 else "") or meta_week_start()
        target_start_date = current_stored_start + timedelta(days=7)

    week = meta_week_payload(target_start_date)
    reset_rows = []
    for row in registros:
        reset_rows.append([
            row[0] if len(row) > 0 and row[0] else f"META-{len(reset_rows) + 1:03d}",
            row[1] if len(row) > 1 else "",
            "Não",
            fechado_em,
            week["semana_inicio"],
            week["semana_fim"],
            "Não",
        ])

    worksheet.update(f"A2:G{len(reset_rows) + 1}", reset_rows, value_input_option="RAW")
    invalidate_values_cache(worksheet.title)
    return week


def maybe_close_week_if_all_confirmed(worksheet, rows=None):
    rows = rows if rows is not None else cached_get_all_values(worksheet.title, worksheet, force=True)
    registros = active_meta_rows(rows)
    if not registros:
        return False, None

    all_confirmed = all(
        len(row) > 6 and str(row[6]).strip().lower() in ["sim", "s"]
        for row in registros
    )
    if not all_confirmed:
        return False, None

    current_start = parse_date_br(registros[0][4] if len(registros[0]) > 4 else "") or meta_week_start()
    next_week = archive_and_reset_metas(worksheet, target_start_date=current_start + timedelta(days=7))
    return True, next_week


def validate_yes_no(value):
    normalized = str(value or "").strip().lower()
    if normalized in ["sim", "s"]:
        return "Sim"
    if normalized in ["não", "nao", "n"]:
        return "Não"
    return None


def find_row_by_id(worksheet, registro_id):
    rows = cached_get_all_values(worksheet.title, worksheet, force=True)
    for index, row in enumerate(rows[1:], start=2):
        if len(row) > 0 and row[0] == registro_id:
            return index, row
    return None, None


def generate_record_id(prefix):
    timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    return f"{prefix}-{timestamp_ms}-{secrets.token_hex(2).upper()}"


def sheet_cell(row, index, default=""):
    return row[index] if len(row) > index else default


def row_to_dict(row, headers):
    return {field: sheet_cell(row, index) for index, field in enumerate(headers)}


def latest_data_rows(rows, limit=LIST_LIMIT):
    data_rows = rows[1:][-limit:] if len(rows) > 1 else []
    data_rows.reverse()
    return data_rows


def financial_summary(rows, value_index=7):
    registros = rows[1:] if len(rows) > 1 else []
    total = 0.0

    for row in registros:
        try:
            total += float(sheet_cell(row, value_index, 0) or 0)
        except (ValueError, TypeError):
            pass

    return {
        "total_registros": len(registros),
        "valor_movimentado": round(total, 2),
        "ultimo_registro": sheet_cell(registros[-1], 1, "--") if registros else "--",
    }


def encomendas_summary(rows):
    registros = rows[1:] if len(rows) > 1 else []
    resumo = financial_summary(rows, value_index=4)
    entregues = sum(1 for row in registros if str(sheet_cell(row, 7)).strip().lower() == "sim")
    resumo.update({
        "entregues": entregues,
        "pendentes": max(len(registros) - entregues, 0),
    })
    return resumo


def active_meta_rows(rows):
    return [row for row in rows[1:] if len(row) > 1 and str(row[1]).strip()]


def validate_numeric_fields(data, required_fields):
    if not isinstance(data, dict):
        return False, "JSON inválido."

    missing = [field for field in required_fields if str(data.get(field, "")).strip() == ""]
    if missing:
        return False, f"Campos obrigatórios ausentes: {', '.join(missing)}"

    try:
        quantidade = int(data["quantidade"])
        valor_unitario = float(data["valor_unitario"])
    except (ValueError, TypeError):
        return False, "Quantidade e valor unitário devem ser numéricos."

    if quantidade <= 0:
        return False, "Quantidade deve ser maior que zero."
    if quantidade > MAX_QUANTITY:
        return False, f"Quantidade deve ser no máximo {MAX_QUANTITY}."
    if valor_unitario < 0:
        return False, "Valor unitário não pode ser negativo."
    if valor_unitario > MAX_MONEY_VALUE:
        return False, "Valor unitário muito alto."

    return True, ""


def normalize_compra(row):
    return row_to_dict(row, COMPRAS_HEADERS)


def normalize_venda(row):
    return row_to_dict(row, VENDAS_HEADERS)


def normalize_encomenda(row):
    item = row_to_dict(row, ENCOMENDAS_HEADERS)
    item["entregue"] = validate_yes_no(item.get("entregue")) or "Não"
    item["itens"] = parse_encomenda_items_json(item.get("itens_json"))
    item.pop("itens_json", None)
    return item


ENCOMENDA_ITEM_PATTERN = re.compile(r"^\s*(\d+)(?:\s*x\s*|\s+)(.+?)\s*$", re.IGNORECASE)


def parse_encomenda_items_json(raw_value):
    if not raw_value:
        return []
    try:
        raw_items = json.loads(str(raw_value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(raw_items, list):
        return []

    items = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        try:
            quantidade = int(raw_item.get("quantidade") or 0)
            valor_unitario = float(raw_item.get("valor_unitario") or 0)
        except (TypeError, ValueError):
            continue
        produto = str(raw_item.get("produto") or "").strip()
        if not produto or quantidade <= 0 or quantidade > MAX_QUANTITY or valor_unitario < 0:
            continue
        items.append({
            "produto": produto,
            "quantidade": quantidade,
            "valor_unitario": round(valor_unitario, 2),
            "valor_total": round(quantidade * valor_unitario, 2),
        })
    return items


def validate_encomenda_items(raw_items):
    if not isinstance(raw_items, list):
        raise ValueError("Os itens da encomenda são inválidos.")

    items = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            raise ValueError("Um dos itens da encomenda é inválido.")
        try:
            quantidade_num = float(raw_item.get("quantidade") or 0)
            valor_unitario = float(raw_item.get("valor_unitario") or 0)
        except (TypeError, ValueError):
            raise ValueError("Quantidade e valor dos produtos devem ser numéricos.")

        if not quantidade_num.is_integer():
            raise ValueError("A quantidade dos produtos deve ser um número inteiro.")
        quantidade = int(quantidade_num)

        # Linhas com quantidade zero são apenas campos ainda não usados no formulário.
        if quantidade == 0:
            continue
        if quantidade < 0 or quantidade > MAX_QUANTITY:
            raise ValueError(f"A quantidade deve ficar entre 1 e {MAX_QUANTITY}.")
        if valor_unitario < 0 or valor_unitario > MAX_MONEY_VALUE:
            raise ValueError("O valor unitário informado é inválido.")

        produto = clean_text(raw_item.get("produto"), "Produto", required=True)
        valor_total = round(quantidade * valor_unitario, 2)
        if valor_total > MAX_MONEY_VALUE:
            raise ValueError("O valor total de um dos produtos é muito alto.")
        items.append({
            "produto": produto,
            "quantidade": quantidade,
            "valor_unitario": round(valor_unitario, 2),
            "valor_total": valor_total,
        })

    if not items:
        raise ValueError("Informe a quantidade de pelo menos um produto: L85 ou Seringa.")

    total = round(sum(item["valor_total"] for item in items), 2)
    if total > MAX_MONEY_VALUE:
        raise ValueError("Valor total da encomenda muito alto.")
    return items, total


def parse_encomenda_item(item_text):
    """Extrai quantidade e produto quando o pedido começa com um número.

    Ex.: "15 L85" ou "15x L85" vira quantidade 15 e produto "L85".
    Quando não há quantidade explícita, a venda é registrada com quantidade 1.
    """
    text = str(item_text or "").strip()
    match = ENCOMENDA_ITEM_PATTERN.match(text)
    if not match:
        return 1, text

    try:
        quantidade = int(match.group(1))
    except (TypeError, ValueError):
        return 1, text

    produto = match.group(2).strip()
    if quantidade <= 0 or quantidade > MAX_QUANTITY or not produto:
        return 1, text
    return quantidade, produto


def venda_id_from_encomenda(encomenda_id):
    """Gera um ID estável para impedir venda duplicada em uma nova tentativa."""
    return f"KKSV-ENC-{str(encomenda_id or '').strip()}"


def build_venda_row_from_encomenda(item, entregue_em=None):
    quantidade, produto = parse_encomenda_item(item.get("o_que_pediu"))
    valor_total = round(float(item.get("valor") or 0), 2)
    valor_unitario = round(valor_total / quantidade, 2) if quantidade else valor_total
    encomenda_id = str(item.get("id") or "").strip()
    prazo = str(item.get("para_quando") or "").strip()
    observacao_original = str(item.get("observacao") or "").strip()

    detalhes = [f"Convertida da encomenda {encomenda_id}."]
    if prazo:
        detalhes.append(f"Prazo combinado: {prazo}.")
    observacao = " ".join(filter(None, [observacao_original, *detalhes]))
    observacao = observacao[:MAX_OBSERVATION_LENGTH]

    return [
        venda_id_from_encomenda(encomenda_id),
        entregue_em or format_timestamp(),
        produto,
        str(item.get("quem_pediu") or "").strip(),
        str(item.get("quem_negociou") or "").strip(),
        valor_unitario,
        quantidade,
        valor_total,
        observacao,
    ]


def build_venda_rows_from_encomenda(item, entregue_em=None):
    """Converte uma encomenda em uma ou mais vendas sem perder os itens combinados."""
    items = parse_encomenda_items_json(item.get("itens_json"))
    if not items:
        return [build_venda_row_from_encomenda(item, entregue_em=entregue_em)]

    encomenda_id = str(item.get("id") or "").strip()
    prazo = str(item.get("para_quando") or "").strip()
    observacao_original = str(item.get("observacao") or "").strip()
    rows = []
    for index, order_item in enumerate(items, start=1):
        detalhes = [f"Convertida da encomenda {encomenda_id} (item {index}/{len(items)})."]
        if prazo:
            detalhes.append(f"Prazo combinado: {prazo}.")
        observacao = " ".join(filter(None, [observacao_original, *detalhes]))[:MAX_OBSERVATION_LENGTH]
        rows.append([
            f"{venda_id_from_encomenda(encomenda_id)}-{index}",
            entregue_em or format_timestamp(),
            order_item["produto"],
            str(item.get("quem_pediu") or "").strip(),
            str(item.get("quem_negociou") or "").strip(),
            order_item["valor_unitario"],
            order_item["quantidade"],
            order_item["valor_total"],
            observacao,
        ])
    return rows


def worksheet_has_record_id(worksheet, registro_id):
    rows = cached_get_all_values(worksheet.title, worksheet, force=True)
    return any(sheet_cell(row, 0) == registro_id for row in rows[1:])


def normalize_family(row):
    item = row_to_dict(row, FAMILIAS_HEADERS)
    item["nome"] = canonical_family_name(item.get("nome"))
    item["mercado"] = normalize_market_status(item.get("mercado"))
    item["flyer_oculto"] = normalize_flag(item.get("flyer_oculto"))
    return item


def normalize_reuniao(row):
    item = row_to_dict(row, REUNIOES_HEADERS)
    item["gangue"] = canonical_family_name(item.get("gangue"))
    raw_status = str(item.get("status", "")).strip().lower()
    if raw_status == "finalizada":
        item["status"] = "Finalizada"
    elif raw_status == "cancelada":
        item["status"] = "Cancelada"
    elif raw_status in {"aguardando confirmação", "aguardando confirmacao", "a confirmar"}:
        item["status"] = "Aguardando confirmação"
    else:
        item["status"] = "Agendada"
    return item


def normalize_meta(row):
    confirmado = str(sheet_cell(row, 6, "Não")).strip().lower() in ["sim", "s"]
    return {
        "id": sheet_cell(row, 0),
        "nome": sheet_cell(row, 1),
        "pago": validate_yes_no(sheet_cell(row, 2, "Não")) or "Não",
        "atualizado_em": sheet_cell(row, 3),
        "semana_inicio": sheet_cell(row, 4),
        "semana_fim": sheet_cell(row, 5),
        "confirmado": confirmado,
    }


@app.get("/")
@require_login
def home():
    user = get_current_user()
    if user and user.get("role") == "member":
        return redirect(url_for("meta_room"))
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if get_current_user():
        return redirect(url_for("home"))

    error = None
    next_url = safe_next_url(request.args.get("next"))

    if request.method == "POST":
        csrf_error = csrf_error_if_invalid()
        if csrf_error:
            error = "Sessão de login expirada. Atualize a página e tente novamente."
            return render_template("login.html", error=error, next_url=next_url), 403

        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        key = login_attempt_key(username)

        if is_login_limited(key):
            error = "Muitas tentativas de login. Aguarde alguns minutos e tente novamente."
            return render_template("login.html", error=error, next_url=next_url), 429

        user = AUTH_USERS.get(username) or get_meta_member_by_username(username)

        if user and verify_password(password, user["password_hash"]):
            session.clear()
            session.permanent = True
            session["username"] = username
            get_csrf_token()
            clear_login_attempts(key)
            if user.get("role") == "member":
                return redirect(url_for("meta_room"))
            return redirect(safe_next_url(request.form.get("next") or next_url))

        record_failed_login(key)
        error = "Usuário ou senha inválidos."

    return render_template("login.html", error=error, next_url=next_url)


@app.route("/logout", methods=["GET", "POST"])
def logout():
    if request.method == "POST":
        csrf_error = csrf_error_if_invalid()
        if csrf_error:
            return csrf_error
    session.clear()
    return redirect(url_for("login"))


@app.get("/api/session")
@require_login
def current_session():
    return jsonify({"ok": True, "user": get_current_user()})


@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "kokusai-system",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })


def build_meta_room_payload(user_id):
    member = get_meta_member_by_id(user_id)
    if not member:
        raise ValueError("Membro não encontrado.")
    submission = get_current_meta_submission(user_id)
    photos = get_meta_photos(submission["id"])
    history = get_meta_room_history(user_id)
    return {
        "member": {
            "id": member["id"],
            "username": member["username"],
            "display_name": member["display_name"],
        },
        "submission": submission,
        "photos": [serialize_meta_photo(photo) for photo in photos],
        "history": history,
        "limits": {
            "max_photos": META_MAX_PHOTOS_PER_WEEK,
            "max_file_mb": round(META_MAX_FILE_BYTES / (1024 * 1024)),
        },
    }


@app.get("/minha-meta")
@require_member
def meta_room():
    return render_template("meta_room.html")


@app.get("/api/meta-room")
@require_member
def current_meta_room():
    try:
        user = get_current_user()
        return jsonify(build_meta_room_payload(user["user_id"]))
    except Exception as error:
        log_error("Falha ao carregar sala individual de meta", error)
        return error_response(str(error))


@app.post("/api/meta-room/photos")
@require_member
def upload_meta_room_photo():
    try:
        user = get_current_user()
        submission = get_current_meta_submission(user["user_id"])
        if submission["status"] == "Pago":
            return error_response("A meta desta semana já foi marcada como paga e está bloqueada para novos envios.", 409)

        current_photos = get_meta_photos(submission["id"])
        if len(current_photos) >= META_MAX_PHOTOS_PER_WEEK:
            return error_response(f"Limite de {META_MAX_PHOTOS_PER_WEEK} fotos por semana atingido.", 400)

        upload = request.files.get("photo")
        stored = store_meta_photo(upload, user["user_id"], submission["week_start"])
        photo_id = f"META-PHOTO-{uuid.uuid4().hex}"
        created_at = format_timestamp()
        try:
            meta_execute(
                """
                INSERT INTO meta_photos (id, submission_id, user_id, object_key, original_name, content_type, size_bytes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    photo_id, submission["id"], user["user_id"], stored["object_key"], stored["original_name"],
                    stored["content_type"], stored["size_bytes"], created_at,
                ),
            )
        except Exception:
            delete_meta_photo_object(stored["object_key"])
            raise

        meta_execute(
            "UPDATE meta_submissions SET status = 'Enviado', submitted_at = ? WHERE id = ?",
            (created_at, submission["id"]),
        )
        return jsonify({"ok": True, "message": "Foto enviada para sua sala com sucesso.", "photo_id": photo_id}), 201
    except ValueError as error:
        return error_response(str(error), 400)
    except Exception as error:
        log_error("Falha no upload da sala de meta", error)
        return error_response(str(error))


@app.delete("/api/meta-room/photos/<photo_id>")
@require_member
def delete_meta_room_photo(photo_id):
    try:
        user = get_current_user()
        photo = meta_query_one(
            """
            SELECT p.id, p.object_key, p.submission_id, p.user_id, s.status, s.week_start
            FROM meta_photos p JOIN meta_submissions s ON s.id = p.submission_id
            WHERE p.id = ? AND p.user_id = ?
            """,
            (photo_id, user["user_id"]),
        )
        if not photo:
            return error_response("Foto não encontrada na sua sala.", 404)
        current_week = meta_week_payload()["semana_inicio"]
        if photo["week_start"] != current_week:
            return error_response("Fotos de semanas anteriores fazem parte do histórico e não podem ser removidas.", 409)
        if photo["status"] == "Pago":
            return error_response("Esta semana já foi marcada como paga.", 409)

        delete_meta_photo_object(photo["object_key"])
        meta_execute("DELETE FROM meta_photos WHERE id = ?", (photo_id,))
        remaining = meta_query_one(
            "SELECT COUNT(*) AS total FROM meta_photos WHERE submission_id = ?",
            (photo["submission_id"],),
        )
        if int(remaining["total"] or 0) == 0:
            meta_execute(
                "UPDATE meta_submissions SET status = 'Pendente', submitted_at = NULL WHERE id = ?",
                (photo["submission_id"],),
            )
        return jsonify({"ok": True, "message": "Foto removida da semana atual."})
    except Exception as error:
        log_error("Falha ao remover foto da sala de meta", error)
        return error_response(str(error))


@app.get("/meta/photo/<photo_id>")
@require_login
def meta_photo_file(photo_id):
    try:
        photo = meta_query_one(
            "SELECT id, user_id, object_key, content_type FROM meta_photos WHERE id = ?",
            (photo_id,),
        )
        if not photo:
            return error_response("Foto não encontrada.", 404)
        user = get_current_user()
        if user["role"] == "member" and photo["user_id"] != user.get("user_id"):
            return error_response("Você não tem acesso a esta foto.", 403)
        if user["role"] not in {"member", "admin"}:
            return error_response("Somente o dono da sala e o administrador podem acessar esta foto.", 403)
        if meta_bucket_configured():
            return redirect(meta_photo_access_url(photo))

        local_root = os.path.abspath(META_LOCAL_UPLOAD_DIR)
        local_path = os.path.abspath(os.path.join(META_LOCAL_UPLOAD_DIR, *photo["object_key"].split("/")))
        if not local_path.startswith(local_root + os.sep) or not os.path.isfile(local_path):
            return error_response("Arquivo da foto não encontrado.", 404)
        return send_file(local_path, mimetype=photo.get("content_type") or "image/webp")
    except Exception as error:
        log_error("Falha ao servir foto da sala de meta", error)
        return error_response(str(error))


@app.get("/api/meta-rooms")
@require_admin
def list_meta_rooms():
    try:
        week = ensure_current_meta_submissions()
        rooms = meta_query_all(
            """
            SELECT u.id AS user_id, u.username, u.display_name, s.id AS submission_id,
                   s.status, s.admin_note, s.submitted_at, s.reviewed_at,
                   (SELECT COUNT(*) FROM meta_photos p WHERE p.submission_id = s.id) AS photo_count
            FROM meta_users u
            JOIN meta_submissions s ON s.user_id = u.id AND s.week_start = ?
            WHERE u.role = 'member' AND u.active = 1
            ORDER BY u.display_name ASC
            """,
            (week["semana_inicio"],),
        )
        return jsonify({"week": week, "rooms": rooms})
    except Exception as error:
        log_error("Falha ao listar salas de meta", error)
        return error_response(str(error))


@app.get("/api/meta-rooms/<user_id>")
@require_admin
def admin_meta_room_detail(user_id):
    try:
        return jsonify(build_meta_room_payload(user_id))
    except ValueError as error:
        return error_response(str(error), 404)
    except Exception as error:
        log_error("Falha ao abrir sala de meta pelo admin", error)
        return error_response(str(error))


@app.post("/api/meta-rooms/<submission_id>/status")
@require_admin
def review_meta_room(submission_id):
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return error_response("JSON inválido.", 400)
        status = str(data.get("status") or "").strip().capitalize()
        if status not in {"Pago", "Pendente", "Recusado"}:
            return error_response("Status deve ser Pago, Pendente ou Recusado.", 400)

        submission = meta_query_one(
            "SELECT id, user_id FROM meta_submissions WHERE id = ?",
            (submission_id,),
        )
        if not submission:
            return error_response("Sala semanal não encontrada.", 404)
        if status == "Pago":
            photo_count = meta_query_one(
                "SELECT COUNT(*) AS total FROM meta_photos WHERE submission_id = ?",
                (submission_id,),
            )
            if int(photo_count["total"] or 0) == 0:
                return error_response("Não é possível marcar como paga sem nenhuma foto enviada.", 400)

        note = clean_text(data.get("admin_note"), "Observação do admin", max_length=500, required=False)
        reviewed_at = format_timestamp()
        admin = get_current_user()
        meta_execute(
            """
            UPDATE meta_submissions
            SET status = ?, admin_note = ?, reviewed_at = ?, reviewed_by = ?
            WHERE id = ?
            """,
            (status, note, reviewed_at, admin["username"], submission_id),
        )
        return jsonify({
            "ok": True,
            "message": f"Meta marcada como {status}.",
            "status": status,
            "reviewed_at": reviewed_at,
        })
    except ValueError as error:
        return error_response(str(error), 400)
    except Exception as error:
        log_error("Falha ao revisar sala de meta", error)
        return error_response(str(error))


@app.get("/api/debug-config")
@require_admin
def debug_config():
    if os.getenv("ENABLE_DEBUG_CONFIG", "false").lower() != "true":
        return error_response("Rota de diagnóstico desativada em produção.", 404)

    credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
    client_email = None
    if credentials_json:
        try:
            client_email = json.loads(credentials_json).get("client_email")
        except Exception:
            client_email = "JSON inválido"

    return jsonify({
        "ok": True,
        "spreadsheet_id_configured": bool(SPREADSHEET_ID),
        "sheet_name": SHEET_NAME,
        "compras_worksheet": COMPRAS_WORKSHEET_NAME,
        "vendas_worksheet": VENDAS_WORKSHEET_NAME,
        "encomendas_worksheet": ENCOMENDAS_WORKSHEET_NAME,
        "metas_worksheet": METAS_WORKSHEET_NAME,
        "historico_metas_worksheet": HISTORICO_METAS_WORKSHEET_NAME,
        "meta_database_configured": bool(META_DATABASE_URL) or not IS_RAILWAY,
        "meta_bucket_configured": meta_bucket_configured(),
        "credentials_present": bool(credentials_json),
        "service_account_email": client_email,
    })


@app.get("/api/compras")
@require_staff
def list_compras():
    try:
        worksheet = get_compras_worksheet()
        rows = cached_get_all_values(COMPRAS_WORKSHEET_NAME, worksheet)
        return jsonify([normalize_compra(row) for row in latest_data_rows(rows)])

    except Exception as e:
        log_error("Falha em /api/compras [GET]", e)
        return error_response(str(e))


@app.post("/api/compras")
@require_admin
def create_compra():
    try:
        data = request.get_json(silent=True)
        ok, message = validate_numeric_fields(
            data,
            ["produto", "quem_pediu", "quem_vendeu", "valor_unitario", "quantidade"]
        )

        if not ok:
            return error_response(message, 400)

        try:
            produto = clean_text_field(data, "produto", "Produto")
            quem_pediu = clean_text_field(data, "quem_pediu", "Quem pediu")
            quem_vendeu = clean_text_field(data, "quem_vendeu", "Quem vendeu")
            observacao = clean_text_field(data, "observacao", "Observação", max_length=MAX_OBSERVATION_LENGTH, required=False)
        except ValueError as validation_error:
            return error_response(str(validation_error), 400)

        quantidade = int(data["quantidade"])
        valor_unitario = float(data["valor_unitario"])
        valor_total = round(quantidade * valor_unitario, 2)
        if valor_total > MAX_MONEY_VALUE:
            return error_response("Valor total muito alto.", 400)

        agora = format_timestamp()
        registro_id = generate_record_id("KKSC")

        worksheet = get_compras_worksheet()
        worksheet.append_row([
            registro_id,
            agora,
            produto,
            quem_pediu,
            quem_vendeu,
            valor_unitario,
            quantidade,
            valor_total,
            observacao,
        ], value_input_option="RAW")
        invalidate_values_cache(COMPRAS_WORKSHEET_NAME)
        log_info(f"Compra registrada com sucesso. ID={registro_id}")

        return jsonify({
            "ok": True,
            "message": "Compra salva com sucesso.",
            "id": registro_id,
            "valor_total": valor_total,
        }), 201

    except Exception as e:
        log_error("Falha em /api/compras [POST]", e)
        return error_response(str(e))


@app.get("/api/vendas")
@require_staff
def list_vendas():
    try:
        worksheet = get_vendas_worksheet()
        rows = cached_get_all_values(VENDAS_WORKSHEET_NAME, worksheet)
        return jsonify([normalize_venda(row) for row in latest_data_rows(rows)])

    except Exception as e:
        log_error("Falha em /api/vendas [GET]", e)
        return error_response(str(e))


@app.post("/api/vendas")
@require_admin
def create_venda():
    try:
        data = request.get_json(silent=True)
        ok, message = validate_numeric_fields(
            data,
            ["produto", "quem_compra", "quem_vende", "valor_unitario", "quantidade"]
        )

        if not ok:
            return error_response(message, 400)

        try:
            produto = clean_text_field(data, "produto", "Produto")
            quem_compra = clean_text_field(data, "quem_compra", "Quem compra")
            quem_vende = clean_text_field(data, "quem_vende", "Quem vende")
            observacao = clean_text_field(data, "observacao", "Observação", max_length=MAX_OBSERVATION_LENGTH, required=False)
        except ValueError as validation_error:
            return error_response(str(validation_error), 400)

        quantidade = int(data["quantidade"])
        valor_unitario = float(data["valor_unitario"])
        valor_total = round(quantidade * valor_unitario, 2)
        if valor_total > MAX_MONEY_VALUE:
            return error_response("Valor total muito alto.", 400)

        agora = format_timestamp()
        registro_id = generate_record_id("KKSV")

        worksheet = get_vendas_worksheet()
        worksheet.append_row([
            registro_id,
            agora,
            produto,
            quem_compra,
            quem_vende,
            valor_unitario,
            quantidade,
            valor_total,
            observacao,
        ], value_input_option="RAW")
        invalidate_values_cache(VENDAS_WORKSHEET_NAME)
        log_info(f"Venda registrada com sucesso. ID={registro_id}")

        return jsonify({
            "ok": True,
            "message": "Venda salva com sucesso.",
            "id": registro_id,
            "valor_total": valor_total,
        }), 201

    except Exception as e:
        log_error("Falha em /api/vendas [POST]", e)
        return error_response(str(e))


@app.get("/api/resumo")
@require_staff
def resumo_compras():
    try:
        worksheet = get_compras_worksheet()
        rows = cached_get_all_values(COMPRAS_WORKSHEET_NAME, worksheet)
        return jsonify(financial_summary(rows))

    except Exception as e:
        log_error("Falha em /api/resumo", e)
        return error_response(str(e))


@app.get("/api/resumo-vendas")
@require_staff
def resumo_vendas():
    try:
        worksheet = get_vendas_worksheet()
        rows = cached_get_all_values(VENDAS_WORKSHEET_NAME, worksheet)
        return jsonify(financial_summary(rows))

    except Exception as e:
        log_error("Falha em /api/resumo-vendas", e)
        return error_response(str(e))


@app.get("/api/encomendas")
@require_staff
def list_encomendas():
    try:
        worksheet = get_encomendas_worksheet()
        rows = cached_get_all_values(ENCOMENDAS_WORKSHEET_NAME, worksheet)
        return jsonify([normalize_encomenda(row) for row in latest_data_rows(rows)])

    except Exception as e:
        log_error("Falha em /api/encomendas [GET]", e)
        return error_response(str(e))


@app.post("/api/encomendas")
@require_admin
def create_encomenda():
    try:
        data = request.get_json(silent=True)
        required_fields = ["quem_pediu", "para_quando", "quem_negociou", "entregue"]

        if not isinstance(data, dict):
            return error_response("JSON inválido.", 400)

        missing = [field for field in required_fields if str(data.get(field, "")).strip() == ""]
        if missing:
            return error_response(f"Campos obrigatórios ausentes: {', '.join(missing)}", 400)

        itens_json = ""
        if isinstance(data.get("itens"), list):
            try:
                items, valor = validate_encomenda_items(data["itens"])
            except ValueError as validation_error:
                return error_response(str(validation_error), 400)
            o_que_pediu = " + ".join(f'{item["quantidade"]}x {item["produto"]}' for item in items)
            itens_json = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
        else:
            # Compatibilidade com registros/clientes antigos que enviam um item livre.
            if str(data.get("o_que_pediu", "")).strip() == "" or str(data.get("valor", "")).strip() == "":
                return error_response("Informe os itens e o valor da encomenda.", 400)
            try:
                valor = float(data["valor"])
            except (ValueError, TypeError):
                return error_response("O valor da encomenda deve ser numérico.", 400)
            if valor < 0:
                return error_response("O valor da encomenda não pode ser negativo.", 400)
            if valor > MAX_MONEY_VALUE:
                return error_response("Valor da encomenda muito alto.", 400)
            try:
                o_que_pediu = clean_text_field(data, "o_que_pediu", "O que pediu")
            except ValueError as validation_error:
                return error_response(str(validation_error), 400)

        entregue = str(data["entregue"]).strip().capitalize()
        if entregue not in ["Sim", "Não", "Nao"]:
            return error_response("O campo 'entregue' deve ser 'Sim' ou 'Não'.", 400)

        if entregue == "Nao":
            entregue = "Não"

        try:
            quem_pediu = clean_text_field(data, "quem_pediu", "Quem pediu")
            para_quando = clean_text_field(data, "para_quando", "Para quando")
            quem_negociou = clean_text_field(data, "quem_negociou", "Quem negociou")
            observacao = clean_text_field(data, "observacao", "Observação", max_length=MAX_OBSERVATION_LENGTH, required=False)
        except ValueError as validation_error:
            return error_response(str(validation_error), 400)

        agora = format_timestamp()
        registro_id = generate_record_id("KKSE")

        encomenda_item = {
            "id": registro_id,
            "data": agora,
            "quem_pediu": quem_pediu,
            "o_que_pediu": o_que_pediu,
            "valor": round(valor, 2),
            "para_quando": para_quando,
            "quem_negociou": quem_negociou,
            "entregue": entregue,
            "observacao": observacao,
            "entregue_em": agora if entregue == "Sim" else "",
            "itens_json": itens_json,
        }

        if entregue == "Sim":
            vendas_worksheet = get_vendas_worksheet()
            venda_rows = build_venda_rows_from_encomenda(encomenda_item, entregue_em=agora)
            for venda_row in venda_rows:
                vendas_worksheet.append_row(venda_row, value_input_option="RAW")
            invalidate_values_cache(VENDAS_WORKSHEET_NAME)
            log_info(f"Encomenda já entregue registrada diretamente em Vendas. ID={registro_id}")

            return jsonify({
                "ok": True,
                "message": "Encomenda entregue e registrada diretamente em Vendas.",
                "id": registro_id,
                "venda_id": venda_rows[0][0],
                "venda_ids": [row[0] for row in venda_rows],
                "valor": round(valor, 2),
                "moved_to_vendas": True,
            }), 201

        worksheet = get_encomendas_worksheet()
        worksheet.append_row([
            registro_id,
            agora,
            quem_pediu,
            o_que_pediu,
            round(valor, 2),
            para_quando,
            quem_negociou,
            entregue,
            observacao,
            "",
            itens_json,
        ], value_input_option="RAW")
        invalidate_values_cache(ENCOMENDAS_WORKSHEET_NAME)
        log_info(f"Encomenda registrada com sucesso. ID={registro_id}")

        return jsonify({
            "ok": True,
            "message": "Encomenda salva com sucesso.",
            "id": registro_id,
            "valor": round(valor, 2),
            "moved_to_vendas": False,
        }), 201

    except Exception as e:
        log_error("Falha em /api/encomendas [POST]", e)
        return error_response(str(e))


@app.post("/api/encomendas/<registro_id>/entrega")
@require_admin
def update_encomenda_entrega(registro_id):
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return error_response("JSON inválido.", 400)

        entregue = validate_yes_no(data.get("entregue"))
        if not entregue:
            return error_response("A entrega deve ser somente 'Sim' ou 'Não'.", 400)

        with _sheets_lock:
            worksheet = get_encomendas_worksheet()
            row_index, row = find_row_by_id(worksheet, registro_id)
            if not row_index:
                return error_response("Encomenda não encontrada.", 404)

            while len(row) < len(ENCOMENDAS_HEADERS):
                row.append("")

            if entregue == "Não":
                worksheet.update(
                    f"H{row_index}:J{row_index}",
                    [["Não", row[8] if len(row) > 8 else "", ""]],
                    value_input_option="RAW",
                )
                invalidate_values_cache(ENCOMENDAS_WORKSHEET_NAME)
                return jsonify({
                    "ok": True,
                    "message": "Encomenda mantida como pendente.",
                    "id": registro_id,
                    "entregue": "Não",
                    "entregue_em": "",
                    "moved_to_vendas": False,
                })

            entregue_em = str(row[9] or "").strip() or format_timestamp()
            encomenda_item = row_to_dict(row, ENCOMENDAS_HEADERS)
            encomenda_item["entregue"] = "Sim"
            encomenda_item["entregue_em"] = entregue_em

            vendas_worksheet = get_vendas_worksheet()
            venda_rows = build_venda_rows_from_encomenda(encomenda_item, entregue_em=entregue_em)
            venda_ids = [venda_row[0] for venda_row in venda_rows]

            # Se a gravação da venda tiver ocorrido e a exclusão da encomenda falhar,
            # uma nova tentativa apenas conclui a exclusão, sem duplicar a venda.
            existing_rows = cached_get_all_values(VENDAS_WORKSHEET_NAME, vendas_worksheet, force=True)
            existing_ids = {sheet_cell(existing_row, 0) for existing_row in existing_rows[1:]}
            for venda_row in venda_rows:
                if venda_row[0] not in existing_ids:
                    vendas_worksheet.append_row(venda_row, value_input_option="RAW")
                    existing_ids.add(venda_row[0])

            worksheet.delete_rows(row_index)
            invalidate_values_cache(ENCOMENDAS_WORKSHEET_NAME, VENDAS_WORKSHEET_NAME)
            log_info(f"Encomenda movida para Vendas. Encomenda={registro_id} Vendas={','.join(venda_ids)}")

        return jsonify({
            "ok": True,
            "message": "Entrega confirmada. A encomenda foi movida para Vendas.",
            "id": registro_id,
            "venda_id": venda_ids[0],
            "venda_ids": venda_ids,
            "entregue": "Sim",
            "entregue_em": entregue_em,
            "moved_to_vendas": True,
        })

    except Exception as e:
        log_error("Falha em /api/encomendas/<id>/entrega [POST]", e)
        return error_response(str(e))


@app.delete("/api/encomendas/<registro_id>")
@require_admin
def cancel_encomenda(registro_id):
    try:
        with _sheets_lock:
            worksheet = get_encomendas_worksheet()
            row_index, row = find_row_by_id(worksheet, registro_id)
            if not row_index:
                return error_response("Encomenda não encontrada.", 404)
            worksheet.delete_rows(row_index)
            invalidate_values_cache(ENCOMENDAS_WORKSHEET_NAME)
        return jsonify({
            "ok": True,
            "message": "Encomenda cancelada e apagada com sucesso.",
            "id": registro_id,
        })
    except Exception as e:
        log_error("Falha em /api/encomendas/<id> [DELETE]", e)
        return error_response(str(e))


@app.get("/api/resumo-encomendas")
@require_staff
def resumo_encomendas():
    try:
        worksheet = get_encomendas_worksheet()
        rows = cached_get_all_values(ENCOMENDAS_WORKSHEET_NAME, worksheet)
        return jsonify(encomendas_summary(rows))

    except Exception as e:
        log_error("Falha em /api/resumo-encomendas", e)
        return error_response(str(e))



@app.get("/api/reunioes")
@require_staff
def list_reunioes():
    try:
        worksheet = get_reunioes_worksheet()
        rows = cached_get_all_values(REUNIOES_WORKSHEET_NAME, worksheet)
        reunioes = [normalize_reuniao(row) for row in latest_data_rows(rows)]
        status_order = {"Agendada": 0, "Aguardando confirmação": 1, "Cancelada": 2, "Finalizada": 3}
        reunioes.sort(key=lambda item: (status_order.get(item.get("status"), 0), item.get("data", ""), item.get("horario", "")))
        return jsonify(reunioes)
    except Exception as e:
        log_error("Falha em /api/reunioes [GET]", e)
        return error_response(str(e))


@app.post("/api/reunioes")
@require_admin
def create_reuniao():
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return error_response("JSON inválido.", 400)

        try:
            titulo = clean_text_field(data, "titulo", "Título")
            gangue = canonical_family_name(clean_text_field(data, "gangue", "Gangue"))
            icone = clean_text_field(data, "icone", "Ícone", max_length=12)
            data_reuniao = clean_text_field(data, "data", "Data", max_length=10)
            horario = clean_text_field(data, "horario", "Horário", max_length=5)
            local = clean_text_field(data, "local", "Local", required=False)
            pauta = clean_text_field(data, "pauta", "Pauta", max_length=MAX_OBSERVATION_LENGTH, required=False)
        except ValueError as validation_error:
            return error_response(str(validation_error), 400)

        try:
            datetime.strptime(data_reuniao, "%Y-%m-%d")
            datetime.strptime(horario, "%H:%M")
        except ValueError:
            return error_response("Informe uma data e um horário válidos.", 400)

        registro_id = generate_record_id("KKSR")
        worksheet = get_reunioes_worksheet()
        worksheet.append_row([
            registro_id, format_timestamp(), titulo, gangue, icone, data_reuniao, horario,
            local, pauta, "Agendada", ""
        ], value_input_option="RAW")
        invalidate_values_cache(REUNIOES_WORKSHEET_NAME)
        return jsonify({"ok": True, "message": "Reunião agendada com sucesso.", "id": registro_id}), 201
    except Exception as e:
        log_error("Falha em /api/reunioes [POST]", e)
        return error_response(str(e))


@app.put("/api/reunioes/<registro_id>")
@require_admin
def update_reuniao(registro_id):
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return error_response("JSON inválido.", 400)

        try:
            titulo = clean_text_field(data, "titulo", "Título")
            gangue = canonical_family_name(clean_text_field(data, "gangue", "Gangue"))
            icone = clean_text_field(data, "icone", "Ícone", max_length=12)
            data_reuniao = clean_text_field(data, "data", "Data", max_length=10)
            horario = clean_text_field(data, "horario", "Horário", max_length=5)
            local = clean_text_field(data, "local", "Local", required=False)
            pauta = clean_text_field(data, "pauta", "Pauta", max_length=MAX_OBSERVATION_LENGTH, required=False)
        except ValueError as validation_error:
            return error_response(str(validation_error), 400)

        try:
            datetime.strptime(data_reuniao, "%Y-%m-%d")
            datetime.strptime(horario, "%H:%M")
        except ValueError:
            return error_response("Informe uma data e um horário válidos.", 400)

        worksheet = get_reunioes_worksheet()
        row_index, row = find_row_by_id(worksheet, registro_id)
        if not row_index:
            return error_response("Reunião não encontrada.", 404)

        while len(row) < len(REUNIOES_HEADERS):
            row.append("")

        row[2] = titulo
        row[3] = gangue
        row[4] = icone
        row[5] = data_reuniao
        row[6] = horario
        row[7] = local
        row[8] = pauta
        # Ao confirmar novos dados de uma reunião pendente, ela passa a estar agendada.
        if str(row[9]).strip().lower() in {"aguardando confirmação", "aguardando confirmacao", "a confirmar"}:
            row[9] = "Agendada"
            row[10] = ""

        worksheet.update(f"A{row_index}:K{row_index}", [row[:len(REUNIOES_HEADERS)]], value_input_option="RAW")
        invalidate_values_cache(REUNIOES_WORKSHEET_NAME)
        return jsonify({"ok": True, "message": "Reunião atualizada com sucesso."})
    except Exception as e:
        log_error("Falha em /api/reunioes/<id> [PUT]", e)
        return error_response(str(e))


@app.post("/api/reunioes/<registro_id>/finalizar")
@require_admin
def finalizar_reuniao(registro_id):
    try:
        worksheet = get_reunioes_worksheet()
        row_index, row = find_row_by_id(worksheet, registro_id)
        if not row_index:
            return error_response("Reunião não encontrada.", 404)

        while len(row) < len(REUNIOES_HEADERS):
            row.append("")
        if str(row[9]).strip().lower() == "cancelada":
            return error_response("Uma reunião cancelada não pode ser finalizada.", 400)

        row[3] = canonical_family_name(row[3])
        row[9] = "Finalizada"
        row[10] = format_timestamp()
        worksheet.update(f"A{row_index}:K{row_index}", [row[:len(REUNIOES_HEADERS)]], value_input_option="RAW")
        invalidate_values_cache(REUNIOES_WORKSHEET_NAME)

        familia_id, created = upsert_family_from_meeting(row[3], row[4])
        message = "Reunião finalizada e família incluída na aba Famílias." if created else "Reunião finalizada. A família já estava cadastrada."
        return jsonify({
            "ok": True,
            "message": message,
            "familia_id": familia_id,
            "family_created": created,
        })
    except Exception as e:
        log_error("Falha em /api/reunioes/<id>/finalizar [POST]", e)
        return error_response(str(e))


@app.post("/api/reunioes/<registro_id>/cancelar")
@require_admin
def cancelar_reuniao(registro_id):
    try:
        worksheet = get_reunioes_worksheet()
        row_index, row = find_row_by_id(worksheet, registro_id)
        if not row_index:
            return error_response("Reunião não encontrada.", 404)

        while len(row) < len(REUNIOES_HEADERS):
            row.append("")
        if str(row[9]).strip().lower() == "finalizada":
            return error_response("Uma reunião finalizada não pode ser cancelada.", 400)
        row[9] = "Cancelada"
        row[10] = format_timestamp()
        worksheet.update(f"A{row_index}:K{row_index}", [row[:len(REUNIOES_HEADERS)]], value_input_option="RAW")
        invalidate_values_cache(REUNIOES_WORKSHEET_NAME)
        return jsonify({"ok": True, "message": "Reunião marcada como cancelada."})
    except Exception as e:
        log_error("Falha em /api/reunioes/<id>/cancelar [POST]", e)
        return error_response(str(e))


@app.get("/api/familias")
@require_staff
def list_familias():
    try:
        worksheet = get_familias_worksheet()
        rows = cached_get_all_values(FAMILIAS_WORKSHEET_NAME, worksheet)
        familias = [normalize_family(row) for row in rows[1:] if str(sheet_cell(row, 2)).strip()]
        familias.sort(key=lambda item: normalized_lookup_key(item.get("nome")))
        return jsonify(familias)
    except Exception as e:
        log_error("Falha em /api/familias [GET]", e)
        return error_response(str(e))


def validate_family_payload(data):
    if not isinstance(data, dict):
        raise ValueError("JSON inválido.")

    name = canonical_family_name(clean_text_field(data, "nome", "Nome da família/gangue"))
    if not normalized_lookup_key(name):
        raise ValueError("Nome da família/gangue é obrigatório.")

    market = normalize_market_status(data.get("mercado"))
    icon = clean_text_field(data, "icone", "Ícone", max_length=12, required=False)
    sale_price = clean_text_field(
        data, "preco_venda_para_familia", "Preço de venda para a família",
        max_length=MAX_OBSERVATION_LENGTH, required=False,
    )
    purchase_price = clean_text_field(
        data, "preco_compra_da_familia", "Preço de compra da família",
        max_length=MAX_OBSERVATION_LENGTH, required=False,
    )
    flyer_url = clean_optional_http_url(data.get("flyer_url"), "Link do flyer")
    contact = clean_text_field(
        data, "contato", "Contato", max_length=200, required=False,
    )
    flyer_hidden = normalize_flag(data.get("flyer_oculto"))
    observation = clean_text_field(
        data, "observacao", "Observação", max_length=MAX_OBSERVATION_LENGTH, required=False,
    )
    return {
        "nome": name,
        "icone": icon,
        "mercado": market,
        "preco_venda_para_familia": sale_price,
        "preco_compra_da_familia": purchase_price,
        "flyer_url": flyer_url,
        "contato": contact,
        "flyer_oculto": flyer_hidden,
        "observacao": observation,
    }


@app.post("/api/familias")
@require_admin
def create_familia():
    try:
        try:
            payload = validate_family_payload(request.get_json(silent=True))
        except ValueError as validation_error:
            return error_response(str(validation_error), 400)

        with _sheets_lock:
            worksheet = get_familias_worksheet()
            rows = cached_get_all_values(FAMILIAS_WORKSHEET_NAME, worksheet, force=True)
            key = normalized_lookup_key(payload["nome"])
            if any(normalized_lookup_key(canonical_family_name(sheet_cell(row, 2))) == key for row in rows[1:]):
                return error_response("Essa família/gangue já está cadastrada.", 409)

            row = build_family_row(payload)
            worksheet.append_row(row, value_input_option="RAW")
            invalidate_values_cache(FAMILIAS_WORKSHEET_NAME)

        return jsonify({
            "ok": True,
            "message": "Família/gangue adicionada com sucesso.",
            "id": row[0],
        }), 201
    except Exception as e:
        log_error("Falha em /api/familias [POST]", e)
        return error_response(str(e))


@app.put("/api/familias/<registro_id>")
@require_admin
def update_familia(registro_id):
    try:
        try:
            payload = validate_family_payload(request.get_json(silent=True))
        except ValueError as validation_error:
            return error_response(str(validation_error), 400)

        with _sheets_lock:
            worksheet = get_familias_worksheet()
            row_index, row = find_row_by_id(worksheet, registro_id)
            if not row_index:
                return error_response("Família/gangue não encontrada.", 404)

            rows = cached_get_all_values(FAMILIAS_WORKSHEET_NAME, worksheet, force=True)
            key = normalized_lookup_key(payload["nome"])
            for other_index, other_row in enumerate(rows[1:], start=2):
                if other_index == row_index:
                    continue
                if normalized_lookup_key(canonical_family_name(sheet_cell(other_row, 2))) == key:
                    return error_response("Já existe outra família/gangue com esse nome.", 409)

            padded = list(row[:len(FAMILIAS_HEADERS)]) + [""] * max(0, len(FAMILIAS_HEADERS) - len(row))
            updated = build_family_row(payload, registro_id=padded[0], criado_em=padded[1])
            worksheet.update(f"A{row_index}:L{row_index}", [updated], value_input_option="RAW")
            invalidate_values_cache(FAMILIAS_WORKSHEET_NAME)

        return jsonify({"ok": True, "message": "Família/gangue atualizada com sucesso."})
    except Exception as e:
        log_error("Falha em /api/familias/<id> [PUT]", e)
        return error_response(str(e))


@app.delete("/api/familias/<registro_id>")
@require_admin
def delete_familia(registro_id):
    try:
        with _sheets_lock:
            worksheet = get_familias_worksheet()
            row_index, row = find_row_by_id(worksheet, registro_id)
            if not row_index:
                return error_response("Família/gangue não encontrada.", 404)
            name = canonical_family_name(sheet_cell(row, 2))
            worksheet.delete_rows(row_index)
            invalidate_values_cache(FAMILIAS_WORKSHEET_NAME)
        return jsonify({"ok": True, "message": f"{name} foi removida da aba Famílias."})
    except Exception as e:
        log_error("Falha em /api/familias/<id> [DELETE]", e)
        return error_response(str(e))


@app.get("/api/metas")
@require_staff
def list_metas():
    try:
        worksheet = get_metas_worksheet()
        rows = cached_get_all_values(METAS_WORKSHEET_NAME, worksheet)
        return jsonify([normalize_meta(row) for row in active_meta_rows(rows)])

    except Exception as e:
        log_error("Falha em /api/metas [GET]", e)
        return error_response(str(e))


@app.get("/api/resumo-metas")
@require_staff
def resumo_metas():
    try:
        week = ensure_current_meta_submissions()
        rows = meta_query_all(
            "SELECT status FROM meta_submissions WHERE week_start = ?",
            (week["semana_inicio"],),
        )
        total = len(rows)
        pagos = sum(1 for row in rows if row["status"] == "Pago")
        enviados = sum(1 for row in rows if row["status"] == "Enviado")
        recusados = sum(1 for row in rows if row["status"] == "Recusado")

        return jsonify({
            "total": total,
            "pagos": pagos,
            "pendentes": max(total - pagos, 0),
            "enviados": enviados,
            "recusados": recusados,
            "confirmados": pagos,
            "faltam_confirmar": max(total - pagos, 0),
            "semana_inicio": week["semana_inicio"],
            "semana_fim": week["semana_fim"],
            "semana_label": week["semana_label"],
        })

    except Exception as e:
        log_error("Falha em /api/resumo-metas", e)
        return error_response(str(e))


@app.post("/api/metas")
@require_admin
def create_meta():
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return error_response("JSON inválido.", 400)

        try:
            nome = clean_text_field(data, "nome", "Nome")
        except ValueError as validation_error:
            return error_response(str(validation_error), 400)
        pago = validate_yes_no(data.get("pago", "Não")) or "Não"

        worksheet = get_metas_worksheet()
        rows = cached_get_all_values(worksheet.title, worksheet, force=True)
        nomes_existentes = {row[1].strip().lower() for row in rows[1:] if len(row) > 1 and row[1].strip()}
        if nome.lower() in nomes_existentes:
            return error_response("Esse nome já está na lista de metas.", 409)

        agora = format_timestamp()
        semana_inicio = rows[1][4] if len(rows) > 1 and len(rows[1]) > 4 and rows[1][4] else meta_week_payload()["semana_inicio"]
        semana_fim = rows[1][5] if len(rows) > 1 and len(rows[1]) > 5 and rows[1][5] else meta_week_payload()["semana_fim"]
        registro_id = generate_record_id("META")
        worksheet.append_row([registro_id, nome, pago, agora, semana_inicio, semana_fim, "Sim"], value_input_option="RAW")
        invalidate_values_cache(METAS_WORKSHEET_NAME)

        return jsonify({
            "ok": True,
            "message": "Nome adicionado na lista de metas.",
            "id": registro_id,
        }), 201

    except Exception as e:
        log_error("Falha em /api/metas [POST]", e)
        return error_response(str(e))


@app.post("/api/metas/<registro_id>/status")
@require_admin
def update_meta_status(registro_id):
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return error_response("JSON inválido.", 400)

        pago = validate_yes_no(data.get("pago"))
        if not pago:
            return error_response("O pagamento deve ser somente 'Sim' ou 'Não'.", 400)

        worksheet = get_metas_worksheet()
        rows = cached_get_all_values(METAS_WORKSHEET_NAME, worksheet, force=True)
        row_index = None
        row = None
        for index, current_row in enumerate(rows[1:], start=2):
            if len(current_row) > 0 and current_row[0] == registro_id:
                row_index = index
                row = current_row
                break

        if not row_index:
            return error_response("Nome não encontrado na lista de metas.", 404)

        agora = format_timestamp()
        semana_inicio = row[4] if len(row) > 4 and row[4] else meta_week_payload()["semana_inicio"]
        semana_fim = row[5] if len(row) > 5 and row[5] else meta_week_payload()["semana_fim"]
        worksheet.update(f"C{row_index}:G{row_index}", [[pago, agora, semana_inicio, semana_fim, "Sim"]], value_input_option="RAW")
        invalidate_values_cache(METAS_WORKSHEET_NAME)

        updated_rows = deepcopy(rows)
        while len(updated_rows[row_index - 1]) < len(META_HEADERS):
            updated_rows[row_index - 1].append("")
        updated_rows[row_index - 1][2:7] = [pago, agora, semana_inicio, semana_fim, "Sim"]
        week_closed, next_week = maybe_close_week_if_all_confirmed(worksheet, rows=updated_rows)

        return jsonify({
            "ok": True,
            "message": "Semana fechada e a próxima semana foi aberta." if week_closed else "Status de pagamento atualizado.",
            "id": registro_id,
            "pago": pago,
            "atualizado_em": agora,
            "week_closed": week_closed,
            "next_week": next_week,
        })

    except Exception as e:
        log_error("Falha em /api/metas/<id>/status [POST]", e)
        return error_response(str(e))


@app.delete("/api/metas/<registro_id>")
@require_admin
def delete_meta(registro_id):
    try:
        worksheet = get_metas_worksheet()
        row_index, row = find_row_by_id(worksheet, registro_id)
        if not row_index:
            return error_response("Nome não encontrado na lista de metas.", 404)

        nome = row[1] if len(row) > 1 else registro_id
        worksheet.delete_rows(row_index)
        invalidate_values_cache(METAS_WORKSHEET_NAME)

        return jsonify({
            "ok": True,
            "message": f"{nome} removido da lista de metas.",
            "id": registro_id,
        })

    except Exception as e:
        log_error("Falha em /api/metas/<id> [DELETE]", e)
        return error_response(str(e))


@app.post("/api/metas/fechar-semana")
@require_admin
def fechar_semana_metas():
    try:
        worksheet = get_metas_worksheet()
        rows = cached_get_all_values(worksheet.title, worksheet, force=True)
        registros = active_meta_rows(rows)
        if not registros:
            return error_response("Nenhum nome cadastrado para fechar a semana.", 400)

        current_start = parse_date_br(registros[0][4] if len(registros[0]) > 4 else "") or meta_week_start()
        next_week = archive_and_reset_metas(worksheet, target_start_date=current_start + timedelta(days=7))

        return jsonify({
            "ok": True,
            "message": "Semana salva no histórico e próxima semana aberta.",
            "next_week": next_week,
        })

    except Exception as e:
        log_error("Falha em /api/metas/fechar-semana [POST]", e)
        return error_response(str(e))


if __name__ == "__main__":
    log_info("Iniciando aplicação Kokusai...")
    if app.secret_key == DEFAULT_SECRET_KEY:
        log_info("ATENÇÃO: SECRET_KEY padrão em uso. Configure SECRET_KEY no Railway antes de publicar.")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
