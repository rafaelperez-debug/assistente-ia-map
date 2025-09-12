from __future__ import annotations
import json, argparse, os, subprocess, sys
from datetime import datetime

PY = sys.executable

def ensure_dir(d: str): os.makedirs(d, exist_ok=True)

def run(cmd: list[str], logf):
    print(">>", " ".join(cmd), flush=True)
    logf.write(">> " + " ".join(cmd) + "\n"); logf.flush()
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in p.stdout:
        print(line, end="")
        logf.write(line)
    p.wait()
    if p.returncode != 0:
        raise RuntimeError(f"Falha: {' '.join(cmd)} (code {p.returncode})")

def main():
    ap = argparse.ArgumentParser(description="Roda o assistente para vários clientes (sem n8n).")
    ap.add_argument("--config", default="clients.json", help="Arquivo JSON com a lista de clientes")
    args = ap.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        clients = json.load(f)

    ensure_dir("logs")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = os.path.join("logs", f"run-multi-{ts}.log")

    ok, fail = [], []
    with open(log_path, "w", encoding="utf-8") as logf:
        for c in clients:
            client = c["client"]
            print(f"\n===== {client} =====")
            logf.write(f"\n===== {client} =====\n")

            cmd = [PY, "assistant_cli.py",
                   "--client", client,
                   "--rules", c.get("rules","company_rules.json"),
                   "--q", c.get("q","Resumo executivo da entrega mais recente.")]

            if c.get("type"): cmd += ["--take", str(c.get("take", 1))]
            # CSVs são opcionais; só passam se tiver caminho
            if c.get("google_csv"): cmd += ["--google_csv", c["google_csv"]]
            if c.get("meta_csv"):   cmd += ["--meta_csv", c["meta_csv"]]

            try:
                run(cmd, logf)
                ok.append(client)
            except Exception as e:
                fail.append((client, str(e)))
                logf.write(f"[ERRO] {client}: {e}\n")

    print("\n✅ Concluído.")
    print("  OK:", ok)
    if fail:
        print("  Falhas:")
        for cl, err in fail:
            print("   -", cl, "->", err)
    print("Logs:", log_path)

if __name__ == "__main__":
    main()
