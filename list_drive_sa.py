from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
CREDS_PATH = "credentials.json"

creds = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
service = build("drive", "v3", credentials=creds)
resp = service.files().list(pageSize=10, fields="files(id,name,mimeType)").execute()
for f in resp.get("files", []):
    print(f'{f["name"]} | {f["mimeType"]} | {f["id"]}')
