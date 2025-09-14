from __future__ import annotations

# FastAPI e utilidades
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import subprocess
import sys
import os
import re
import tempfile
import urllib.request
import shutil
import glob

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
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # depois podemos restringir ao domínio do AI Studio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # depois pode restringir para ["https://aistudio.google.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Servir arquivos estáticos ---
# Crie um diretório chamado "web" na raiz do projeto e coloque seu chat.html e scripts lá.
STATIC_DIR = os.path.join(ROOT, "web")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# --- Funções utilitárias ---
def slugify(s: str) -> str:
    return re.sub(r"\W+", "_", s, flags=re.UNICODE).strip("_").lower() or "cliente"

def download_to_tmp(url: str) -> str:
    tf = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    with urllib.request.urlopen(url) as r, open(tf.name, "wb") as f:
        shutil.copyfileobj(r, f)
    return tf.name

def latest_md_for(client_slug: str) -> tuple[str | None, str]:
    """Retorna (caminho, conteúdo) do .md mais recente em reports/ ."""
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

# --- Modelos de requisição ---
class RunReq(BaseModel):
    client: str
    q: str
    take: int | None = 1
    type: str | None = None          # se enviado, força o tipo (ex.: "chat")
    google_csv_url: str | None = None
    meta_csv_url: str | None = None

class ChatReq(BaseModel):
    client: str
    q: str

# --- Rotas básicas ---
@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/")
def root():
    return {
        "ok": True,
        "service": "Assistente de Dados Runner",
        "docs": "Para conversar, acesse /static/chat.html (se configurado) ou use o endpoint /chat",
    }

# --- Rota para geração de relatórios executivos (fluxo completo) ---
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
            cmd += ["--google_csv", tmp_g]
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

# --- Rota de chat simples ---
@app.post("/chat")
def chat(req: ChatReq, x_api_key: str | None = Header(None)):
    """
    Endpoint para perguntas avulsas. Retorna a resposta em texto.
    Exemplo de uso:
      POST /chat
      {
        "client": "ai_studio",
        "q": "Qual é o status do projeto X?"
      }
    """
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")

    q = (req.q or "").strip()
    if not q:
        return {"reply": "Pergunta vazia."}

    # chama o script ask_with_context.py para responder
    script_path = os.path.join(ROOT, "ask_with_context.py")
    cmd = [PY, script_path, "--q", q]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)

    # resposta é o stdout do script; se vazio, mostra mensagem padrão
    answer = proc.stdout.strip() or "Não há resposta disponível."
    return {
        "client": slugify(req.client),
        "query": q,
        "reply": answer,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
# --- INGEST ROUTE (append at end) ---
from pydantic import BaseModel
from fastapi import Header
import os, subprocess, sys

SERVICE_API_KEY = os.getenv("SERVICE_API_KEY", "")
PY = sys.executable

class IngestReq(BaseModel):
    client: str
    types: list[str] | None = None   # ex: ["daily","weekly"]
    export: str | None = "txt"       # "txt" ou "csv"

@app.post("/ingest")
def ingest(req: IngestReq, x_api_key: str | None = Header(default=None)):
    if SERVICE_API_KEY and x_api_key != SERVICE_API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")

    doc_types = req.types or [
        "daily",
        "weekly",
        "checkin",
        "planejamento",
        "replanejamento",
        "benchmarking",
    ]

    for t in doc_types:
        subprocess.run(
            [PY, "smart_search_sa.py", "--client", req.client, "--type", t, "--export", req.export],
            check=True,
        )

    subprocess.run([PY, "ingest_txt.py"], check=True)

    return {"ok": True, "client": req.client, "types": doc_types, "export": req.export}
