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
import unicodedata
from pathlib import Path
from copy import deepcopy
from datetime import datetime, timedelta, date, timezone
from functools import wraps
from flask import Flask, jsonify, render_template, request, redirect, session, url_for, g, send_from_directory
import gspread
from google.oauth2.service_account import Credentials
from werkzeug.utils import secure_filename

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
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", str(10 * 1024 * 1024)))


SHEET_NAME = os.getenv("SHEET_NAME", "KokusaiDB")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "").strip()
COMPRAS_WORKSHEET_NAME = os.getenv("COMPRAS_WORKSHEET_NAME", "Compras")
VENDAS_WORKSHEET_NAME = os.getenv("VENDAS_WORKSHEET_NAME", "Vendas")
ENCOMENDAS_WORKSHEET_NAME = os.getenv("ENCOMENDAS_WORKSHEET_NAME", "Encomendas")
METAS_WORKSHEET_NAME = os.getenv("METAS_WORKSHEET_NAME", "Pagamento de Metas")
HISTORICO_METAS_WORKSHEET_NAME = os.getenv("HISTORICO_METAS_WORKSHEET_NAME", "Historico Metas")
REUNIOES_WORKSHEET_NAME = os.getenv("REUNIOES_WORKSHEET_NAME", "Reunioes")
META_RESET_WEEKDAY = int(os.getenv("META_RESET_WEEKDAY", "2"))  # 0=segunda, 2=quarta
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "America/Sao_Paulo")
APP_UTC_OFFSET_HOURS = int(os.getenv("APP_UTC_OFFSET_HOURS", "-3"))

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

# Proteções simples contra abuso. Como o app roda em poucos usuários,
# limites curtos já reduzem bastante risco de força bruta e payload gigante.
LOGIN_ATTEMPTS = {}
LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_WINDOW_SECONDS = int(os.getenv("LOGIN_WINDOW_SECONDS", "900"))
MAX_TEXT_LENGTH = int(os.getenv("MAX_TEXT_LENGTH", "120"))
MAX_OBSERVATION_LENGTH = int(os.getenv("MAX_OBSERVATION_LENGTH", "500"))
MAX_QUANTITY = int(os.getenv("MAX_QUANTITY", "1000000"))
MAX_MONEY_VALUE = float(os.getenv("MAX_MONEY_VALUE", "1000000000"))
MAX_FLYER_UPLOAD_BYTES = int(os.getenv("MAX_FLYER_UPLOAD_BYTES", str(8 * 1024 * 1024)))
MAX_PRICE_DESCRIPTION_LENGTH = int(os.getenv("MAX_PRICE_DESCRIPTION_LENGTH", "1200"))
SHEET_FORMULA_PREFIXES = ("=", "+", "-", "@")

# Arquivos enviados pelo painel. No Railway, aponte KOKUSAI_DATA_DIR para um Volume
# (ex.: /data/kokusai) para que uploads e descrições sobrevivam a novos deploys.
KOKUSAI_DATA_DIR = Path(os.getenv("KOKUSAI_DATA_DIR", str(Path(app.root_path) / "data"))).resolve()
FLYER_UPLOAD_DIR = KOKUSAI_DATA_DIR / "flyers"
FLYER_METADATA_PATH = KOKUSAI_DATA_DIR / "flyers_metadata.json"
_flyer_lock = threading.RLock()


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
    "Biel",
    "Dulce",
    "Dylan",
    "Eloá",
    "GB",
    "Gohan",
    "Hinata",
    "João",
    "Junior Azul",
    "Lara Salles",
    "Liam",
    "Lipe",
    "Larissa",
    "Lucas",
    "Lucas Ricci",
    "Luciano",
    "Matheus",
    "Mia",
    "Minazuki",
    "Morgan",
    "Nanami",
    "Ricardo",
    "Semente",
    "Yori",
    "Wanda",
    "Yan (Gordin)",
    "Haper",
    "Vô Chico",
    "Kyotaka",
]

COMPRAS_HEADERS = ["id", "data", "produto", "quem_pediu", "quem_vendeu", "valor_unitario", "quantidade", "valor_total", "observacao"]
VENDAS_HEADERS = [
    "id", "data", "produto", "quem_compra", "quem_vende", "valor_unitario", "quantidade",
    "valor_total", "observacao", "tipo_dinheiro", "valor_base",
    "quantidade_l85", "valor_unitario_l85", "quantidade_seringa", "valor_unitario_seringa",
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
    "quantidade_l85",
    "valor_unitario_l85",
    "quantidade_seringa",
    "valor_unitario_seringa",
]
META_HEADERS = ["id", "nome", "pago", "atualizado_em", "semana_inicio", "semana_fim", "confirmado"]
META_HISTORY_HEADERS = ["semana_inicio", "semana_fim", "fechado_em", "id", "nome", "pago", "atualizado_em"]
REUNIOES_HEADERS = ["id", "criado_em", "titulo", "gangue", "icone", "data", "horario", "local", "pauta", "status", "finalizada_em", "organizacao_id"]

