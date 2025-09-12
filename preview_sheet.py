from __future__ import annotations
import argparse, pandas as pd, re

CANDS = {
    "data": ["data","dia","date","mês","mes"],
    "leads": ["lead","leads"],
    "gasto": ["gasto","invest","custo","spend"],
    "clicks": ["clique","click"],
    "impr": ["impre","impres","impressions"],
    "conv": ["convers","conv."]
}

def suggest(cols):
    low = [c.lower() for c in cols]
    out = {}
    for key, pats in CANDS.items():
        hit = None
        for p in pats:
            for i,c in enumerate(low):
                if p in c:
                    hit = cols[i]; break
            if hit: break
        out[key] = hit
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    args = ap.parse_args()

    xls = pd.ExcelFile(args.path)
    print("Sheets:", xls.sheet_names)
    for sh in xls.sheet_names:
        df = pd.read_excel(args.path, sheet_name=sh)
        print(f"\n=== Sheet: {sh} | shape={df.shape} ===")
        print("Colunas:", list(df.columns))
        print("Sugestões:", suggest(list(df.columns)))
        # Mostra até 8 linhas para prévia
        with pd.option_context("display.max_columns", None, "display.width", 200):
            print(df.head(8))
