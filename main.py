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
from urllib.parse import urlparse, unquote
from werkzeug.middleware.proxy_fix import ProxyFix
from flask import Flask, jsonify, render_template, request, redirect, session, url_for, g, send_file, Response
import gspread
from google.oauth2.service_account import Credentials
from meta_members import META_MEMBERS

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

app = Flask(__name__)
APP_RELEASE = "2026.10.07-fotos-perfil"
DEFAULT_SECRET_KEY = "kokusai-dev-secret-change-this"
IS_RAILWAY = bool(
    os.getenv("RAILWAY_ENVIRONMENT")
    or os.getenv("RAILWAY_ENVIRONMENT_NAME")
    or os.getenv("RAILWAY_PROJECT_ID")
)
app.secret_key = os.getenv("SECRET_KEY", "").strip() or DEFAULT_SECRET_KEY
if IS_RAILWAY and app.secret_key == DEFAULT_SECRET_KEY:
    # Com a chave padrão (pública no código) qualquer pessoa conseguiria forjar
    # um cookie de sessão de administrador. Em produção o app se recusa a iniciar.
    raise RuntimeError(
        "SECRET_KEY não configurada. Defina uma SECRET_KEY longa e aleatória nas variáveis do Railway antes de publicar."
    )

# Quantidade de proxies confiáveis à frente do app (Railway = 1). Com ProxyFix,
# request.remote_addr passa a ser o IP real registrado pelo proxy, e não o valor
# de X-Forwarded-For enviado pelo cliente (que pode ser forjado).
TRUSTED_PROXY_COUNT = int(os.getenv("TRUSTED_PROXY_COUNT", "1" if IS_RAILWAY else "0"))
if TRUSTED_PROXY_COUNT > 0:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=TRUSTED_PROXY_COUNT, x_proto=TRUSTED_PROXY_COUNT)
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
REUNIOES_WORKSHEET_NAME = os.getenv("REUNIOES_WORKSHEET_NAME", "Reunioes")
FAMILIAS_WORKSHEET_NAME = os.getenv("FAMILIAS_WORKSHEET_NAME", "Familias")
LEGACY_FLYERS_WORKSHEET_NAME = os.getenv("FLYERS_WORKSHEET_NAME", "Flyers")
# O ciclo de metas é fixo: sexta-feira 00:00 até quarta-feira 23:59.
# Quinta-feira fica exclusivamente para a conferência do administrador.
META_RESET_WEEKDAY = 4  # datetime.weekday(): 4 = sexta-feira
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
FLYER_LOCAL_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "flyer_uploads")
BUCKET_REFERENCE_PREFIX = "kokusai-bucket://"
META_MAX_FILE_BYTES = int(os.getenv("META_MAX_FILE_BYTES", str(10 * 1024 * 1024)))
META_MAX_PHOTOS_PER_WEEK = 10
META_ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
META_IMAGE_MAX_SIDE = int(os.getenv("META_IMAGE_MAX_SIDE", "2200"))
META_IMAGE_WEBP_QUALITY = int(os.getenv("META_IMAGE_WEBP_QUALITY", "88"))

_meta_db_lock = threading.RLock()
_meta_db_ready = False
_meta_storage_client_cache = {"client": None}

# Cache simples para não estourar a quota do Google Sheets.
# O Google Sheets cobra cada leitura da API; antes o painel fazia várias leituras
# ao mesmo tempo ao abrir a tela. Com cache, a tela reaproveita os dados por alguns segundos.
SHEETS_CACHE_SECONDS = int(os.getenv("SHEETS_CACHE_SECONDS", "45"))
SHEETS_MAINTENANCE_SECONDS = int(os.getenv("SHEETS_MAINTENANCE_SECONDS", "300"))
_sheets_lock = threading.RLock()
_gsheet_client_cache = {"client": None}
_spreadsheet_cache = {"spreadsheet": None}
_worksheet_cache = {}
_values_cache = {}
_familias_maintenance_cache = {"checked_at": 0}

# Proteções simples contra abuso. Como o app roda em poucos usuários,
# limites curtos já reduzem bastante risco de força bruta e payload gigante.
LOGIN_ATTEMPTS = {}
LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
# Limite por usuário (somando todos os IPs): freia ataques distribuídos sem permitir
# que um terceiro bloqueie o login de alguém com poucas tentativas.
LOGIN_MAX_ATTEMPTS_PER_USER = int(os.getenv("LOGIN_MAX_ATTEMPTS_PER_USER", "25"))

# Contas e perfil.
MAX_OPEN_ACCOUNTS = 2  # contas autenticadas ao mesmo tempo no mesmo navegador
APELIDO_MAX_LENGTH = 30
PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))
PASSWORD_MAX_LENGTH = 128
PASSWORD_HASH_ITERATIONS = int(os.getenv("PASSWORD_HASH_ITERATIONS", "600000"))
AVATAR_SIZE = 256
AVATAR_THUMB_SIZE = 96
AVATAR_WEBP_QUALITY = 86
LOGIN_WINDOW_SECONDS = int(os.getenv("LOGIN_WINDOW_SECONDS", "900"))
MAX_TEXT_LENGTH = int(os.getenv("MAX_TEXT_LENGTH", "120"))
MAX_OBSERVATION_LENGTH = int(os.getenv("MAX_OBSERVATION_LENGTH", "500"))
MAX_QUANTITY = int(os.getenv("MAX_QUANTITY", "1000000"))
MAX_MONEY_VALUE = float(os.getenv("MAX_MONEY_VALUE", "1000000000"))
DEFAULT_DIRTY_MONEY_PERCENTAGE = 30.0
MIN_DIRTY_MONEY_PERCENTAGE = 1.0
MAX_DIRTY_MONEY_PERCENTAGE = 30.0
SHEET_FORMULA_PREFIXES = ("=", "+", "-", "@")


# Usuário administrador. A senha nunca fica no código: o hash PBKDF2-SHA256 vem da
# variável KOKUSAI_PASSWORD_HASH (gere com: python scripts/generate_password_hash.py).
ADMIN_PASSWORD_HASH = os.getenv("KOKUSAI_PASSWORD_HASH", "").strip()
if not ADMIN_PASSWORD_HASH and IS_RAILWAY:
    raise RuntimeError(
        "KOKUSAI_PASSWORD_HASH não configurada. Cole a variável do arquivo railway-variaveis.txt "
        "nas variáveis do Railway antes de publicar."
    )
if not ADMIN_PASSWORD_HASH:
    print(
        "[KOKUSAI][AVISO] KOKUSAI_PASSWORD_HASH não definida: o login do administrador está desativado neste ambiente.",
        flush=True,
    )

AUTH_USERS = {}
if ADMIN_PASSWORD_HASH:
    AUTH_USERS["kokusai"] = {
        "display_name": "Kokusai",
        "role": "admin",
        "password_hash": ADMIN_PASSWORD_HASH,
    }


COMPRAS_HEADERS = [
    "id", "data", "produto", "quem_pediu", "quem_vendeu", "valor_unitario", "quantidade",
    "valor_total", "observacao", "tipo_dinheiro", "valor_base", "acrescimo_dinheiro_sujo",
    "percentual_dinheiro_sujo",
    "familia_id", "familia_nome", "familia_icone",
]
VENDAS_HEADERS = [
    "id",
    "data",
    "produto",
    "quem_compra",
    "quem_vende",
    "valor_unitario",
    "quantidade",
    "valor_total",
    "observacao",
    "familia_id",
    "familia_nome",
    "familia_icone",
    "encomenda_id",
    "tipo_dinheiro",
    "valor_base",
    "acrescimo_dinheiro_sujo",
    "percentual_dinheiro_sujo",
]
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
    "familia_id",
    "familia_nome",
    "familia_icone",
    "tipo_dinheiro",
    "valor_base",
    "acrescimo_dinheiro_sujo",
    "prioridade",
    "percentual_dinheiro_sujo",
]
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
    "contato_2",
    "flyer_url_2",
    "responsavel_contato",
]
DEFAULT_FAMILIAS = [
    {
        "nome": "Ruptura", "icone": "💥", "mercado": "Aberto", "responsavel_contato": "Larissa",
    },
    {
        "nome": "Leviatã", "icone": "🐉", "mercado": "Aberto", "responsavel_contato": "Larissa",
    },
    {
        "nome": "Distrito", "icone": "🏙️", "mercado": "Aberto", "responsavel_contato": "Wanda",
    },
    {
        "nome": "Black Hearts", "icone": "🖤", "mercado": "Aberto", "responsavel_contato": "Wanda",
    },
    {
        "nome": "The Lost MC", "icone": "🏍️", "mercado": "Aberto", "responsavel_contato": "Kiyotaka",
    },
    {
        "nome": "Ballas", "icone": "🟣", "mercado": "Aberto", "responsavel_contato": "Matheus",
    },
    {
        "nome": "Legacy", "icone": "👑", "mercado": "Aberto", "responsavel_contato": "Matheus",
    },
    {
        "nome": "Aura", "icone": "✨", "mercado": "Aberto", "responsavel_contato": "Gohan",
    },
    {
        "nome": "La Guardia", "icone": "🛡️", "mercado": "Aberto", "responsavel_contato": "Gohan",
    },
    {
        "nome": "Vendetta", "icone": "🔴", "mercado": "Aberto", "responsavel_contato": "Max",
    },
    {
        "nome": "Cartel", "icone": "🦂", "mercado": "Aberto", "responsavel_contato": "Max",
    },
    {
        "nome": "Hells", "icone": "🏴", "mercado": "Aberto", "responsavel_contato": "Theo",
    },
    {
        "nome": "Nox", "icone": "🌑", "mercado": "Sem mercado", "responsavel_contato": "",
        "observacao": "Não compramos nem vendemos para esta família enquanto estiver sem mercado aberto.",
    },
    {
        "nome": "Void", "icone": "⚫", "mercado": "Sem mercado", "responsavel_contato": "",
        "observacao": "Não compramos nem vendemos para esta família enquanto estiver sem mercado aberto.",
    },
    {
        "nome": "Meraki", "icone": "🔹", "mercado": "Sem mercado", "responsavel_contato": "",
        "observacao": "Não compramos nem vendemos para esta família enquanto estiver sem mercado aberto.",
    },
    {
        "nome": "Chaos", "icone": "🌀", "mercado": "Em negociação", "responsavel_contato": "",
        "observacao": "Mercado ainda não estabelecido. Compras, vendas e encomendas ficam bloqueadas.",
    },
    {
        "nome": "Balaclava", "icone": "🥷", "mercado": "Em negociação", "responsavel_contato": "",
        "observacao": "Mercado ainda não estabelecido. Compras, vendas e encomendas ficam bloqueadas.",
    },
]
RESTRICTED_FAMILY_MARKETS = {
    "nox": "Sem mercado",
    "void": "Sem mercado",
    "meraki": "Sem mercado",
}
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


def parse_meta_timestamp(value):
    raw_value = str(value or "").strip()
    if not raw_value:
        return None
    for timestamp_format in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw_value[:19], timestamp_format)
        except Exception:
            continue
    return None


def meta_week_start(today=None):
    today = today or now_local().date()
    days_since_reset = (today.weekday() - META_RESET_WEEKDAY) % 7
    return today - timedelta(days=days_since_reset)


def meta_week_end(start_date):
    # A sala abre na sexta e recebe comprovantes até quarta-feira.
    return start_date + timedelta(days=5)


def meta_week_payload(start_date=None):
    start_date = start_date or meta_week_start()
    end_date = meta_week_end(start_date)
    review_date = start_date + timedelta(days=6)
    current_date = now_local().date()
    if start_date <= current_date <= end_date:
        phase = "open"
    elif current_date == review_date:
        phase = "review"
    elif current_date < start_date:
        phase = "upcoming"
    else:
        phase = "closed"
    return {
        "semana_inicio": format_date_br(start_date),
        "semana_fim": format_date_br(end_date),
        "semana_label": f"{format_date_br(start_date)} até {format_date_br(end_date)}",
        "prazo_pagamento": f"{format_date_br(end_date)} 23:59",
        "data_conferencia": format_date_br(review_date),
        "proxima_semana": format_date_br(start_date + timedelta(days=7)),
        "fase": phase,
        "envios_abertos": phase == "open",
    }


def meta_submission_uploads_open(submission, current_dt=None):
    current_dt = current_dt or now_local()
    start_date = parse_date_br(submission.get("week_start"))
    end_date = parse_date_br(submission.get("week_end"))
    if not start_date or not end_date:
        return False
    return start_date <= current_dt.date() <= end_date


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


# Colunas acrescentadas depois que a tabela já existia em produção.
BAU_EXTRA_COLUMNS = {
    "responsavel": "TEXT NOT NULL DEFAULT ''",
    "arquivado": "INTEGER NOT NULL DEFAULT 0",
    "arquivado_em": "TEXT NOT NULL DEFAULT ''",
    "arquivado_por": "TEXT NOT NULL DEFAULT ''",
}


def ensure_table_columns(cursor, table, columns):
    """Acrescenta colunas que faltam (SQLite e Postgres), sem mexer nos dados existentes."""
    if meta_db_uses_postgres():
        for name, ddl in columns.items():
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {ddl}")
        return
    cursor.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cursor.fetchall()}
    for name, ddl in columns.items():
        if name not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


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


# Usuários de acesso renomeados (antigo -> novo). A conta continua a mesma (id, semanas,
# fotos, perfil e senha); só o nome usado no login muda. O nome antigo ainda é aceito no
# login e na variável META_MEMBERS_JSON, então não é preciso mexer no Railway.
MEMBER_USERNAME_RENAMES = {
    "kyotaka": "kiyotaka",
}


def canonical_member_username(username):
    value = str(username or "").strip().lower()
    return MEMBER_USERNAME_RENAMES.get(value, value)


def apply_member_username_renames(cursor):
    renamed = []
    for old, new in MEMBER_USERNAME_RENAMES.items():
        cursor.execute(meta_sql("SELECT id FROM meta_users WHERE username = ?"), (new,))
        if cursor.fetchone():
            continue  # já renomeado (ou o novo nome já existe): não mexe
        cursor.execute(meta_sql("UPDATE meta_users SET username = ? WHERE username = ?"), (new, old))
        if cursor.rowcount:
            renamed.append(f"{old} -> {new}")
    return renamed


def canonical_meta_week_dates(week_start):
    """Converte ciclos antigos para o calendário sexta-feira–quarta-feira."""
    start_date = parse_date_br(week_start)
    if not start_date:
        return None
    days_until_friday = (META_RESET_WEEKDAY - start_date.weekday()) % 7
    canonical_start = start_date + timedelta(days=days_until_friday)
    canonical_end = meta_week_end(canonical_start)
    return format_date_br(canonical_start), format_date_br(canonical_end)


def migrate_legacy_meta_weeks(connection):
    """Une semanas do calendário antigo sem perder fotos já enviadas.

    A versão anterior chegou a criar ciclos de quarta a terça. Quando o ciclo
    correto de sexta a quarta foi ativado, alguns membros ficaram com fotos em
    duas submissões diferentes da mesma semana. Esta migração move todas as
    fotos para o ciclo canônico e remove somente a submissão duplicada.
    """
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT id, user_id, week_start, week_end, status, admin_note,
               submitted_at, reviewed_at, reviewed_by, created_at
        FROM meta_submissions
        """
    )
    submissions = meta_rows_from_cursor(cursor)
    migrated = 0
    status_priority = {"Pendente": 0, "Enviado": 1, "Recusado": 2, "Não pago": 3, "Pago": 4}

    for legacy in submissions:
        canonical = canonical_meta_week_dates(legacy.get("week_start"))
        if not canonical:
            continue
        canonical_start, canonical_end = canonical
        if legacy.get("week_start") == canonical_start and legacy.get("week_end") == canonical_end:
            continue

        cursor.execute(
            meta_sql(
                """
                SELECT id, status, admin_note, submitted_at, reviewed_at, reviewed_by, created_at
                FROM meta_submissions WHERE user_id = ? AND week_start = ? AND id <> ?
                """
            ),
            (legacy["user_id"], canonical_start, legacy["id"]),
        )
        existing_rows = meta_rows_from_cursor(cursor)
        target = existing_rows[0] if existing_rows else None

        if target:
            target_status = str(target.get("status") or "Pendente")
            legacy_status = str(legacy.get("status") or "Pendente")
            merged_status = (
                legacy_status
                if status_priority.get(legacy_status, 0) > status_priority.get(target_status, 0)
                else target_status
            )
            cursor.execute(
                meta_sql(
                    """
                    UPDATE meta_submissions
                    SET week_end = ?, status = ?, admin_note = ?, submitted_at = ?,
                        reviewed_at = ?, reviewed_by = ?
                    WHERE id = ?
                    """
                ),
                (
                    canonical_end,
                    merged_status,
                    target.get("admin_note") or legacy.get("admin_note") or "",
                    target.get("submitted_at") or legacy.get("submitted_at"),
                    target.get("reviewed_at") or legacy.get("reviewed_at"),
                    target.get("reviewed_by") or legacy.get("reviewed_by"),
                    target["id"],
                ),
            )
            cursor.execute(
                meta_sql("UPDATE meta_photos SET submission_id = ? WHERE submission_id = ?"),
                (target["id"], legacy["id"]),
            )
            cursor.execute(meta_sql("DELETE FROM meta_submissions WHERE id = ?"), (legacy["id"],))
        else:
            cursor.execute(
                meta_sql("UPDATE meta_submissions SET week_start = ?, week_end = ? WHERE id = ?"),
                (canonical_start, canonical_end, legacy["id"]),
            )
        migrated += 1

    # Logs já finalizados também recebem as datas canônicas. O texto do log é
    # preservado, trocando apenas o período antigo pelo novo.
    cursor.execute(
        """
        SELECT id, week_start, week_end, payment_deadline, review_date, log_text
        FROM meta_week_closures
        """
    )
    closures = meta_rows_from_cursor(cursor)
    for closure in closures:
        canonical = canonical_meta_week_dates(closure.get("week_start"))
        if not canonical:
            continue
        canonical_start, canonical_end = canonical
        if closure.get("week_start") == canonical_start and closure.get("week_end") == canonical_end:
            continue
        cursor.execute(meta_sql("SELECT id FROM meta_week_closures WHERE week_start = ?"), (canonical_start,))
        if meta_rows_from_cursor(cursor):
            continue
        review_date = format_date_br(parse_date_br(canonical_end) + timedelta(days=1))
        log_text = str(closure.get("log_text") or "")
        log_text = log_text.replace(str(closure.get("week_start") or ""), canonical_start)
        log_text = log_text.replace(str(closure.get("week_end") or ""), canonical_end)
        cursor.execute(
            meta_sql(
                """
                UPDATE meta_week_closures
                SET week_start = ?, week_end = ?, payment_deadline = ?, review_date = ?, log_text = ?
                WHERE id = ?
                """
            ),
            (canonical_start, canonical_end, f"{canonical_end} 23:59", review_date, log_text, closure["id"]),
        )

    return migrated


def repair_meta_photo_week_assignments(connection):
    """Reassocia fotos antigas usando a data real em que foram enviadas.

    Uma migração anterior consolidava ciclos inteiros de quarta–terça no ciclo
    sexta–quarta seguinte. Isso podia levar uma foto enviada antes da sexta
    para a sala da semana nova. O arquivo continua preservado, mas volta para
    a submissão semanal correta e deixa de aparecer como foto da semana atual.
    """
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT p.id AS photo_id, p.submission_id, p.user_id, p.created_at,
               s.week_start, s.week_end
        FROM meta_photos p
        INNER JOIN meta_submissions s ON s.id = p.submission_id
        """
    )
    photos = meta_rows_from_cursor(cursor)
    repaired = 0
    affected_submission_ids = set()

    for photo in photos:
        created_at = parse_meta_timestamp(photo.get("created_at"))
        if not created_at:
            continue

        target_start_date = meta_week_start(created_at.date())
        target_week_start = format_date_br(target_start_date)
        target_week_end = format_date_br(meta_week_end(target_start_date))
        if photo.get("week_start") == target_week_start:
            continue

        cursor.execute(
            meta_sql(
                """
                SELECT id FROM meta_submissions
                WHERE user_id = ? AND week_start = ?
                """
            ),
            (photo["user_id"], target_week_start),
        )
        target_rows = meta_rows_from_cursor(cursor)
        if target_rows:
            target_submission_id = target_rows[0]["id"]
        else:
            target_submission_id = f"META-SUB-{uuid.uuid4().hex}"
            cursor.execute(
                meta_sql(
                    """
                    INSERT INTO meta_submissions
                        (id, user_id, week_start, week_end, status, submitted_at, created_at)
                    VALUES (?, ?, ?, ?, 'Enviado', ?, ?)
                    """
                ),
                (
                    target_submission_id,
                    photo["user_id"],
                    target_week_start,
                    target_week_end,
                    photo.get("created_at"),
                    photo.get("created_at") or format_timestamp(),
                ),
            )

        cursor.execute(
            meta_sql("UPDATE meta_photos SET submission_id = ? WHERE id = ?"),
            (target_submission_id, photo["photo_id"]),
        )
        affected_submission_ids.update({photo["submission_id"], target_submission_id})
        repaired += 1

    # Mantém o resumo das duas salas coerente depois de mover as fotos. Status
    # administrativos finais nunca são alterados por esta reparação.
    for submission_id in affected_submission_ids:
        cursor.execute(
            meta_sql(
                """
                SELECT COUNT(*) AS total, MIN(created_at) AS first_photo_at
                FROM meta_photos WHERE submission_id = ?
                """
            ),
            (submission_id,),
        )
        count_rows = meta_rows_from_cursor(cursor)
        photo_count = int(count_rows[0].get("total") or 0) if count_rows else 0
        first_photo_at = count_rows[0].get("first_photo_at") if count_rows else None
        cursor.execute(meta_sql("SELECT status FROM meta_submissions WHERE id = ?"), (submission_id,))
        status_rows = meta_rows_from_cursor(cursor)
        if not status_rows:
            continue
        current_status = str(status_rows[0].get("status") or "Pendente")
        if photo_count == 0 and current_status == "Enviado":
            cursor.execute(
                meta_sql("UPDATE meta_submissions SET status = 'Pendente', submitted_at = NULL WHERE id = ?"),
                (submission_id,),
            )
        elif photo_count > 0 and current_status == "Pendente":
            cursor.execute(
                meta_sql("UPDATE meta_submissions SET status = 'Enviado', submitted_at = ? WHERE id = ?"),
                (first_photo_at or format_timestamp(), submission_id),
            )

    return repaired