# Cadastro central das organizações e dos flyers originais do projeto. Novos flyers
# também podem ser enviados pelo painel e ficam salvos no diretório KOKUSAI_DATA_DIR.
ORGANIZACOES = [
    {
        "id": "ballas", "nome": "Ballas", "icone": "🟣",
        "aliases": ["Ballas"],
        "flyers": [{"id": "ballas-acessorios", "titulo": "Tabela de acessórios", "arquivo": "images/flyers/ballas.webp"}],
    },
    {
        "id": "los-bandoleros", "nome": "Los Bandoleros", "icone": "🟡",
        "aliases": ["Los Bandoleros", "Bandoleros", "Cartel"],
        "flyers": [{"id": "bandoleros-valores", "titulo": "Tabela de valores", "arquivo": "images/flyers/los-bandoleros.webp"}],
    },
    {
        "id": "distrito", "nome": "Distrito", "icone": "⚪",
        "aliases": ["Distrito"],
        "flyers": [{"id": "distrito-parceiros", "titulo": "Valores para parceiros", "arquivo": "images/flyers/distrito.webp"}],
    },
    {
        "id": "families", "nome": "Families", "icone": "💚",
        "aliases": ["Families", "FMLS"],
        "flyers": [{"id": "families-valores", "titulo": "Tabela de valores", "arquivo": "images/flyers/families.webp"}],
    },
    {
        "id": "hells", "nome": "Hells", "icone": "💗",
        "aliases": ["Hells", "Sinfuriosa", "Sin Furiosa"],
        "flyers": [{"id": "hells-produtos", "titulo": "Produtos e valores", "arquivo": "images/flyers/hells.webp"}],
    },
    {
        "id": "hydra", "nome": "Hydra", "icone": "🐉",
        "aliases": ["Hydra"],
        "flyers": [
            {"id": "hydra-colete", "titulo": "Colete e C4", "arquivo": "images/flyers/hydra-colete.webp"},
            {"id": "hydra-attach", "titulo": "Acessórios", "arquivo": "images/flyers/hydra-attach.webp"},
        ],
    },
    {
        "id": "leviata", "nome": "Leviatã", "icone": "🐲",
        "aliases": ["Leviatã", "Leviata", "Leviathan"],
        "flyers": [{"id": "leviata-cnpj", "titulo": "Tabela CNPJ", "arquivo": "images/flyers/leviata.webp"}],
    },
    {
        "id": "legacy", "nome": "Legacy", "icone": "👑",
        "aliases": ["Legacy"],
        "flyers": [{"id": "legacy-tec9", "titulo": "Tabela TEC-9", "arquivo": "images/flyers/legacy.webp"}],
    },
    {
        "id": "la-guardia", "nome": "La Guardia", "icone": "🟪",
        "aliases": ["La Guardia", "Laguardia", "LaGuardia"],
        "flyers": [{"id": "la-guardia-acessorios", "titulo": "Acessórios", "arquivo": "images/flyers/la-guardia.webp"}],
    },
    {
        "id": "vagos", "nome": "Vagos", "icone": "💛",
        "aliases": ["Vagos", "Los Vagos"],
        "flyers": [{"id": "vagos-armas", "titulo": "Tabela de armas", "arquivo": "images/flyers/vagos.webp"}],
    },
    {
        "id": "vendetta", "nome": "Vendetta", "icone": "🟠",
        "aliases": ["Vendetta"],
        "flyers": [{"id": "vendetta-produtos", "titulo": "Tabela de produtos", "arquivo": "images/flyers/vendetta.webp"}],
    },
    # Organizações já presentes na agenda, mas ainda sem uma imagem enviada.
    {"id": "blackherts", "nome": "Blackherts", "icone": "🖤", "aliases": ["Blackherts", "Blackhearts"], "flyers": []},
    {"id": "the-lost", "nome": "The Lost", "icone": "🏍️", "aliases": ["The Lost", "Lost"], "flyers": []},
]
ORGANIZACOES_POR_ID = {item["id"]: item for item in ORGANIZACOES}
LIST_LIMIT = int(os.getenv("LIST_LIMIT", "100"))


def default_flyer_metadata():
    return {"organizations": {}, "uploaded_flyers": [], "flyer_states": {}}


def ensure_flyer_storage():
    KOKUSAI_DATA_DIR.mkdir(parents=True, exist_ok=True)
    FLYER_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def load_flyer_metadata():
    ensure_flyer_storage()
    with _flyer_lock:
        if not FLYER_METADATA_PATH.exists():
            return default_flyer_metadata()
        try:
            payload = json.loads(FLYER_METADATA_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log_error("Falha ao ler metadados dos flyers", exc)
            return default_flyer_metadata()

        if not isinstance(payload, dict):
            return default_flyer_metadata()
        payload.setdefault("organizations", {})
        payload.setdefault("uploaded_flyers", [])
        payload.setdefault("flyer_states", {})
        if not isinstance(payload["organizations"], dict):
            payload["organizations"] = {}
        if not isinstance(payload["uploaded_flyers"], list):
            payload["uploaded_flyers"] = []
        if not isinstance(payload["flyer_states"], dict):
            payload["flyer_states"] = {}
        return payload


def save_flyer_metadata(payload):
    ensure_flyer_storage()
    with _flyer_lock:
        temp_path = FLYER_METADATA_PATH.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temp_path, FLYER_METADATA_PATH)


def detect_uploaded_image_extension(content):
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp"
    return ""


def builtin_flyer_by_id(organization, flyer_id):
    for flyer in organization.get("flyers", []):
        if str(flyer.get("id")) == str(flyer_id):
            return flyer
    return None


def uploaded_flyer_by_id(metadata, organization_id, flyer_id):
    for flyer in metadata.get("uploaded_flyers", []):
        if flyer.get("organization_id") == organization_id and str(flyer.get("id")) == str(flyer_id):
            return flyer
    return None


def serialize_flyer(organization, flyer, metadata, is_builtin=False):
    flyer_id = str(flyer.get("id") or "")
    if is_builtin:
        state = metadata.get("flyer_states", {}).get(flyer_id, {})
        visible = bool(state.get("visible", True))
        removed = bool(state.get("removed", False))
        return {
            "id": flyer_id,
            "titulo": flyer.get("titulo") or "Flyer",
            "url": url_for("static", filename=flyer.get("arquivo")),
            "visible": visible and not removed,
            "removed": removed,
            "builtin": True,
            "uploaded_by": "Projeto",
            "created_at": "",
        }

    filename = secure_filename(str(flyer.get("filename") or ""))
    return {
        "id": flyer_id,
        "titulo": flyer.get("titulo") or "Flyer",
        "url": url_for("uploaded_flyer_file", filename=filename),
        "visible": bool(flyer.get("visible", False)),
        "removed": False,
        "builtin": False,
        "uploaded_by": flyer.get("uploaded_by") or "Usuário",
        "created_at": flyer.get("created_at") or "",
    }


def normalize_organization_key(value):
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", text)


