from fastapi import FastAPI
from pydantic import BaseModel
import subprocess, sys, os, re, glob

PY = sys.executable
app = FastAPI(title="Assistant Runner")

def slugify(s: str) -> str:
    import re
    return re.sub(r"\W+","_", s).strip("_").lower() or "cliente"

class RunReq(BaseModel):
    client: str
    q: str
    take: int | None = 1
    type: str | None = None  # opcional; se não vier, o assistant_cli detecta

@app.post("/run")
def run(req: RunReq):
    cmd = [PY, "assistant_cli.py", "--client", req.client, "--q", req.q, "--take", str(req.take or 1)]
    # (se quiser forçar um tipo: cmd += ["--take", ...] já faz; o type é opcional)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return {"ok": False, "stdout": proc.stdout, "stderr": proc.stderr}

    slug = slugify(req.client)
    latest = os.path.join("reports", slug, "relatorio.md")
    md = ""
    if os.path.exists(latest):
        with open(latest, "r", encoding="utf-8") as f:
            md = f.read()
    return {"ok": True, "report_path": latest, "markdown": md, "stdout": proc.stdout}
