from __future__ import annotations
import io, os, argparse, mimetypes, re, json
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.service_account import Credentials

# Escopos necessários
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

EXPORT_MAP = {
    "application/vnd.google-apps.document": ("text/plain", "txt"),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xlsx"
    ),
    "application/vnd.google-apps.presentation": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "pptx"
    ),
    "application/vnd.google-apps.drawing": ("image/png", "png"),
    "application/vnd.google-apps.jam": ("application/pdf", "pdf"),
}

def sanitize_filename(name: str, max_len: int = 120) -> str:
    # remove caracteres inválidos: <>:"/\|?* e controles
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]+', " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = name.rstrip(". ")
    reserved = {
        "CON","PRN","AUX","NUL","COM1","COM2","COM3","COM4",
        "COM5","COM6","COM7","COM8","COM9","LPT1","LPT2",
        "LPT3","LPT4","LPT5","LPT6","LPT7","LPT8","LPT9"
    }
    if name.upper() in reserved:
        name = f"_{name}"
    return name[:max_len] if len(name) > max_len else name

def main(file_id: str):
    # 🔑 Agora usando variável de ambiente em vez do credentials.json
    service_account_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
    service = build("drive", "v3", credentials=creds)

    # Pega metadados do arquivo
    meta = service.files().get(fileId=file_id, fields="id,name,mimeType").execute()
    raw_name, mtype = meta["name"], meta["mimeType"]
    base_name = sanitize_filename(raw_name)

    os.makedirs("data/downloads", exist_ok=True)

    if mtype.startswith("application/vnd.google-apps."):
        export_mime, ext = EXPORT_MAP.get(mtype, ("application/pdf", "pdf"))
        request = service.files().export_media(fileId=file_id, mimeType=export_mime)
        filename = f"{base_name}.{ext}"
    else:
        request = service.files().get_media(fileId=file_id)
        ext = mimetypes.guess_extension(mtype) or ""
        ext = ext[1:] if ext.startswith(".") else ext
        filename = f"{base_name}.{ext}" if ext else base_name

    out_path = os.path.join("data", "downloads", filename)
    print(f"Salvando como: {filename}")  # debug

    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    with open(out_path, "wb") as f:
        f.write(buf.getvalue())

    print(f"Arquivo salvo em: {out_path}  |  mimeType: {mtype}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="ID do arquivo no Drive")
    args = ap.parse_args()
    main(args.id)
