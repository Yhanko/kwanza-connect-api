# ========================================================
# 1. Builder Stage: Instalação e compilação de dependências
# ========================================================
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instala ferramentas necessárias para compilação C
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Cria um virtualenv isolado em /opt/venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ========================================================
# 2. Runner Stage: Imagem de produção enxuta e segura
# ========================================================
FROM python:3.12-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Instala apenas as bibliotecas de runtime necessárias
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Criação de grupo e utilizador não-root
RUN groupadd -g 1000 django && \
    useradd -u 1000 -g django -d /home/django -m -s /bin/bash django

# Copia o virtualenv completo com todas as dependências e binários (daphne, celery, etc)
COPY --from=builder /opt/venv /opt/venv

# Cria diretórios para arquivos estáticos e media com permissões
RUN mkdir -p /app/staticfiles /app/media && \
    chown -R django:django /app /opt/venv

# Copia o código da aplicação
COPY --chown=django:django . .

# Copia o script de entrypoint e converte quebras de linha Windows (CRLF para LF)
COPY --chown=django:django docker/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && \
    chmod +x /entrypoint.sh

# Alterna para o utilizador sem privilégios
USER django

EXPOSE 8000

# Verificação contínua de saúde do container
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health/ || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "app.asgi:application"]