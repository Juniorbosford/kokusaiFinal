import os
import json
import traceback
import base64
import hashlib
import hmac
import time
import threading
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
app.secret_key = os.getenv("SECRET_KEY", "kokusai-dev-secret-change-this")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=12)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"


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

META_HEADERS = ["id", "nome", "pago", "atualizado_em", "semana_inicio", "semana_fim", "confirmado"]
META_HISTORY_HEADERS = ["semana_inicio", "semana_fim", "fechado_em", "id", "nome", "pago", "atualizado_em"]


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
    }


def log_info(message):
    print(f"[KOKUSAI][INFO] {message}", flush=True)


def log_error(context, error):
    print(f"[KOKUSAI][ERROR] {context}: {repr(error)}", flush=True)
    traceback.print_exc()


def error_response(message, status=500, details=None):
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

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
    log_info(f"GOOGLE_CREDENTIALS_JSON presente? {bool(credentials_json)}")
    log_info(f"SPREADSHEET_ID configurado? {bool(SPREADSHEET_ID)}")
    log_info(f"COMPRAS_WORKSHEET_NAME={COMPRAS_WORKSHEET_NAME}")
    log_info(f"VENDAS_WORKSHEET_NAME={VENDAS_WORKSHEET_NAME}")
    log_info(f"ENCOMENDAS_WORKSHEET_NAME={ENCOMENDAS_WORKSHEET_NAME}")
    log_info(f"METAS_WORKSHEET_NAME={METAS_WORKSHEET_NAME}")

    try:
        if credentials_json:
            creds_dict = json.loads(credentials_json)
            client_email = creds_dict.get("client_email", "")
            log_info(f"Service account em uso: {client_email or 'NÃO ENCONTRADO NO JSON'}")
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
    return get_or_create_worksheet(
        COMPRAS_WORKSHEET_NAME,
        ["id", "data", "produto", "quem_pediu", "quem_vendeu", "valor_unitario", "quantidade", "valor_total", "observacao"]
    )


def get_vendas_worksheet():
    return get_or_create_worksheet(
        VENDAS_WORKSHEET_NAME,
        ["id", "data", "produto", "quem_compra", "quem_vende", "valor_unitario", "quantidade", "valor_total", "observacao"]
    )


def get_encomendas_worksheet():
    return get_or_create_worksheet(
        ENCOMENDAS_WORKSHEET_NAME,
        ["id", "data", "quem_pediu", "o_que_pediu", "valor", "para_quando", "quem_negociou", "entregue", "observacao"]
    )


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
            worksheet.append_rows(seed_rows, value_input_option="USER_ENTERED")
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
        worksheet.update(f"A2:G{len(updated_rows) + 1}", updated_rows, value_input_option="USER_ENTERED")
        invalidate_values_cache(worksheet.title)
        log_info("Aba de metas atualizada para o formato semanal.")


def ensure_current_meta_week(worksheet):
    rows = cached_get_all_values(worksheet.title, worksheet, force=True)
    registros = [row for row in rows[1:] if len(row) > 1 and str(row[1]).strip()]
    if not registros:
        return

    stored_start = parse_date_br(registros[0][4] if len(registros[0]) > 4 else "")
    current_start = meta_week_start()

    if stored_start and stored_start < current_start:
        log_info("Virada semanal detectada. Salvando histórico e resetando metas.")
        archive_and_reset_metas(worksheet, target_start_date=current_start)


def archive_and_reset_metas(worksheet, target_start_date=None):
    rows = cached_get_all_values(worksheet.title, worksheet, force=True)
    registros = [row for row in rows[1:] if len(row) > 1 and str(row[1]).strip()]
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
        historico.append_rows(history_rows, value_input_option="USER_ENTERED")
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

    worksheet.update(f"A2:G{len(reset_rows) + 1}", reset_rows, value_input_option="USER_ENTERED")
    invalidate_values_cache(worksheet.title)
    return week


