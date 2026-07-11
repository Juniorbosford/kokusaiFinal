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
from copy import deepcopy
from datetime import datetime, timedelta, date, timezone
from functools import wraps
from flask import Flask, jsonify, render_template, request, redirect, session, url_for, g
import gspread
from google.oauth2.service_account import Credentials

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
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", str(64 * 1024)))


SHEET_NAME = os.getenv("SHEET_NAME", "KokusaiDB")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "").strip()
COMPRAS_WORKSHEET_NAME = os.getenv("COMPRAS_WORKSHEET_NAME", "Compras")
VENDAS_WORKSHEET_NAME = os.getenv("VENDAS_WORKSHEET_NAME", "Vendas")
ENCOMENDAS_WORKSHEET_NAME = os.getenv("ENCOMENDAS_WORKSHEET_NAME", "Encomendas")
METAS_WORKSHEET_NAME = os.getenv("METAS_WORKSHEET_NAME", "Pagamento de Metas")
HISTORICO_METAS_WORKSHEET_NAME = os.getenv("HISTORICO_METAS_WORKSHEET_NAME", "Historico Metas")
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
]
META_HEADERS = ["id", "nome", "pago", "atualizado_em", "semana_inicio", "semana_fim", "confirmado"]
META_HISTORY_HEADERS = ["semana_inicio", "semana_fim", "fechado_em", "id", "nome", "pago", "atualizado_em"]
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


def worksheet_has_record_id(worksheet, registro_id):
    rows = cached_get_all_values(worksheet.title, worksheet, force=True)
    return any(sheet_cell(row, 0) == registro_id for row in rows[1:])


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
        required_fields = ["quem_pediu", "o_que_pediu", "valor", "para_quando", "quem_negociou", "entregue"]

        if not isinstance(data, dict):
            return error_response("JSON inválido.", 400)

        missing = [field for field in required_fields if str(data.get(field, "")).strip() == ""]
        if missing:
            return error_response(f"Campos obrigatórios ausentes: {', '.join(missing)}", 400)

        try:
            valor = float(data["valor"])
        except (ValueError, TypeError):
            return error_response("O valor da encomenda deve ser numérico.", 400)

        if valor < 0:
            return error_response("O valor da encomenda não pode ser negativo.", 400)
        if valor > MAX_MONEY_VALUE:
            return error_response("Valor da encomenda muito alto.", 400)

        entregue = str(data["entregue"]).strip().capitalize()
        if entregue not in ["Sim", "Não", "Nao"]:
            return error_response("O campo 'entregue' deve ser 'Sim' ou 'Não'.", 400)

        if entregue == "Nao":
            entregue = "Não"

        try:
            quem_pediu = clean_text_field(data, "quem_pediu", "Quem pediu")
            o_que_pediu = clean_text_field(data, "o_que_pediu", "O que pediu")
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
        }

        if entregue == "Sim":
            vendas_worksheet = get_vendas_worksheet()
            venda_row = build_venda_row_from_encomenda(encomenda_item, entregue_em=agora)
            vendas_worksheet.append_row(venda_row, value_input_option="RAW")
            invalidate_values_cache(VENDAS_WORKSHEET_NAME)
            log_info(f"Encomenda já entregue registrada diretamente em Vendas. ID={registro_id}")

            return jsonify({
                "ok": True,
                "message": "Encomenda entregue e registrada diretamente em Vendas.",
                "id": registro_id,
                "venda_id": venda_row[0],
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
            encomenda_item = normalize_encomenda(row)
            encomenda_item["entregue"] = "Sim"
            encomenda_item["entregue_em"] = entregue_em

            vendas_worksheet = get_vendas_worksheet()
            venda_row = build_venda_row_from_encomenda(encomenda_item, entregue_em=entregue_em)
            venda_id = venda_row[0]

            # Se a gravação da venda tiver ocorrido e a exclusão da encomenda falhar,
            # uma nova tentativa apenas conclui a exclusão, sem duplicar a venda.
            if not worksheet_has_record_id(vendas_worksheet, venda_id):
                vendas_worksheet.append_row(venda_row, value_input_option="RAW")

            worksheet.delete_rows(row_index)
            invalidate_values_cache(ENCOMENDAS_WORKSHEET_NAME, VENDAS_WORKSHEET_NAME)
            log_info(f"Encomenda movida para Vendas. Encomenda={registro_id} Venda={venda_id}")

        return jsonify({
            "ok": True,
            "message": "Entrega confirmada. A encomenda foi movida para Vendas.",
            "id": registro_id,
            "venda_id": venda_id,
            "entregue": "Sim",
            "entregue_em": entregue_em,
            "moved_to_vendas": True,
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
