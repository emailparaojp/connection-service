# =============================================================
# Dockerfile de produção — connection-service
# Imagem: python:3.12-slim
# Porta:  8080
# =============================================================

FROM python:3.12-slim

# --- Metadados ---
LABEL maintainer="connection-service"
LABEL description="Serviço centralizado de conexões Oracle criptografadas"
LABEL version="1.0.0"

# --- Variáveis de build ---
ARG APP_HOME=/app
ARG APP_USER=appuser
ARG APP_GROUP=appgroup

# --- Variáveis de ambiente do container ---
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100

# --- Dependências de sistema ---
# Instala apenas o necessário; remove cache do apt ao final
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# --- Usuário não-root (segurança) ---
RUN groupadd --system ${APP_GROUP} \
    && useradd --system --gid ${APP_GROUP} --home ${APP_HOME} --shell /bin/bash ${APP_USER}

# --- Diretório de trabalho ---
WORKDIR ${APP_HOME}

# --- Dependências Python ---
# Copia apenas o requirements primeiro para aproveitar o cache de camadas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Código da aplicação ---
COPY app/ ./app/

# --- Diretório de logs ---
RUN mkdir -p logs && chown -R ${APP_USER}:${APP_GROUP} ${APP_HOME}

# --- Troca para usuário não-root ---
USER ${APP_USER}

# --- Porta exposta ---
EXPOSE 8080

# --- Health check nativo do Docker ---
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# --- Comando de inicialização ---
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--workers", "1", \
     "--log-level", "warning", \
     "--no-access-log"]
