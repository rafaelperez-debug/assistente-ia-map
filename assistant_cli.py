# assistant_cli.py
from __future__ import annotations
import argparse, os, re, subprocess, sys, glob, shutil
from datetime import datetime

PY   = sys.executable
ROOT = os.getenv("APP_ROOT", os.getcwd())

TYPES = {
    "replanejamento": ["replanejamento","revisão do plano","revisão de estratégia","re-plan"],
    "planejamento":   ["planejamento","plano","estratégia"],
    "checkin":        ["check-in","checkin","check in"],
    "weekly":         ["weekly","semanal","wk"],
    "daily":          ["daily","diária","reunião diária"],
    "benchmarking":   ["benchmark","concorrentes","competitive analysis","mop","estudo de concorrência"],
    "chat":           ["chat","conversa","pergunta","responda","diga","fale"]
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

def run(cmd: list[str], allow_fail: bool = False) -> int:
    print(">>", " ".join(cmd), flush=True)
    p = subprocess.run(cmd, cwd=ROOT)
    if p.returncode != 0 and not allow_fail:
        raise subprocess.CalledProcessError(p.returncode, cmd)
    return p.returncode

def slugify(name: str) -> str:
    slug = re.sub(r"\W+", "_", name, flags=re.UNICODE).strip("_").lower()
    return slug or "cliente"

def paths_for(client_slug: str) -> tuple[str, str]:
    rep_dir = os.path.join(ROOT, "reports", client_slug)
    os.makedirs(rep_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M")
    ts_path = os.path.join(rep_dir, f"relatorio-{ts}.md")
    latest_path = os.path.join(rep_dir, "relatorio.md")
    return ts_path, latest_path

def main():
    ap = argparse.ArgumentParser(description="Agente de Dados (router)")
    ap.add_argument("--client", required=True, help='Ex.: "Start TI"')
    ap.add_argument("--rules", default="company_rules.json")
    ap.add_argument("--q", required=True, help="Pergunta em linguagem natural")
    ap.add_argument("--take", default="1")
    ap.add_argument("--type", dest="type", help="Força o tipo: chat, weekly, replanejamento, etc.")
    # opcionais de Ads
    ap.add_argument("--google_csv")
    ap.add_argument("--meta_csv")
    args = ap.parse_args()

    client_slug = slugify(args.client)
    ts_path, latest_path = paths_for(client_slug)

    # 0) Se vierem CSVs de Ads, gera o _kpis.txt antes de tudo
    if args.google_csv or args.meta_csv:
        cmd = [PY, "ads_kpis_from_csv.py", "--client", args.client]
        if args.google_csv: cmd += ["--google_csv", args.google_csv]
        if args.meta_csv:   cmd += ["--meta_csv", args.meta_csv]
        run(cmd)

    # 1) Define tipo (preferir o que veio via --type)
    doc_type = (args.type or "").strip().lower() or detect_type(args.q)
    print(f"[router] tipo selecionado: {doc_type}")

    # 2) Se for chat, pular busca/ingestão e ir direto ao relatório simples
    if doc_type == "chat":
        prompt = args.q.strip()
        try:
            run([PY, "report_exec.py", "--q", prompt, "--out", ts_path])
        except subprocess.CalledProcessError:
            # fallback alternativo caso report_exec exija contexto
            run([PY, "ask_with_context.py", "--q", prompt, "--out", ts_path], allow_fail=False)

        # copiar para última versão
        try:
            shutil.copyfile(ts_path, latest_path)
        except Exception as e:
            print(f"[warn] não consegui copiar para {latest_path}: {e}")
        print(f"\nOK! Relatório (chat) em:\n- {ts_path}\n- {latest_path} (última versão)")
        return

    # 3) Fluxos não-chat: busca inteligente + ingest
    #    Se falhar, fazemos fallback para chat com o prompt original
    try:
        run([PY, "smart_search_sa.py",
             "--client", args.client,
             "--type", doc_type,
             "--export", "txt",
             "--take", args.take,
             "--rules", args.rules])

        run([PY, "ingest_txt.py"])
    except subprocess.CalledProcessError as e:
        print(f"[warn] busca/ingestão falhou (code {e.returncode}). Fallback para chat puro.")
        # Fallback para chat
        prompt_fb = args.q.strip()
        try:
            run([PY, "report_exec.py", "--q", prompt_fb, "--out", ts_path])
        except subprocess.CalledProcessError:
            run([PY, "ask_with_context.py", "--q", prompt_fb, "--out", ts_path], allow_fail=False)
        try:
            shutil.copyfile(ts_path, latest_path)
        except Exception as ee:
            print(f"[warn] não consegui copiar para {latest_path}: {ee}")
        print(f"\nOK! Relatório (fallback chat) em:\n- {ts_path}\n- {latest_path}")
        return

    # 4) Monta pergunta final considerando possível presença de KPIs de mídia
    ads_txt = glob.glob(os.path.join(ROOT, "data","raw", f"ads_kpis_{client_slug}.txt"))
    combine_ads = bool(ads_txt) or wants_ads(args.q)

    if combine_ads:
        prompt = (args.q.strip() +
                  " | Se houver KPIs de mídia (Google/Meta) no contexto, combine e destaque: "
                  "gasto, impressões, cliques, conversões, CTR, CPC, CPA; "
                  "traga 6 bullets e próximos passos. Cite fontes.")
    else:
        prompt = args.q.strip() + " | Traga 6 bullets executivos e próximos passos. Cite fontes."

    # 5) Gera relatório e copia para última versão
    try:
        run([PY, "report_exec.py", "--q", prompt, "--out", ts_path])
    except subprocess.CalledProcessError:
        # fallback alternativo
        run([PY, "ask_with_context.py", "--q", prompt, "--out", ts_path], allow_fail=False)

    try:
        shutil.copyfile(ts_path, latest_path)
    except Exception as e:
        print(f"[warn] não consegui copiar para {latest_path}: {e}")

    print(f"\nOK! Relatório em:\n- {ts_path}\n- {latest_path} (última versão)")

if __name__ == "__main__":
    main()
