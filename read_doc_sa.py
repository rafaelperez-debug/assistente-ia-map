import os
import json
from googleapiclient.discovery import build
from google.oauth2 import service_account

# Escopo necessário para acessar Documentos do Google
SCOPES = ["https://www.googleapis.com/auth/documents.readonly"]

def authenticate_docs():
    """
    Autentica no Google Docs usando a variável de ambiente GOOGLE_SERVICE_ACCOUNT_JSON.
    """
    service_account_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES
    )
    service = build("docs", "v1", credentials=creds)
    return service

def read_doc(document_id):
    """
    Lê o conteúdo de um documento Google Docs pelo ID.
    """
    service = authenticate_docs()
    doc = service.documents().get(documentId=document_id).execute()

    print(f"Título do Documento: {doc.get('title')}\n")

    content = doc.get("body", {}).get("content", [])
    for element in content:
        if "paragraph" in element:
            for text_run in element["paragraph"].get("elements", []):
                if "textRun" in text_run:
                    print(text_run["textRun"].get("content", ""), end="")

if __name__ == "__main__":
    # Exemplo de uso: substituir pelo ID do seu documento
    doc_id = "COLOQUE_O_ID_DO_DOCUMENTO_AQUI"
    read_doc(doc_id)
