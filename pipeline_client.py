# pipeline_client.py
from __future__ import annotations
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime

PY = sys.executable

def ensure_dir(d: str):
    os.makedirs(d, exist_ok=True)

def clean_old_logs(path_glob: str, keep: int = 10):
    files = sorted(glob.glob(path_glob), key=os.path.getmtime, reverse=True)
    for f in files[keep:]:
        try:
            os.remove(f)
        except:
            pass

def run_and_log(cmd: list[str], logf):
    print(">>", " ".join(cmd), flush=True)
    logf.write(">> " + " ".join(cmd) + "\n"); logf.flush()

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in proc.stdout:
        line = line.rstrip("\n")
        print(line)
        logf.write(line + "\n")
    proc.wait()
    if proc.returncode != 0:
        raise SystemExit(f"Comando falhou: {' '.join(cmd)} (code {proc.returncode})")

def slugify(name: str) -> str:
    return re.sub(r"\W+", "_", name, flags=re.UNICODE).strip("_").lower() or "cliente"

def main():
    ap = argparse.ArgumentParser(description="Pipeline: busca -> ingest -> relatório (1 comando).")
    ap.add_argument("--client", required=True, help='Ex.: "Start TI"')
    ap.add_argument("--type", required=True,
                    choices=["daily","weekly","checkin","planejamento","replanejamento","benchmarking"])
    ap.add_argument("--rules", default="company_rules.json", help="Arquivo de regras da empresa")
    ap.add_argument("--q", default="Resuma a entrega mais recente e combine com KPIs (gasto, leads, CPL). Traga 6 bullets e próximos passos.",
                    help="Pergunta usada no relatório")
    ap.add_argument("--take", default="1", help="Quantidade de resultados da busca inteligente (default=1)")
    # opcionais: processar Ads CSV no mesmo fluxo (se quiser)
    ap.add_argument("--google_csv")
    ap.add_argument("--meta_csv")
    args = ap.parse_args()

    ensure_dir("logs")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = os.path.join("logs", f"run-{ts}.log")
    clean_old_logs("logs/run-*.log", keep=10)

    client_slug = slugify(args.client)
    client_dir  = os.path.join("reports", client_slug)
    ensure_dir(client_dir)
    ts_report   = datetime.now().strftime("%Y%m%d-%H%M")
    out_ts_path = os.path.join(client_dir, f"relatorio-{ts_report}.md")
    out_latest  = os.path.join(client_dir, "relatorio.md")

    with open(log_path, "w", encoding="utf-8") as logf:
        logf.write(f"Pipeline start: {ts}\n")

        # (opcional) se vierem CSVs de Ads, processa antes
        if args.google_csv or args.meta_csv:
            cmd_ads = [PY, "ads_kpis_from_csv.py", "--client", args.client]
            if args.google_csv: cmd_ads += ["--google_csv", args.google_csv]
            if args.meta_csv:   cmd_ads += ["--meta_csv", args.meta_csv]
            run_and_log(cmd_ads, logf)

        # 1) Busca inteligente + export (txt/csv cai em data/raw)
        run_and_log([PY, "smart_search_sa.py", "--client", args.client, "--type", args.type,
                     "--export", "txt", "--take", str(args.take), "--rules", args.rules], logf)

        # 2) Ingestão do que caiu em data/raw
        run_and_log([PY, "ingest_txt.py"], logf)

        # 3) Relatório executivo -> salva por cliente (com timestamp) e copia como latest
        run_and_log([PY, "report_exec.py", "--q", args.q, "--out", out_ts_path], logf)

        try:
            shutil.copyfile(out_ts_path, out_latest)
        except Exception as e:
            logf.write(f"[warn] copy latest failed: {e}\n")

        logf.write("Pipeline OK\n")

    print("OK! Pipeline concluído. Veja:")
    print(f"- {out_ts_path}")
    print(f"- {out_latest} (última versão)")
    print(f"- {log_path}")

if __name__ == "__main__":
    main()
