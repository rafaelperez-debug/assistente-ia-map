# smart_search_sa.py
# Busca inteligente no Google Drive usando Service Account + regras por arquivo.
# Estratégia: nome oficial (client+tokens+mime) → parcial → pastas preferidas → sinônimos → fullText.
# Exporta o 1º resultado (opcional) como txt/csv/pdf e salva em data/raw (txt/csv) ou data/downloads (binários).

from __future__ import annotations
import os, json, re, io, argparse
from typing import List, Dict

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
CREDS_PATH = "credentials.json"


# -------------------- utils --------------------
def esc(s: str) -> str:
    """Escapa aspas simples para usar em queries do Drive."""
    return s.replace("'", "\\'")


def sanitize(name: str, max_len=120) -> str:
    """Sanitiza nomes de arquivo para Windows/macOS."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]+', " ", name)
    name = re.sub(r"\s+", " ", name).strip().rstrip(". ")
    return name[:max_len]


def load_rules(path: str) -> dict:
    """Carrega regras de nomeclatura/pastas/sinônimos por empresa."""
    if not os.path.exists(path):
        raise SystemExit(f"Arquivo de regras não encontrado: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def service_sa():
    """Constroi cliente Drive usando Service Account."""
    creds = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def drive_search(service, q: str, page_size=25, order="modifiedTime desc") -> List[dict]:
    """Wrapper do files.list com campos úteis e suporte a Shared Drives."""
    resp = service.files().list(
        q=q,
        pageSize=page_size,
        fields=(
            "files(id,name,mimeType,modifiedTime,createdTime,webViewLink,"
            "parents,owners(displayName,emailAddress))"
        ),
        orderBy=order,
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
    ).execute()
    return resp.get("files", [])


def find_folders_by_names(service, names: List[str]) -> List[str]:
    """Retorna IDs de pastas que contenham os nomes informados."""
    ids = []
    for n in names or []:
        q = (
            "mimeType = 'application/vnd.google-apps.folder' and "
            f"name contains '{esc(n)}' and trashed=false"
        )
        for f in drive_search(service, q, page_size=10):
            ids.append(f["id"])
    # remove duplicados preservando ordem
    return list(dict.fromkeys(ids))


# -------------------- core: passes de busca --------------------
def search_passes(
    service,
    client: str,
    type_key: str,
    rules: dict,
    date_hint: str | None = None,
    page_size: int = 25,
) -> List[dict]:
    """
    Passos:
      1) Nome oficial: client + todos tokens + mime + trashed=false
      2) Parcial:      client + (qualquer token) + mime
      3) Pastas:       'id in parents' + client + (qualquer token) + mime
      4) Sinônimos:    client + (sinônimos) + mime
      5) FullText:     client + (tokens | sinônimos) em fullText
    """
    nm = rules.get("naming", {}).get(type_key, {})
    tokens: List[str] = nm.get("tokens", [])
    mimes: List[str] = nm.get("mimeTypes", [])
    folders: List[str] = nm.get("folder_names", [])
    syns: List[str] = rules.get("synonyms", {}).get(type_key, [])

    # filtro de mime
    mime_q = ""
    if mimes:
        parts = [f"mimeType = '{esc(mt)}'" for mt in mimes]
        mime_q = "(" + " or ".join(parts) + ") and "

    results: List[dict] = []

    # 1) nome oficial (todos tokens)
    must = [f"name contains '{esc(client)}'"] + [f"name contains '{esc(t)}'" for t in tokens]
    if must:
        q1 = f"{mime_q}{' and '.join(must)} and trashed=false"
        results += drive_search(service, q1, page_size=page_size)

    # 2) parcial (qualquer token)
    if not results and tokens:
        anytok = " or ".join([f"name contains '{esc(t)}'" for t in tokens])
        q2 = f"{mime_q}name contains '{esc(client)}' and ({anytok}) and trashed=false"
        results += drive_search(service, q2, page_size=page_size)

    # 3) pastas preferidas
    if not results and folders:
        folder_ids = find_folders_by_names(service, folders)
        if folder_ids:
            parents_q = " or ".join([f"'{fid}' in parents" for fid in folder_ids])
            anytok = (
                " or ".join([f"name contains '{esc(t)}'" for t in tokens]) if tokens else "name contains ''"
            )
            q3 = f"{mime_q}({parents_q}) and name contains '{esc(client)}' and ({anytok}) and trashed=false"
            results += drive_search(service, q3, page_size=page_size)

    # 4) sinônimos
    if not results and syns:
        anysyn = " or ".join([f"name contains '{esc(s)}'" for s in syns])
        q4 = f"{mime_q}name contains '{esc(client)}' and ({anysyn}) and trashed=false"
        results += drive_search(service, q4, page_size=page_size)

    # 5) fullText (último fallback)
    if not results:
        key_terms = tokens or syns or [type_key]
        anytxt = " or ".join([f"fullText contains '{esc(t)}'" for t in key_terms])
        q5 = f"{mime_q}name contains '{esc(client)}' and ({anytxt}) and trashed=false"
        results += drive_search(service, q5, page_size=page_size)

    return results


# -------------------- export/download --------------------
def export_or_download(service, file_id: str, mime_type: str, kind: str = "txt") -> tuple[bytes, str]:
    """
    Exporta arquivos Google (Docs/Slides/Sheets) para txt/csv/pdf.
    Faz download direto para binários. Retorna (bytes, ext).
    """
    import mimetypes

    if mime_type.startswith("application/vnd.google-apps."):
        if kind == "txt":
            mime, ext = "text/plain", "txt"
            # Heurística: para Sheets, prefira CSV se usuário pediu txt
            if "spreadsheet" in mime_type:
                mime, ext = "text/csv", "csv"
        elif kind == "csv":
            mime, ext = "text/csv", "csv"
        elif kind == "pdf":
            mime, ext = "application/pdf", "pdf"
        else:
            raise ValueError("kind deve ser txt|csv|pdf")
        req = service.files().export_media(fileId=file_id, mimeType=mime)
    else:
        req = service.files().get_media(fileId=file_id)
        guessed = mimetypes.guess_extension(mime_type) or ".bin"
        ext = guessed[1:] if guessed.startswith(".") else guessed

    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, req)
    done = False
    while not done:
        _, done = dl.next_chunk()
    return buf.getvalue(), ext


# -------------------- CLI --------------------
def main():
    ap = argparse.ArgumentParser(description="Busca inteligente no Drive com SA + regras por arquivo.")
    ap.add_argument("--client", required=True, help="Cliente (ex.: 'Start TI')")
    ap.add_argument(
        "--type",
        required=True,
        choices=["daily", "weekly", "checkin", "planejamento", "replanejamento", "benchmarking"],
        help="Tipo de documento buscado",
    )
    ap.add_argument("--goal", default="mais recente", help="Meta textual (opcional, só informativo)")
    ap.add_argument("--take", type=int, default=3, help="Quantos resultados listar (default=3)")
    ap.add_argument(
        "--export",
        choices=["none", "txt", "csv", "pdf"],
        default="none",
        help="Exportar o 1º resultado (opcional): txt/csv/pdf",
    )
    ap.add_argument(
        "--rules",
        default="company_rules.json",
        help="Arquivo de regras (ex.: company_rules_acme.json)",
    )
    args = ap.parse_args()

    rules = load_rules(args.rules)
    service = service_sa()

    files = search_passes(service, args.client, args.type, rules)
    if not files:
        print("Nada encontrado com as regras. Ajuste tokens/pastas no arquivo de regras.")
        return

    print("Top resultados (ordenados por modifiedTime desc):")
    for i, f in enumerate(files[: args.take], 1):
        print(f"{i}. {f['name']} | {f['mimeType']} | {f['id']} | {f.get('modifiedTime')}")

    if args.export != "none":
        f0 = files[0]
        content, ext = export_or_download(service, f0["id"], f0["mimeType"], kind=args.export)
        subdir = "data/raw" if ext in {"txt", "csv"} else "data/downloads"
        os.makedirs(subdir, exist_ok=True)
        out_path = os.path.join(subdir, f"{sanitize(f0['name'])}.{ext}")
        with open(out_path, "wb") as fp:
            fp.write(content)
        print("Salvo:", out_path)
        if ext in {"txt", "csv"}:
            print("Dica: rode  python .\\ingest_txt.py  para o RAG ver esse conteúdo.")


if __name__ == "__main__":
    main()
