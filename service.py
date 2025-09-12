# service.py
from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess, sys, os, re, tempfile, urllib.request, shutil, glob

# --- Configurações globais ---
PY = sys.executable
API_KEY = os.getenv("SERVICE_API_KEY", "")  # defina uma chave no Render
ROOT = os.getenv("APP_ROOT", os.getcwd())   # normalmente '/app' no Render

def _resolve_cli_path() -> str:
    # tenta achar o assistant_cli.py em locais comuns
    for p in [
        os.path.join(ROOT, "assistant_cli.py"),
        "/app/assistant_cli.py",
        "assistant_cli.py",
    ]:
        if os.path.exists(p):
            return p
    return "assistant_cli.py"

CLI = _resolve_cli_path()

# --- Inicialização do app ---
app = FastAPI(title="Assistente de Dados Runner", version="1.0.0")

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # depois pode restringir para ["https://aistudio.google.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Funções utilitárias ---
def slugify(s: str) -> str:
    return re.sub(r"\W+", "_", s, flags=re.UNICODE).strip("_").lower() or "cliente"

def download_to_tmp(url: str) -> str:
    tf = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    with urllib.request.urlopen(url) as r, open(tf.name, "wb") as f:
        shutil.copyfileobj(r, f)
    return tf.name

def latest_md_for(client_slug: str) -> tuple[str | None, str]:
    """Retorna (caminho, conteúdo) do .md mais recente em reports/<slug>."""
    rep_dir = os.path.join(ROOT, "reports", client_slug)
    if not os.path.isdir(rep_dir):
        return None, ""
    candidates = glob.glob(os.path.join(rep_dir, "*.md"))
    if not candidates:
        return None, ""
    newest = max(candidates, key=os.path.getmtime)
    try:
        with open(newest, "r", encoding="utf-8") as f:
            return newest, f.read()
    except Exception:
        return newest, ""

# --- Modelo de requisição ---
class RunReq(BaseModel):
    client: str
    q: str
    take: int | None = 1
    type: str | None = None          # se enviado, força o tipo (ex.: "chat")
    google_csv_url: str | None = None
    meta_csv_url: str | None = None

# --- Rotas ---
@app.get("/healthz")
def healthz():
    return {"ok": True}
@app.get("/")
def root():
    return {"ok": True, "service": "Assistente de Dados Runner"}

@app.post("/run")
def run(req: RunReq, x_api_key: str | None = Header(None)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")

    client = slugify(req.client)
    q = (req.q or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="empty prompt")

    tmp_g = tmp_m = None
    try:
        # baixa CSVs (opcional)
        if req.google_csv_url:
            tmp_g = download_to_tmp(req.google_csv_url)
        if req.meta_csv_url:
            tmp_m = download_to_tmp(req.meta_csv_url)

        # monta comando
        cmd = [PY, CLI, "--client", client, "--q", q, "--take", str(req.take or 1)]

        # respeita explicitamente o tipo, se vier do front (ex.: chat, weekly, replanejamento)
        if req.type:
            cmd += ["--type", req.type.strip().lower()]

        if tmp_g:
            cmd += ["--google_csv", tmp_g]  # mantenho o formato com _ para compatibilidade
        if tmp_m:
            cmd += ["--meta_csv", tmp_m]

        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)

        # localiza o último relatório gerado
        md_path, md_content = latest_md_for(client)

        return {
            "ok": proc.returncode == 0,
            "client": client,
            "type_used": (req.type or "auto"),
            "cmd": " ".join(cmd),
            "report_path": md_path,
            "markdown": md_content,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }

    finally:
        # limpa temporários
        for p in [tmp_g, tmp_m]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
