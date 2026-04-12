import os
import json
import traceback
from datetime import datetime
from flask import Flask, jsonify, render_template, request
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

SHEET_NAME = os.getenv("SHEET_NAME", "KokusaiDB")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "").strip()
COMPRAS_WORKSHEET_NAME = os.getenv("COMPRAS_WORKSHEET_NAME", "Compras")
VENDAS_WORKSHEET_NAME = os.getenv("VENDAS_WORKSHEET_NAME", "Vendas")
ENCOMENDAS_WORKSHEET_NAME = os.getenv("ENCOMENDAS_WORKSHEET_NAME", "Encomendas")


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


def get_gsheet_client():
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
        log_info("Autenticação com Google Sheets concluída com sucesso.")
        return client

    except json.JSONDecodeError as e:
        log_error("GOOGLE_CREDENTIALS_JSON inválido", e)
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON está com JSON inválido.")
    except Exception as e:
        log_error("Falha ao autenticar no Google Sheets", e)
        raise RuntimeError(f"Erro ao autenticar no Google Sheets: {str(e)}")


def get_or_create_spreadsheet():
    client = get_gsheet_client()

    if SPREADSHEET_ID:
        try:
            log_info(f"Abrindo planilha pelo ID: {SPREADSHEET_ID}")
            spreadsheet = client.open_by_key(SPREADSHEET_ID)
            log_info(f"Planilha aberta com sucesso: {spreadsheet.title}")
            return spreadsheet
        except Exception as e:
            log_error("Falha ao abrir planilha pelo SPREADSHEET_ID", e)
            raise RuntimeError(
                "Não foi possível abrir a planilha pelo SPREADSHEET_ID. "
                "Verifique se o ID está correto e se a service account tem acesso de editor."
            )

    try:
        log_info(f"Abrindo planilha pelo nome: {SHEET_NAME}")
        spreadsheet = client.open(SHEET_NAME)
        log_info(f"Planilha aberta pelo nome com sucesso: {spreadsheet.title}")
        return spreadsheet
    except gspread.SpreadsheetNotFound:
        log_info(f"Planilha '{SHEET_NAME}' não encontrada. Criando automaticamente.")
        spreadsheet = client.create(SHEET_NAME)
        log_info(f"Planilha criada com sucesso: {spreadsheet.title}")
        return spreadsheet
    except Exception as e:
        log_error("Erro ao abrir/criar planilha", e)
        raise RuntimeError(f"Erro ao abrir/criar planilha: {str(e)}")


def ensure_headers(worksheet, headers):
    current_headers = worksheet.row_values(1)
    if not current_headers:
        worksheet.append_row(headers)
        log_info(f"Cabeçalho criado na aba {worksheet.title}")
    elif current_headers != headers:
        log_info(
            f"Cabeçalho existente na aba {worksheet.title}: {current_headers}. "
            f"Esperado: {headers}"
        )


def get_or_create_worksheet(name, headers):
    spreadsheet = get_or_create_spreadsheet()

    try:
        worksheet = spreadsheet.worksheet(name)
        log_info(f"Aba encontrada: {name}")
        ensure_headers(worksheet, headers)
        return worksheet
    except gspread.WorksheetNotFound:
        log_info(f"Aba '{name}' não encontrada. Criando automaticamente.")
        worksheet = spreadsheet.add_worksheet(title=name, rows=1000, cols=20)
        worksheet.append_row(headers)
        return worksheet
    except Exception as e:
        log_error(f"Erro ao abrir/criar aba {name}", e)
        raise RuntimeError(f"Erro ao abrir/criar aba '{name}': {str(e)}")


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


@app.get("/")
def home():
    return render_template("index.html")


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
    })


@app.get("/api/debug-config")
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
        "credentials_present": bool(credentials_json),
        "service_account_email": client_email,
    })


@app.get("/api/compras")
def list_compras():
    try:
        rows = get_compras_worksheet().get_all_values()
        if len(rows) <= 1:
            return jsonify([])

        data_rows = rows[1:][-100:]
        data_rows.reverse()
        return jsonify([normalize_compra(row) for row in data_rows])

    except Exception as e:
        log_error("Falha em /api/compras [GET]", e)
        return error_response(str(e))


@app.post("/api/compras")
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
def list_vendas():
    try:
        rows = get_vendas_worksheet().get_all_values()
        if len(rows) <= 1:
            return jsonify([])

        data_rows = rows[1:][-100:]
        data_rows.reverse()
        return jsonify([normalize_venda(row) for row in data_rows])

    except Exception as e:
        log_error("Falha em /api/vendas [GET]", e)
        return error_response(str(e))


@app.post("/api/vendas")
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
def resumo_compras():
    try:
        rows = get_compras_worksheet().get_all_values()
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
def resumo_vendas():
    try:
        rows = get_vendas_worksheet().get_all_values()
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
def list_encomendas():
    try:
        rows = get_encomendas_worksheet().get_all_values()
        if len(rows) <= 1:
            return jsonify([])

        data_rows = rows[1:][-100:]
        data_rows.reverse()
        return jsonify([normalize_encomenda(row) for row in data_rows])

    except Exception as e:
        log_error("Falha em /api/encomendas [GET]", e)
        return error_response(str(e))


@app.post("/api/encomendas")
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
def resumo_encomendas():
    try:
        rows = get_encomendas_worksheet().get_all_values()
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


if __name__ == "__main__":
    log_info("Iniciando aplicação Kokusai...")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
