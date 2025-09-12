from __future__ import annotations
import io, os, argparse
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
CREDS_PATH = "credentials.json"

def export_doc(file_id: str) -> None:
    creds = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
    service = build("drive", "v3", credentials=creds)
    request = service.files().export_media(fileId=file_id, mimeType="text/plain")
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    text = buf.getvalue().decode("utf-8", errors="ignore")

    os.makedirs("data/raw", exist_ok=True)
    out_path = os.path.join("data", "raw", f"{file_id}.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"Salvo: {out_path}\n--- Preview ---\n{(text[:800] if text else '[vazio]')}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="ID do arquivo Google Docs")
    args = ap.parse_args()
    export_doc(args.id)