def maybe_close_week_if_all_confirmed(worksheet, rows=None):
    rows = rows if rows is not None else cached_get_all_values(worksheet.title, worksheet, force=True)
    registros = [row for row in rows[1:] if len(row) > 1 and str(row[1]).strip()]
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
    if valor_unitario < 0:
        return False, "Valor unitário não pode ser negativo."

    return True, ""


def normalize_compra(row):
    return {
        "id": row[0] if len(row) > 0 else "",
        "data": row[1] if len(row) > 1 else "",
        "produto": row[2] if len(row) > 2 else "",
        "quem_pediu": row[3] if len(row) > 3 else "",
        "quem_vendeu": row[4] if len(row) > 4 else "",
        "valor_unitario": row[5] if len(row) > 5 else "",
        "quantidade": row[6] if len(row) > 6 else "",
        "valor_total": row[7] if len(row) > 7 else "",
        "observacao": row[8] if len(row) > 8 else "",
    }


def normalize_venda(row):
    return {
        "id": row[0] if len(row) > 0 else "",
        "data": row[1] if len(row) > 1 else "",
        "produto": row[2] if len(row) > 2 else "",
        "quem_compra": row[3] if len(row) > 3 else "",
        "quem_vende": row[4] if len(row) > 4 else "",
        "valor_unitario": row[5] if len(row) > 5 else "",
        "quantidade": row[6] if len(row) > 6 else "",
        "valor_total": row[7] if len(row) > 7 else "",
        "observacao": row[8] if len(row) > 8 else "",
    }


def normalize_encomenda(row):
    return {
        "id": row[0] if len(row) > 0 else "",
        "data": row[1] if len(row) > 1 else "",
        "quem_pediu": row[2] if len(row) > 2 else "",
        "o_que_pediu": row[3] if len(row) > 3 else "",
        "valor": row[4] if len(row) > 4 else "",
        "para_quando": row[5] if len(row) > 5 else "",
        "quem_negociou": row[6] if len(row) > 6 else "",
        "entregue": row[7] if len(row) > 7 else "",
        "observacao": row[8] if len(row) > 8 else "",
    }


def normalize_meta(row):
    confirmado = str(row[6] if len(row) > 6 else "Não").strip().lower() in ["sim", "s"]
    return {
        "id": row[0] if len(row) > 0 else "",
        "nome": row[1] if len(row) > 1 else "",
        "pago": validate_yes_no(row[2] if len(row) > 2 else "Não") or "Não",
        "atualizado_em": row[3] if len(row) > 3 else "",
        "semana_inicio": row[4] if len(row) > 4 else "",
        "semana_fim": row[5] if len(row) > 5 else "",
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
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        user = AUTH_USERS.get(username)

        if user and verify_password(password, user["password_hash"]):
            session.clear()
            session.permanent = True
            session["username"] = username
            return redirect(safe_next_url(request.form.get("next") or next_url))

        error = "Usuário ou senha inválidos."

    return render_template("login.html", error=error, next_url=next_url)


@app.route("/logout", methods=["GET", "POST"])
def logout():
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
        "service": "kokusai-system-final",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "spreadsheet_id_configured": bool(SPREADSHEET_ID),
        "compras_worksheet": COMPRAS_WORKSHEET_NAME,
        "vendas_worksheet": VENDAS_WORKSHEET_NAME,
        "encomendas_worksheet": ENCOMENDAS_WORKSHEET_NAME,
        "metas_worksheet": METAS_WORKSHEET_NAME,
        "historico_metas_worksheet": HISTORICO_METAS_WORKSHEET_NAME,
    })


