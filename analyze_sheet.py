from __future__ import annotations
import argparse, os, re, math
import pandas as pd
import numpy as np

def to_num(x):
    if pd.isna(x): return np.nan
    if isinstance(x, (int, float)): return float(x)
    s = str(x)
    s = s.replace("R$", "").replace("%", "").strip()
    s = re.sub(r"[.\s]", "", s)  # remove separador de milhar
    s = s.replace(",", ".")      # decimal brasileiro
    try: return float(s)
    except: return np.nan

def find_col(cols, *candidates):
    cols_low = {c.lower(): c for c in cols}
    for cand in candidates:
        for c in cols:
            if cand in c.lower():
                return c
    return None

def main(path: str):
    df = pd.read_excel(path)
    orig_cols = list(df.columns)
    # tenta detectar colunas relevantes (case-insensitive, pt/br variações)
    c_data   = find_col(orig_cols, "data", "dia", "date", "mês", "mes")
    c_leads  = find_col(orig_cols, "lead", "leads")
    c_gasto  = find_col(orig_cols, "gasto", "invest", "custo", "spend")
    c_clicks = find_col(orig_cols, "clique", "click")
    c_impr   = find_col(orig_cols, "impre", "impres", "impressions")
    c_conv   = find_col(orig_cols, "convers", "conv.")

    # normaliza numéricos
    for c in [c_leads, c_gasto, c_clicks, c_impr, c_conv]:
        if c and c in df.columns: df[c] = df[c].map(to_num)

    # datas
    if c_data and c_data in df.columns:
        df[c_data] = pd.to_datetime(df[c_data], errors="coerce", dayfirst=True)
        df["mes"] = df[c_data].dt.to_period("M").astype(str)
    else:
        df["mes"] = "sem_data"

    # métricas derivadas
    if c_impr and c_clicks and c_impr in df.columns and c_clicks in df.columns:
        df["CTR_%"] = np.where(df[c_impr] > 0, (df[c_clicks] / df[c_impr]) * 100, np.nan)
    if c_leads and c_gasto and c_leads in df.columns and c_gasto in df.columns:
        df["CPL"] = np.where(df[c_leads] > 0, df[c_gasto] / df[c_leads], np.nan)

    # agregação por mês
    agg_cols = {}
    for name in [("Leads", c_leads), ("Gasto", c_gasto), ("Cliques", c_clicks), ("Impressões", c_impr), ("Conversões", c_conv), ("CPL", "CPL"), ("CTR_%", "CTR_%")]:
        label, col = name
        if col and col in df.columns:
            if label in ["CPL", "CTR_%"]:
                agg_cols[col] = "mean"
            else:
                agg_cols[col] = "sum"

    monthly = df.groupby("mes").agg(agg_cols).reset_index() if agg_cols else pd.DataFrame({"mes":[],})

    # totais
    def ssum(c): 
        return float(np.nansum(df[c])) if c in df.columns else np.nan
    tot_leads  = ssum(c_leads) if c_leads else np.nan
    tot_spend  = ssum(c_gasto) if c_gasto else np.nan
    tot_clicks = ssum(c_clicks) if c_clicks else np.nan
    tot_impr   = ssum(c_impr) if c_impr else np.nan
    cpl = (tot_spend / tot_leads) if (not math.isnan(tot_spend) and not math.isnan(tot_leads) and tot_leads>0) else np.nan
    ctr = (tot_clicks / tot_impr * 100) if (not math.isnan(tot_clicks) and not math.isnan(tot_impr) and tot_impr>0) else np.nan

    # saída
    os.makedirs("data/derived", exist_ok=True)
    out_csv = "data/derived/metrics_summary.csv"
    monthly.to_csv(out_csv, index=False)

    def f(x, casas=2): 
        return ("-" if (x is None or math.isnan(x)) else (f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X",".")))

    print("\n=== RESUMO GERAL ===")
    print(f"- Leads totais: {f(tot_leads,0)}")
    print(f"- Gasto total: R$ {f(tot_spend)}")
    if not math.isnan(cpl): print(f"- CPL médio: R$ {f(cpl)}")
    if not math.isnan(tot_clicks): print(f"- Cliques totais: {f(tot_clicks,0)}")
    if not math.isnan(tot_impr):   print(f"- Impressões totais: {f(tot_impr,0)}")
    if not math.isnan(ctr):        print(f"- CTR média: {f(ctr)}%")

    if not monthly.empty:
        print("\n=== POR MÊS ===")
        print(monthly)

    # opcional: salva um txt para alimentar o RAG depois
    base = os.path.splitext(os.path.basename(path))[0]
    rag_txt = os.path.join("data/raw", f"{base}_kpis.txt")
    with open(rag_txt, "w", encoding="utf-8") as ftxt:
        ftxt.write("RESUMO GERAL\n")
        ftxt.write(f"Leads totais: {tot_leads}\nGasto total: {tot_spend}\nCPL médio: {cpl}\nCliques: {tot_clicks}\nImpressões: {tot_impr}\nCTR média: {ctr}\n\n")
        if not monthly.empty:
            ftxt.write("POR MÊS\n")
            monthly.to_csv(ftxt, index=False)
    print(f"\nArquivos gerados:\n- {out_csv}\n- {rag_txt}")
    print("\nDica: para o RAG ver essas métricas, rode depois:  python .\\ingest_txt.py")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True, help="Caminho do .xlsx")
    args = ap.parse_args()
    main(args.path)