def apply_member_seed_password(cursor, user_id, env_hash, now_text):
    """Aplica a senha vinda de META_MEMBERS_JSON somente quando ela mudou.

    Antes, todo deploy regravava a senha do arquivo. Agora o hash aplicado por último
    fica em user_profiles.seed_hash: se a variável do Railway não mudou, a senha que o
    membro escolheu pelo perfil é preservada; se você troca o hash dele na variável,
    isso vale como redefinição de senha e desconecta os aparelhos dele.
    """
    cursor.execute(meta_sql("SELECT seed_hash FROM user_profiles WHERE user_id = ?"), (user_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.execute(
            meta_sql("INSERT INTO user_profiles (user_id, seed_hash, updated_at) VALUES (?, ?, ?)"),
            (user_id, env_hash, now_text),
        )
        cursor.execute(meta_sql("UPDATE meta_users SET password_hash = ? WHERE id = ?"), (env_hash, user_id))
    elif not row[0]:
        cursor.execute(
            meta_sql("UPDATE user_profiles SET seed_hash = ?, updated_at = ? WHERE user_id = ?"),
            (env_hash, now_text, user_id),
        )
    elif row[0] != env_hash:
        cursor.execute(meta_sql("UPDATE meta_users SET password_hash = ? WHERE id = ?"), (env_hash, user_id))
        cursor.execute(
            meta_sql(
                "UPDATE user_profiles SET seed_hash = ?, session_version = session_version + 1, "
                "password_changed_at = '', updated_at = ? WHERE user_id = ?"
            ),
            (env_hash, now_text, user_id),
        )


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
                """
                CREATE TABLE IF NOT EXISTS meta_week_closures (
                    id TEXT PRIMARY KEY,
                    week_start TEXT UNIQUE NOT NULL,
                    week_end TEXT NOT NULL,
                    payment_deadline TEXT NOT NULL,
                    review_date TEXT NOT NULL,
                    closed_at TEXT NOT NULL,
                    closed_by TEXT NOT NULL,
                    total_count INTEGER NOT NULL,
                    paid_count INTEGER NOT NULL,
                    unpaid_count INTEGER NOT NULL,
                    log_text TEXT NOT NULL
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_meta_submissions_week ON meta_submissions(week_start)",
                "CREATE INDEX IF NOT EXISTS idx_meta_photos_submission ON meta_photos(submission_id)",
                "CREATE INDEX IF NOT EXISTS idx_meta_closures_week ON meta_week_closures(week_start)",
                """
                CREATE TABLE IF NOT EXISTS bau_registros (
                    id TEXT PRIMARY KEY,
                    object_key TEXT NOT NULL,
                    original_name TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    legenda TEXT NOT NULL DEFAULT '',
                    registrado_por TEXT NOT NULL DEFAULT '',
                    mes TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_ts TEXT NOT NULL,
                    responsavel TEXT NOT NULL DEFAULT '',
                    arquivado INTEGER NOT NULL DEFAULT 0,
                    arquivado_em TEXT NOT NULL DEFAULT '',
                    arquivado_por TEXT NOT NULL DEFAULT ''
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_bau_registros_ts ON bau_registros(created_ts)",
                "CREATE INDEX IF NOT EXISTS idx_bau_registros_mes ON bau_registros(mes)",
                """
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    apelido TEXT NOT NULL DEFAULT '',
                    avatar_b64 TEXT NOT NULL DEFAULT '',
                    thumb_b64 TEXT NOT NULL DEFAULT '',
                    avatar_version INTEGER NOT NULL DEFAULT 0,
                    session_version INTEGER NOT NULL DEFAULT 0,
                    seed_hash TEXT NOT NULL DEFAULT '',
                    password_changed_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(user_id) REFERENCES meta_users(id)
                )
                """,
            ]
            for statement in statements:
                cursor.execute(statement)
            ensure_table_columns(cursor, "bau_registros", BAU_EXTRA_COLUMNS)

            created_at = format_timestamp()
            # META_MEMBERS_JSON só CADASTRA quem ainda não existe no banco. Quem entra e quem
            # sai da equipe passa a ser decidido pelo painel de metas (aba "Gerenciar membros"):
            # remover alguém lá o deixa inativo (semanas, fotos e logs ficam guardados) e um novo
            # deploy não o reativa. Quem não está mais na variável também não é desativado sozinho.
            seed_query = meta_sql(
                """
                INSERT INTO meta_users (id, username, display_name, password_hash, role, active, created_at)
                VALUES (?, ?, ?, ?, 'member', 1, ?)
                ON CONFLICT(username) DO UPDATE SET
                    display_name = excluded.display_name
                """
            )
            renamed_usernames = apply_member_username_renames(cursor)
            for member in META_MEMBERS:
                username = canonical_member_username(member["username"])
                # O id vem do banco quando a conta já existe (contas renomeadas mantêm o id antigo).
                cursor.execute(meta_sql("SELECT id FROM meta_users WHERE username = ?"), (username,))
                existing = cursor.fetchone()
                member_id = existing[0] if existing else meta_member_id(username)
                cursor.execute(seed_query, (
                    member_id,
                    username,
                    member["display_name"],
                    member["password_hash"],
                    created_at,
                ))
                apply_member_seed_password(cursor, member_id, member["password_hash"], created_at)
            migrated_weeks = migrate_legacy_meta_weeks(connection)
            repaired_photos = repair_meta_photo_week_assignments(connection)
            connection.commit()
            _meta_db_ready = True
            if renamed_usernames:
                log_info(f"Usuários de acesso renomeados: {', '.join(renamed_usernames)}")
            if migrated_weeks:
                log_info(f"Semanas antigas de meta migradas para sexta–quarta: {migrated_weeks}")
            if repaired_photos:
                log_info(f"Fotos de meta reassociadas à semana correta: {repaired_photos}")
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def get_meta_member_by_username(username):
    try:
        return meta_query_one(
            """
            SELECT u.id, u.username, u.display_name, u.password_hash, u.role, u.active,
                   COALESCE(p.session_version, 0) AS session_version,
                   COALESCE(p.apelido, '') AS apelido
            FROM meta_users u
            LEFT JOIN user_profiles p ON p.user_id = u.id
            WHERE u.username = ? AND u.active = 1
            """,
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
    return get_meta_submission(user_id, week["semana_inicio"])


def get_meta_submission(user_id, week_start):
    return meta_query_one(
        """
        SELECT id, user_id, week_start, week_end, status, admin_note, submitted_at, reviewed_at, reviewed_by, created_at
        FROM meta_submissions WHERE user_id = ? AND week_start = ?
        """,
        (user_id, week_start),
    )


def get_meta_photos(submission_id):
    return meta_query_all(
        """
        SELECT id, submission_id, user_id, object_key, original_name, content_type, size_bytes, created_at
        FROM meta_photos WHERE submission_id = ? ORDER BY created_at ASC
        """,
        (submission_id,),
    )


def get_meta_room_history(user_id, exclude_week_start=None, limit=12):
    excluded_week = exclude_week_start or meta_week_payload()["semana_inicio"]
    return meta_query_all(
        """
        SELECT s.id, s.week_start, s.week_end, s.status, s.admin_note, s.submitted_at, s.reviewed_at,
               (SELECT COUNT(*) FROM meta_photos p WHERE p.submission_id = s.id) AS photo_count
        FROM meta_submissions s
        WHERE s.user_id = ? AND s.week_start <> ?
        ORDER BY substr(s.week_start, 7, 4) || substr(s.week_start, 4, 2) || substr(s.week_start, 1, 2) DESC
        LIMIT ?
        """,
        (user_id, excluded_week, int(limit)),
    )


def get_meta_unpaid_streaks():
    """Conta semanas finalizadas consecutivas com resultado Não pago."""
    rows = meta_query_all(
        """
        SELECT s.user_id, s.status, s.week_start
        FROM meta_submissions s
        INNER JOIN meta_week_closures c ON c.week_start = s.week_start
        ORDER BY s.user_id ASC,
                 substr(s.week_start, 7, 4) || substr(s.week_start, 4, 2) || substr(s.week_start, 1, 2) DESC
        """
    )
    streaks = {}
    completed_users = set()
    for row in rows:
        user_id = row["user_id"]
        if user_id in completed_users:
            continue
        if row["status"] == "Não pago":
            streaks[user_id] = streaks.get(user_id, 0) + 1
        else:
            completed_users.add(user_id)
    return streaks


def get_meta_week_closure(week_start):
    return meta_query_one(
        """
        SELECT id, week_start, week_end, payment_deadline, review_date, closed_at, closed_by,
               total_count, paid_count, unpaid_count, log_text
        FROM meta_week_closures WHERE week_start = ?
        """,
        (week_start,),
    )


def get_admin_meta_week():
    """Prioriza a última semana vencida ainda não finalizada; caso contrário mostra a atual."""
    current_week = ensure_current_meta_submissions()
    rows = meta_query_all("SELECT DISTINCT week_start, week_end FROM meta_submissions")
    today = now_local().date()
    reviewable = []
    for row in rows:
        start_date = parse_date_br(row.get("week_start"))
        end_date = parse_date_br(row.get("week_end"))
        if start_date and end_date and end_date < today:
            reviewable.append((end_date, start_date, row))

    target_week = current_week
    if reviewable:
        _, latest_start, latest_row = max(reviewable, key=lambda item: item[0])
        if not get_meta_week_closure(latest_row["week_start"]):
            target_week = meta_week_payload(latest_start)

    closure = get_meta_week_closure(target_week["semana_inicio"])
    target_end = parse_date_br(target_week["semana_fim"])
    review_mode = bool(target_end and target_end < today and not closure)
    return {
        **target_week,
        "review_mode": review_mode,
        "closed": bool(closure),
        "closure": {
            "closed_at": closure["closed_at"],
            "closed_by": closure["closed_by"],
            "paid_count": int(closure["paid_count"] or 0),
            "unpaid_count": int(closure["unpaid_count"] or 0),
        } if closure else None,
    }


def storage_bucket_configured():
    return all([META_BUCKET_NAME, META_BUCKET_ENDPOINT, META_BUCKET_ACCESS_KEY, META_BUCKET_SECRET_KEY])


def get_storage_client():
    if not storage_bucket_configured():
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


def prepare_image_upload(upload, label="imagem"):
    if not upload or not upload.filename:
        raise ValueError(f"Selecione uma {label} para enviar.")

    raw = upload.stream.read(META_MAX_FILE_BYTES + 1)
    if len(raw) > META_MAX_FILE_BYTES:
        raise ValueError(f"A {label} ultrapassa o limite de 10 MB.")
    if not raw:
        raise ValueError(f"A {label} enviada está vazia.")

    try:
        from PIL import Image, ImageOps
    except ImportError as error:
        raise RuntimeError("Dependência Pillow não instalada. Execute pip install -r requirements.txt.") from error

    try:
        image = Image.open(BytesIO(raw))
        detected_format = str(image.format or "").upper()
        # Alguns celulares/navegadores enviam JPG como image/jpg ou mesmo sem
        # MIME. Validamos o arquivo de verdade pelo Pillow, não pelo cabeçalho
        # enviado pelo navegador.
        if detected_format not in META_ALLOWED_IMAGE_FORMATS:
            raise ValueError("Envie somente imagens JPG, JPEG, PNG ou WEBP.")
        image.load()
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
    except ValueError:
        raise
    except Exception as error:
        raise ValueError(f"Não foi possível ler essa {label}. Tente enviar outro arquivo.") from error


def store_meta_photo(upload, user_id, week_start):
    image_bytes = prepare_image_upload(upload, "foto")
    object_key = f"metas/{user_id}/{week_start.replace('/', '-')}/{uuid.uuid4().hex}.webp"
    client = get_storage_client()
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
    client = get_storage_client()
    if client:
        client.delete_object(Bucket=META_BUCKET_NAME, Key=object_key)
        return
    local_path = os.path.join(META_LOCAL_UPLOAD_DIR, *str(object_key).split("/"))
    if os.path.isfile(local_path):
        os.remove(local_path)


def meta_photo_access_url(photo):
    client = get_storage_client()
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


def bucket_reference(object_key):
    return f"{BUCKET_REFERENCE_PREFIX}{str(object_key or '').lstrip('/')}"


def bucket_key_from_reference(value):
    reference = str(value or "").strip()
    if not reference.startswith(BUCKET_REFERENCE_PREFIX):
        return ""
    return reference[len(BUCKET_REFERENCE_PREFIX):].lstrip("/")


def bucket_key_from_legacy_flyer_url(value):
    """Recupera a chave de links temporários antigos do Bucket do Railway.

    Versões anteriores podiam acabar salvando a URL assinada, que expira, em
    vez da referência ``kokusai-bucket://``. A chave continua presente no
    caminho da URL e pode ser convertida novamente para a referência estável.
    """
    raw_value = str(value or "").strip()
    parsed = urlparse(raw_value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return ""

    endpoint_host = (urlparse(META_BUCKET_ENDPOINT).hostname or "").lower()
    value_host = parsed.hostname.lower()
    if not endpoint_host or not (
        value_host == endpoint_host or value_host.endswith(f".{endpoint_host}")
    ):
        return ""

    path_parts = [unquote(part) for part in parsed.path.split("/") if part]
    try:
        flyer_index = path_parts.index("flyers")
    except ValueError:
        return ""
    object_parts = path_parts[flyer_index:]
    if len(object_parts) < 2 or any(part in {".", ".."} for part in object_parts):
        return ""
    return "/".join(object_parts)


def stable_family_flyer_reference(value):
    reference = str(value or "").strip()
    object_key = bucket_key_from_reference(reference) or bucket_key_from_legacy_flyer_url(reference)
    return bucket_reference(object_key) if object_key else reference


def family_flyer_storage_path(object_key):
    local_root = os.path.abspath(FLYER_LOCAL_UPLOAD_DIR)
    local_path = os.path.abspath(os.path.join(local_root, *str(object_key).split("/")))
    if not local_path.startswith(local_root + os.sep):
        raise ValueError("Referência de flyer inválida.")
    return local_path


def store_family_flyer(upload, family_id, slot):
    image_bytes = prepare_image_upload(upload, "imagem do flyer")
    clean_family_id = re.sub(r"[^A-Za-z0-9_-]+", "-", str(family_id or "")).strip("-")
    if not clean_family_id:
        raise ValueError("Família inválida para armazenar o flyer.")
    object_key = f"flyers/{clean_family_id}/slot-{int(slot)}/{uuid.uuid4().hex}.webp"
    client = get_storage_client()
    if client:
        client.put_object(
            Bucket=META_BUCKET_NAME,
            Key=object_key,
            Body=image_bytes,
            ContentType="image/webp",
            CacheControl="private, max-age=3600",
        )
        # Só grava a referência no Google Sheets depois que o Bucket confirma
        # que o objeto existe. Assim um deploy nunca deixa um cadastro apontando
        # para um upload incompleto ou para o disco temporário do serviço.
        client.head_object(Bucket=META_BUCKET_NAME, Key=object_key)
    else:
        if IS_RAILWAY:
            raise RuntimeError("Bucket de imagens não configurado no Railway.")
        local_path = family_flyer_storage_path(object_key)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as file_handle:
            file_handle.write(image_bytes)
    return bucket_reference(object_key)


def delete_family_flyer_reference(reference):
    object_key = bucket_key_from_reference(reference)
    if not object_key or not object_key.startswith("flyers/"):
        return
    client = get_storage_client()
    if client:
        client.delete_object(Bucket=META_BUCKET_NAME, Key=object_key)
        return
    local_path = family_flyer_storage_path(object_key)
    if os.path.isfile(local_path):
        os.remove(local_path)


def family_flyer_access_url(reference, family_id, slot):
    value = stable_family_flyer_reference(reference)
    object_key = bucket_key_from_reference(value)
    if not object_key:
        return value
    if not object_key.startswith("flyers/"):
        return ""
    # A URL do navegador permanece estável. O servidor busca o arquivo privado
    # no Bucket a cada acesso, sem expor nem depender de uma URL assinada que
    # expira depois de uma hora.
    return url_for("family_flyer_file", registro_id=family_id, slot=int(slot))


_USER_CACHE_KEY = "_current_user_cache"


def read_session_accounts():
    """Contas abertas na sessão, em ordem (a mais recente por último). None = sessão antiga.

    Guardamos uma lista de pares [usuario, versao] porque o Flask grava dicionários do
    cookie em ordem alfabética, o que apagaria a informação de qual conta é a mais antiga.
    """
    raw = session.get("accounts")
    if not isinstance(raw, list):
        return None
    accounts = {}
    for entry in raw:
        if isinstance(entry, (list, tuple)) and len(entry) == 2 and isinstance(entry[0], str):
            accounts[entry[0]] = entry[1]
    return accounts


def write_session_accounts(accounts):
    session["accounts"] = [[username, int(version)] for username, version in accounts.items()]


def invalidate_current_user():
    """Descarta o usuário em cache da requisição (chamar sempre que a sessão mudar)."""
    g.pop(_USER_CACHE_KEY, None)


def lookup_account_record(username):
    """Registro do usuário (admin do ambiente ou membro ativo no banco), ou None."""
    username = str(username or "").strip().lower()
    admin = AUTH_USERS.get(username)
    if admin:
        return {**admin, "id": None, "session_version": 0, "apelido": ""}
    return get_meta_member_by_username(username)


def account_payload(username, record):
    return {
        "username": username,
        "display_name": record["display_name"],
        "apelido": str(record.get("apelido") or ""),
        "role": record["role"],
        "can_write": record["role"] == "admin",
        "user_id": record.get("id"),
    }


def account_is_valid(username, record, accounts):
    """A conta vale se existe, está ativa e a versão de sessão guardada ainda é a atual."""
    if not record:
        return False
    if accounts is None:
        return True  # cookie anterior ao recurso de contas múltiplas
    stored = accounts.get(username)
    try:
        return stored is not None and int(stored) == int(record.get("session_version") or 0)
    except (TypeError, ValueError):
        return False


def _resolve_current_user():
    username = session.get("username")
    if not username:
        return None

    accounts = read_session_accounts()

    while True:
        record = lookup_account_record(username)
        if account_is_valid(username, record, accounts):
            if accounts is None:
                write_session_accounts({username: int(record.get("session_version") or 0)})
            return account_payload(username, record)

        # Conta inválida (removida, desativada ou "sair de todos" usado em outro aparelho).
        if accounts is not None:
            accounts.pop(username, None)
        fallback = next(iter(accounts), None) if accounts else None
        if not fallback:
            session.clear()
            return None
        write_session_accounts(accounts)
        session["username"] = username = fallback


# Cada página aberta informa em qual conta foi carregada (cabeçalho enviado pelo account.js).
# Assim, trocar de conta numa aba não faz as outras abas agirem com a conta errada:
# a sala de metas aberta como "gohan" continua enviando fotos como "gohan" mesmo que
# outra aba tenha passado para a conta "kokusai". Só vale para contas já autenticadas
# neste navegador; o cabeçalho não dá acesso a nenhuma conta que não esteja aberta.
TAB_ACCOUNT_HEADER = "X-Kokusai-Conta"
_TAB_MISMATCH_KEY = "_kokusai_tab_account_missing"


def requested_tab_account():
    value = str(request.headers.get(TAB_ACCOUNT_HEADER) or "").strip().lower()
    return value[:64] or None


def resolve_open_account(username):
    """Payload da conta se ela estiver aberta e válida neste navegador; senão None."""
    accounts = read_session_accounts()
    if not username or not accounts or username not in accounts:
        return None
    record = lookup_account_record(username)
    if not account_is_valid(username, record, accounts):
        return None
    return account_payload(username, record)


def get_current_user():
    if _USER_CACHE_KEY in g:
        return g.get(_USER_CACHE_KEY)
    user = _resolve_current_user()
    wanted = requested_tab_account() if user else None
    if wanted and wanted != user["username"]:
        user = resolve_open_account(wanted)
        setattr(g, _TAB_MISMATCH_KEY, user is None)
    setattr(g, _USER_CACHE_KEY, user)
    return user


def home_url_for(account):
    if account and account.get("role") == "member":
        return url_for("meta_room")
    return url_for("home")


def get_open_accounts():
    """Contas autenticadas neste navegador (no máximo MAX_OPEN_ACCOUNTS), já validadas."""
    active = get_current_user()
    accounts = read_session_accounts()
    if not active or accounts is None:
        return []
    result = []
    for username in list(accounts):
        record = lookup_account_record(username)
        if account_is_valid(username, record, accounts):
            payload = account_payload(username, record)
            payload["active"] = username == active["username"]
            result.append(payload)
        else:
            accounts.pop(username, None)
    write_session_accounts(accounts)
    return result


def start_session_for(username, record):
    """Autentica a conta neste navegador, mantendo a outra conta já aberta (se houver)."""
    previous = get_open_accounts()
    stored = read_session_accounts() or {}
    kept = {
        account["username"]: stored[account["username"]]
        for account in previous
        if account["username"] != username and account["username"] in stored
    }
    kept = dict(list(kept.items())[-(MAX_OPEN_ACCOUNTS - 1):]) if MAX_OPEN_ACCOUNTS > 1 else {}
    kept[username] = int(record.get("session_version") or 0)
    session.clear()
    session.permanent = True
    write_session_accounts(kept)
    session["username"] = username
    get_csrf_token()
    invalidate_current_user()


def leave_current_account(username=None):
    """Sai de uma conta (por padrão, a ativa). Devolve a URL de destino.

    Se a conta que saiu não era a ativa (pedido vindo de outra aba), a ativa continua.
    Senão, passa para a outra conta aberta, ou volta para o login.
    """
    active = session.get("username")
    username = username or active
    accounts = read_session_accounts() or {}
    accounts.pop(username, None)
    if username != active and active in accounts:
        record = lookup_account_record(active)
        if account_is_valid(active, record, accounts):
            write_session_accounts(accounts)
            invalidate_current_user()
            return home_url_for(account_payload(active, record))
        accounts.pop(active, None)
    for candidate in list(accounts):
        record = lookup_account_record(candidate)
        if account_is_valid(candidate, record, accounts):
            write_session_accounts(accounts)
            session["username"] = candidate
            invalidate_current_user()
            return home_url_for(account_payload(candidate, record))
        accounts.pop(candidate, None)
    session.clear()
    invalidate_current_user()
    return url_for("login")


def webp_data_uri(value):
    return f"data:image/webp;base64,{value}" if value else ""


def attach_thumbs(accounts):
    """Acrescenta a miniatura (data URI) de cada conta de membro."""
    ids = [account["user_id"] for account in accounts if account.get("user_id")]
    thumbs = {}
    if ids:
        placeholders = ",".join("?" for _ in ids)
        for row in meta_query_all(f"SELECT user_id, thumb_b64 FROM user_profiles WHERE user_id IN ({placeholders})", ids):
            thumbs[row["user_id"]] = webp_data_uri(row["thumb_b64"])
    return [{**account, "thumb": thumbs.get(account.get("user_id"), "")} for account in accounts]


def public_account(account):
    return {
        "username": account["username"],
        "display_name": account["display_name"],
        "apelido": account.get("apelido") or "",
        "role": account["role"],
        "active": bool(account.get("active")),
        "thumb": account.get("thumb") or "",
    }


def hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"), salt, PASSWORD_HASH_ITERATIONS)
    return "$".join([
        "pbkdf2_sha256",
        str(PASSWORD_HASH_ITERATIONS),
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    ])


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
    # Nunca lemos X-Forwarded-For diretamente: o cliente consegue forjar esse cabeçalho
    # e escapar do limite de tentativas. O ProxyFix (acima) já entrega o IP correto aqui.
    return request.remote_addr or "unknown"


def login_attempt_key(username):
    return f"{get_client_ip()}:{str(username or '').lower()[:64]}"


def login_user_key(username):
    return f"user:{str(username or '').lower()[:64]}"


def is_login_limited(key, limit=None):
    limit = LOGIN_MAX_ATTEMPTS if limit is None else limit
    now = time.time()
    with _sheets_lock:
        attempts = [ts for ts in LOGIN_ATTEMPTS.get(key, []) if now - ts < LOGIN_WINDOW_SECONDS]
        LOGIN_ATTEMPTS[key] = attempts
        return len(attempts) >= limit


def record_failed_login(key):
    now = time.time()
    with _sheets_lock:
        attempts = [ts for ts in LOGIN_ATTEMPTS.get(key, []) if now - ts < LOGIN_WINDOW_SECONDS]
        attempts.append(now)
        LOGIN_ATTEMPTS[key] = attempts
        if len(LOGIN_ATTEMPTS) > 5000:
            # Evita crescimento indefinido da memória com chaves antigas.
            stale = [k for k, v in LOGIN_ATTEMPTS.items() if not v or now - v[-1] >= LOGIN_WINDOW_SECONDS]
            for stale_key in stale:
                LOGIN_ATTEMPTS.pop(stale_key, None)


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
    if request.path.startswith("/api/") and g.get(_TAB_MISMATCH_KEY):
        return error_response(
            f"Esta aba foi aberta com a conta @{requested_tab_account()}, que não está mais conectada "
            "neste navegador. Recarregue a página para continuar.",
            409,
        )


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
        "img-src 'self' data: blob: https: http:; "
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


def canonical_staff_name(value):
    name = str(value or "").strip()
    aliases = {
        "kyotaka": "Kiyotaka",
        "kiyotaka": "Kiyotaka",
    }
    return aliases.get(normalized_lookup_key(name), name)


def normalize_money_type(value):
    normalized = normalized_lookup_key(value)
    if normalized in {"dinheiro sujo", "sujo", "dirty", "dirty money"}:
        return "Dinheiro sujo"
    return "Dinheiro limpo"


def normalize_dirty_money_percentage(value, money_type):
    if normalize_money_type(money_type) != "Dinheiro sujo":
        return 0.0
    raw_value = DEFAULT_DIRTY_MONEY_PERCENTAGE if value is None or str(value).strip() == "" else value
    try:
        percentage = float(str(raw_value).replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError("A porcentagem do dinheiro sujo deve ser numérica.")
    if not MIN_DIRTY_MONEY_PERCENTAGE <= percentage <= MAX_DIRTY_MONEY_PERCENTAGE:
        raise ValueError(
            "A porcentagem do dinheiro sujo deve ficar entre "
            f"{MIN_DIRTY_MONEY_PERCENTAGE:g}% e {MAX_DIRTY_MONEY_PERCENTAGE:g}%."
        )
    return round(percentage, 2)


def calculate_payment_values(base_value, money_type, dirty_percentage=None):
    try:
        base = round(float(base_value or 0), 2)
    except (TypeError, ValueError):
        raise ValueError("O valor base informado é inválido.")
    if base < 0 or base > MAX_MONEY_VALUE:
        raise ValueError("O valor base informado é inválido.")

    normalized_type = normalize_money_type(money_type)
    percentage = normalize_dirty_money_percentage(dirty_percentage, normalized_type)
    surcharge = round(base * (percentage / 100), 2) if normalized_type == "Dinheiro sujo" else 0.0
    total = round(base + surcharge, 2)
    if total > MAX_MONEY_VALUE:
        raise ValueError("Valor total muito alto.")
    return normalized_type, base, surcharge, total, percentage


def apply_payment_defaults(item, total_field):
    money_type = normalize_money_type(item.get("tipo_dinheiro"))
    try:
        total = round(float(item.get(total_field) or 0), 2)
    except (TypeError, ValueError):
        total = 0.0
    try:
        base = round(float(item.get("valor_base") or total), 2)
    except (TypeError, ValueError):
        base = total
    try:
        surcharge = round(float(item.get("acrescimo_dinheiro_sujo") or 0), 2)
    except (TypeError, ValueError):
        surcharge = 0.0

    raw_percentage = item.get("percentual_dinheiro_sujo")
    if money_type == "Dinheiro sujo" and (raw_percentage is None or str(raw_percentage).strip() == ""):
        raw_percentage = round((surcharge / base) * 100, 2) if base > 0 and str(item.get("acrescimo_dinheiro_sujo") or "").strip() else DEFAULT_DIRTY_MONEY_PERCENTAGE
    try:
        percentage = normalize_dirty_money_percentage(raw_percentage, money_type)
    except ValueError:
        percentage = DEFAULT_DIRTY_MONEY_PERCENTAGE if money_type == "Dinheiro sujo" else 0.0

    item["tipo_dinheiro"] = money_type
    item["valor_base"] = base
    item["acrescimo_dinheiro_sujo"] = surcharge
    item["percentual_dinheiro_sujo"] = percentage
    return item


def canonical_family_name(value):
    name = str(value or "").strip()
    aliases = {
        "bandoleros": "Cartel",
        "bandolero": "Cartel",
        "los bandoleros": "Cartel",
        "blackherts": "Black Hearts",
        "black heart": "Black Hearts",
        "black hearts": "Black Hearts",
        "the lost": "The Lost MC",
        "the lost mc": "The Lost MC",
        "lost mc": "The Lost MC",
        "laguardia": "La Guardia",
        "la guardia": "La Guardia",
        "leviata": "Leviatã",
        "hells angels": "Hells",
        "caos": "Chaos",
        "balaklava": "Balaclava",
    }
    return aliases.get(normalized_lookup_key(name), name)


def normalize_market_status(value):
    normalized = normalized_lookup_key(value)
    if normalized in {"sem mercado", "mercado inexistente", "nao temos mercado", "sem mercado aberto"}:
        return "Sem mercado"
    if normalized in {"em negociacao", "negociacao", "mercado em negociacao", "ainda sem mercado"}:
        return "Em negociação"
    if normalized in {"fechado", "fechada", "mercado fechado", "nao", "n"}:
        return "Fechado"
    return "Aberto"


def family_market_is_open(value):
    return normalize_market_status(value) == "Aberto"


def family_market_block_message(family):
    name = str(family.get("nome") or "Esta família").strip()
    status = normalize_market_status(family.get("mercado"))
    if status == "Em negociação":
        return f"{name} ainda não possui mercado estabelecido. Compras, vendas e encomendas estão bloqueadas."
    if status == "Sem mercado":
        return f"{name} está sem mercado aberto. Não compramos nem vendemos para esta família."
    return f"O mercado de {name} está fechado. Compras, vendas e encomendas estão bloqueadas."


def normalize_flag(value):
    if isinstance(value, bool):
        return value
    return normalized_lookup_key(value) in {"1", "true", "sim", "yes", "on"}


def family_id_from_name(name):
    digest = hashlib.sha1(normalized_lookup_key(name).encode("utf-8")).hexdigest()[:12].upper()
    return f"KKSF-{digest}"


def clean_optional_image_reference(value, field_name="Flyer"):
    reference = clean_text(value, field_name, max_length=1000, required=False)
    if not reference:
        return ""
    reference = stable_family_flyer_reference(reference)
    object_key = bucket_key_from_reference(reference)
    if object_key:
        if not object_key.startswith("flyers/"):
            raise ValueError(f"{field_name} possui uma referência de armazenamento inválida.")
        return bucket_reference(object_key)
    parsed = urlparse(reference)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field_name} deve ser uma imagem enviada ou um link http/https válido.")
    return reference


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
        str(data.get("contato_2") or "").strip(),
        str(data.get("flyer_url_2") or "").strip(),
        canonical_staff_name(data.get("responsavel_contato")),
    ]


def merge_duplicate_family_rows(primary_row, duplicate_row, canonical_name):
    """Consolida duplicatas sem descartar flyers, contatos ou regras comerciais."""
    size = len(FAMILIAS_HEADERS)
    primary = list(primary_row[:size]) + [""] * max(0, size - len(primary_row))
    duplicate = list(duplicate_row[:size]) + [""] * max(0, size - len(duplicate_row))
    original = list(primary)

    primary[FAMILIAS_HEADERS.index("nome")] = canonical_name

    # Campos simples: o cadastro principal prevalece, e a duplicata preenche lacunas.
    for field_name in (
        "icone", "preco_venda_para_familia", "preco_compra_da_familia",
        "observacao", "responsavel_contato",
    ):
        field_index = FAMILIAS_HEADERS.index(field_name)
        if not str(primary[field_index] or "").strip() and str(duplicate[field_index] or "").strip():
            primary[field_index] = duplicate[field_index]

    # Se uma das grafias já foi liberada, mantém o mercado aberto na unificação.
    market_index = FAMILIAS_HEADERS.index("mercado")
    if family_market_is_open(duplicate[market_index]) and not family_market_is_open(primary[market_index]):
        primary[market_index] = "Aberto"

    # Aproveita os dois espaços disponíveis para não perder flyers nem contatos.
    for first_field, second_field in (("flyer_url", "flyer_url_2"), ("contato", "contato_2")):
        first_index = FAMILIAS_HEADERS.index(first_field)
        second_index = FAMILIAS_HEADERS.index(second_field)
        unique_values = []
        for value in (primary[first_index], primary[second_index], duplicate[first_index], duplicate[second_index]):
            clean_value = str(value or "").strip()
            if clean_value and clean_value not in unique_values:
                unique_values.append(clean_value)
        primary[first_index] = unique_values[0] if unique_values else ""
        primary[second_index] = unique_values[1] if len(unique_values) > 1 else ""

    if normalize_flag(duplicate[FAMILIAS_HEADERS.index("flyer_oculto")]):
        primary[FAMILIAS_HEADERS.index("flyer_oculto")] = "Sim"

    if primary != original:
        primary[FAMILIAS_HEADERS.index("atualizado_em")] = format_timestamp()
    return primary, primary != original


def ensure_familias_ready(worksheet, force=False):
    # Serializa a manutenção para impedir cadastros duplicados em acessos simultâneos.
    with _sheets_lock:
        return _ensure_familias_ready_locked(worksheet, force=force)


def _ensure_familias_ready_locked(worksheet, force=False):
    now = time.time()
    with _sheets_lock:
        if not force and now - _familias_maintenance_cache.get("checked_at", 0) < SHEETS_MAINTENANCE_SECONDS:
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
            primary_index, primary_row = existing[key]
            merged_row, merged_changed = merge_duplicate_family_rows(primary_row, row, name)
            if merged_changed:
                worksheet.update(
                    f"A{primary_index}:O{primary_index}",
                    [merged_row[:len(FAMILIAS_HEADERS)]],
                    value_input_option="RAW",
                )
                existing[key] = (primary_index, merged_row)
                changed = True
            duplicate_indexes.append(row_index)
            continue
        existing[key] = (row_index, row)
        if name != sheet_cell(row, 2):
            worksheet.update_cell(row_index, 3, name)
            changed = True

    # Remove a linha repetida somente depois de consolidar seus dados no cadastro principal.
    for row_index in reversed(duplicate_indexes):
        worksheet.delete_rows(row_index)
        changed = True

    if duplicate_indexes:
        invalidate_values_cache(FAMILIAS_WORKSHEET_NAME)
        rows = cached_get_all_values(FAMILIAS_WORKSHEET_NAME, worksheet, force=True)
        existing = {}
        for row_index, row in enumerate(rows[1:], start=2):
            key = normalized_lookup_key(canonical_family_name(sheet_cell(row, 2)))
            if key and key not in existing:
                existing[key] = (row_index, row)

    # Os cadastros padrão já foram migrados nas versões anteriores. A manutenção
    # só corrige famílias que ainda existem; nunca recria uma família excluída.
    for default in DEFAULT_FAMILIAS:
        key = normalized_lookup_key(default["nome"])
        if key not in existing:
            continue

        row_index, existing_row = existing[key]
        if not row_index:
            continue
        padded = list(existing_row[:len(FAMILIAS_HEADERS)]) + [""] * max(0, len(FAMILIAS_HEADERS) - len(existing_row))
        row_changed = False
        responsible_index = FAMILIAS_HEADERS.index("responsavel_contato")
        current_responsible = str(padded[responsible_index] or "").strip()
        canonical_responsible = canonical_staff_name(current_responsible)
        if canonical_responsible != current_responsible:
            padded[responsible_index] = canonical_responsible
            row_changed = True
        elif not current_responsible and default.get("responsavel_contato"):
            padded[responsible_index] = default["responsavel_contato"]
            row_changed = True
        if not str(padded[FAMILIAS_HEADERS.index("icone")] or "").strip() and default.get("icone"):
            padded[FAMILIAS_HEADERS.index("icone")] = default["icone"]
            row_changed = True
        restricted_status = RESTRICTED_FAMILY_MARKETS.get(key)
        if restricted_status and normalize_market_status(padded[FAMILIAS_HEADERS.index("mercado")]) != restricted_status:
            padded[FAMILIAS_HEADERS.index("mercado")] = restricted_status
            row_changed = True
        if row_changed:
            padded[FAMILIAS_HEADERS.index("atualizado_em")] = format_timestamp()
            worksheet.update(f"A{row_index}:O{row_index}", [padded[:len(FAMILIAS_HEADERS)]], value_input_option="RAW")
            existing[key] = (row_index, padded)
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
                worksheet.update(f"A{row_index}:O{row_index}", [padded[:len(FAMILIAS_HEADERS)]], value_input_option="RAW")
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
    item = row_to_dict(row, COMPRAS_HEADERS)
    item["familia_id"] = str(item.get("familia_id") or "").strip()
    item["familia_nome"] = str(item.get("familia_nome") or item.get("quem_vendeu") or "").strip()
    item["familia_icone"] = str(item.get("familia_icone") or "").strip()
    return apply_payment_defaults(item, "valor_total")


def normalize_venda(row):
    item = row_to_dict(row, VENDAS_HEADERS)
    item["familia_nome"] = str(item.get("familia_nome") or item.get("quem_compra") or "").strip()
    item["familia_icone"] = str(item.get("familia_icone") or "").strip()
    item["encomenda_id"] = str(item.get("encomenda_id") or "").strip()
    return apply_payment_defaults(item, "valor_total")


def normalize_encomenda(row):
    item = row_to_dict(row, ENCOMENDAS_HEADERS)
    item["entregue"] = validate_yes_no(item.get("entregue")) or "Não"
    item["itens"] = parse_encomenda_items_json(item.get("itens_json"))
    item["familia_nome"] = str(item.get("familia_nome") or item.get("quem_pediu") or "").strip()
    item["familia_icone"] = str(item.get("familia_icone") or "").strip()
    item["prioridade"] = normalize_flag(item.get("prioridade"))
    deadline = parse_encomenda_deadline(item.get("para_quando"), item.get("data"))
    item["prazo_iso"] = deadline.isoformat(timespec="minutes") if deadline else ""
    item["para_quando_exibicao"] = (
        deadline.strftime("%d/%m/%Y às %H:%M") if deadline else str(item.get("para_quando") or "").strip()
    )
    item.pop("itens_json", None)
    return apply_payment_defaults(item, "valor")


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
        raise ValueError("Informe a quantidade de pelo menos um produto do pedido.")

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


def price_order_items(items, money_type, dirty_percentage=None):
    """Aplica a porcentagem escolhida e distribui os centavos entre os itens."""
    normalized_type = normalize_money_type(money_type)
    total_base = round(sum(float(item.get("valor_total") or 0) for item in items), 2)
    _, _, total_surcharge, total_value, percentage = calculate_payment_values(
        total_base, normalized_type, dirty_percentage,
    )
    remaining_surcharge = total_surcharge
    priced_items = []

    for index, item in enumerate(items):
        base_value = round(float(item.get("valor_total") or 0), 2)
        if normalized_type == "Dinheiro sujo":
            if index == len(items) - 1:
                surcharge = round(remaining_surcharge, 2)
            else:
                surcharge = min(round(base_value * (percentage / 100), 2), max(remaining_surcharge, 0.0))
                remaining_surcharge = round(remaining_surcharge - surcharge, 2)
        else:
            surcharge = 0.0
        priced_item = dict(item)
        priced_item.update({
            "tipo_dinheiro": normalized_type,
            "valor_base": base_value,
            "acrescimo_dinheiro_sujo": surcharge,
            "percentual_dinheiro_sujo": percentage,
            "valor_final": round(base_value + surcharge, 2),
        })
        priced_items.append(priced_item)

    return priced_items, total_base, total_surcharge, total_value


def build_venda_row_from_encomenda(item, entregue_em=None):
    quantidade, produto = parse_encomenda_item(item.get("o_que_pediu"))
    money_type = normalize_money_type(item.get("tipo_dinheiro"))
    raw_base_value = item.get("valor_base")
    if str(raw_base_value or "").strip() == "":
        raw_base_value = item.get("valor")
    payment = apply_payment_defaults(dict(item), "valor")
    percentage = payment["percentual_dinheiro_sujo"]
    _, valor_base, surcharge, valor_total, percentage = calculate_payment_values(
        raw_base_value, money_type, percentage,
    )
    valor_unitario = round(valor_base / quantidade, 2) if quantidade else valor_base
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
        str(item.get("familia_id") or "").strip(),
        str(item.get("familia_nome") or item.get("quem_pediu") or "").strip(),
        str(item.get("familia_icone") or "").strip(),
        encomenda_id,
        money_type,
        valor_base,
        surcharge,
        percentage,
    ]


def build_venda_rows_from_encomenda(item, entregue_em=None):
    """Converte uma encomenda em uma ou mais vendas sem perder os itens combinados."""
    items = parse_encomenda_items_json(item.get("itens_json"))
    if not items:
        return [build_venda_row_from_encomenda(item, entregue_em=entregue_em)]

    payment = apply_payment_defaults(dict(item), "valor")
    money_type = payment["tipo_dinheiro"]
    percentage = payment["percentual_dinheiro_sujo"]
    priced_items, _, _, _ = price_order_items(items, money_type, percentage)
    encomenda_id = str(item.get("id") or "").strip()
    prazo = str(item.get("para_quando") or "").strip()
    observacao_original = str(item.get("observacao") or "").strip()
    rows = []
    for index, order_item in enumerate(priced_items, start=1):
        detalhes = [f"Convertida da encomenda {encomenda_id} (item {index}/{len(priced_items)})."]
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
            order_item["valor_final"],
            observacao,
            str(item.get("familia_id") or "").strip(),
            str(item.get("familia_nome") or item.get("quem_pediu") or "").strip(),
            str(item.get("familia_icone") or "").strip(),
            encomenda_id,
            money_type,
            order_item["valor_base"],
            order_item["acrescimo_dinheiro_sujo"],
            order_item["percentual_dinheiro_sujo"],
        ])
    return rows


