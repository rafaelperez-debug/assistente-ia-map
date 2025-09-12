from __future__ import annotations
import argparse, os, re, math
import pandas as pd
import numpy as np

def to_num(x):
    if pd.isna(x): return np.nan
    if isinstance(x, (int, float)): return float(x)
    s = str(x)
    s = s.replace("R$", "").replace("%", "").strip()
    s = re.sub(r"[.\s]", "", s)     # remove milhar
    s = s.replace(",", ".")         # decimal pt-BR
    try: return float(s)
    except: return np.nan

def norm_metric(name: str) -> str:
    n = str(name).strip().lower()
    # mapeia nomes mais comuns
    if "gasto" in n or "invest" in n or "custo" in n: return "spend"
    if "lead" in n: return "leads"
    if "clique" in n or "click" in n: return "clicks"
    if "impre" in n: return "impressions"
    if "convers" in n: return "conversions"
    if "vendas" in n: return "sales"
    if "oportunidade" in n: return "opportunities"
    if "faturamento" in n: return "revenue"
    return n

def analyze_matrix(path: str, sheet: str):
    df = pd.read_excel(path, sheet_name=sheet, header=0)
    # remove colunas e linhas totalmente vazias
    df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")

    first_col = df.columns[0]
    df[first_col] = df[first_col].astype(str).str.strip()

    # ignora linhas de cabeçalho tipo "DADOS" / "PERIODO"
    mask = df[first_col].str.len() > 0
    mask &= ~df[first_col].str.contains("DADOS", case=False, na=False)
    mask &= ~df[first_col].str.contains("PERIODO", case=False, na=False)
    df = df.loc[mask].copy()

    period_cols = [c for c in df.columns if c != first_col]
    # alguns "Unnamed" no final podem estar 100% vazios — tira
    keep = []
    for c in period_cols:
        colvals = df[c]
        if not colvals.dropna().empty:
            keep.append(c)
    period_cols = keep

    long = df.melt(id_vars=[first_col], value_vars=period_cols, var_name="period", value_name="value")
    long["metric"] = long[first_col]
    long["metric_key"] = long["metric"].map(norm_metric)
    long["value"] = long["value"].apply(to_num)
    long = long.dropna(subset=["value"])
    long = long[long["metric_key"] != ""]  # sanidade
    long["period"] = long["period"].astype(str).str.strip()

    # agrega por período + métrica
    agg = long.groupby(["period", "metric_key"], as_index=False)["value"].sum()

    # totais
    def tsum(key):
        s = agg.loc[agg["metric_key"]==key, "value"].sum()
        return float(s) if pd.notna(s) else np.nan
    tot_spend  = tsum("spend")
    tot_leads  = tsum("leads")
    tot_clicks = tsum("clicks")
    tot_impr   = tsum("impressions")

    cpl = (tot_spend / tot_leads) if (tot_leads and tot_leads>0 and pd.notna(tot_spend)) else np.nan
    ctr = (tot_clicks / tot_impr * 100) if (tot_impr and tot_impr>0 and pd.notna(tot_clicks)) else np.nan

    # métricas por período (CPL/CTR derivadas se possível)
    pivot = agg.pivot(index="period", columns="metric_key", values="value").fillna(np.nan)
    if "spend" in pivot and "leads" in pivot:
        pivot["CPL"] = np.where(pivot["leads"]>0, pivot["spend"]/pivot["leads"], np.nan)
    if "clicks" in pivot and "impressions" in pivot:
        pivot["CTR_%"] = np.where(pivot["impressions"]>0, (pivot["clicks"]/pivot["impressions"])*100, np.nan)
    pivot = pivot.reset_index()

    # salvar saídas
    os.makedirs("data/derived", exist_ok=True)
    out_csv = "data/derived/metrics_summary_matrix.csv"
    pivot.to_csv(out_csv, index=False)

    # texto para RAG
    base = os.path.splitext(os.path.basename(path))[0]
    rag_txt = os.path.join("data", "raw", f"{base}_{sheet}_kpis.txt")
    with open(rag_txt, "w", encoding="utf-8") as f:
        f.write("KPIs derivados do sheet (formato matriz)\n")
        f.write(f"TOTAIS: spend={tot_spend}, leads={tot_leads}, cpl={cpl}, clicks={tot_clicks}, impressions={tot_impr}, ctr%={ctr}\n\n")
        f.write(pivot.to_csv(index=False))

    def fmt(x, casas=2):
        if pd.isna(x): return "-"
        return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X",".")

    print("\n=== RESUMO GERAL ===")
    print(f"- Gasto total: R$ {fmt(tot_spend)}")
    print(f"- Leads totais: {fmt(tot_leads,0)}")
    if not pd.isna(cpl): print(f"- CPL médio: R$ {fmt(cpl)}")
    if not pd.isna(ctr): print(f"- CTR média: {fmt(ctr)}%")

    print("\n=== POR PERÍODO (amostra) ===")
    with pd.option_context("display.max_columns", None, "display.width", 160):
        print(pivot.head(8))

    print(f"\nArquivos gerados:\n- {out_csv}\n- {rag_txt}")
    print("Dica: para o RAG considerar estes KPIs, rode depois:  python .\\ingest_txt.py")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True, help="Caminho do .xlsx")
    ap.add_argument("--sheet", required=True, help="Nome do sheet (ex.: 'BD MENSAL' ou 'BD SEMANAL')")
    args = ap.parse_args()
    analyze_matrix(args.path, args.sheet)
