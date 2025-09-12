from __future__ import annotations
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
CREDS_PATH = "credentials.json"
TOKEN_PATH = "token.json"

def get_creds() -> Credentials:
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return creds

if __name__ == "__main__":
    service = build("drive", "v3", credentials=get_creds())
    resp = service.files().list(pageSize=10, fields="files(id, name, mimeType)").execute()
    for f in resp.get("files", []):
        print(f'{f["name"]}  |  {f["mimeType"]}  |  {f["id"]}')