def move_encomenda_to_vendas(worksheet, row_index, encomenda_item, entregue_em=None):
    """Grava a venda e só então remove a encomenda da aba ativa.

    A operação é idempotente: se uma tentativa anterior tiver criado a venda,
    a próxima apenas confirma as linhas existentes e conclui a exclusão da
    encomenda. Isso evita tanto duplicidade quanto uma entrega "pela metade".
    """
    vendas_worksheet = get_vendas_worksheet()
    venda_rows = build_venda_rows_from_encomenda(encomenda_item, entregue_em=entregue_em)
    venda_ids = [str(venda_row[0]) for venda_row in venda_rows]

    existing_rows = cached_get_all_values(VENDAS_WORKSHEET_NAME, vendas_worksheet, force=True)
    existing_ids = {sheet_cell(existing_row, 0) for existing_row in existing_rows[1:]}
    for venda_row in venda_rows:
        if venda_row[0] not in existing_ids:
            vendas_worksheet.append_row(venda_row, value_input_option="RAW")
            existing_ids.add(venda_row[0])

    # Confirma no Google Sheets que todas as vendas foram persistidas antes
    # de apagar a encomenda. Sem essa confirmação ela continua disponível
    # para uma nova tentativa, sem perder o pedido.
    invalidate_values_cache(VENDAS_WORKSHEET_NAME)
    persisted_rows = cached_get_all_values(VENDAS_WORKSHEET_NAME, vendas_worksheet, force=True)
    persisted_ids = {sheet_cell(persisted_row, 0) for persisted_row in persisted_rows[1:]}
    missing_ids = [venda_id for venda_id in venda_ids if venda_id not in persisted_ids]
    if missing_ids:
        raise RuntimeError("Não foi possível confirmar a venda no Google Sheets. A encomenda foi mantida para nova tentativa.")

    worksheet.delete_rows(row_index)
    invalidate_values_cache(ENCOMENDAS_WORKSHEET_NAME, VENDAS_WORKSHEET_NAME)
    return venda_ids


