# Usa uma imagem oficial e leve do Python
FROM python:3.12-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Instala as dependências primeiro (aproveita o cache de camadas do Docker)
COPY requirements.txt . 
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código do projeto
COPY . . 

# Expoe a porta padrao do Streamlit
EXPOSE 8501

# Comando para rodar a app quando o container subir
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]