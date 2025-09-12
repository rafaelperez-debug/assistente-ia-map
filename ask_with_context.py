from __future__ import annotations
import argparse, os

# Chroma compat
try:
    from chromadb import PersistentClient
    client = PersistentClient(path=".chromadb")
except Exception:
    from chromadb import Client
    from chromadb.config import Settings
    client = Client(Settings(persist_directory=".chromadb"))

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise SystemExit("Defina GOOGLE_API_KEY no .env")
genai.configure(api_key=api_key)

col = client.get_or_create_collection("workspace_knowledge")

def ask(q: str, k: int = 4) -> str:
    hits = col.query(query_texts=[q], n_results=k)
    docs = hits.get("documents", [[]])[0]
    metas = hits.get("metadatas", [[]])[0]

    contexto = []
    cites = []
    for d, m in zip(docs, metas):
        src = os.path.basename(m.get("source",""))
        ch = m.get("chunk","?")
        contexto.append(f"[{src} | chunk {ch}]\n{d}\n")
        cites.append(f"[{src} | chunk {ch}]")
    ctx = "\n\n".join(contexto) if contexto else "[sem contexto]"

    prompt = f"""Responda de forma objetiva usando apenas o contexto abaixo. 
Se a resposta não estiver no contexto, diga que não há informação suficiente.
Mostre no final as fontes entre colchetes.

Contexto:
{ctx}

Pergunta:
{q}

Responda:"""

    model = genai.GenerativeModel("gemini-1.5-flash")
    resp = model.generate_content(prompt)
    ans = resp.text.strip()
    if cites:
        ans += "\n\nFontes: " + " | ".join(cites)
    return ans

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--q", required=True, help="Pergunta")
    args = ap.parse_args()
    print(ask(args.q))
