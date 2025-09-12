import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise SystemExit("Defina GOOGLE_API_KEY no arquivo .env")

genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-1.5-flash")
resp = model.generate_content("Responda apenas: OK")
print(resp.text.strip())
