# report_exec.py
from __future__ import annotations
import argparse
import os
import subprocess
import sys
from datetime import datetime

PY = sys.executable

HEADER = "# Relatório Executivo\n\n"

def run_capture(cmd: list[str]) -> str:
    """Roda um comando e retorna o stdout (como string)."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out_lines = []
    for line in proc.stdout:
        out_lines.append(line)
    proc.wait()
    if proc.returncode != 0:
        raise SystemExit(f"Comando falhou: {' '.join(cmd)} (code {proc.returncode})")
    return "".join(out_lines).strip()

def build_markdown(question: str, body: str) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    md = []
    md.append(HEADER)
    md.append(f"**Pergunta:** {question}\n")
    md.append(f"**Gerado em:** {ts}\n")
    md.append("\n---\n\n")
    md.append(body.strip())
    md.append("\n")
    return "\n".join(md)

def main():
    ap = argparse.ArgumentParser(description="Gera relatório executivo em Markdown com base no RAG.")
    ap.add_argument("--q", required=True, help="Pergunta / instrução para o relatório")
    ap.add_argument("--out", default="reports/relatorio.md", help="Caminho do arquivo de saída .md")
    args = ap.parse_args()

    out_path = args.out or "reports/relatorio.md"
    out_dir = os.path.dirname(out_path) or "."
    os.makedirs(out_dir, exist_ok=True)

    # 1) Pede o corpo da resposta ao seu script de pergunta com contexto
    #    (mantemos sua lógica atual de RAG sem mexer no core).
    body = run_capture([PY, "ask_with_context.py", "--q", args.q])

    # 2) Monta o markdown com cabeçalho padrão
    markdown = build_markdown(args.q, body)

    # 3) Salva
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"Relatório salvo em: {out_path}")

if __name__ == "__main__":
    main()
