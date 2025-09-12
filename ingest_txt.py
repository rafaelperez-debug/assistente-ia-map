from __future__ import annotations
import os, glob, textwrap

# Chroma compat
try:
    from chromadb import PersistentClient
    client = PersistentClient(path=".chromadb")
except Exception:
    from chromadb import Client
    from chromadb.config import Settings
    client = Client(Settings(persist_directory=".chromadb"))

COLLECTION = "workspace_knowledge"

def chunk(text: str, size: int = 1200, overlap: int = 150):
    # quebra por parágrafos e faz janela deslizante
    parts = []
    buf = ""
    for para in text.split("\n\n"):
        if len(buf) + len(para) + 2 <= size:
            buf += (para + "\n\n")
        else:
            if buf:
                parts.append(buf.strip())
            buf = para + "\n\n"
    if buf:
        parts.append(buf.strip())
    # aplica overlap simples se necessário
    if not parts: 
        return []
    if overlap > 0 and len(parts) > 1:
        with_overlap = []
        for i, p in enumerate(parts):
            prev_tail = parts[i-1][-overlap:] if i > 0 else ""
            with_overlap.append((prev_tail + "\n" + p).strip())
        parts = with_overlap
    return parts

# recria coleção para evitar duplicados
try:
    client.delete_collection(COLLECTION)
except Exception:
    pass
col = client.get_or_create_collection(COLLECTION)

os.makedirs("data/raw", exist_ok=True)
paths = glob.glob("data/raw/*.txt")

docs, ids, metas = [], [], []
for p in paths:
    base_id = os.path.splitext(os.path.basename(p))[0]
    with open(p, "r", encoding="utf-8", errors="ignore") as f:
        txt = f.read()
    chunks = chunk(txt)
    for idx, ck in enumerate(chunks):
        docs.append(ck)
        ids.append(f"{base_id}::chunk-{idx:03d}")
        metas.append({"source": p, "chunk": idx})

if docs:
    col.add(documents=docs, ids=ids, metadatas=metas)
    print(f"Ingeridos {len(docs)} chunks a partir de {len(paths)} arquivo(s).")
else:
    print("Nenhum .txt em data/raw para ingerir.")
