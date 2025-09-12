# Assistente de Dados IA — Guia de Implantação (cliente novo)

## 1) Pré-requisitos
- Python 3.10+  
- `credentials.json` (Service Account com acesso de leitura ao Drive do cliente)  
- Chave do Google AI Studio (Gemini) para relatórios: `GOOGLE_API_KEY`

## 2) Instalação (primeira vez)
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt  # ou: pip install google-generativeai google-api-python-client google-auth google-auth-oauthlib chromadb pandas openpyxl