def normalize_family(row):
    item = row_to_dict(row, FAMILIAS_HEADERS)
    item["nome"] = canonical_family_name(item.get("nome"))
    item["mercado"] = normalize_market_status(item.get("mercado"))
    item["mercado_aberto"] = family_market_is_open(item.get("mercado"))
    item["responsavel_contato"] = canonical_staff_name(item.get("responsavel_contato"))
    item["flyer_oculto"] = normalize_flag(item.get("flyer_oculto"))
    for slot, field in ((1, "flyer_url"), (2, "flyer_url_2")):
        stored_reference = stable_family_flyer_reference(item.get(field))
        item[f"{field}_stored"] = stored_reference
        item[field] = family_flyer_access_url(stored_reference, item.get("id"), slot)
    return item


def get_family_snapshot(family_id, require_open=False):
    """Resolve a família no servidor para não confiar no nome enviado pelo navegador."""
    clean_id = clean_text(family_id, "Família/gangue", max_length=80, required=True)
    worksheet = get_familias_worksheet()
    row_index, row = find_row_by_id(worksheet, clean_id)
    if not row_index:
        raise ValueError("Selecione uma família/gangue cadastrada.")
    family = normalize_family(row)
    if not str(family.get("nome") or "").strip():
        raise ValueError("A família/gangue selecionada não possui um cadastro válido.")
    if require_open and not family.get("mercado_aberto"):
        raise ValueError(family_market_block_message(family))
    return {
        "id": str(family.get("id") or clean_id).strip(),
        "nome": str(family.get("nome") or "").strip(),
        "icone": str(family.get("icone") or "").strip(),
        "mercado": family["mercado"],
        "mercado_aberto": bool(family.get("mercado_aberto")),
        "responsavel_contato": family["responsavel_contato"],
    }


def validate_manual_party_against_families(name):
    """Impede que um cadastro de família seja contornado pelo campo de texto livre."""
    lookup_key = normalized_lookup_key(canonical_family_name(name))
    if not lookup_key:
        return

    worksheet = get_familias_worksheet()
    rows = cached_get_all_values(FAMILIAS_WORKSHEET_NAME, worksheet)
    for row in rows[1:]:
        family = normalize_family(row)
        if normalized_lookup_key(family.get("nome")) != lookup_key:
            continue
        if not family.get("mercado_aberto"):
            raise ValueError(family_market_block_message(family))
        raise ValueError(
            f"{family['nome']} já está cadastrada. Selecione essa família no campo Família/gangue "
            "para registrar o responsável e manter os relatórios corretos."
        )


def parse_record_datetime(value):
    """Lê as datas já usadas nas planilhas, inclusive registros antigos."""
    raw_value = str(value or "").strip()
    if not raw_value:
        return None

    for pattern in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw_value, pattern)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def parse_encomenda_deadline(value, created_at=None):
    """Converte o prazo da encomenda em data ordenável, inclusive formatos antigos."""
    raw_value = str(value or "").strip()
    if not raw_value:
        return None

    parsed = parse_record_datetime(raw_value)
    if parsed:
        # Datas sem horário representam o fim daquele dia.
        if not re.search(r"(?:T|\s)\d{1,2}:\d{2}", raw_value):
            parsed = parsed.replace(hour=23, minute=59, second=0, microsecond=0)
        if parsed.tzinfo:
            parsed = parsed.astimezone(now_local().tzinfo).replace(tzinfo=None)
        return parsed

    # Compatibilidade: "15/08 - 21h", "15/08 21:30" e variações.
    match = re.search(
        r"(?<!\d)(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?"
        r"(?:\D+?(\d{1,2})(?::|h)(\d{2})?)?",
        raw_value,
        re.IGNORECASE,
    )
    if not match:
        return None

    created = parse_record_datetime(created_at) or now_local().replace(tzinfo=None)
    if created.tzinfo:
        created = created.astimezone(now_local().tzinfo).replace(tzinfo=None)
    day, month = int(match.group(1)), int(match.group(2))
    raw_year = match.group(3)
    year = int(raw_year) if raw_year else created.year
    if year < 100:
        year += 2000
    hour = int(match.group(4)) if match.group(4) is not None else 23
    minute = int(match.group(5)) if match.group(5) is not None else (0 if match.group(4) is not None else 59)

    try:
        deadline = datetime(year, month, day, hour, minute)
    except ValueError:
        return None

    # Um pedido criado no fim do ano para janeiro pertence ao ano seguinte.
    if not raw_year and deadline < created - timedelta(days=180):
        try:
            deadline = deadline.replace(year=year + 1)
        except ValueError:
            return None
    return deadline


def encomenda_sort_key(item):
    deadline = parse_encomenda_deadline(item.get("para_quando"), item.get("data")) or datetime.max
    created = parse_record_datetime(item.get("data")) or datetime.max
    if created.tzinfo:
        created = created.astimezone(now_local().tzinfo).replace(tzinfo=None)
    # Prioridade manual vence; dentro de cada grupo, o prazo mais próximo vem primeiro.
    return (0 if normalize_flag(item.get("prioridade")) else 1, deadline, created)


def report_month_payload(value):
    month_value = str(value or "").strip() or now_local().strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-\d{2}", month_value):
        raise ValueError("Mês inválido. Use o formato AAAA-MM.")

    year, month = (int(part) for part in month_value.split("-", 1))
    if year < 2000 or year > 2100 or month < 1 or month > 12:
        raise ValueError("Mês inválido.")

    month_names = (
        "janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
    )
    return {
        "value": month_value,
        "year": year,
        "month": month,
        "label": f"{month_names[month - 1].capitalize()} de {year}",
    }


def record_is_in_report_month(record, month_payload):
    record_date = parse_record_datetime(record.get("data"))
    return bool(
        record_date
        and record_date.year == month_payload["year"]
        and record_date.month == month_payload["month"]
    )


