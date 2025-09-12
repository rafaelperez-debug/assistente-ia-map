from __future__ import annotations
import argparse, os, re, subprocess, sys, glob, shutil
from datetime import datetime

PY = sys.executable

TYPES = {
    "replanejamento": ["replanejamento","revisão do plano","revisão de estratégia","re-plan"],
    "planejamento":   ["planejamento","plano","estratégia"],
    "checkin":        ["check-in","checkin","check in"],
    "weekly":         ["weekly","semanal","wk"],
    "daily":          ["daily","diária","reunião diária"],
    "benchmarking":   ["benchmark","concorrentes","competitive analysis","mop","estudo de concorrência"],
}

ADS_HINTS = ["mídia","google ads","meta","facebook","instagram","cpl","ctr","cpc","cpa","conversões","cliques","impressões","gasto"]

def detect_type(q: str) -> str:
    ql = q.lower()
    for t, kws in TYPES.items():
        if any(k in ql for k in kws):
            return t
    return "replanejamento"  # padrão seguro

def wants_ads(q: str) -> bool:
    ql = q.lower()
    return any(k in ql for k in ADS_HINTS)

def run(cmd: list[str]):
    print(">>", " ".join(cmd), flush=True)
    subprocess.check_call(cmd)

def slugify(name: str) -> str:
    slug = re.sub(r"\W+", "_", name, flags=re.UNICODE).strip("_").lower()
    return slug or "cliente"

def main():
    ap = argparse.ArgumentParser(description="Agente de Dados (roteia busca -> ingest -> relatório).")
    ap.add_argument("--client", required=True, help='Ex.: "Start TI"')
    ap.add_argument("--rules", default="company_rules.json")
    ap.add_argument("--q", required=True, help="Pergunta em linguagem natural")
    ap.add_argument("--take", default="1")
    # opcionais: processar Ads CSV no mesmo fluxo
    ap.add_argument("--google_csv")
    ap.add_argument("--meta_csv")
    args = ap.parse_args()

    # 0) Se vierem CSVs de Ads, gera o _kpis.txt antes de tudo
    if args.google_csv or args.meta_csv:
        cmd = [PY, "ads_kpis_from_csv.py", "--client", args.client]
        if args.google_csv: cmd += ["--google_csv", args.google_csv]
        if args.meta_csv:   cmd += ["--meta_csv", args.meta_csv]
        run(cmd)

    # 1) Detecta tipo
    doc_type = detect_type(args.q)
    print(f"[router] tipo detectado: {doc_type}")

    # 2) Busca inteligente + export (txt/csv vai p/ data/raw)
    run([PY, "smart_search_sa.py", "--client", args.client, "--type", doc_type,
         "--export", "txt", "--take", args.take, "--rules", args.rules])

    # 3) Ingestão
    run([PY, "ingest_txt.py"])

    # 4) Monta pergunta final (verifica se há KPIs de mídia)
    client_slug = slugify(args.client)
    client_dir  = os.path.join("reports", client_slug)
    os.makedirs(client_dir, exist_ok=True)
    ts          = datetime.now().strftime("%Y%m%d-%H%M")
    ts_path     = os.path.join(client_dir, f"relatorio-{ts}.md")
    latest_path = os.path.join(client_dir, "relatorio.md")

    ads_txt = glob.glob(os.path.join("data","raw", f"ads_kpis_{client_slug}.txt"))
    combine_ads = bool(ads_txt) or wants_ads(args.q)

    if combine_ads:
        prompt = (args.q.strip() +
                  " | Se houver KPIs de mídia (Google/Meta) no contexto, combine e destaque: gasto, impressões, cliques, "
                  "conversões, CTR, CPC, CPA; traga 6 bullets e próximos passos. Cite fontes.")
    else:
        prompt = args.q.strip() + " | Traga 6 bullets executivos e próximos passos. Cite fontes."

    # 5) Relatório executivo -> salva direto no path com timestamp
    run([PY, "report_exec.py", "--q", prompt, "--out", ts_path])

    # 6) Copia como 'relatorio.md' (última versão)
    try:
        shutil.copyfile(ts_path, latest_path)
    except Exception as e:
        print(f"[warn] não consegui copiar para {latest_path}: {e}")

    print(f"\nOK! Relatório em:\n- {ts_path}\n- {latest_path} (última versão)")

if __name__ == "__main__":
    main()
