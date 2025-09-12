import os
import json
from googleapiclient.discovery import build
from google.oauth2 import service_account

# Escopos necessários para acesso ao Google Drive
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/presentations"
]

def authenticate_drive():
    """
    Autentica no Google Drive usando credenciais carregadas da variável
    de ambiente GOOGLE_SERVICE_ACCOUNT_JSON.
    """
    service_account_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES
    )
    service = build("drive", "v3", credentials=creds)
    return service

def list_files(query=""):
    """
    Lista arquivos no Google Drive com base em um query opcional.
    Exemplo: query = "name contains 'MAP'"
    """
    service = authenticate_drive()
    results = service.files().list(
        q=query,
        pageSize=10,
        fields="files(id, name, mimeType, modifiedTime)"
    ).execute()

    items = results.get("files", [])
    if not items:
        print("Nenhum arquivo encontrado.")
    else:
        for item in items:
            print(f"{item['name']} ({item['id']}) - {item['mimeType']} - {item['modifiedTime']}")

if __name__ == "__main__":
    # Exemplo de uso: lista todos os arquivos
    list_files()
