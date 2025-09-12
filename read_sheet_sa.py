import os
import json
from googleapiclient.discovery import build
from google.oauth2 import service_account

# Escopo necessário para acessar Planilhas do Google
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

def authenticate_sheets():
    """
    Autentica no Google Sheets usando a variável de ambiente GOOGLE_SERVICE_ACCOUNT_JSON.
    """
    service_account_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES
    )
    service = build("sheets", "v4", credentials=creds)
    return service

def read_sheet(spreadsheet_id, range_name):
    """
    Lê os valores de uma planilha Google Sheets.
    :param spreadsheet_id: ID da planilha
    :param range_name: Ex: "Página1!A1:D10"
    """
    service = authenticate_sheets()
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
    values = result.get("values", [])

    if not values:
        print("Nenhum dado encontrado.")
    else:
        for row in values:
            print("\t".join(row))

if __name__ == "__main__":
    # Exemplo de uso: substituir pelo ID da planilha e intervalo
    sheet_id = "COLOQUE_O_ID_DA_PLANILHA_AQUI"
    range_name = "Página1!A1:D10"
    read_sheet(sheet_id, range_name)