def find_organization(organizacao_id=None, nome=None):
    org_id = str(organizacao_id or "").strip().lower()
    if org_id and org_id in ORGANIZACOES_POR_ID:
        return ORGANIZACOES_POR_ID[org_id]

    key = normalize_organization_key(nome)
    if not key:
        return None

    for organization in ORGANIZACOES:
        candidates = [organization.get("nome", ""), *organization.get("aliases", [])]
        if any(normalize_organization_key(candidate) == key for candidate in candidates):
            return organization
    return None


def serialize_organization(organization, metadata=None, include_hidden=None):
    metadata = metadata or load_flyer_metadata()
    user = get_current_user()
    is_admin = bool(user and user.get("role") == "admin")
    if include_hidden is None:
        include_hidden = is_admin

    all_flyers = [
        serialize_flyer(organization, flyer, metadata, is_builtin=True)
        for flyer in organization.get("flyers", [])
    ]
    all_flyers.extend(
        serialize_flyer(organization, flyer, metadata, is_builtin=False)
        for flyer in metadata.get("uploaded_flyers", [])
        if flyer.get("organization_id") == organization.get("id")
    )

    visible_flyers = [flyer for flyer in all_flyers if flyer.get("visible")]
    hidden_flyers = [flyer for flyer in all_flyers if not flyer.get("visible")]
    commercial = metadata.get("organizations", {}).get(organization["id"], {})

    return {
        "id": organization["id"],
        "nome": organization["nome"],
        "icone": organization.get("icone", "🤝"),
        "tem_flyer": bool(visible_flyers),
        "flyers": visible_flyers,
        "pending_flyers": hidden_flyers if include_hidden else [],
        "total_flyers": len(all_flyers),
        "preco_venda_para_organizacao": commercial.get("preco_venda_para_organizacao", ""),
        "preco_compra_da_organizacao": commercial.get("preco_compra_da_organizacao", ""),
        "can_upload": bool(user),
        "can_manage": is_admin,
    }

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


