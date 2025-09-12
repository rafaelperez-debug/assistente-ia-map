from __future__ import annotations
import argparse, os, re
import pandas as pd
import numpy as np
from datetime import datetime

def read_csv_any(path: str) -> pd.DataFrame:
    # tenta , como decimal e ; como separador (Meta às vezes exporta assim)
    try:
        df = pd.read_csv(path, encoding="utf-8")
    except Exception:
        try:
            df = pd.read_csv(path, sep=";", encoding="utf-8")
        except Exception:
            df = pd.read_csv(path, sep=";", encoding="latin-1")
    return df

def to_float(x):
    if pd.isna(x): return np.nan
    if isinstance(x, (int, float)): return float(x)
    s = str(x).strip()
    s = s.replace("R$", "").replace("BRL", "").replace("%", "")
    s = s.replace(".", "").replace(",", ".")
    try: return float(s)
    except: return np.nan

def find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    cols = {c.lower(): c for c in df.columns}
    for cand in candidates:
        lc = cand.lower()
        if lc in cols: return cols[lc]
    # tentativa “contains”
    for c in df.columns:
        cl = c.lower()
        if any(lc in cl for lc in [x.lower() for x in candidates]):
            return c
    return None

def normalize_ads(df: pd.DataFrame, vendor: str) -> pd.DataFrame:
    # Mapas de possíveis nomes de colunas
    date_cols = ["Date", "Day", "Data", "Reporting starts", "Reporting Starts", "Start date"]
    imp_cols  = ["Impressions", "Impressões", "Impr."]
    clk_cols  = ["Clicks", "Cliques", "Link clicks", "Cliques no link"]
    cost_cols = ["Cost", "Amount Spent", "Amount Spent (BRL)", "Amount spent", "Custo", "Spend"]
    conv_cols = ["Conversions", "All conv.", "Leads", "Resultados", "Results", "Website leads", "Leads (form)"]

    c_date = find_col(df, date_cols)
    c_imp  = find_col(df, imp_cols)
    c_clk  = find_col(df, clk_cols)
    c_cost = find_col(df, cost_cols)
    c_conv = find_col(df, conv_cols)

    # joga fora linhas totalmente vazias
    df = df.dropna(how="all")

    # data → mês (AAAA-MM)
    if c_date is None:
        # alguns exports trazem uma coluna "Month"
        c_month = find_col(df, ["Month", "Mês"])
        if c_month is None:
            raise SystemExit(f"[{vendor}] Nenhuma coluna de data encontrada.")
        month_series = df[c_month].astype(str).str.strip()
    else:
        # tenta parse de data
        s = pd.to_datetime(df[c_date], errors="coerce", dayfirst=True, utc=False)
        # se falhar, tenta YYYY-MM-DD literal
        bad = s.isna()
        if bad.any():
            try:
                s2 = pd.to_datetime(df[c_date].astype(str).str[:10], errors="coerce")
                s = s.fillna(s2)
            except Exception:
                pass
        month_series = s.dt.strftime("%Y-%m").fillna(df[c_date].astype(str))

    out = pd.DataFrame({"month": month_series})

    # numéricos
    def get_num(colname):
        if colname is None: return pd.Series(np.nan, index=df.index)
        return df[colname].apply(to_float)

    out["impressions"] = get_num(c_imp)
    out["clicks"]      = get_num(c_clk)
    out["cost"]        = get_num(c_cost)
    out["conversions"] = get_num(c_conv)

    out["vendor"] = vendor
    # remove linhas sem nada
    out = out.dropna(how="all", subset=["impressions","clicks","cost","conversions"])
    return out

def summarize(df_all: pd.DataFrame, client: str) -> tuple[pd.DataFrame, str]:
    # agrega por mês e vendor
    grp = df_all.groupby(["month","vendor"], as_index=False).agg({
        "impressions":"sum","clicks":"sum","cost":"sum","conversions":"sum"
    })
    # métricas derivadas
    grp["ctr_%"] = np.where(grp["impressions"]>0, grp["clicks"]/grp["impressions"]*100, np.nan)
    grp["cpc"]   = np.where(grp["clicks"]>0, grp["cost"]/grp["clicks"], np.nan)
    grp["cpa"]   = np.where(grp["conversions"]>0, grp["cost"]/grp["conversions"], np.nan)

    # texto p/ RAG
    lines = []
    lines.append(f"KPIs de mídia — {client}")
    lines.append("- Valores consolidados por mês e plataforma (Google/Meta).")
    for (m, v), sub in grp.groupby(["month","vendor"]):
        r = sub.iloc[0]
        def fmt(x, casas=2):
            if pd.isna(x): return "-"
            return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X",".")
        lines.append(
            f"{m} | {v}: custo=R$ {fmt(r['cost'])}, impr={fmt(r['impressions'],0)}, cliques={fmt(r['clicks'],0)}, "
            f"conv={fmt(r['conversions'],0)}, CTR={fmt(r['ctr_%'])}%, CPC=R$ {fmt(r['cpc'])}, CPA=R$ {fmt(r['cpa'])}"
        )
    txt = "\n".join(lines)
    return grp, txt

def main():
    ap = argparse.ArgumentParser(description="Gera KPIs de Ads (Google/Meta) a partir de CSV e grava um _kpis.txt para o RAG.")
    ap.add_argument("--client", required=True, help='Ex.: "Start TI"')
    ap.add_argument("--google_csv", help="Caminho do CSV exportado do Google Ads")
    ap.add_argument("--meta_csv", help="Caminho do CSV exportado do Meta Ads (Facebook/Instagram)")
    ap.add_argument("--out", default=None, help="Caminho de saída do TXT (opcional)")
    args = ap.parse_args()

    if not args.google_csv and not args.meta_csv:
        raise SystemExit("Informe ao menos um CSV: --google_csv e/ou --meta_csv")

    frames = []
    if args.google_csv:
        g = read_csv_any(args.google_csv)
        frames.append(normalize_ads(g, "Google Ads"))
    if args.meta_csv:
        m = read_csv_any(args.meta_csv)
        frames.append(normalize_ads(m, "Meta Ads"))

    df_all = pd.concat(frames, ignore_index=True).dropna(how="all")
    if df_all.empty:
        raise SystemExit("Nada para consolidar. Verifique os CSVs.")

    grp, txt = summarize(df_all, args.client)

    os.makedirs("data/derived", exist_ok=True)
    os.makedirs("data/raw", exist_ok=True)
    csv_out = os.path.join("data","derived", f"ads_kpis_{re.sub(r'\\W+','_',args.client)}.csv")
    grp.to_csv(csv_out, index=False)

    out_path = args.out or os.path.join("data","raw", f"ads_kpis_{re.sub(r'\\W+','_',args.client)}.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(txt)

    print("Gerado:")
    print(" -", csv_out)
    print(" -", out_path)
    print("Dica: rode  python .\\ingest_txt.py  para o RAG usar estes KPIs.")

if __name__ == "__main__":
    main()