def encomenda_id_from_venda(venda):
    explicit_id = str(venda.get("encomenda_id") or "").strip()
    if explicit_id:
        return explicit_id

    observation = str(venda.get("observacao") or "")
    match = re.search(r"Convertida da encomenda\s+([^\s.]+)", observation, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def build_family_sales_report(month_value=None):
    month_payload = report_month_payload(month_value)

    family_worksheet = get_familias_worksheet()
    family_rows = cached_get_all_values(FAMILIAS_WORKSHEET_NAME, family_worksheet)
    families = [normalize_family(row) for row in family_rows[1:] if str(sheet_cell(row, 2)).strip()]
    families_by_id = {str(item.get("id") or "").strip(): item for item in families if str(item.get("id") or "").strip()}
    families_by_name = {normalized_lookup_key(item.get("nome")): item for item in families if normalized_lookup_key(item.get("nome"))}

    groups = {}

    def resolve_family(record, name_field):
        """Resolve somente famílias existentes no cadastro atual.

        Registros antigos podem ter colunas extras deslocadas. Por isso, nunca
        usamos um nome/emoji gravado na venda como uma nova família do ranking:
        ele precisa corresponder a um cadastro real em Famílias.
        """
        family_id = str(record.get("familia_id") or "").strip()
        current = families_by_id.get(family_id)
        if current:
            return {
                "id": str(current.get("id") or family_id).strip(),
                "nome": str(current.get("nome") or "").strip(),
                "icone": str(current.get("icone") or "").strip(),
                "responsavel_contato": str(current.get("responsavel_contato") or "").strip(),
                "mercado": current.get("mercado") or "Aberto",
            }

        # Primeiro tentamos a foto do cadastro gravada na venda; depois, o
        # comprador/pedinte. Assim uma coluna deslocada (ex.: "825000") não
        # impede a recuperação do nome real, se ele estiver em quem_compra.
        candidates = [record.get("familia_nome"), record.get(name_field)]
        checked = set()
        for candidate in candidates:
            record_name = str(candidate or "").strip()
            lookup_key = normalized_lookup_key(canonical_family_name(record_name))
            if not lookup_key or lookup_key in checked:
                continue
            checked.add(lookup_key)
            current = families_by_name.get(lookup_key)
            if current:
                return {
                    "id": str(current.get("id") or "").strip(),
                    "nome": str(current.get("nome") or record_name).strip(),
                    "icone": str(current.get("icone") or "").strip(),
                    "responsavel_contato": str(current.get("responsavel_contato") or "").strip(),
                    "mercado": current.get("mercado") or "Aberto",
                }
        return None

    def get_group(family):
        family_key = str(family.get("id") or "").strip() or normalized_lookup_key(family.get("nome"))
        if family_key not in groups:
            groups[family_key] = {
                "familia_id": str(family.get("id") or "").strip(),
                "nome": str(family.get("nome") or "Família sem nome").strip(),
                "icone": str(family.get("icone") or "").strip() or "🤝",
                "responsavel_contato": str(family.get("responsavel_contato") or "").strip(),
                "mercado": normalize_market_status(family.get("mercado")),
                "total_gasto": 0.0,
                "valor_pendente": 0.0,
                "itens_comprados": 0,
                "vendas_linhas": 0,
                "_transacoes": set(),
                "_encomendas_finalizadas": set(),
                "_compras_diretas": set(),
                "_encomendas_pendentes": set(),
            }
        return groups[family_key]

    vendas_worksheet = get_vendas_worksheet()
    vendas_rows = cached_get_all_values(VENDAS_WORKSHEET_NAME, vendas_worksheet)
    unlinked_sales = 0
    unlinked_value = 0.0

    for row in vendas_rows[1:]:
        venda = normalize_venda(row)
        if not record_is_in_report_month(venda, month_payload):
            continue
        try:
            sale_value = float(venda.get("valor_total") or 0)
        except (TypeError, ValueError):
            sale_value = 0.0
        try:
            quantity = int(float(venda.get("quantidade") or 0))
        except (TypeError, ValueError):
            quantity = 0

        family = resolve_family(venda, "quem_compra")
        if not family:
            unlinked_sales += 1
            unlinked_value += sale_value
            continue

        group = get_group(family)
        sale_id = str(venda.get("id") or "").strip() or f"linha-{group['vendas_linhas'] + 1}"
        order_id = encomenda_id_from_venda(venda)
        if order_id:
            group["_encomendas_finalizadas"].add(order_id)
            group["_transacoes"].add(f"encomenda:{order_id}")
        else:
            group["_compras_diretas"].add(sale_id)
            group["_transacoes"].add(f"venda:{sale_id}")
        group["total_gasto"] += sale_value
        group["itens_comprados"] += max(quantity, 0)
        group["vendas_linhas"] += 1

    encomendas_worksheet = get_encomendas_worksheet()
    encomendas_rows = cached_get_all_values(ENCOMENDAS_WORKSHEET_NAME, encomendas_worksheet)
    for row in encomendas_rows[1:]:
        encomenda = normalize_encomenda(row)
        if not record_is_in_report_month(encomenda, month_payload):
            continue
        family = resolve_family(encomenda, "quem_pediu")
        if not family:
            continue
        group = get_group(family)
        order_id = str(encomenda.get("id") or "").strip()
        if order_id:
            group["_encomendas_pendentes"].add(order_id)
        try:
            group["valor_pendente"] += float(encomenda.get("valor") or 0)
        except (TypeError, ValueError):
            pass

    ranking = []
    for group in groups.values():
        item = {
            "familia_id": group["familia_id"],
            "nome": group["nome"],
            "icone": group["icone"],
            "responsavel_contato": group["responsavel_contato"],
            "mercado": group["mercado"],
            "total_gasto": round(group["total_gasto"], 2),
            "valor_pendente": round(group["valor_pendente"], 2),
            "compras": len(group["_transacoes"]),
            "compras_diretas": len(group["_compras_diretas"]),
            "encomendas_finalizadas": len(group["_encomendas_finalizadas"]),
            "encomendas_pendentes": len(group["_encomendas_pendentes"]),
            "itens_comprados": group["itens_comprados"],
            "vendas_linhas": group["vendas_linhas"],
        }
        ranking.append(item)

    ranking.sort(
        key=lambda item: (
            -item["total_gasto"],
            -item["compras"],
            -item["encomendas_pendentes"],
            normalized_lookup_key(item["nome"]),
        )
    )
    for position, item in enumerate(ranking, start=1):
        item["posicao"] = position

    summary = {
        "gangues": len(ranking),
        "total_gasto": round(sum(item["total_gasto"] for item in ranking), 2),
        "compras": sum(item["compras"] for item in ranking),
        "encomendas_finalizadas": sum(item["encomendas_finalizadas"] for item in ranking),
        "encomendas_pendentes": sum(item["encomendas_pendentes"] for item in ranking),
        "valor_pendente": round(sum(item["valor_pendente"] for item in ranking), 2),
        "vendas_sem_familia": unlinked_sales,
        "valor_sem_familia": round(unlinked_value, 2),
    }
    return {
        "mes": month_payload["value"],
        "mes_label": month_payload["label"],
        "gerado_em": format_timestamp(),
        "resumo": summary,
        "ranking": ranking,
    }


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


@app.get("/")
@require_login
def home():
    user = get_current_user()
    if user and user.get("role") == "member":
        return redirect(url_for("meta_room"))
    return render_template("index.html")


def render_login(error=None, selected="", next_url=None, status=200):
    return render_template(
        "login.html",
        error=error,
        selected_username=selected,
        next_url=next_url or safe_next_url(None),
        open_accounts=[public_account(account) for account in attach_thumbs(get_open_accounts())],
    ), status


@app.route("/login", methods=["GET", "POST"])
def login():
    # Com ?trocar=1 a tela de escolha de conta abre mesmo para quem já está logado
    # (é como se entra com uma segunda conta ou se alterna entre as abertas).
    switching = request.values.get("trocar") == "1"
    if get_current_user() and not switching:
        return redirect(url_for("home"))

    next_url = safe_next_url(request.args.get("next"))

    if request.method == "POST":
        csrf_error = csrf_error_if_invalid()
        if csrf_error:
            return render_login("Sessão de login expirada. Atualize a página e tente novamente.", next_url=next_url, status=403)

        username = canonical_member_username(request.form.get("username", ""))
        password = request.form.get("password", "")
        key = login_attempt_key(username)
        user_key = login_user_key(username)

        if is_login_limited(key) or is_login_limited(user_key, LOGIN_MAX_ATTEMPTS_PER_USER):
            return render_login("Muitas tentativas de login. Aguarde alguns minutos e tente novamente.", username, next_url, 429)

        record = lookup_account_record(username)

        if record and verify_password(password, record["password_hash"]):
            start_session_for(username, record)
            clear_login_attempts(key)
            if record.get("role") == "member":
                return redirect(url_for("meta_room"))
            return redirect(safe_next_url(request.form.get("next") or next_url))

        record_failed_login(key)
        record_failed_login(user_key)
        return render_login("Usuário ou senha inválidos.", username, next_url)

    return render_login(next_url=next_url)


@app.route("/logout", methods=["GET", "POST"])
def logout():
    if request.method == "POST":
        csrf_error = csrf_error_if_invalid()
        if csrf_error:
            return csrf_error
        # Por padrão sai só da conta da página (e passa para a outra conta aberta, se houver).
        if request.form.get("escopo") != "todas":
            conta = str(request.form.get("conta") or "").strip().lower()
            accounts = read_session_accounts() or {}
            return redirect(leave_current_account(conta if conta in accounts else None))
    session.clear()
    invalidate_current_user()
    return redirect(url_for("login"))


@app.post("/conta/trocar")
def switch_account():
    csrf_error = csrf_error_if_invalid()
    if csrf_error:
        return csrf_error
    username = request.form.get("username", "").strip().lower()
    for account in get_open_accounts():
        if account["username"] == username:
            session["username"] = username
            session.permanent = True
            invalidate_current_user()
            return redirect(home_url_for(account))
    # A conta não está mais aberta neste navegador: volta para a escolha de conta.
    return redirect(url_for("login", trocar=1))


@app.get("/api/auth/accounts")
@require_login
def list_open_accounts():
    accounts = [public_account(account) for account in attach_thumbs(get_open_accounts())]
    response = jsonify({
        "ok": True,
        "active": next((account for account in accounts if account["active"]), None),
        "others": [account for account in accounts if not account["active"]],
        "max": MAX_OPEN_ACCOUNTS,
    })
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/session")
@require_login
def current_session():
    return jsonify({"ok": True, "user": get_current_user()})


@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "kokusai-system",
        "version": APP_RELEASE,
        "persistent_storage": "bucket" if storage_bucket_configured() else ("unavailable" if IS_RAILWAY else "local-development"),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })


def build_meta_room_payload(user_id, week_start=None):
    member = get_meta_member_by_id(user_id)
    if not member:
        raise ValueError("Membro não encontrado.")
    if week_start:
        submission = get_meta_submission(user_id, week_start)
    else:
        submission = get_current_meta_submission(user_id)
    if not submission:
        raise ValueError("Sala semanal não encontrada.")
    photos = get_meta_photos(submission["id"])
    profile = get_member_profile(user_id)
    history = get_meta_room_history(user_id, exclude_week_start=submission["week_start"])
    start_date = parse_date_br(submission["week_start"])
    schedule = meta_week_payload(start_date) if start_date else {}
    closure = get_meta_week_closure(submission["week_start"])
    uploads_open = meta_submission_uploads_open(submission) and not closure
    unpaid_streak = int(get_meta_unpaid_streaks().get(user_id, 0))
    return {
        "member": {
            "id": member["id"],
            "username": member["username"],
            "display_name": member["display_name"],
            "apelido": profile.get("apelido") or "",
            "avatar": member_avatar_url(member["id"], profile.get("avatar_version"), profile.get("thumb_b64"), thumb=False),
            "thumb": member_avatar_url(member["id"], profile.get("avatar_version"), profile.get("thumb_b64")),
        },
        "submission": submission,
        "schedule": {
            **schedule,
            "envios_abertos": uploads_open,
            "closed": bool(closure),
        },
        "photos": [serialize_meta_photo(photo) for photo in photos],
        "history": history,
        "payment_monitor": {
            "consecutive_unpaid_weeks": unpaid_streak,
            "warning": unpaid_streak >= 3,
            "warning_threshold": 3,
        },
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
        response = jsonify(build_meta_room_payload(user["user_id"]))
        # As URLs das fotos são temporárias e a quantidade muda após cada
        # envio; esta resposta nunca deve ser reutilizada pelo navegador.
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        return response
    except Exception as error:
        log_error("Falha ao carregar sala individual de meta", error)
        return error_response(str(error))


@app.post("/api/meta-room/photos")
@require_member
def upload_meta_room_photo():
    try:
        user = get_current_user()
        submission = get_current_meta_submission(user["user_id"])
        if not meta_submission_uploads_open(submission) or get_meta_week_closure(submission["week_start"]):
            return error_response(
                f"O prazo desta meta terminou em {submission['week_end']} às 23:59. A quinta-feira é reservada para conferência.",
                409,
            )
        if submission["status"] in {"Pago", "Não pago"}:
            return error_response("Esta meta já foi revisada pela administração.", 409)

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
        photos = get_meta_photos(submission["id"])
        response = jsonify({
            "ok": True,
            "message": "Foto enviada para sua sala com sucesso.",
            "photo_id": photo_id,
            "photos": [serialize_meta_photo(photo) for photo in photos],
        })
        response.headers["Cache-Control"] = "no-store"
        return response, 201
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
            SELECT p.id, p.object_key, p.submission_id, p.user_id, s.status, s.week_start, s.week_end
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
        if not meta_submission_uploads_open(photo) or get_meta_week_closure(photo["week_start"]):
            return error_response("O prazo terminou na quarta-feira às 23:59 e as fotos estão bloqueadas para conferência.", 409)
        if photo["status"] in {"Pago", "Não pago"}:
            return error_response("Esta meta já foi revisada pela administração.", 409)

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
        if storage_bucket_configured():
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
        week = get_admin_meta_week()
        rooms = meta_query_all(
            """
            SELECT u.id AS user_id, u.username, u.display_name, s.id AS submission_id,
                   s.status, s.admin_note, s.submitted_at, s.reviewed_at,
                   (SELECT COUNT(*) FROM meta_photos p WHERE p.submission_id = s.id) AS photo_count,
                   COALESCE(pr.apelido, '') AS apelido,
                   COALESCE(pr.avatar_version, 0) AS avatar_version,
                   CASE WHEN COALESCE(pr.thumb_b64, '') <> '' THEN 1 ELSE 0 END AS has_photo
            FROM meta_users u
            JOIN meta_submissions s ON s.user_id = u.id AND s.week_start = ?
            LEFT JOIN user_profiles pr ON pr.user_id = u.id
            WHERE u.role = 'member' AND u.active = 1
            ORDER BY u.display_name ASC
            """,
            (week["semana_inicio"],),
        )
        unpaid_streaks = get_meta_unpaid_streaks()
        for room in rooms:
            room["avatar"] = member_avatar_url(room["user_id"], room.pop("avatar_version"), room.pop("has_photo"))
            streak = int(unpaid_streaks.get(room["user_id"], 0))
            room["consecutive_unpaid_weeks"] = streak
            room["payment_warning"] = streak >= 3
        pending_reviews = sum(1 for room in rooms if room["status"] not in {"Pago", "Não pago"})
        week["pending_reviews"] = pending_reviews
        week["can_finalize"] = bool(week.get("review_mode") and pending_reviews == 0 and rooms)
        return jsonify({"week": week, "rooms": rooms})
    except Exception as error:
        log_error("Falha ao listar salas de meta", error)
        return error_response(str(error))


@app.get("/api/meta-rooms/<user_id>")
@require_admin
def admin_meta_room_detail(user_id):
    try:
        week_start = str(request.args.get("week_start") or "").strip()
        return jsonify(build_meta_room_payload(user_id, week_start=week_start or None))
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
        if status not in {"Pago", "Não pago", "Pendente"}:
            return error_response("Status deve ser Pago, Não pago ou Pendente.", 400)

        submission = meta_query_one(
            "SELECT id, user_id, week_start, week_end FROM meta_submissions WHERE id = ?",
            (submission_id,),
        )
        if not submission:
            return error_response("Sala semanal não encontrada.", 404)
        if get_meta_week_closure(submission["week_start"]):
            return error_response("Esta semana já foi finalizada e está bloqueada.", 409)
        if meta_submission_uploads_open(submission):
            return error_response(
                f"A conferência será liberada após {submission['week_end']} às 23:59.",
                409,
            )

        # Fotos são comprovantes opcionais. O administrador também pode
        # confirmar um pagamento verificado por outro meio.

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


def meta_week_log_response(log_text, week_start):
    filename = f"kokusai-metas-{str(week_start).replace('/', '-')}.txt"
    response = Response("\ufeff" + str(log_text), content_type="text/plain; charset=utf-8")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post("/api/meta-weeks/finalize")
@require_admin
def finalize_meta_week():
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return error_response("JSON inválido.", 400)
        week_start = str(data.get("week_start") or "").strip()
        start_date = parse_date_br(week_start)
        if not start_date:
            return error_response("Semana inválida.", 400)

        existing_closure = get_meta_week_closure(week_start)
        if existing_closure:
            return meta_week_log_response(existing_closure["log_text"], week_start)

        submissions = meta_query_all(
            """
            SELECT s.id, s.week_start, s.week_end, s.status, s.admin_note, s.submitted_at,
                   s.reviewed_at, s.reviewed_by, u.display_name, u.username,
                   (SELECT COUNT(*) FROM meta_photos p WHERE p.submission_id = s.id) AS photo_count
            FROM meta_submissions s
            JOIN meta_users u ON u.id = s.user_id
            WHERE s.week_start = ? AND u.role = 'member' AND u.active = 1
            ORDER BY u.display_name ASC
            """,
            (week_start,),
        )
        if not submissions:
            return error_response("Nenhuma sala encontrada para essa semana.", 404)

        week_end = str(submissions[0]["week_end"] or "").strip()
        end_date = parse_date_br(week_end)
        if not end_date or end_date >= now_local().date():
            return error_response(f"A semana só pode ser finalizada após {week_end} às 23:59.", 409)

        pending = [row["display_name"] for row in submissions if row["status"] not in {"Pago", "Não pago"}]
        if pending:
            preview = ", ".join(pending[:5])
            suffix = "..." if len(pending) > 5 else ""
            return error_response(
                f"Revise todas as pessoas antes de finalizar. Faltam {len(pending)}: {preview}{suffix}",
                409,
            )

        closed_at = format_timestamp()
        admin = get_current_user()
        paid_count = sum(1 for row in submissions if row["status"] == "Pago")
        unpaid_count = len(submissions) - paid_count
        schedule = meta_week_payload(start_date)
        lines = [
            "KOKUSAI - LOG DE FECHAMENTO DAS METAS",
            "=" * 48,
            f"Período: {week_start} até {week_end}",
            f"Prazo para pagamento: {schedule['prazo_pagamento']}",
            f"Dia de conferência: {schedule['data_conferencia']}",
            f"Finalizado em: {closed_at}",
            f"Finalizado por: {admin['display_name']} (@{admin['username']})",
            "",
            "RESUMO",
            f"Total de membros: {len(submissions)}",
            f"Pagaram: {paid_count}",
            f"Não pagaram: {unpaid_count}",
            "",
            "DETALHAMENTO",
            "-" * 48,
        ]
        for index, row in enumerate(submissions, start=1):
            note = " ".join(str(row.get("admin_note") or "").split()) or "Sem observação"
            lines.extend([
                f"{index:02d}. {row['display_name']} (@{row['username']})",
                f"    Resultado: {str(row['status']).upper()}",
                f"    Fotos enviadas: {int(row['photo_count'] or 0)}",
                f"    Enviado em: {row['submitted_at'] or 'Não enviou comprovante'}",
                f"    Revisado em: {row['reviewed_at'] or 'Não informado'}",
                f"    Revisado por: {row['reviewed_by'] or admin['username']}",
                f"    Observação: {note}",
                "",
            ])
        log_text = "\r\n".join(lines).rstrip() + "\r\n"

        try:
            meta_execute(
                """
                INSERT INTO meta_week_closures (
                    id, week_start, week_end, payment_deadline, review_date, closed_at, closed_by,
                    total_count, paid_count, unpaid_count, log_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(week_start) DO NOTHING
                """,
                (
                    f"META-CLOSE-{uuid.uuid4().hex}", week_start, week_end, schedule["prazo_pagamento"],
                    schedule["data_conferencia"], closed_at, admin["username"], len(submissions),
                    paid_count, unpaid_count, log_text,
                ),
            )
        except Exception:
            raise

        closure = get_meta_week_closure(week_start)
        return meta_week_log_response(closure["log_text"] if closure else log_text, week_start)
    except Exception as error:
        log_error("Falha ao finalizar semana de metas", error)
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
        "meta_database_configured": bool(META_DATABASE_URL) or not IS_RAILWAY,
        "storage_bucket_configured": storage_bucket_configured(),
        "credentials_present": bool(credentials_json),
        "service_account_email": client_email,
    })


@app.get("/api/compras")
@require_staff
def list_compras():
    try:
        worksheet = get_compras_worksheet()
        rows = cached_get_all_values(COMPRAS_WORKSHEET_NAME, worksheet)
        family_worksheet = get_familias_worksheet()
        family_rows = cached_get_all_values(FAMILIAS_WORKSHEET_NAME, family_worksheet)
        families_by_id = {
            str(family.get("id") or "").strip(): family
            for family in (normalize_family(row) for row in family_rows[1:])
            if str(family.get("id") or "").strip()
        }
        compras = []
        for row in latest_data_rows(rows):
            compra = normalize_compra(row)
            family = families_by_id.get(compra.get("familia_id"))
            if family:
                compra["familia_nome"] = family["nome"]
                compra["familia_icone"] = family.get("icone") or ""
                compra["familia_responsavel"] = family.get("responsavel_contato") or ""
                compra["familia_mercado"] = family.get("mercado") or "Aberto"
            compras.append(compra)
        return jsonify(compras)

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
            ["produto", "quem_pediu", "valor_unitario", "quantidade"]
        )

        if not ok:
            return error_response(message, 400)

        try:
            produto = clean_text_field(data, "produto", "Produto")
            quem_pediu = clean_text_field(data, "quem_pediu", "Quem pediu")
            observacao = clean_text_field(data, "observacao", "Observação", max_length=MAX_OBSERVATION_LENGTH, required=False)
            family_id = str(data.get("familia_id") or "").strip()
            if family_id:
                family = get_family_snapshot(family_id, require_open=True)
                quem_vendeu = family["nome"]
            else:
                family = {"id": "", "nome": "", "icone": ""}
                quem_vendeu = clean_text_field(data, "quem_vendeu", "Quem vendeu")
                validate_manual_party_against_families(quem_vendeu)
        except ValueError as validation_error:
            return error_response(str(validation_error), 400)

        quantidade = int(data["quantidade"])
        valor_unitario = float(data["valor_unitario"])
        try:
            money_type, valor_base, surcharge, valor_total, dirty_percentage = calculate_payment_values(
                quantidade * valor_unitario,
                data.get("tipo_dinheiro"),
                data.get("percentual_dinheiro_sujo"),
            )
        except ValueError as validation_error:
            return error_response(str(validation_error), 400)

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
            money_type,
            valor_base,
            surcharge,
            dirty_percentage,
            family["id"],
            family["nome"],
            family["icone"],
        ], value_input_option="RAW")
        invalidate_values_cache(COMPRAS_WORKSHEET_NAME)
        log_info(f"Compra registrada com sucesso. ID={registro_id}")

        return jsonify({
            "ok": True,
            "message": "Compra salva com sucesso.",
            "id": registro_id,
            "valor_total": valor_total,
            "tipo_dinheiro": money_type,
            "valor_base": valor_base,
            "acrescimo_dinheiro_sujo": surcharge,
            "percentual_dinheiro_sujo": dirty_percentage,
            "familia_id": family["id"],
        }), 201

    except Exception as e:
        log_error("Falha em /api/compras [POST]", e)
        return error_response(str(e))