@app.get("/api/debug-config")
@require_admin
def debug_config():
    credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
    client_email = None
    if credentials_json:
        try:
            client_email = json.loads(credentials_json).get("client_email")
        except Exception:
            client_email = "JSON inválido"

    return jsonify({
        "ok": True,
        "spreadsheet_id": SPREADSHEET_ID,
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
        if len(rows) <= 1:
            return jsonify([])

        data_rows = rows[1:][-100:]
        data_rows.reverse()
        return jsonify([normalize_compra(row) for row in data_rows])

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

        quantidade = int(data["quantidade"])
        valor_unitario = float(data["valor_unitario"])
        valor_total = round(quantidade * valor_unitario, 2)
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        registro_id = f"KKSC-{int(datetime.utcnow().timestamp())}"

        worksheet = get_compras_worksheet()
        worksheet.append_row([
            registro_id,
            agora,
            data["produto"].strip(),
            data["quem_pediu"].strip(),
            data["quem_vendeu"].strip(),
            valor_unitario,
            quantidade,
            valor_total,
            data.get("observacao", "").strip(),
        ])
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
        if len(rows) <= 1:
            return jsonify([])

        data_rows = rows[1:][-100:]
        data_rows.reverse()
        return jsonify([normalize_venda(row) for row in data_rows])

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

        quantidade = int(data["quantidade"])
        valor_unitario = float(data["valor_unitario"])
        valor_total = round(quantidade * valor_unitario, 2)
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        registro_id = f"KKSV-{int(datetime.utcnow().timestamp())}"

        worksheet = get_vendas_worksheet()
        worksheet.append_row([
            registro_id,
            agora,
            data["produto"].strip(),
            data["quem_compra"].strip(),
            data["quem_vende"].strip(),
            valor_unitario,
            quantidade,
            valor_total,
            data.get("observacao", "").strip(),
        ])
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
        if len(rows) <= 1:
            return jsonify({"total_registros": 0, "valor_movimentado": 0, "ultimo_registro": "--"})

        registros = rows[1:]
        total = 0.0

        for row in registros:
            if len(row) > 7 and row[7]:
                try:
                    total += float(row[7])
                except ValueError:
                    pass

        ultimo = registros[-1][1] if registros else "--"

        return jsonify({
            "total_registros": len(registros),
            "valor_movimentado": round(total, 2),
            "ultimo_registro": ultimo
        })

    except Exception as e:
        log_error("Falha em /api/resumo", e)
        return error_response(str(e))


@app.get("/api/resumo-vendas")
@require_login
def resumo_vendas():
    try:
        worksheet = get_vendas_worksheet()
        rows = cached_get_all_values(VENDAS_WORKSHEET_NAME, worksheet)
        if len(rows) <= 1:
            return jsonify({"total_registros": 0, "valor_movimentado": 0, "ultimo_registro": "--"})

        registros = rows[1:]
        total = 0.0

        for row in registros:
            if len(row) > 7 and row[7]:
                try:
                    total += float(row[7])
                except ValueError:
                    pass

        ultimo = registros[-1][1] if registros else "--"

        return jsonify({
            "total_registros": len(registros),
            "valor_movimentado": round(total, 2),
            "ultimo_registro": ultimo
        })

    except Exception as e:
        log_error("Falha em /api/resumo-vendas", e)
        return error_response(str(e))


@app.get("/api/encomendas")
@require_login
def list_encomendas():
    try:
        worksheet = get_encomendas_worksheet()
        rows = cached_get_all_values(ENCOMENDAS_WORKSHEET_NAME, worksheet)
        if len(rows) <= 1:
            return jsonify([])

        data_rows = rows[1:][-100:]
        data_rows.reverse()
        return jsonify([normalize_encomenda(row) for row in data_rows])

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

        entregue = str(data["entregue"]).strip().capitalize()
        if entregue not in ["Sim", "Não", "Nao"]:
            return error_response("O campo 'entregue' deve ser 'Sim' ou 'Não'.", 400)

        if entregue == "Nao":
            entregue = "Não"

        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        registro_id = f"KKSE-{int(datetime.utcnow().timestamp())}"

        worksheet = get_encomendas_worksheet()
        worksheet.append_row([
            registro_id,
            agora,
            data["quem_pediu"].strip(),
            data["o_que_pediu"].strip(),
            round(valor, 2),
            data["para_quando"].strip(),
            data["quem_negociou"].strip(),
            entregue,
            data.get("observacao", "").strip(),
        ])
        invalidate_values_cache(ENCOMENDAS_WORKSHEET_NAME)
        log_info(f"Encomenda registrada com sucesso. ID={registro_id}")

        return jsonify({
            "ok": True,
            "message": "Encomenda salva com sucesso.",
            "id": registro_id,
            "valor": round(valor, 2),
        }), 201

    except Exception as e:
        log_error("Falha em /api/encomendas [POST]", e)
        return error_response(str(e))


@app.get("/api/resumo-encomendas")
@require_login
def resumo_encomendas():
    try:
        worksheet = get_encomendas_worksheet()
        rows = cached_get_all_values(ENCOMENDAS_WORKSHEET_NAME, worksheet)
        if len(rows) <= 1:
            return jsonify({"total_registros": 0, "valor_movimentado": 0, "ultimo_registro": "--", "pendentes": 0, "entregues": 0})

        registros = rows[1:]
        total = 0.0
        pendentes = 0
        entregues = 0

        for row in registros:
            if len(row) > 4 and row[4]:
                try:
                    total += float(row[4])
                except ValueError:
                    pass
            status = row[7].strip().lower() if len(row) > 7 else ""
            if status == "sim":
                entregues += 1
            else:
                pendentes += 1

        ultimo = registros[-1][1] if registros else "--"

        return jsonify({
            "total_registros": len(registros),
            "valor_movimentado": round(total, 2),
            "ultimo_registro": ultimo,
            "pendentes": pendentes,
            "entregues": entregues,
        })

    except Exception as e:
        log_error("Falha em /api/resumo-encomendas", e)
        return error_response(str(e))


@app.get("/api/metas")
@require_login
def list_metas():
    try:
        worksheet = get_metas_worksheet()
        rows = cached_get_all_values(METAS_WORKSHEET_NAME, worksheet)
        if len(rows) <= 1:
            return jsonify([])

        data_rows = [row for row in rows[1:] if len(row) > 1 and str(row[1]).strip()]
        return jsonify([normalize_meta(row) for row in data_rows])

    except Exception as e:
        log_error("Falha em /api/metas [GET]", e)
        return error_response(str(e))


@app.get("/api/resumo-metas")
@require_login
def resumo_metas():
    try:
        worksheet = get_metas_worksheet()
        rows = cached_get_all_values(METAS_WORKSHEET_NAME, worksheet)
        registros = [row for row in rows[1:] if len(row) > 1 and str(row[1]).strip()]
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

        nome = str(data.get("nome", "")).strip()
        pago = validate_yes_no(data.get("pago", "Não")) or "Não"

        if not nome:
            return error_response("Informe o nome da pessoa.", 400)

        worksheet = get_metas_worksheet()
        rows = cached_get_all_values(worksheet.title, worksheet, force=True)
        nomes_existentes = {row[1].strip().lower() for row in rows[1:] if len(row) > 1 and row[1].strip()}
        if nome.lower() in nomes_existentes:
            return error_response("Esse nome já está na lista de metas.", 409)

        agora = format_timestamp()
        rows = cached_get_all_values(worksheet.title, worksheet, force=True)
        semana_inicio = rows[1][4] if len(rows) > 1 and len(rows[1]) > 4 and rows[1][4] else meta_week_payload()["semana_inicio"]
        semana_fim = rows[1][5] if len(rows) > 1 and len(rows[1]) > 5 and rows[1][5] else meta_week_payload()["semana_fim"]
        registro_id = f"META-{int(datetime.utcnow().timestamp())}"
        worksheet.append_row([registro_id, nome, pago, agora, semana_inicio, semana_fim, "Sim"], value_input_option="USER_ENTERED")
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
        worksheet.update(f"C{row_index}:G{row_index}", [[pago, agora, semana_inicio, semana_fim, "Sim"]], value_input_option="USER_ENTERED")
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
        registros = [row for row in rows[1:] if len(row) > 1 and str(row[1]).strip()]
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
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
