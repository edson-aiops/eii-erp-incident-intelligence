# Estágio 1: Builder (instala dependências)
FROM python:3.11-slim as builder

WORKDIR /app

# Instalar dependências de build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Estágio 2: Runtime (imagem final leve)
FROM python:3.11-slim

WORKDIR /app

# Copiar apenas o necessário do builder
COPY --from=builder /root/.local /root/.local
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages

# Adicionar local bin ao PATH
ENV PATH=/root/.local/bin:$PATH

# Copiar código do projeto
COPY . .

# Health check para orquestradores
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:7860/api/health || exit 1

# Variáveis de ambiente seguras
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    GRADIO_ANALYTICS_ENABLED=false

# Porta do Gradio
EXPOSE 7860

# Comando de inicialização
CMD ["python", "app_hf.py"]