@app.delete("/api/compras/<registro_id>")
@require_admin
def delete_compra(registro_id):
    try:
        with _sheets_lock:
            worksheet = get_compras_worksheet()
            row_index, row = find_row_by_id(worksheet, registro_id)
            if not row_index:
                return error_response("Compra não encontrada.", 404)
            compra = normalize_compra(row)
            worksheet.delete_rows(row_index)
            invalidate_values_cache(COMPRAS_WORKSHEET_NAME)

        user = get_current_user()
        # A linha some da planilha de forma definitiva; este log é o único rastro de quem removeu o quê.
        log_info(
            "Compra removida. "
            f"ID={registro_id} produto={compra.get('produto')} quantidade={compra.get('quantidade')} "
            f"total={compra.get('valor_total')} por={user['display_name'] if user else '?'}"
        )
        return jsonify({
            "ok": True,
            "message": "Compra removida com sucesso.",
            "id": registro_id,
        })
    except Exception as e:
        log_error("Falha em /api/compras/<id> [DELETE]", e)
        return error_response(str(e))


# ---------------------------------------------------------------------------
# Produtos de venda por tempo limitado
# ---------------------------------------------------------------------------
# Cada item aparece como atalho no formulário de Vendas apenas entre "inicio" e "fim"
# (datas inclusivas, no fuso do sistema) e some sozinho depois. Para liberar outro
# produto temporário, basta incluir uma linha aqui.
TEMPORARY_SALE_PRODUCTS = [
    {"nome": "M16", "inicio": "2026-10-07", "fim": "2026-10-13"},  # 7 dias
]

# Produtos de linha: sempre disponíveis em Vendas e em Encomendas. Os temporários
# acima entram como adicionais, sem tirar nenhum destes.
PERMANENT_SALE_PRODUCTS = ["L85", "Seringa", "Circuito Eletrônico"]


def active_temporary_sale_products():
    today = now_local().date()
    active = []
    for product in TEMPORARY_SALE_PRODUCTS:
        start = datetime.strptime(product["inicio"], "%Y-%m-%d").date()
        end = datetime.strptime(product["fim"], "%Y-%m-%d").date()
        if start <= today <= end:
            active.append({
                "nome": product["nome"],
                "ate": end.strftime("%d/%m/%Y"),
                "dias_restantes": (end - today).days + 1,
            })
    return active


@app.get("/api/produtos-venda")
@require_staff
def list_sale_products():
    try:
        response = jsonify({
            "ok": True,
            "fixos": list(PERMANENT_SALE_PRODUCTS),
            "temporarios": active_temporary_sale_products(),
        })
        response.headers["Cache-Control"] = "no-store"
        return response
    except Exception as e:
        log_error("Falha em /api/produtos-venda [GET]", e)
        return error_response(str(e))


@app.get("/api/produtos-temporarios")
@require_staff
def list_temporary_sale_products():
    try:
        response = jsonify({"ok": True, "items": active_temporary_sale_products()})
        response.headers["Cache-Control"] = "no-store"
        return response
    except Exception as e:
        log_error("Falha em /api/produtos-temporarios [GET]", e)
        return error_response(str(e))


@app.get("/api/vendas")
@require_staff
def list_vendas():
    try:
        worksheet = get_vendas_worksheet()
        rows = cached_get_all_values(VENDAS_WORKSHEET_NAME, worksheet)
        family_worksheet = get_familias_worksheet()
        family_rows = cached_get_all_values(FAMILIAS_WORKSHEET_NAME, family_worksheet)
        families_by_id = {
            str(family.get("id") or "").strip(): family
            for family in (normalize_family(row) for row in family_rows[1:])
            if str(family.get("id") or "").strip()
        }
        vendas = []
        for row in latest_data_rows(rows):
            venda = normalize_venda(row)
            family = families_by_id.get(str(venda.get("familia_id") or "").strip())
            if family:
                venda["familia_nome"] = family["nome"]
                venda["familia_icone"] = family.get("icone") or ""
                venda["familia_responsavel"] = family.get("responsavel_contato") or ""
                venda["familia_mercado"] = family.get("mercado") or "Aberto"
            vendas.append(venda)
        return jsonify(vendas)

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
            ["produto", "quem_vende", "valor_unitario", "quantidade"]
        )

        if not ok:
            return error_response(message, 400)

        try:
            produto = clean_text_field(data, "produto", "Produto")
            quem_vende = clean_text_field(data, "quem_vende", "Quem vende")
            observacao = clean_text_field(data, "observacao", "Observação", max_length=MAX_OBSERVATION_LENGTH, required=False)
            family_id = str(data.get("familia_id") or "").strip()
            if family_id:
                family = get_family_snapshot(family_id, require_open=True)
                quem_compra = family["nome"]
            else:
                family = {"id": "", "nome": "", "icone": ""}
                quem_compra = clean_text_field(data, "quem_compra", "Quem compra")
                validate_manual_party_against_families(quem_compra)
        except ValueError as validation_error:
            return error_response(str(validation_error), 400)

        quantidade = int(data["quantidade"])
        valor_unitario = float(data["valor_unitario"])
        try:
            money_type, valor_base, surcharge, valor_total, dirty_percentage = calculate_payment_values(
                quantidade * valor_unitario,
                data.get("tipo_dinheiro"),
                data.get("percentual_dinheiro_sujo"),
            )
        except ValueError as validation_error:
            return error_response(str(validation_error), 400)

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
            family["id"],
            family["nome"],
            family["icone"],
            "",
            money_type,
            valor_base,
            surcharge,
            dirty_percentage,
        ], value_input_option="RAW")
        invalidate_values_cache(VENDAS_WORKSHEET_NAME)
        log_info(f"Venda registrada com sucesso. ID={registro_id}")

        return jsonify({
            "ok": True,
            "message": "Venda salva com sucesso.",
            "id": registro_id,
            "valor_total": valor_total,
            "familia_id": family["id"],
            "tipo_dinheiro": money_type,
            "valor_base": valor_base,
            "acrescimo_dinheiro_sujo": surcharge,
            "percentual_dinheiro_sujo": dirty_percentage,
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


@app.get("/api/relatorios/gangues")
@require_staff
def relatorio_gangues():
    try:
        return jsonify(build_family_sales_report(request.args.get("mes")))
    except ValueError as validation_error:
        return error_response(str(validation_error), 400)
    except Exception as e:
        log_error("Falha em /api/relatorios/gangues", e)
        return error_response(str(e))


@app.get("/api/encomendas")
@require_staff
def list_encomendas():
    try:
        worksheet = get_encomendas_worksheet()
        rows = cached_get_all_values(ENCOMENDAS_WORKSHEET_NAME, worksheet)
        family_worksheet = get_familias_worksheet()
        family_rows = cached_get_all_values(FAMILIAS_WORKSHEET_NAME, family_worksheet)
        families_by_id = {
            str(family.get("id") or "").strip(): family
            for family in (normalize_family(row) for row in family_rows[1:])
            if str(family.get("id") or "").strip()
        }
        orders = []
        for row in latest_data_rows(rows):
            order = normalize_encomenda(row)
            # Entregas antigas que já foram marcadas como concluídas não devem
            # permanecer na aba ativa. As novas são excluídas fisicamente ao
            # virar venda; este filtro também corrige os registros legados.
            if order["entregue"] == "Sim":
                continue
            family = families_by_id.get(str(order.get("familia_id") or "").strip())
            if family:
                order["familia_nome"] = family["nome"]
                order["familia_icone"] = family.get("icone") or ""
                order["familia_responsavel"] = family.get("responsavel_contato") or ""
                order["familia_mercado"] = family.get("mercado") or "Aberto"
            orders.append(order)
        orders.sort(key=encomenda_sort_key)
        return jsonify(orders)

    except Exception as e:
        log_error("Falha em /api/encomendas [GET]", e)
        return error_response(str(e))


@app.post("/api/encomendas")
@require_admin
def create_encomenda():
    try:
        data = request.get_json(silent=True)
        required_fields = ["familia_id", "para_quando", "quem_negociou", "entregue"]

        if not isinstance(data, dict):
            return error_response("JSON inválido.", 400)

        missing = [field for field in required_fields if str(data.get(field, "")).strip() == ""]
        if missing:
            return error_response(f"Campos obrigatórios ausentes: {', '.join(missing)}", 400)

        itens_json = ""
        if isinstance(data.get("itens"), list):
            try:
                items, valor_base = validate_encomenda_items(data["itens"])
            except ValueError as validation_error:
                return error_response(str(validation_error), 400)
            o_que_pediu = " + ".join(f'{item["quantidade"]}x {item["produto"]}' for item in items)
            itens_json = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
        else:
            # Compatibilidade com registros/clientes antigos que enviam um item livre.
            if str(data.get("o_que_pediu", "")).strip() == "" or str(data.get("valor", "")).strip() == "":
                return error_response("Informe os itens e o valor da encomenda.", 400)
            try:
                valor_base = float(data["valor"])
            except (ValueError, TypeError):
                return error_response("O valor da encomenda deve ser numérico.", 400)
            if valor_base < 0:
                return error_response("O valor da encomenda não pode ser negativo.", 400)
            if valor_base > MAX_MONEY_VALUE:
                return error_response("Valor da encomenda muito alto.", 400)
            try:
                o_que_pediu = clean_text_field(data, "o_que_pediu", "O que pediu")
            except ValueError as validation_error:
                return error_response(str(validation_error), 400)

        try:
            money_type, valor_base, surcharge, valor, dirty_percentage = calculate_payment_values(
                valor_base,
                data.get("tipo_dinheiro"),
                data.get("percentual_dinheiro_sujo"),
            )
        except ValueError as validation_error:
            return error_response(str(validation_error), 400)

        entregue = str(data["entregue"]).strip().capitalize()
        if entregue not in ["Sim", "Não", "Nao"]:
            return error_response("O campo 'entregue' deve ser 'Sim' ou 'Não'.", 400)

        if entregue == "Nao":
            entregue = "Não"

        try:
            family = get_family_snapshot(data.get("familia_id"), require_open=True)
            quem_pediu = family["nome"]
            para_quando = clean_text_field(data, "para_quando", "Para quando")
            quem_negociou = clean_text_field(data, "quem_negociou", "Quem negociou")
            observacao = clean_text_field(data, "observacao", "Observação", max_length=MAX_OBSERVATION_LENGTH, required=False)
        except ValueError as validation_error:
            return error_response(str(validation_error), 400)

        agora = format_timestamp()
        deadline = parse_encomenda_deadline(para_quando, agora)
        if not deadline:
            return error_response("Informe uma data e um horário válidos para a entrega.", 400)
        para_quando = deadline.isoformat(timespec="minutes")
        registro_id = generate_record_id("KKSE")
        prioridade = "Sim" if normalize_flag(data.get("prioridade")) else "Não"

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
            "familia_id": family["id"],
            "familia_nome": family["nome"],
            "familia_icone": family["icone"],
            "tipo_dinheiro": money_type,
            "valor_base": valor_base,
            "acrescimo_dinheiro_sujo": surcharge,
            "prioridade": prioridade,
            "percentual_dinheiro_sujo": dirty_percentage,
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
                "tipo_dinheiro": money_type,
                "percentual_dinheiro_sujo": dirty_percentage,
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
            family["id"],
            family["nome"],
            family["icone"],
            money_type,
            valor_base,
            surcharge,
            prioridade,
            dirty_percentage,
        ], value_input_option="RAW")
        invalidate_values_cache(ENCOMENDAS_WORKSHEET_NAME)
        log_info(f"Encomenda registrada com sucesso. ID={registro_id}")

        return jsonify({
            "ok": True,
            "message": "Encomenda salva com sucesso.",
            "id": registro_id,
            "valor": round(valor, 2),
            "tipo_dinheiro": money_type,
            "prioridade": prioridade,
            "percentual_dinheiro_sujo": dirty_percentage,
            "moved_to_vendas": False,
        }), 201

    except Exception as e:
        log_error("Falha em /api/encomendas [POST]", e)
        return error_response(str(e))


@app.put("/api/encomendas/<registro_id>")
@require_admin
def update_encomenda(registro_id):
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return error_response("JSON inválido.", 400)

        required_fields = ["familia_id", "para_quando", "quem_negociou", "entregue"]
        missing = [field for field in required_fields if str(data.get(field, "")).strip() == ""]
        if missing:
            return error_response(f"Campos obrigatórios ausentes: {', '.join(missing)}", 400)

        try:
            items, valor_base = validate_encomenda_items(data.get("itens"))
            family = get_family_snapshot(data.get("familia_id"), require_open=True)
            quem_pediu = family["nome"]
            para_quando = clean_text_field(data, "para_quando", "Para quando")
            quem_negociou = clean_text_field(data, "quem_negociou", "Quem negociou")
            observacao = clean_text_field(
                data, "observacao", "Observação", max_length=MAX_OBSERVATION_LENGTH, required=False,
            )
        except ValueError as validation_error:
            return error_response(str(validation_error), 400)

        deadline = parse_encomenda_deadline(para_quando)
        if not deadline:
            return error_response("Informe uma data e um horário válidos para a entrega.", 400)
        para_quando = deadline.isoformat(timespec="minutes")

        try:
            money_type, valor_base, surcharge, valor, dirty_percentage = calculate_payment_values(
                valor_base,
                data.get("tipo_dinheiro"),
                data.get("percentual_dinheiro_sujo"),
            )
        except ValueError as validation_error:
            return error_response(str(validation_error), 400)

        entregue = validate_yes_no(data.get("entregue"))
        if not entregue:
            return error_response("O campo 'entregue' deve ser 'Sim' ou 'Não'.", 400)

        o_que_pediu = " + ".join(f'{item["quantidade"]}x {item["produto"]}' for item in items)
        itens_json = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
        prioridade = "Sim" if normalize_flag(data.get("prioridade")) else "Não"

        with _sheets_lock:
            worksheet = get_encomendas_worksheet()
            row_index, row = find_row_by_id(worksheet, registro_id)
            if not row_index:
                return error_response("Encomenda não encontrada.", 404)

            while len(row) < len(ENCOMENDAS_HEADERS):
                row.append("")

            original_date = str(row[1] or "").strip() or format_timestamp()
            encomenda_item = {
                "id": registro_id,
                "data": original_date,
                "quem_pediu": quem_pediu,
                "o_que_pediu": o_que_pediu,
                "valor": round(valor, 2),
                "para_quando": para_quando,
                "quem_negociou": quem_negociou,
                "entregue": entregue,
                "observacao": observacao,
                "entregue_em": "",
                "itens_json": itens_json,
                "familia_id": family["id"],
                "familia_nome": family["nome"],
                "familia_icone": family["icone"],
                "tipo_dinheiro": money_type,
                "valor_base": valor_base,
                "acrescimo_dinheiro_sujo": surcharge,
                "prioridade": prioridade,
                "percentual_dinheiro_sujo": dirty_percentage,
            }

            if entregue == "Sim":
                entregue_em = format_timestamp()
                encomenda_item["entregue_em"] = entregue_em
                venda_ids = move_encomenda_to_vendas(worksheet, row_index, encomenda_item, entregue_em)
                return jsonify({
                    "ok": True,
                    "message": "Encomenda atualizada, entregue e movida para Vendas.",
                    "id": registro_id,
                    "moved_to_vendas": True,
                    "venda_ids": venda_ids,
                })

            worksheet.update(
                f"A{row_index}:S{row_index}",
                [[
                    registro_id,
                    original_date,
                    quem_pediu,
                    o_que_pediu,
                    round(valor, 2),
                    para_quando,
                    quem_negociou,
                    "Não",
                    observacao,
                    "",
                    itens_json,
                    family["id"],
                    family["nome"],
                    family["icone"],
                    money_type,
                    valor_base,
                    surcharge,
                    prioridade,
                    dirty_percentage,
                ]],
                value_input_option="RAW",
            )
            invalidate_values_cache(ENCOMENDAS_WORKSHEET_NAME)

        return jsonify({
            "ok": True,
            "message": "Encomenda atualizada com sucesso.",
            "id": registro_id,
            "valor": round(valor, 2),
            "tipo_dinheiro": money_type,
            "prioridade": prioridade,
            "percentual_dinheiro_sujo": dirty_percentage,
            "moved_to_vendas": False,
        })
    except Exception as e:
        log_error("Falha em /api/encomendas/<id> [PUT]", e)
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

            family_id = str(encomenda_item.get("familia_id") or "").strip()
            if not family_id:
                return error_response(
                    "Antes de confirmar a entrega, clique em Editar e selecione a família/gangue responsável.",
                    409,
                )
            try:
                family = get_family_snapshot(family_id)
            except ValueError as validation_error:
                return error_response(str(validation_error), 409)
            encomenda_item["quem_pediu"] = family["nome"]
            encomenda_item["familia_nome"] = family["nome"]
            encomenda_item["familia_icone"] = family["icone"]

            venda_ids = move_encomenda_to_vendas(worksheet, row_index, encomenda_item, entregue_em)
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
        family_worksheet = get_familias_worksheet()
        family_rows = cached_get_all_values(FAMILIAS_WORKSHEET_NAME, family_worksheet)
        families_by_name = {
            normalized_lookup_key(family.get("nome")): family
            for family in (normalize_family(row) for row in family_rows[1:])
            if normalized_lookup_key(family.get("nome"))
        }
        for reuniao in reunioes:
            family = families_by_name.get(normalized_lookup_key(reuniao.get("gangue")))
            if family:
                reuniao["responsavel_contato"] = family.get("responsavel_contato") or ""
                reuniao["mercado"] = family.get("mercado") or "Aberto"
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


@app.get("/familias/<registro_id>/flyer/<int:slot>")
@require_staff
def family_flyer_file(registro_id, slot):
    try:
        if slot not in {1, 2}:
            return error_response("Flyer inválido.", 404)
        worksheet = get_familias_worksheet()
        row_index, row = find_row_by_id(worksheet, registro_id)
        if not row_index:
            return error_response("Família/gangue não encontrada.", 404)
        field_index = FAMILIAS_HEADERS.index("flyer_url" if slot == 1 else "flyer_url_2")
        object_key = bucket_key_from_reference(sheet_cell(row, field_index))
        if not object_key:
            object_key = bucket_key_from_legacy_flyer_url(sheet_cell(row, field_index))
        if not object_key or not object_key.startswith("flyers/"):
            return error_response("Flyer não encontrado.", 404)

        client = get_storage_client()
        if client:
            bucket_object = client.get_object(Bucket=META_BUCKET_NAME, Key=object_key)
            body = bucket_object.get("Body")
            image_bytes = body.read() if body else b""
            if body and hasattr(body, "close"):
                body.close()
            if not image_bytes:
                return error_response("Arquivo do flyer não encontrado.", 404)
            response = send_file(
                BytesIO(image_bytes),
                mimetype=bucket_object.get("ContentType") or "image/webp",
                max_age=0,
            )
            response.headers["Cache-Control"] = "private, no-store, max-age=0"
            return response

        if IS_RAILWAY:
            return error_response("Bucket de imagens não configurado no Railway.", 503)
        local_path = family_flyer_storage_path(object_key)
        if not os.path.isfile(local_path):
            return error_response("Arquivo do flyer não encontrado.", 404)
        response = send_file(local_path, mimetype="image/webp", max_age=0)
        response.headers["Cache-Control"] = "private, no-store, max-age=0"
        return response
    except Exception as error:
        log_error("Falha ao servir flyer da família", error)
        return error_response(str(error))


