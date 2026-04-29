# Base estável Python 3.7
FROM python:3.7-slim

# Diretório de trabalho
WORKDIR /app

# Instala ferramentas de compilação (gfortran é essencial para o core do Xfoil no Linux)
RUN apt-get update && apt-get install -y \
    build-essential \
    gfortran \
    g++ \
    libatlas-base-dev \
    && rm -rf /var/lib/apt/lists/*

# Força o uso dos compiladores instalados
ENV CC=gcc
ENV CXX=g++

# Copia e instala as dependências
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir numpy==1.21.5
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o conteúdo da sua pasta 'app' para a raiz do container
COPY app/ .

# Comando padrão ao iniciar o container
CMD ["python", "batch_xfoil_to_mat.py"]