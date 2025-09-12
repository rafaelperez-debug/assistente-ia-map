# service.py
from __future__ import annotations
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import subprocess, sys, os, re, tempfile, urllib.request, shutil

PY = sys.executable
API_KEY = os.getenv("SERVICE_API_KEY", "")  # defina uma chave

def slugify(s: str) -> str:
    return re.sub(r"\W+","_", s, flags=re.UNICODE).strip("_").lower() or "cliente"

def download_to_tmp(url: str) -> str:
    tf = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    with urllib.request.urlopen(url) as r, open(tf.name, "wb") as f:
        shutil.copyfileobj(r, f)
    return tf.name

class RunReq(BaseModel):
    client: str
    q: str
    take: int | None = 1
    type: str | None = None          # opcional (assistant_cli detecta)
    google_csv_url: str | None = None
    meta_csv_url: str | None = None

app = FastAPI(title="Assistente de Dados Runner", version="1.0.0")

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.post("/run")
def run(req: RunReq, x_api_key: str = Header(default="")):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")

    tmp_g = tmp_m = None
    try:
        # baixa CSVs (opcional)
        if req.google_csv_url:
            tmp_g = download_to_tmp(req.google_csv_url)
        if req.meta_csv_url:
            tmp_m = download_to_tmp(req.meta_csv_url)

        cmd = [PY, "assistant_cli.py", "--client", req.client, "--q", req.q, "--take", str(req.take or 1)]
        if tmp_g: cmd += ["--google_csv", tmp_g]
        if tmp_m: cmd += ["--meta_csv", tmp_m]
        # type é opcional; o assistant_cli roteia sozinho. Se quiser forçar, acrescente a lógica aqui.

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            return {"ok": False, "stdout": proc.stdout, "stderr": proc.stderr}

        slug = slugify(req.client)
        latest = os.path.join("reports", slug, "relatorio.md")
        md = ""
        if os.path.exists(latest):
            with open(latest, "r", encoding="utf-8") as f:
                md = f.read()

        return {"ok": True, "client": req.client, "report_path": latest, "markdown": md, "stdout": proc.stdout}
    finally:
        for p in [tmp_g, tmp_m]:
            if p and os.path.exists(p):
                try: os.remove(p)
                except: pass