@app.get("/api/familias")
@require_staff
def list_familias():
    try:
        worksheet = get_familias_worksheet()
        rows = cached_get_all_values(FAMILIAS_WORKSHEET_NAME, worksheet)
        familias = [normalize_family(row) for row in rows[1:] if str(sheet_cell(row, 2)).strip()]
        familias.sort(key=lambda item: normalized_lookup_key(item.get("nome")))
        response = jsonify(familias)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response
    except Exception as e:
        log_error("Falha em /api/familias [GET]", e)
        return error_response(str(e))


@app.post("/api/familias/<registro_id>/flyers")
@require_admin
def upload_familia_flyer(registro_id):
    new_reference = ""
    try:
        try:
            slot = int(request.form.get("slot") or 0)
        except (TypeError, ValueError):
            slot = 0
        if slot not in {1, 2}:
            return error_response("Escolha o espaço 1 ou 2 para o flyer.", 400)

        upload = request.files.get("flyer")
        new_reference = store_family_flyer(upload, registro_id, slot)
        old_reference = ""

        try:
            with _sheets_lock:
                worksheet = get_familias_worksheet()
                row_index, row = find_row_by_id(worksheet, registro_id)
                if not row_index:
                    delete_family_flyer_reference(new_reference)
                    return error_response("Família/gangue não encontrada.", 404)

                padded = list(row[:len(FAMILIAS_HEADERS)]) + [""] * max(0, len(FAMILIAS_HEADERS) - len(row))
                field_name = "flyer_url" if slot == 1 else "flyer_url_2"
                field_index = FAMILIAS_HEADERS.index(field_name)
                old_reference = str(padded[field_index] or "").strip()
                padded[field_index] = new_reference
                padded[FAMILIAS_HEADERS.index("flyer_oculto")] = "Não"
                padded[FAMILIAS_HEADERS.index("atualizado_em")] = format_timestamp()
                worksheet.update(
                    f"A{row_index}:O{row_index}",
                    [padded[:len(FAMILIAS_HEADERS)]],
                    value_input_option="RAW",
                )
                invalidate_values_cache(FAMILIAS_WORKSHEET_NAME)
        except Exception:
            delete_family_flyer_reference(new_reference)
            raise

        if old_reference and old_reference != new_reference:
            try:
                delete_family_flyer_reference(old_reference)
            except Exception as cleanup_error:
                log_error("Flyer antigo não pôde ser removido do Bucket", cleanup_error)

        response = jsonify({
            "ok": True,
            "message": f"Flyer {slot} armazenado permanentemente.",
            "slot": slot,
            "flyer_url": family_flyer_access_url(new_reference, registro_id, slot),
            "flyer_url_stored": new_reference,
        })
        response.headers["Cache-Control"] = "no-store"
        return response, 201
    except ValueError as error:
        return error_response(str(error), 400)
    except Exception as error:
        log_error("Falha ao armazenar flyer da família", error)
        return error_response(str(error))


def validate_family_payload(data):
    if not isinstance(data, dict):
        raise ValueError("JSON inválido.")

    name = canonical_family_name(clean_text_field(data, "nome", "Nome da família/gangue"))
    if not normalized_lookup_key(name):
        raise ValueError("Nome da família/gangue é obrigatório.")

    market = normalize_market_status(data.get("mercado"))
    restricted_market = RESTRICTED_FAMILY_MARKETS.get(normalized_lookup_key(name))
    if restricted_market:
        market = restricted_market
    icon = clean_text_field(data, "icone", "Ícone", max_length=12, required=False)
    sale_price = clean_text_field(
        data, "preco_venda_para_familia", "Preço de venda para a família",
        max_length=MAX_OBSERVATION_LENGTH, required=False,
    )
    purchase_price = clean_text_field(
        data, "preco_compra_da_familia", "Preço de compra da família",
        max_length=MAX_OBSERVATION_LENGTH, required=False,
    )
    flyer_url = clean_optional_image_reference(data.get("flyer_url"), "Flyer 1")
    flyer_url_2 = clean_optional_image_reference(data.get("flyer_url_2"), "Flyer 2")
    contact = clean_text_field(
        data, "contato", "Contato 1", max_length=200, required=False,
    )
    contact_2 = clean_text_field(
        data, "contato_2", "Contato 2", max_length=200, required=False,
    )
    responsible = canonical_staff_name(clean_text_field(
        data, "responsavel_contato", "Responsável pelo contato", max_length=120, required=False,
    ))
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
        "flyer_url_2": flyer_url_2,
        "contato": contact,
        "contato_2": contact_2,
        "responsavel_contato": responsible,
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
    replaced_flyers = []
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
            for field_name in ("flyer_url", "flyer_url_2"):
                field_index = FAMILIAS_HEADERS.index(field_name)
                old_reference = str(padded[field_index] or "").strip()
                new_reference = str(updated[field_index] or "").strip()
                if old_reference != new_reference:
                    replaced_flyers.append(old_reference)
            worksheet.update(f"A{row_index}:O{row_index}", [updated], value_input_option="RAW")
            invalidate_values_cache(FAMILIAS_WORKSHEET_NAME)

        for reference in replaced_flyers:
            try:
                delete_family_flyer_reference(reference)
            except Exception as cleanup_error:
                log_error("Flyer substituído não pôde ser removido do Bucket", cleanup_error)
        return jsonify({
            "ok": True,
            "message": "Informações da família/gangue salvas com sucesso.",
            "id": registro_id,
        })
    except Exception as e:
        log_error("Falha em /api/familias/<id> [PUT]", e)
        return error_response(str(e))


@app.delete("/api/familias/<registro_id>")
@require_admin
def delete_familia(registro_id):
    flyer_references = []
    try:
        with _sheets_lock:
            worksheet = get_familias_worksheet()
            row_index, row = find_row_by_id(worksheet, registro_id)
            if not row_index:
                return error_response("Família/gangue não encontrada.", 404)
            name = canonical_family_name(sheet_cell(row, 2))
            flyer_references = [
                sheet_cell(row, FAMILIAS_HEADERS.index("flyer_url")),
                sheet_cell(row, FAMILIAS_HEADERS.index("flyer_url_2")),
            ]

            worksheet.delete_rows(row_index)
            invalidate_values_cache(FAMILIAS_WORKSHEET_NAME)
        for reference in flyer_references:
            try:
                delete_family_flyer_reference(reference)
            except Exception as cleanup_error:
                log_error("Flyer da família removida não pôde ser apagado do Bucket", cleanup_error)
        return jsonify({
            "ok": True,
            "message": f"{name} foi excluída do cadastro. As transações e encomendas anteriores foram preservadas.",
        })
    except Exception as e:
        log_error("Falha em /api/familias/<id> [DELETE]", e)
        return error_response(str(e))


@app.get("/api/resumo-metas")
@require_staff
def resumo_metas():
    try:
        week = get_admin_meta_week()
        rows = meta_query_all(
            """
            SELECT s.status
            FROM meta_submissions s
            JOIN meta_users u ON u.id = s.user_id
            WHERE s.week_start = ? AND u.role = 'member' AND u.active = 1
            """,
            (week["semana_inicio"],),
        )
        total = len(rows)
        pagos = sum(1 for row in rows if row["status"] == "Pago")
        enviados = sum(1 for row in rows if row["status"] == "Enviado")
        nao_pagos = sum(1 for row in rows if row["status"] in {"Não pago", "Recusado"})
        a_revisar = sum(1 for row in rows if row["status"] not in {"Pago", "Não pago", "Recusado"})

        return jsonify({
            "total": total,
            "pagos": pagos,
            "pendentes": a_revisar,
            "enviados": enviados,
            "nao_pagos": nao_pagos,
            "recusados": nao_pagos,
            "confirmados": pagos,
            "faltam_confirmar": a_revisar,
            "semana_inicio": week["semana_inicio"],
            "semana_fim": week["semana_fim"],
            "semana_label": week["semana_label"],
        })

    except Exception as e:
        log_error("Falha em /api/resumo-metas", e)
        return error_response(str(e))


# ---------------------------------------------------------------------------
# Registro do Baú: fotos arquivadas (arquivo no Bucket + índice no banco)
# ---------------------------------------------------------------------------
BAU_MAX_CAPTION_LENGTH = 200
BAU_MAX_PERSON_LENGTH = 40
BAU_PAGE_SIZE_DEFAULT = 24
BAU_PAGE_SIZE_MAX = 60
BAU_MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def clean_plain_text(value, label, max_length, required=False):
    """Texto de linha única para o banco (sem a proteção de fórmulas do Google Sheets)."""
    text = "".join(ch for ch in str(value or "").replace("\x00", "") if ord(ch) >= 32 or ch in "\n\t")
    text = re.sub(r"\s+", " ", text).strip()
    if required and not text:
        raise ValueError(f"{label} é obrigatório.")
    if len(text) > max_length:
        raise ValueError(f"{label} deve ter no máximo {max_length} caracteres.")
    return text


def store_bau_photo(upload, month):
    image_bytes = prepare_image_upload(upload, "foto")
    object_key = f"bau/{month}/{uuid.uuid4().hex}.webp"
    client = get_storage_client()
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
        "original_name": os.path.basename(upload.filename or "")[:180] or "imagem",
        "content_type": "image/webp",
        "size_bytes": len(image_bytes),
    }


def serialize_bau(row):
    return {
        "id": row["id"],
        "legenda": row["legenda"] or "",
        "registrado_por": row["registrado_por"] or "",
        "responsavel": row.get("responsavel") or "",
        "arquivado": bool(row.get("arquivado")),
        "arquivado_em": row.get("arquivado_em") or "",
        "arquivado_por": row.get("arquivado_por") or "",
        "created_at": row["created_at"],
        "mes": row["mes"],
        "original_name": row["original_name"],
        "size_bytes": int(row["size_bytes"] or 0),
        # URL estável dentro do próprio sistema: a sessão é checada a cada acesso.
        "url": url_for("bau_photo_file", photo_id=row["id"]),
    }


@app.get("/api/bau")
@require_staff
def list_bau():
    try:
        month = str(request.args.get("mes") or "").strip()
        if month and not BAU_MONTH_PATTERN.match(month):
            return error_response("Mês inválido.", 400)
        try:
            offset = max(0, int(request.args.get("offset", 0)))
            limit = min(max(1, int(request.args.get("limit", BAU_PAGE_SIZE_DEFAULT))), BAU_PAGE_SIZE_MAX)
        except (TypeError, ValueError):
            return error_response("Paginação inválida.", 400)
        archived = 1 if str(request.args.get("arquivadas") or "") == "1" else 0

        columns = (
            "id, original_name, content_type, size_bytes, legenda, registrado_por, responsavel, "
            "arquivado, arquivado_em, arquivado_por, mes, created_at"
        )
        where, params = "arquivado = ?", [archived]
        if month:
            where += " AND mes = ?"
            params.append(month)
        total_row = meta_query_one(f"SELECT COUNT(*) AS total FROM bau_registros WHERE {where}", tuple(params))
        rows = meta_query_all(
            f"SELECT {columns} FROM bau_registros WHERE {where} ORDER BY created_ts DESC, id DESC LIMIT ? OFFSET ?",
            tuple(params + [limit, offset]),
        )
        months = meta_query_all(
            "SELECT mes, COUNT(*) AS total FROM bau_registros WHERE arquivado = ? GROUP BY mes ORDER BY mes DESC",
            (archived,),
        )
        archived_row = meta_query_one("SELECT COUNT(*) AS total FROM bau_registros WHERE arquivado = 1")
        total = int((total_row or {}).get("total") or 0)

        response = jsonify({
            "ok": True,
            "items": [serialize_bau(row) for row in rows],
            "total": total,
            "offset": offset,
            "has_more": offset + len(rows) < total,
            "months": [{"mes": row["mes"], "total": int(row["total"] or 0)} for row in months],
            "arquivadas": bool(archived),
            "total_arquivadas": int((archived_row or {}).get("total") or 0),
        })
        response.headers["Cache-Control"] = "no-store"
        return response
    except Exception as error:
        log_error("Falha em /api/bau [GET]", error)
        return error_response(str(error))


@app.post("/api/bau/photos")
@require_admin
def upload_bau_photo():
    try:
        legenda = clean_plain_text(request.form.get("legenda"), "Legenda", BAU_MAX_CAPTION_LENGTH)
        # A conta kokusai é compartilhada: o nome de quem está registrando vai junto da foto.
        responsavel = clean_plain_text(request.form.get("responsavel"), "Quem registrou", BAU_MAX_PERSON_LENGTH, required=True)
        now = now_local()
        stored = store_bau_photo(request.files.get("photo"), now.strftime("%Y-%m"))
        user = get_current_user()
        record_id = f"BAU-{uuid.uuid4().hex}"
        try:
            meta_execute(
                """
                INSERT INTO bau_registros
                    (id, object_key, original_name, content_type, size_bytes, legenda, registrado_por, responsavel,
                     mes, created_at, created_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id, stored["object_key"], stored["original_name"], stored["content_type"],
                    stored["size_bytes"], legenda, user["display_name"], responsavel, now.strftime("%Y-%m"),
                    format_timestamp(now), now.strftime("%Y-%m-%dT%H:%M:%S.%f"),
                ),
            )
        except Exception:
            delete_meta_photo_object(stored["object_key"])
            raise
        log_info(f"Foto do baú registrada. ID={record_id} quem={responsavel} conta={user['username']} em={format_timestamp(now)}")
        return jsonify({"ok": True, "message": "Foto registrada com sucesso.", "id": record_id}), 201
    except ValueError as error:
        return error_response(str(error), 400)
    except Exception as error:
        log_error("Falha em /api/bau/photos [POST]", error)
        return error_response(str(error))


@app.put("/api/bau/photos/<photo_id>")
@require_admin
def update_bau_photo(photo_id):
    try:
        data = request.get_json(silent=True) or {}
        legenda = clean_plain_text(data.get("legenda"), "Legenda", BAU_MAX_CAPTION_LENGTH)
        row = meta_query_one("SELECT id, arquivado FROM bau_registros WHERE id = ?", (photo_id,))
        if not row:
            return error_response("Registro não encontrado.", 404)
        if row["arquivado"]:
            return error_response("Restaure a foto antes de editar a legenda.", 409)
        meta_execute("UPDATE bau_registros SET legenda = ? WHERE id = ?", (legenda, photo_id))
        return jsonify({"ok": True, "message": "Legenda atualizada.", "legenda": legenda})
    except ValueError as error:
        return error_response(str(error), 400)
    except Exception as error:
        log_error("Falha em /api/bau/photos [PUT]", error)
        return error_response(str(error))


@app.delete("/api/bau/photos/<photo_id>")
@require_admin
def archive_bau_photo(photo_id):
    """Arquiva (não apaga). A foto continua no Bucket e no banco e pode ser restaurada."""
    try:
        data = request.get_json(silent=True) or {}
        responsavel = clean_plain_text(data.get("responsavel"), "Quem está arquivando", BAU_MAX_PERSON_LENGTH, required=True)
        row = meta_query_one("SELECT id, arquivado FROM bau_registros WHERE id = ?", (photo_id,))
        if not row:
            return error_response("Registro não encontrado.", 404)
        if row["arquivado"]:
            return error_response("Esta foto já está arquivada.", 409)
        quando = format_timestamp()
        meta_execute(
            "UPDATE bau_registros SET arquivado = 1, arquivado_em = ?, arquivado_por = ? WHERE id = ?",
            (quando, responsavel, photo_id),
        )
        log_info(f"Foto do baú arquivada. ID={photo_id} quem={responsavel} conta={get_current_user()['username']} em={quando}")
        return jsonify({"ok": True, "message": "Foto arquivada. Ela continua guardada em Arquivadas."})
    except ValueError as error:
        return error_response(str(error), 400)
    except Exception as error:
        log_error("Falha em /api/bau/photos [DELETE]", error)
        return error_response(str(error))


@app.post("/api/bau/photos/<photo_id>/restaurar")
@require_admin
def restore_bau_photo(photo_id):
    try:
        row = meta_query_one("SELECT id, arquivado FROM bau_registros WHERE id = ?", (photo_id,))
        if not row:
            return error_response("Registro não encontrado.", 404)
        if not row["arquivado"]:
            return error_response("Esta foto não está arquivada.", 409)
        meta_execute(
            "UPDATE bau_registros SET arquivado = 0, arquivado_em = '', arquivado_por = '' WHERE id = ?",
            (photo_id,),
        )
        log_info(f"Foto do baú restaurada. ID={photo_id} conta={get_current_user()['username']} em={format_timestamp()}")
        return jsonify({"ok": True, "message": "Foto restaurada para o registro."})
    except Exception as error:
        log_error("Falha em /api/bau/photos/restaurar [POST]", error)
        return error_response(str(error))


@app.get("/bau/foto/<photo_id>")
@require_staff
def bau_photo_file(photo_id):
    try:
        row = meta_query_one("SELECT id, object_key, content_type FROM bau_registros WHERE id = ?", (photo_id,))
        if not row:
            return error_response("Foto não encontrada.", 404)
        if storage_bucket_configured():
            response = redirect(meta_photo_access_url({"object_key": row["object_key"], "id": row["id"]}))
            response.headers["Cache-Control"] = "private, max-age=120"
            return response

        local_root = os.path.abspath(META_LOCAL_UPLOAD_DIR)
        local_path = os.path.abspath(os.path.join(META_LOCAL_UPLOAD_DIR, *row["object_key"].split("/")))
        if not local_path.startswith(local_root + os.sep) or not os.path.isfile(local_path):
            return error_response("Arquivo da foto não encontrado.", 404)
        response = send_file(local_path, mimetype=row.get("content_type") or "image/webp")
        response.headers["Cache-Control"] = "private, max-age=120"
        return response
    except Exception as error:
        log_error("Falha ao servir foto do baú", error)
        return error_response(str(error))


# ---------------------------------------------------------------------------
# Perfil do usuário (foto, apelido, senha)
# ---------------------------------------------------------------------------
def json_no_store(payload, status=200):
    response = jsonify(payload)
    response.headers["Cache-Control"] = "no-store"
    return response, status


def require_personal_account(view):
    """Ações de perfil: só contas pessoais (a conta Kokusai é compartilhada) e sempre com CSRF."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if not user:
            return error_response("Login necessário para acessar o sistema.", 401)
        if user["role"] != "member" or not user.get("user_id"):
            return error_response("A conta Kokusai é compartilhada e não pode ser alterada pelo perfil.", 403)
        csrf_error = csrf_error_if_invalid()
        if csrf_error:
            return csrf_error
        return view(*args, **kwargs)

    return wrapped


def ensure_profile_row(user_id):
    meta_execute(
        "INSERT INTO user_profiles (user_id, updated_at) VALUES (?, ?) ON CONFLICT(user_id) DO NOTHING",
        (user_id, format_timestamp()),
    )


def get_member_profile(user_id):
    row = meta_query_one(
        "SELECT user_id, apelido, avatar_b64, thumb_b64, avatar_version, session_version FROM user_profiles WHERE user_id = ?",
        (user_id,),
    )
    return row or {"user_id": user_id, "apelido": "", "avatar_b64": "", "thumb_b64": "", "avatar_version": 0, "session_version": 0}


def profile_payload(user):
    shared = user["role"] != "member" or not user.get("user_id")
    profile = {} if shared else get_member_profile(user["user_id"])
    return {
        "username": user["username"],
        "display_name": user["display_name"],
        "apelido": "" if shared else (profile.get("apelido") or ""),
        "role": user["role"],
        "role_label": "Administração (conta compartilhada)" if shared else "Membro",
        "shared": shared,
        "can_edit": not shared,
        "avatar": "" if shared else webp_data_uri(profile.get("avatar_b64")),
        "thumb": "" if shared else webp_data_uri(profile.get("thumb_b64")),
        "limits": {
            "apelido_max": APELIDO_MAX_LENGTH,
            "senha_min": PASSWORD_MIN_LENGTH,
            "senha_max": PASSWORD_MAX_LENGTH,
            "foto_max_mb": round(META_MAX_FILE_BYTES / (1024 * 1024)),
        },
    }


def prepare_avatar_upload(upload):
    """Valida a imagem e devolve (foto 256px, miniatura 96px), ambas WEBP quadradas."""
    if not upload or not upload.filename:
        raise ValueError("Selecione uma foto para enviar.")
    raw = upload.stream.read(META_MAX_FILE_BYTES + 1)
    if len(raw) > META_MAX_FILE_BYTES:
        raise ValueError("A foto ultrapassa o limite de 10 MB.")
    if not raw:
        raise ValueError("A foto enviada está vazia.")

    from PIL import Image, ImageOps

    try:
        image = Image.open(BytesIO(raw))
        if str(image.format or "").upper() not in META_ALLOWED_IMAGE_FORMATS:
            raise ValueError("Envie somente imagens JPG, JPEG, PNG ou WEBP.")
        image.load()
        image = ImageOps.exif_transpose(image)
        if image.mode != "RGB":
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, (16, 17, 21))
            background.paste(rgba, mask=rgba.getchannel("A"))
            image = background
        outputs = []
        for size in (AVATAR_SIZE, AVATAR_THUMB_SIZE):
            square = ImageOps.fit(image, (size, size), method=Image.Resampling.LANCZOS)
            buffer = BytesIO()
            square.save(buffer, format="WEBP", quality=AVATAR_WEBP_QUALITY, method=6)
            outputs.append(buffer.getvalue())
        return outputs[0], outputs[1]
    except ValueError:
        raise
    except Exception as error:
        raise ValueError("Não foi possível ler essa foto. Tente enviar outro arquivo.") from error


