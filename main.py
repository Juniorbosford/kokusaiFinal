import os
import json
from datetime import datetime
from flask import Flask, jsonify, render_template, request
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

SHEET_NAME = os.getenv("SHEET_NAME", "KokusaiDB")
COMPRAS_WORKSHEET_NAME = os.getenv("WORKSHEET_NAME", "Compras")
VENDAS_WORKSHEET_NAME = os.getenv("VENDAS_WORKSHEET_NAME", "Vendas")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")


def get_gsheet_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    if GOOGLE_CREDENTIALS_JSON:
        creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    else:
        creds = Credentials.from_service_account_file("service_account.json", scopes=scopes)

    return gspread.authorize(creds)


def get_or_create_spreadsheet():
    client = get_gsheet_client()
    try:
        spreadsheet = client.open(SHEET_NAME)
    except gspread.SpreadsheetNotFound:
        spreadsheet = client.create(SHEET_NAME)
    return spreadsheet


def get_or_create_worksheet(name, headers):
    spreadsheet = get_or_create_spreadsheet()
    try:
        worksheet = spreadsheet.worksheet(name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=name, rows=1000, cols=20)
        worksheet.append_row(headers)
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


def validate_numeric_fields(data, required_fields):
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


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "kokusai-system-final", "timestamp": datetime.utcnow().isoformat() + "Z"})


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
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/compras")
def create_compra():
    try:
        data = request.get_json(force=True)
        ok, message = validate_numeric_fields(data, ["produto", "quem_pediu", "quem_vendeu", "valor_unitario", "quantidade"])
        if not ok:
            return jsonify({"ok": False, "error": message}), 400

        quantidade = int(data["quantidade"])
        valor_unitario = float(data["valor_unitario"])
        valor_total = round(quantidade * valor_unitario, 2)
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        registro_id = f"KKSC-{int(datetime.utcnow().timestamp())}"

        get_compras_worksheet().append_row([
            registro_id, agora, data["produto"].strip(), data["quem_pediu"].strip(), data["quem_vendeu"].strip(),
            valor_unitario, quantidade, valor_total, str(data.get("observacao", "")).strip()
        ])

        return jsonify({"ok": True, "message": "Compra registrada com sucesso."}), 201
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


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
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/vendas")
def create_venda():
    try:
        data = request.get_json(force=True)
        ok, message = validate_numeric_fields(data, ["produto", "quem_compra", "quem_vende", "valor_unitario", "quantidade"])
        if not ok:
            return jsonify({"ok": False, "error": message}), 400

        quantidade = int(data["quantidade"])
        valor_unitario = float(data["valor_unitario"])
        valor_total = round(quantidade * valor_unitario, 2)
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        registro_id = f"KKSV-{int(datetime.utcnow().timestamp())}"

        get_vendas_worksheet().append_row([
            registro_id, agora, data["produto"].strip(), data["quem_compra"].strip(), data["quem_vende"].strip(),
            valor_unitario, quantidade, valor_total, str(data.get("observacao", "")).strip()
        ])

        return jsonify({"ok": True, "message": "Venda registrada com sucesso."}), 201
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


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
        return jsonify({"total_registros": len(registros), "valor_movimentado": round(total, 2), "ultimo_registro": ultimo})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


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
        return jsonify({"total_registros": len(registros), "valor_movimentado": round(total, 2), "ultimo_registro": ultimo})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