def get_current_user():
    username = session.get("username")
    if not username:
        return None

    user = AUTH_USERS.get(username)
    if not user:
        session.clear()
        return None

    return {
        "username": username,
        "display_name": user["display_name"],
        "role": user["role"],
        "can_write": user["role"] == "admin",
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


def require_authenticated_write(view):
    """Permite escrita a qualquer usuário autenticado, mantendo proteção CSRF."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if not user:
            return error_response("Login necessário para acessar o sistema.", 401)
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
        "img-src 'self' data:; "
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


def numeric_value(value, default=0.0):
    try:
        if str(value or "").strip() == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def integer_value(value, default=0):
    try:
        if str(value or "").strip() == "":
            return default
        number = float(value)
        if not number.is_integer():
            return default
        return int(number)
    except (TypeError, ValueError):
        return default


def parse_item_quantity(data, key, label):
    raw = data.get(key, "")
    if str(raw or "").strip() == "":
        return 0
    try:
        quantity = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{label} deve ser uma quantidade inteira.")
    if quantity < 0:
        raise ValueError(f"{label} não pode ser negativa.")
    if quantity > MAX_QUANTITY:
        raise ValueError(f"{label} deve ser no máximo {MAX_QUANTITY}.")
    return quantity


def parse_item_price(data, key, label, required=False):
    raw = data.get(key, "")
    if str(raw or "").strip() == "":
        if required:
            raise ValueError(f"{label} é obrigatório quando a quantidade é maior que zero.")
        return 0.0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{label} deve ser numérico.")
    if value < 0:
        raise ValueError(f"{label} não pode ser negativo.")
    if value > MAX_MONEY_VALUE:
        raise ValueError(f"{label} está muito alto.")
    return round(value, 2)


def parse_special_product_lines(data):
    quantity_l85 = parse_item_quantity(data, "quantidade_l85", "Quantidade de L85")
    quantity_syringe = parse_item_quantity(data, "quantidade_seringa", "Quantidade de seringas")
    price_l85 = parse_item_price(
        data,
        "valor_unitario_l85",
        "Valor unitário da L85",
        required=quantity_l85 > 0,
    )
    price_syringe = parse_item_price(
        data,
        "valor_unitario_seringa",
        "Valor unitário da seringa",
        required=quantity_syringe > 0,
    )

    if quantity_l85 == 0 and price_l85:
        raise ValueError("Informe a quantidade de L85 para usar o valor unitário da L85.")
    if quantity_syringe == 0 and price_syringe:
        raise ValueError("Informe a quantidade de seringas para usar o valor unitário da seringa.")

    return {
        "quantidade_l85": quantity_l85,
        "valor_unitario_l85": price_l85,
        "quantidade_seringa": quantity_syringe,
        "valor_unitario_seringa": price_syringe,
        "valor_calculado": round(quantity_l85 * price_l85 + quantity_syringe * price_syringe, 2),
    }


def product_description(quantity_l85=0, quantity_syringe=0, extra="", extra_quantity=0):
    parts = []
    if quantity_l85:
        parts.append(f"{quantity_l85}x L85")
    if quantity_syringe:
        label = "Seringa" if quantity_syringe == 1 else "Seringas"
        parts.append(f"{quantity_syringe}x {label}")
    extra = str(extra or "").strip()
    if extra:
        parts.append(f"{extra_quantity}x {extra}" if extra_quantity else extra)
    return " + ".join(parts)


def parse_venda_items(data):
    special = parse_special_product_lines(data)
    product = clean_text_field(data, "produto", "Outro produto", required=False)
    generic_quantity_raw = data.get("quantidade", "")
    generic_price_raw = data.get("valor_unitario", "")
    has_generic_numbers = numeric_value(generic_quantity_raw, 0) > 0 or numeric_value(generic_price_raw, 0) > 0

    generic_quantity = 0
    generic_price = 0.0
    if product or has_generic_numbers:
        if not product:
            raise ValueError("Informe o nome do outro produto.")
        generic_quantity = parse_item_quantity(data, "quantidade", "Quantidade do outro produto")
        if generic_quantity <= 0:
            raise ValueError("A quantidade do outro produto deve ser maior que zero.")
        generic_price = parse_item_price(data, "valor_unitario", "Valor unitário do outro produto", required=True)

    total_quantity = special["quantidade_l85"] + special["quantidade_seringa"] + generic_quantity
    if total_quantity <= 0:
        raise ValueError("Informe ao menos uma quantidade de L85, seringa ou outro produto.")

    total_value = round(
        special["valor_calculado"] + generic_quantity * generic_price,
        2,
    )
    if total_value > MAX_MONEY_VALUE:
        raise ValueError("Valor total muito alto.")

    description = product_description(
        special["quantidade_l85"],
        special["quantidade_seringa"],
        product,
        generic_quantity,
    )
    average_unit = round(total_value / total_quantity, 2) if total_quantity else 0
    return {
        **special,
        "produto": description,
        "quantidade": total_quantity,
        "valor_unitario": average_unit,
        "valor_total": total_value,
    }


def parse_encomenda_items(data):
    special = parse_special_product_lines(data)
    extra = clean_text_field(data, "o_que_pediu", "Outro item / descrição", required=False)
    description = product_description(
        special["quantidade_l85"],
        special["quantidade_seringa"],
        extra,
    )
    if not description:
        raise ValueError("Informe ao menos L85, seringa ou uma descrição do pedido.")

    raw_value = data.get("valor", "")
    if str(raw_value or "").strip() == "":
        if special["valor_calculado"] <= 0:
            raise ValueError("Informe o valor total da encomenda.")
        total_value = special["valor_calculado"]
    else:
        try:
            total_value = round(float(raw_value), 2)
        except (TypeError, ValueError):
            raise ValueError("O valor da encomenda deve ser numérico.")
    if total_value < 0:
        raise ValueError("O valor da encomenda não pode ser negativo.")
    if total_value > MAX_MONEY_VALUE:
        raise ValueError("Valor da encomenda muito alto.")

    return {
        **special,
        "o_que_pediu": description,
        "valor": total_value,
    }


def normalize_money_type(value):
    normalized = str(value or "").strip().lower()
    if normalized == "limpo":
        return "Limpo"
    if normalized == "sujo":
        return "Sujo"
    return ""


def calculate_payment_value(base_value, money_type):
    base = round(float(base_value or 0), 2)
    normalized_type = normalize_money_type(money_type)
    final_value = round(base * 1.30, 2) if normalized_type == "Sujo" else base
    return base, final_value, normalized_type


def format_brl_value(value):
    formatted = f"{float(value or 0):,.2f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def normalize_venda(row):
    item = row_to_dict(row, VENDAS_HEADERS)
    item["tipo_dinheiro"] = normalize_money_type(item.get("tipo_dinheiro"))
    item["valor_base"] = round(numeric_value(item.get("valor_base") or item.get("valor_total"), 0), 2)
    item["quantidade_l85"] = integer_value(item.get("quantidade_l85"), 0)
    item["quantidade_seringa"] = integer_value(item.get("quantidade_seringa"), 0)
    item["valor_unitario_l85"] = round(numeric_value(item.get("valor_unitario_l85"), 0), 2)
    item["valor_unitario_seringa"] = round(numeric_value(item.get("valor_unitario_seringa"), 0), 2)
    return item


def normalize_encomenda(row):
    item = row_to_dict(row, ENCOMENDAS_HEADERS)
    item["entregue"] = validate_yes_no(item.get("entregue")) or "Não"
    item["valor"] = round(numeric_value(item.get("valor"), 0), 2)
    item["quantidade_l85"] = integer_value(item.get("quantidade_l85"), 0)
    item["quantidade_seringa"] = integer_value(item.get("quantidade_seringa"), 0)
    item["valor_unitario_l85"] = round(numeric_value(item.get("valor_unitario_l85"), 0), 2)
    item["valor_unitario_seringa"] = round(numeric_value(item.get("valor_unitario_seringa"), 0), 2)
    return item


ENCOMENDA_ITEM_PATTERN = re.compile(r"^\s*(\d+)(?:\s*x\s*|\s+)(.+?)\s*$", re.IGNORECASE)


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


def build_venda_row_from_encomenda(item, entregue_em=None, tipo_dinheiro="Limpo"):
    quantity_l85 = integer_value(item.get("quantidade_l85"), 0)
    quantity_syringe = integer_value(item.get("quantidade_seringa"), 0)
    specialized_quantity = quantity_l85 + quantity_syringe

    if specialized_quantity > 0:
        quantity = specialized_quantity
        product = str(item.get("o_que_pediu") or "").strip() or product_description(quantity_l85, quantity_syringe)
    else:
        quantity, product = parse_encomenda_item(item.get("o_que_pediu"))

    base_value, total_value, normalized_money_type = calculate_payment_value(item.get("valor"), tipo_dinheiro)
    if not normalized_money_type:
        raise ValueError("Escolha se a entrega foi paga em dinheiro limpo ou sujo.")

    unit_value = round(total_value / quantity, 2) if quantity else total_value
    money_factor = 1.30 if normalized_money_type == "Sujo" else 1.0
    unit_l85 = round(numeric_value(item.get("valor_unitario_l85"), 0) * money_factor, 2)
    unit_syringe = round(numeric_value(item.get("valor_unitario_seringa"), 0) * money_factor, 2)
    encomenda_id = str(item.get("id") or "").strip()
    deadline = str(item.get("para_quando") or "").strip()
    original_observation = str(item.get("observacao") or "").strip()

    details = [f"Convertida da encomenda {encomenda_id}."]
    if deadline:
        details.append(f"Prazo combinado: {deadline}.")
    if normalized_money_type == "Sujo":
        details.append(f"Pagamento em dinheiro sujo (+30%). Valor base: R$ {format_brl_value(base_value)}.")
    else:
        details.append("Pagamento em dinheiro limpo.")

    observation = " ".join(filter(None, [original_observation, *details]))
    observation = observation[:MAX_OBSERVATION_LENGTH]

    return [
        venda_id_from_encomenda(encomenda_id),
        entregue_em or format_timestamp(),
        product,
        str(item.get("quem_pediu") or "").strip(),
        str(item.get("quem_negociou") or "").strip(),
        unit_value,
        quantity,
        total_value,
        observation,
        normalized_money_type,
        base_value,
        quantity_l85,
        unit_l85,
        quantity_syringe,
        unit_syringe,
    ]


def worksheet_has_record_id(worksheet, registro_id):
    rows = cached_get_all_values(worksheet.title, worksheet, force=True)
    return any(sheet_cell(row, 0) == registro_id for row in rows[1:])


def move_encomenda_row_to_vendas(encomendas_worksheet, row_index, row, tipo_dinheiro):
    while len(row) < len(ENCOMENDAS_HEADERS):
        row.append("")

    delivered_at = str(row[9] or "").strip() or format_timestamp()
    item = normalize_encomenda(row)
    item["entregue"] = "Sim"
    item["entregue_em"] = delivered_at

    sales_worksheet = get_vendas_worksheet()
    sale_row = build_venda_row_from_encomenda(
        item,
        entregue_em=delivered_at,
        tipo_dinheiro=tipo_dinheiro,
    )
    sale_id = sale_row[0]

    existing_index, existing_row = find_row_by_id(sales_worksheet, sale_id)
    if existing_index:
        while len(existing_row) < len(VENDAS_HEADERS):
            existing_row.append("")
        sale_row = existing_row[:len(VENDAS_HEADERS)]
    else:
        sales_worksheet.append_row(sale_row, value_input_option="RAW")

    encomendas_worksheet.delete_rows(row_index)
    invalidate_values_cache(ENCOMENDAS_WORKSHEET_NAME, VENDAS_WORKSHEET_NAME)
    log_info(f"Encomenda movida para Vendas. Encomenda={item.get('id')} Venda={sale_id}")
    return {
        "venda_id": sale_id,
        "entregue_em": delivered_at,
        "tipo_dinheiro": sale_row[9],
        "valor_base": sale_row[10],
        "valor_total": sale_row[7],
    }


def normalize_reuniao(row):
    item = row_to_dict(row, REUNIOES_HEADERS)
    raw_status = str(item.get("status", "")).strip().lower()
    if raw_status == "finalizada":
        item["status"] = "Finalizada"
    elif raw_status == "cancelada":
        item["status"] = "Cancelada"
    elif raw_status in {"aguardando confirmação", "aguardando confirmacao", "a confirmar"}:
        item["status"] = "Aguardando confirmação"
    else:
        item["status"] = "Agendada"

    organization = find_organization(item.get("organizacao_id"), item.get("gangue"))
    if organization:
        item["organizacao_id"] = organization["id"]
        item["organizacao"] = serialize_organization(organization)
        item["gangue"] = organization["nome"]
        item["icone"] = item.get("icone") or organization.get("icone", "🤝")
    else:
        item["organizacao_id"] = ""
        item["organizacao"] = None
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


@app.errorhandler(413)
def request_too_large(_error):
    if wants_json_response():
        return error_response("Arquivo ou requisição maior que o limite permitido.", 413)
    return "Arquivo ou requisição maior que o limite permitido.", 413


@app.get("/")
@require_login
def home():
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

        user = AUTH_USERS.get(username)

        if user and verify_password(password, user["password_hash"]):
            session.clear()
            session.permanent = True
            session["username"] = username
            get_csrf_token()
            clear_login_attempts(key)
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
        "credentials_present": bool(credentials_json),
        "service_account_email": client_email,
    })


@app.get("/api/organizacoes")
@require_login
def list_organizacoes():
    metadata = load_flyer_metadata()
    return jsonify([serialize_organization(item, metadata=metadata) for item in ORGANIZACOES])


@app.get("/uploads/flyers/<path:filename>")
@require_login
def uploaded_flyer_file(filename):
    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename:
        return error_response("Arquivo inválido.", 404)
    return send_from_directory(str(FLYER_UPLOAD_DIR), safe_name, max_age=3600)


@app.post("/api/organizacoes/<organizacao_id>/flyers")
@require_authenticated_write
def upload_organization_flyer(organizacao_id):
    organization = find_organization(organizacao_id=organizacao_id)
    if not organization:
        return error_response("Organização não encontrada.", 404)

    uploaded_file = request.files.get("flyer")
    if not uploaded_file or not uploaded_file.filename:
        return error_response("Selecione uma imagem para enviar.", 400)

    try:
        title = clean_text(
            request.form.get("titulo", ""),
            "Título do flyer",
            max_length=100,
            required=True,
        )
    except ValueError as validation_error:
        return error_response(str(validation_error), 400)

    content = uploaded_file.stream.read(MAX_FLYER_UPLOAD_BYTES + 1)
    if len(content) > MAX_FLYER_UPLOAD_BYTES:
        return error_response(
            f"O flyer deve ter no máximo {MAX_FLYER_UPLOAD_BYTES // (1024 * 1024)} MB.",
            413,
        )

    extension = detect_uploaded_image_extension(content)
    if not extension:
        return error_response("Formato inválido. Envie PNG, JPG/JPEG ou WEBP.", 400)

    user = get_current_user()
    flyer_id = f"flyer-{secrets.token_hex(8)}"
    filename = f"{flyer_id}{extension}"
    ensure_flyer_storage()
    destination = FLYER_UPLOAD_DIR / filename
    temporary = destination.with_suffix(destination.suffix + ".tmp")

    try:
        temporary.write_bytes(content)
        os.replace(temporary, destination)
        metadata = load_flyer_metadata()
        record = {
            "id": flyer_id,
            "organization_id": organization["id"],
            "titulo": title,
            "filename": filename,
            "uploaded_by": user.get("display_name") or user.get("username"),
            "created_at": format_timestamp(),
            # Kokusai publica imediatamente; outros usuários enviam para aprovação.
            "visible": user.get("role") == "admin",
        }
        metadata["uploaded_flyers"].append(record)
        save_flyer_metadata(metadata)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    status_message = (
        "Flyer enviado e publicado com sucesso."
        if record["visible"]
        else "Flyer enviado. Ele ficará aguardando a aprovação da Kokusai."
    )
    return jsonify({
        "ok": True,
        "message": status_message,
        "organization": serialize_organization(organization, metadata=metadata),
    }), 201


@app.patch("/api/organizacoes/<organizacao_id>/precos")
@require_admin
def update_organization_prices(organizacao_id):
    organization = find_organization(organizacao_id=organizacao_id)
    if not organization:
        return error_response("Organização não encontrada.", 404)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("JSON inválido.", 400)

    try:
        sale_description = clean_text(
            data.get("preco_venda_para_organizacao", ""),
            "Descrição do preço de venda para a organização",
            max_length=MAX_PRICE_DESCRIPTION_LENGTH,
            required=False,
        )
        purchase_description = clean_text(
            data.get("preco_compra_da_organizacao", ""),
            "Descrição do preço de compra da organização",
            max_length=MAX_PRICE_DESCRIPTION_LENGTH,
            required=False,
        )
    except ValueError as validation_error:
        return error_response(str(validation_error), 400)

    metadata = load_flyer_metadata()
    metadata["organizations"][organization["id"]] = {
        "preco_venda_para_organizacao": sale_description,
        "preco_compra_da_organizacao": purchase_description,
        "updated_at": format_timestamp(),
        "updated_by": get_current_user().get("display_name"),
    }
    save_flyer_metadata(metadata)
    return jsonify({
        "ok": True,
        "message": "Descrições comerciais atualizadas com sucesso.",
        "organization": serialize_organization(organization, metadata=metadata),
    })


@app.patch("/api/organizacoes/<organizacao_id>/flyers/<flyer_id>")
@require_admin
def update_organization_flyer(organizacao_id, flyer_id):
    organization = find_organization(organizacao_id=organizacao_id)
    if not organization:
        return error_response("Organização não encontrada.", 404)
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or "visible" not in data:
        return error_response("Informe se o flyer deve ficar visível.", 400)

    visible = bool(data.get("visible"))
    metadata = load_flyer_metadata()
    builtin = builtin_flyer_by_id(organization, flyer_id)
    uploaded = uploaded_flyer_by_id(metadata, organization["id"], flyer_id)
    if not builtin and not uploaded:
        return error_response("Flyer não encontrado.", 404)

    if builtin:
        state = metadata["flyer_states"].setdefault(str(flyer_id), {})
        state["visible"] = visible
        if visible:
            state["removed"] = False
    else:
        uploaded["visible"] = visible
        uploaded["reviewed_at"] = format_timestamp()
        uploaded["reviewed_by"] = get_current_user().get("display_name")

    save_flyer_metadata(metadata)
    return jsonify({
        "ok": True,
        "message": "Flyer colocado na organização." if visible else "Flyer retirado da organização.",
        "organization": serialize_organization(organization, metadata=metadata),
    })


@app.delete("/api/organizacoes/<organizacao_id>/flyers/<flyer_id>")
@require_admin
def delete_organization_flyer(organizacao_id, flyer_id):
    organization = find_organization(organizacao_id=organizacao_id)
    if not organization:
        return error_response("Organização não encontrada.", 404)

    metadata = load_flyer_metadata()
    builtin = builtin_flyer_by_id(organization, flyer_id)
    uploaded = uploaded_flyer_by_id(metadata, organization["id"], flyer_id)
    if not builtin and not uploaded:
        return error_response("Flyer não encontrado.", 404)

    if builtin:
        state = metadata["flyer_states"].setdefault(str(flyer_id), {})
        state["visible"] = False
        state["removed"] = True
    else:
        filename = secure_filename(str(uploaded.get("filename") or ""))
        metadata["uploaded_flyers"] = [
            flyer for flyer in metadata["uploaded_flyers"]
            if not (
                flyer.get("organization_id") == organization["id"]
                and str(flyer.get("id")) == str(flyer_id)
            )
        ]
        if filename:
            try:
                (FLYER_UPLOAD_DIR / filename).unlink(missing_ok=True)
            except OSError as exc:
                log_error("Não foi possível apagar o arquivo do flyer", exc)

    save_flyer_metadata(metadata)
    return jsonify({
        "ok": True,
        "message": "Flyer removido com sucesso.",
        "organization": serialize_organization(organization, metadata=metadata),
    })


@app.get("/api/compras")
@require_login
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
@require_login
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
        if not isinstance(data, dict):
            return error_response("JSON inválido.", 400)

        try:
            items = parse_venda_items(data)
            buyer = clean_text_field(data, "quem_compra", "Quem compra")
            seller = clean_text_field(data, "quem_vende", "Quem vende")
            observation = clean_text_field(
                data,
                "observacao",
                "Observação",
                max_length=MAX_OBSERVATION_LENGTH,
                required=False,
            )
        except ValueError as validation_error:
            return error_response(str(validation_error), 400)

        now = format_timestamp()
        record_id = generate_record_id("KKSV")
        worksheet = get_vendas_worksheet()
        worksheet.append_row([
            record_id,
            now,
            items["produto"],
            buyer,
            seller,
            items["valor_unitario"],
            items["quantidade"],
            items["valor_total"],
            observation,
            "",
            items["valor_total"],
            items["quantidade_l85"],
            items["valor_unitario_l85"],
            items["quantidade_seringa"],
            items["valor_unitario_seringa"],
        ], value_input_option="RAW")
        invalidate_values_cache(VENDAS_WORKSHEET_NAME)
        log_info(f"Venda registrada com sucesso. ID={record_id}")

        return jsonify({
            "ok": True,
            "message": "Venda salva com sucesso.",
            "id": record_id,
            "valor_total": items["valor_total"],
            "quantidade_total": items["quantidade"],
        }), 201

    except Exception as e:
        log_error("Falha em /api/vendas [POST]", e)
        return error_response(str(e))


@app.get("/api/resumo")
@require_login
def resumo_compras():
    try:
        worksheet = get_compras_worksheet()
        rows = cached_get_all_values(COMPRAS_WORKSHEET_NAME, worksheet)
        return jsonify(financial_summary(rows))

    except Exception as e:
        log_error("Falha em /api/resumo", e)
        return error_response(str(e))


@app.get("/api/resumo-vendas")
@require_login
def resumo_vendas():
    try:
        worksheet = get_vendas_worksheet()
        rows = cached_get_all_values(VENDAS_WORKSHEET_NAME, worksheet)
        return jsonify(financial_summary(rows))

    except Exception as e:
        log_error("Falha em /api/resumo-vendas", e)
        return error_response(str(e))


@app.get("/api/encomendas")
@require_login
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
        if not isinstance(data, dict):
            return error_response("JSON inválido.", 400)

        required_fields = ["quem_pediu", "para_quando", "quem_negociou", "entregue"]
        missing = [field for field in required_fields if str(data.get(field, "")).strip() == ""]
        if missing:
            return error_response(f"Campos obrigatórios ausentes: {', '.join(missing)}", 400)

        delivered = validate_yes_no(data.get("entregue"))
        if not delivered:
            return error_response("O campo 'entregue' deve ser 'Sim' ou 'Não'.", 400)

        money_type = normalize_money_type(data.get("tipo_dinheiro"))
        if delivered == "Sim" and not money_type:
            return error_response("Escolha se a entrega foi paga em dinheiro limpo ou sujo.", 400)

        try:
            items = parse_encomenda_items(data)
            requester = clean_text_field(data, "quem_pediu", "Quem pediu")
            deadline = clean_text_field(data, "para_quando", "Para quando")
            negotiator = clean_text_field(data, "quem_negociou", "Quem negociou")
            observation = clean_text_field(
                data,
                "observacao",
                "Observação",
                max_length=MAX_OBSERVATION_LENGTH,
                required=False,
            )
        except ValueError as validation_error:
            return error_response(str(validation_error), 400)

        now = format_timestamp()
        record_id = generate_record_id("KKSE")
        item = {
            "id": record_id,
            "data": now,
            "quem_pediu": requester,
            "o_que_pediu": items["o_que_pediu"],
            "valor": items["valor"],
            "para_quando": deadline,
            "quem_negociou": negotiator,
            "entregue": delivered,
            "observacao": observation,
            "entregue_em": now if delivered == "Sim" else "",
            "quantidade_l85": items["quantidade_l85"],
            "valor_unitario_l85": items["valor_unitario_l85"],
            "quantidade_seringa": items["quantidade_seringa"],
            "valor_unitario_seringa": items["valor_unitario_seringa"],
        }

        if delivered == "Sim":
            sales_worksheet = get_vendas_worksheet()
            sale_row = build_venda_row_from_encomenda(item, entregue_em=now, tipo_dinheiro=money_type)
            sales_worksheet.append_row(sale_row, value_input_option="RAW")
            invalidate_values_cache(VENDAS_WORKSHEET_NAME)
            log_info(f"Encomenda já entregue registrada diretamente em Vendas. ID={record_id}")
            return jsonify({
                "ok": True,
                "message": "Encomenda entregue e registrada diretamente em Vendas.",
                "id": record_id,
                "venda_id": sale_row[0],
                "valor": sale_row[7],
                "valor_base": sale_row[10],
                "tipo_dinheiro": sale_row[9],
                "moved_to_vendas": True,
            }), 201

        worksheet = get_encomendas_worksheet()
        worksheet.append_row([
            record_id,
            now,
            requester,
            items["o_que_pediu"],
            items["valor"],
            deadline,
            negotiator,
            "Não",
            observation,
            "",
            items["quantidade_l85"],
            items["valor_unitario_l85"],
            items["quantidade_seringa"],
            items["valor_unitario_seringa"],
        ], value_input_option="RAW")
        invalidate_values_cache(ENCOMENDAS_WORKSHEET_NAME)
        log_info(f"Encomenda registrada com sucesso. ID={record_id}")

        return jsonify({
            "ok": True,
            "message": "Encomenda salva com sucesso.",
            "id": record_id,
            "valor": items["valor"],
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

        required_fields = ["quem_pediu", "para_quando", "quem_negociou"]
        missing = [field for field in required_fields if str(data.get(field, "")).strip() == ""]
        if missing:
            return error_response(f"Campos obrigatórios ausentes: {', '.join(missing)}", 400)

        confirm_delivery = bool(data.get("confirmar_entrega"))
        money_type = normalize_money_type(data.get("tipo_dinheiro"))
        if confirm_delivery and not money_type:
            return error_response("Escolha dinheiro limpo ou sujo para confirmar a entrega.", 400)

        try:
            items = parse_encomenda_items(data)
            requester = clean_text_field(data, "quem_pediu", "Quem pediu")
            deadline = clean_text_field(data, "para_quando", "Para quando")
            negotiator = clean_text_field(data, "quem_negociou", "Quem negociou")
            observation = clean_text_field(
                data,
                "observacao",
                "Observação",
                max_length=MAX_OBSERVATION_LENGTH,
                required=False,
            )
        except ValueError as validation_error:
            return error_response(str(validation_error), 400)

        with _sheets_lock:
            worksheet = get_encomendas_worksheet()
            row_index, row = find_row_by_id(worksheet, registro_id)
            if not row_index:
                return error_response("Encomenda não encontrada.", 404)

            while len(row) < len(ENCOMENDAS_HEADERS):
                row.append("")
            if validate_yes_no(row[7]) == "Sim":
                return error_response("Essa encomenda já foi entregue e não pode mais ser editada aqui.", 409)

            row[2] = requester
            row[3] = items["o_que_pediu"]
            row[4] = items["valor"]
            row[5] = deadline
            row[6] = negotiator
            row[7] = "Não"
            row[8] = observation
            row[9] = ""
            row[10] = items["quantidade_l85"]
            row[11] = items["valor_unitario_l85"]
            row[12] = items["quantidade_seringa"]
            row[13] = items["valor_unitario_seringa"]

            if confirm_delivery:
                delivery_result = move_encomenda_row_to_vendas(
                    worksheet,
                    row_index,
                    row,
                    money_type,
                )
                return jsonify({
                    "ok": True,
                    "message": "Alterações salvas e entrega confirmada. A encomenda foi movida para Vendas.",
                    "id": registro_id,
                    "moved_to_vendas": True,
                    **delivery_result,
                })

            end_col = "N"
            worksheet.update(
                f"A{row_index}:{end_col}{row_index}",
                [row[:len(ENCOMENDAS_HEADERS)]],
                value_input_option="RAW",
            )
            invalidate_values_cache(ENCOMENDAS_WORKSHEET_NAME)

        return jsonify({
            "ok": True,
            "message": "Encomenda atualizada com sucesso.",
            "item": normalize_encomenda(row),
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

        delivered = validate_yes_no(data.get("entregue"))
        if not delivered:
            return error_response("A entrega deve ser somente 'Sim' ou 'Não'.", 400)

        money_type = normalize_money_type(data.get("tipo_dinheiro"))
        if delivered == "Sim" and not money_type:
            return error_response("Escolha se a entrega foi paga em dinheiro limpo ou sujo.", 400)

        with _sheets_lock:
            worksheet = get_encomendas_worksheet()
            row_index, row = find_row_by_id(worksheet, registro_id)
            if not row_index:
                return error_response("Encomenda não encontrada.", 404)

            while len(row) < len(ENCOMENDAS_HEADERS):
                row.append("")

            if delivered == "Não":
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

            delivery_result = move_encomenda_row_to_vendas(
                worksheet,
                row_index,
                row,
                money_type,
            )

        return jsonify({
            "ok": True,
            "message": "Entrega confirmada. A encomenda foi movida para Vendas.",
            "id": registro_id,
            "entregue": "Sim",
            "moved_to_vendas": True,
            **delivery_result,
        })

    except Exception as e:
        log_error("Falha em /api/encomendas/<id>/entrega [POST]", e)
        return error_response(str(e))


@app.get("/api/resumo-encomendas")
@require_login
def resumo_encomendas():
    try:
        worksheet = get_encomendas_worksheet()
        rows = cached_get_all_values(ENCOMENDAS_WORKSHEET_NAME, worksheet)
        return jsonify(encomendas_summary(rows))

    except Exception as e:
        log_error("Falha em /api/resumo-encomendas", e)
        return error_response(str(e))



@app.get("/api/reunioes")
@require_login
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
            organizacao_id = clean_text_field(data, "organizacao_id", "Organização", max_length=60, required=False).lower()
            gangue = clean_text_field(data, "gangue", "Gangue / grupo")
            icone = clean_text_field(data, "icone", "Ícone", max_length=12)
            organization = find_organization(organizacao_id, gangue)
            if organization:
                organizacao_id = organization["id"]
                gangue = organization["nome"]
                icone = organization.get("icone", icone)
            else:
                organizacao_id = ""
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
            local, pauta, "Agendada", "", organizacao_id
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
            organizacao_id = clean_text_field(data, "organizacao_id", "Organização", max_length=60, required=False).lower()
            gangue = clean_text_field(data, "gangue", "Gangue / grupo")
            icone = clean_text_field(data, "icone", "Ícone", max_length=12)
            organization = find_organization(organizacao_id, gangue)
            if organization:
                organizacao_id = organization["id"]
                gangue = organization["nome"]
                icone = organization.get("icone", icone)
            else:
                organizacao_id = ""
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
        row[11] = organizacao_id
        # Ao confirmar novos dados de uma reunião pendente, ela passa a estar agendada.
        if str(row[9]).strip().lower() in {"aguardando confirmação", "aguardando confirmacao", "a confirmar"}:
            row[9] = "Agendada"
            row[10] = ""

        worksheet.update(f"A{row_index}:L{row_index}", [row[:len(REUNIOES_HEADERS)]], value_input_option="RAW")
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
        row[9] = "Finalizada"
        row[10] = format_timestamp()
        worksheet.update(f"A{row_index}:L{row_index}", [row[:len(REUNIOES_HEADERS)]], value_input_option="RAW")
        invalidate_values_cache(REUNIOES_WORKSHEET_NAME)
        return jsonify({"ok": True, "message": "Reunião marcada como finalizada."})
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
        worksheet.update(f"A{row_index}:L{row_index}", [row[:len(REUNIOES_HEADERS)]], value_input_option="RAW")
        invalidate_values_cache(REUNIOES_WORKSHEET_NAME)
        return jsonify({"ok": True, "message": "Reunião marcada como cancelada."})
    except Exception as e:
        log_error("Falha em /api/reunioes/<id>/cancelar [POST]", e)
        return error_response(str(e))


@app.get("/api/metas")
@require_login
def list_metas():
    try:
        worksheet = get_metas_worksheet()
        rows = cached_get_all_values(METAS_WORKSHEET_NAME, worksheet)
        return jsonify([normalize_meta(row) for row in active_meta_rows(rows)])

    except Exception as e:
        log_error("Falha em /api/metas [GET]", e)
        return error_response(str(e))


@app.get("/api/resumo-metas")
@require_login
def resumo_metas():
    try:
        worksheet = get_metas_worksheet()
        rows = cached_get_all_values(METAS_WORKSHEET_NAME, worksheet)
        registros = active_meta_rows(rows)
        total = len(registros)
        pagos = 0
        confirmados = 0

        for row in registros:
            status = row[2].strip().lower() if len(row) > 2 else ""
            if status == "sim":
                pagos += 1
            if len(row) > 6 and str(row[6]).strip().lower() in ["sim", "s"]:
                confirmados += 1

        if registros:
            semana_inicio = registros[0][4] if len(registros[0]) > 4 else meta_week_payload()["semana_inicio"]
            semana_fim = registros[0][5] if len(registros[0]) > 5 else meta_week_payload()["semana_fim"]
        else:
            week = meta_week_payload()
            semana_inicio = week["semana_inicio"]
            semana_fim = week["semana_fim"]

        return jsonify({
            "total": total,
            "pagos": pagos,
            "pendentes": max(total - pagos, 0),
            "confirmados": confirmados,
            "faltam_confirmar": max(total - confirmados, 0),
            "semana_inicio": semana_inicio,
            "semana_fim": semana_fim,
            "semana_label": f"{semana_inicio} até {semana_fim}",
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