def bump_member_session_version(user_id, new_password_hash=None):
    """Invalida as sessões abertas do membro em todos os aparelhos. Devolve a nova versão."""
    ensure_meta_database_ready()
    now_text = format_timestamp()
    connection = meta_db_connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            meta_sql("INSERT INTO user_profiles (user_id, updated_at) VALUES (?, ?) ON CONFLICT(user_id) DO NOTHING"),
            (user_id, now_text),
        )
        if new_password_hash:
            cursor.execute(meta_sql("UPDATE meta_users SET password_hash = ? WHERE id = ?"), (new_password_hash, user_id))
            cursor.execute(
                meta_sql(
                    "UPDATE user_profiles SET session_version = session_version + 1, "
                    "password_changed_at = ?, updated_at = ? WHERE user_id = ?"
                ),
                (now_text, now_text, user_id),
            )
        else:
            cursor.execute(
                meta_sql("UPDATE user_profiles SET session_version = session_version + 1, updated_at = ? WHERE user_id = ?"),
                (now_text, user_id),
            )
        cursor.execute(meta_sql("SELECT session_version FROM user_profiles WHERE user_id = ?"), (user_id,))
        version = int(cursor.fetchone()[0])
        connection.commit()
        return version
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@app.get("/perfil")
@require_login
def profile_page():
    return render_template("perfil.html")


def member_avatar_url(user_id, version, has_photo, thumb=True):
    """Endereço da foto de perfil do membro (vazio se ele não tem foto).

    A versão entra na URL: quando a foto muda, o endereço muda e o navegador busca de novo;
    enquanto não muda, a imagem fica em cache e não pesa nas listas do painel.
    """
    if not has_photo:
        return ""
    params = {"user_id": user_id, "v": int(version or 0)}
    if thumb:
        params["t"] = 1
    return url_for("member_avatar", **params)


@app.get("/avatar/<user_id>")
@require_login
def member_avatar(user_id):
    user = get_current_user()
    # Membros veem só a própria foto; a equipe (admin e leitura) vê a de todos.
    if user["role"] == "member" and user.get("user_id") != user_id:
        return error_response("Sem acesso a esta foto.", 403)
    row = meta_query_one(
        "SELECT thumb_b64, avatar_b64, avatar_version FROM user_profiles WHERE user_id = ?",
        (user_id,),
    )
    field = "thumb_b64" if request.args.get("t") == "1" else "avatar_b64"
    data = (row or {}).get(field) or ""
    if not data:
        return error_response("Foto não encontrada.", 404)
    response = Response(base64.b64decode(data), mimetype="image/webp")
    current = str(int((row or {}).get("avatar_version") or 0))
    if request.args.get("v") == current:
        response.headers["Cache-Control"] = "private, max-age=31536000, immutable"
    else:
        response.headers["Cache-Control"] = "private, no-cache"
    response.headers["ETag"] = f'"{user_id}-{current}-{field[0]}"'
    return response


@app.get("/api/pessoas")
@require_staff
def list_people():
    """Membros ativos com foto, para o painel mostrar o rosto ao lado do nome."""
    try:
        rows = meta_query_all(
            """
            SELECT u.id, u.username, u.display_name, COALESCE(p.apelido, '') AS apelido,
                   COALESCE(p.avatar_version, 0) AS avatar_version,
                   CASE WHEN COALESCE(p.thumb_b64, '') <> '' THEN 1 ELSE 0 END AS has_photo
            FROM meta_users u
            LEFT JOIN user_profiles p ON p.user_id = u.id
            WHERE u.role = 'member' AND u.active = 1
            ORDER BY u.display_name ASC
            """
        )
        return json_no_store({
            "ok": True,
            "pessoas": [{
                "id": row["id"],
                "username": row["username"],
                "display_name": row["display_name"],
                "apelido": row["apelido"],
                "avatar": member_avatar_url(row["id"], row["avatar_version"], row["has_photo"]),
            } for row in rows],
        })
    except Exception as error:
        log_error("Falha em /api/pessoas", error)
        return error_response(str(error))


@app.get("/api/perfil")
@require_login
def get_profile():
    try:
        return json_no_store({"ok": True, "perfil": profile_payload(get_current_user())})
    except Exception as error:
        log_error("Falha em /api/perfil [GET]", error)
        return error_response(str(error))


@app.put("/api/perfil")
@require_personal_account
def update_profile():
    try:
        data = request.get_json(silent=True) or {}
        apelido = clean_plain_text(data.get("apelido"), "Apelido", APELIDO_MAX_LENGTH)
        user = get_current_user()
        ensure_profile_row(user["user_id"])
        meta_execute(
            "UPDATE user_profiles SET apelido = ?, updated_at = ? WHERE user_id = ?",
            (apelido, format_timestamp(), user["user_id"]),
        )
        invalidate_current_user()
        return json_no_store({
            "ok": True,
            "message": "Apelido salvo." if apelido else "Apelido removido.",
            "perfil": profile_payload(get_current_user()),
        })
    except ValueError as error:
        return error_response(str(error), 400)
    except Exception as error:
        log_error("Falha em /api/perfil [PUT]", error)
        return error_response(str(error))


@app.post("/api/perfil/foto")
@require_personal_account
def upload_profile_photo():
    try:
        avatar, thumb = prepare_avatar_upload(request.files.get("photo"))
        user = get_current_user()
        ensure_profile_row(user["user_id"])
        meta_execute(
            "UPDATE user_profiles SET avatar_b64 = ?, thumb_b64 = ?, avatar_version = avatar_version + 1, updated_at = ? WHERE user_id = ?",
            (
                base64.b64encode(avatar).decode("ascii"),
                base64.b64encode(thumb).decode("ascii"),
                format_timestamp(),
                user["user_id"],
            ),
        )
        return json_no_store({"ok": True, "message": "Foto atualizada.", "perfil": profile_payload(user)}, 201)
    except ValueError as error:
        return error_response(str(error), 400)
    except Exception as error:
        log_error("Falha em /api/perfil/foto [POST]", error)
        return error_response(str(error))


@app.delete("/api/perfil/foto")
@require_personal_account
def delete_profile_photo():
    try:
        user = get_current_user()
        ensure_profile_row(user["user_id"])
        meta_execute(
            "UPDATE user_profiles SET avatar_b64 = '', thumb_b64 = '', avatar_version = avatar_version + 1, updated_at = ? WHERE user_id = ?",
            (format_timestamp(), user["user_id"]),
        )
        return json_no_store({"ok": True, "message": "Foto removida.", "perfil": profile_payload(user)})
    except Exception as error:
        log_error("Falha em /api/perfil/foto [DELETE]", error)
        return error_response(str(error))


@app.post("/api/perfil/senha")
@require_personal_account
def change_profile_password():
    try:
        data = request.get_json(silent=True) or {}
        atual = str(data.get("atual") or "")
        nova = str(data.get("nova") or "")
        confirmar = str(data.get("confirmar") or "")
        user = get_current_user()

        limit_key = login_user_key("senha:" + user["username"])
        if is_login_limited(limit_key):
            return error_response("Muitas tentativas. Aguarde alguns minutos e tente novamente.", 429)

        record = get_meta_member_by_username(user["username"])
        if not record or not verify_password(atual, record["password_hash"]):
            record_failed_login(limit_key)
            return error_response("A senha atual está incorreta.", 400)

        if len(nova) < PASSWORD_MIN_LENGTH:
            return error_response(f"A nova senha deve ter pelo menos {PASSWORD_MIN_LENGTH} caracteres.", 400)
        if len(nova) > PASSWORD_MAX_LENGTH:
            return error_response(f"A nova senha deve ter no máximo {PASSWORD_MAX_LENGTH} caracteres.", 400)
        if nova != confirmar:
            return error_response("A confirmação não confere com a nova senha.", 400)
        if nova == atual:
            return error_response("A nova senha precisa ser diferente da atual.", 400)
        if nova.strip().lower() == user["username"]:
            return error_response("A senha não pode ser igual ao seu usuário.", 400)

        new_version = bump_member_session_version(user["user_id"], hash_password(nova))
        clear_login_attempts(limit_key)

        # Este aparelho continua conectado; os demais precisam entrar de novo.
        accounts = read_session_accounts() or {}
        accounts[user["username"]] = new_version
        write_session_accounts(accounts)
        invalidate_current_user()
        log_info(f"Senha alterada pelo perfil. usuario={user['username']}")
        return json_no_store({"ok": True, "message": "Senha alterada. Os outros aparelhos foram desconectados."})
    except Exception as error:
        log_error("Falha em /api/perfil/senha [POST]", error)
        return error_response(str(error))


@app.post("/api/perfil/sair-todos")
@require_personal_account
def sign_out_everywhere():
    try:
        user = get_current_user()
        bump_member_session_version(user["user_id"])
        target = leave_current_account(user["username"])
        return json_no_store({"ok": True, "message": "Você saiu de todos os aparelhos.", "redirect": target})
    except Exception as error:
        log_error("Falha em /api/perfil/sair-todos [POST]", error)
        return error_response(str(error))


# ---------------------------------------------------------------------------
# Gerenciar membros das metas (somente administrador)
# ---------------------------------------------------------------------------
MEMBER_USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")
MEMBER_DISPLAY_NAME_MAX_LENGTH = 40
TEMP_PASSWORD_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def generate_temp_password(length=10):
    return "".join(secrets.choice(TEMP_PASSWORD_ALPHABET) for _ in range(length))


def meta_member_row(user_id):
    return meta_query_one(
        "SELECT id, username, display_name, role, active FROM meta_users WHERE id = ? AND role = 'member'",
        (user_id,),
    )


def display_name_in_use(display_name, exclude_id=""):
    rows = meta_query_all(
        "SELECT id, display_name FROM meta_users WHERE role = 'member' AND active = 1"
    )
    wanted = str(display_name or "").strip().lower()
    return any(row["id"] != exclude_id and str(row["display_name"] or "").strip().lower() == wanted for row in rows)


@app.get("/api/meta-members")
@require_admin
def list_meta_members():
    try:
        ensure_meta_database_ready()
        seeded = {member["username"] for member in META_MEMBERS}
        rows = meta_query_all(
            """
            SELECT u.id, u.username, u.display_name, u.active, u.created_at,
                   COALESCE(p.apelido, '') AS apelido,
                   COALESCE(p.avatar_version, 0) AS avatar_version,
                   CASE WHEN COALESCE(p.thumb_b64, '') <> '' THEN 1 ELSE 0 END AS has_photo
            FROM meta_users u
            LEFT JOIN user_profiles p ON p.user_id = u.id
            WHERE u.role = 'member'
            ORDER BY u.active DESC, u.display_name ASC
            """
        )
        members = [{
            "id": row["id"],
            "username": row["username"],
            "display_name": row["display_name"],
            "apelido": row["apelido"],
            "active": bool(row["active"]),
            "created_at": row["created_at"],
            "in_env": row["username"] in seeded,
            "avatar": member_avatar_url(row["id"], row["avatar_version"], row["has_photo"]),
        } for row in rows]
        return json_no_store({"ok": True, "members": members})
    except Exception as error:
        log_error("Falha em /api/meta-members [GET]", error)
        return error_response(str(error))


@app.post("/api/meta-members")
@require_admin
def add_meta_member():
    try:
        data = request.get_json(silent=True) or {}
        username = str(data.get("username") or "").strip().lower()
        if not MEMBER_USERNAME_PATTERN.match(username):
            return error_response("Usuário inválido: use de 3 a 32 letras minúsculas, números, ponto, hífen ou sublinhado.", 400)
        if username in AUTH_USERS:
            return error_response("Esse usuário é reservado para a equipe administrativa.", 400)
        display_name = clean_plain_text(data.get("display_name"), "Nome", MEMBER_DISPLAY_NAME_MAX_LENGTH, required=True)

        provided = str(data.get("password") or "")
        if provided:
            if len(provided) < PASSWORD_MIN_LENGTH or len(provided) > PASSWORD_MAX_LENGTH:
                return error_response(f"A senha deve ter entre {PASSWORD_MIN_LENGTH} e {PASSWORD_MAX_LENGTH} caracteres.", 400)
            password = provided
        else:
            password = generate_temp_password()

        if username in MEMBER_USERNAME_RENAMES:
            return error_response(f"Esse usuário foi renomeado para {MEMBER_USERNAME_RENAMES[username]}. Escolha outro.", 409)
        existing = meta_query_one("SELECT id, active, role FROM meta_users WHERE username = ?", (username,))
        if existing:
            if existing["role"] != "member" or existing["active"]:
                return error_response("Já existe um usuário com esse nome de acesso.", 409)
            return error_response("Esse usuário já existiu e está removido. Use o botão Reativar na lista de removidos.", 409)
        if display_name_in_use(display_name):
            return error_response("Já existe um membro ativo com esse nome. Use um nome diferente para não confundir o painel de metas.", 409)

        user_id = meta_member_id(username)
        if meta_query_one("SELECT id FROM meta_users WHERE id = ?", (user_id,)):
            return error_response("Já existe um usuário com esse nome de acesso.", 409)
        meta_execute(
            "INSERT INTO meta_users (id, username, display_name, password_hash, role, active, created_at) "
            "VALUES (?, ?, ?, ?, 'member', 1, ?)",
            (user_id, username, display_name, hash_password(password), format_timestamp()),
        )
        ensure_profile_row(user_id)
        ensure_current_meta_submissions()
        log_info(f"Membro adicionado ao painel de metas. usuario={username} por={get_current_user()['username']}")
        payload = {
            "ok": True,
            "message": f"{display_name} foi adicionado às metas.",
            "member": {"id": user_id, "username": username, "display_name": display_name},
        }
        if not provided:
            payload["senha_provisoria"] = password
        return json_no_store(payload, 201)
    except ValueError as error:
        return error_response(str(error), 400)
    except Exception as error:
        log_error("Falha em /api/meta-members [POST]", error)
        return error_response(str(error))


@app.delete("/api/meta-members/<user_id>")
@require_admin
def remove_meta_member(user_id):
    try:
        member = meta_member_row(user_id)
        if not member:
            return error_response("Membro não encontrado.", 404)
        if not member["active"]:
            return error_response("Esse membro já está removido.", 409)
        meta_execute("UPDATE meta_users SET active = 0 WHERE id = ?", (user_id,))
        # Derruba as sessões abertas dele e impede que voltem se ele for reativado depois.
        bump_member_session_version(user_id)
        log_info(f"Membro removido do painel de metas. usuario={member['username']} por={get_current_user()['username']}")
        return json_no_store({
            "ok": True,
            "message": f"{member['display_name']} foi removido das metas. O histórico e as fotos continuam guardados.",
        })
    except Exception as error:
        log_error("Falha em /api/meta-members [DELETE]", error)
        return error_response(str(error))


@app.post("/api/meta-members/<user_id>/reativar")
@require_admin
def reactivate_meta_member(user_id):
    try:
        member = meta_member_row(user_id)
        if not member:
            return error_response("Membro não encontrado.", 404)
        if member["active"]:
            return error_response("Esse membro já está ativo.", 409)
        if display_name_in_use(member["display_name"], exclude_id=user_id):
            return error_response("Já existe um membro ativo com esse nome. Remova ou renomeie o outro antes de reativar.", 409)
        meta_execute("UPDATE meta_users SET active = 1 WHERE id = ?", (user_id,))
        # A senha antiga continua valendo; as sessões de antes da remoção continuam derrubadas.
        bump_member_session_version(user_id)
        ensure_current_meta_submissions()
        log_info(f"Membro reativado no painel de metas. usuario={member['username']} por={get_current_user()['username']}")
        return json_no_store({"ok": True, "message": f"{member['display_name']} voltou para as metas."})
    except Exception as error:
        log_error("Falha em /api/meta-members/reativar [POST]", error)
        return error_response(str(error))


@app.post("/api/meta-members/<user_id>/redefinir-senha")
@require_admin
def reset_meta_member_password(user_id):
    try:
        member = meta_member_row(user_id)
        if not member:
            return error_response("Membro não encontrado.", 404)
        if not member["active"]:
            return error_response("Reative o membro antes de redefinir a senha.", 409)
        password = generate_temp_password()
        bump_member_session_version(user_id, hash_password(password))
        log_info(f"Senha de membro redefinida pelo administrador. usuario={member['username']} por={get_current_user()['username']}")
        return json_no_store({
            "ok": True,
            "message": f"Nova senha provisória de {member['display_name']} gerada. Os aparelhos dele foram desconectados.",
            "senha_provisoria": password,
        })
    except Exception as error:
        log_error("Falha em /api/meta-members/redefinir-senha [POST]", error)
        return error_response(str(error))


if __name__ == "__main__":
    log_info("Iniciando aplicação Kokusai...")
    if app.secret_key == DEFAULT_SECRET_KEY:
        log_info("ATENÇÃO: SECRET_KEY padrão em uso. Configure SECRET_KEY no Railway antes de publicar.")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
