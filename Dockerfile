# Imagem base do Python
FROM python:3.11-slim

# Definir diretório de trabalho
WORKDIR /app

# Copiar requisitos
COPY requirements.txt .

# Instalar dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o resto do código
COPY . .

# Expor a porta usada pelo Uvicorn
EXPOSE 8080

# Comando de inicialização
CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8080"]
