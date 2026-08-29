# ========================================================
# 1. Builder Stage: Instalação e compilação de dependências
# ========================================================
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instala ferramentas necessárias para compilar pacotes C (psycopg2, argon2, pillow, cryptography)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências no diretório local do usuário (/root/.local)
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ========================================================
# 2. Runner Stage: Imagem de produção enxuta e segura
# ========================================================
FROM python:3.12-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/django/.local/bin:$PATH"

WORKDIR /app

# Instala apenas as bibliotecas de runtime necessárias (sem compiladores)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Criação de grupo e utilizador não-root (Segurança: Principle of Least Privilege)
RUN groupadd -g 1000 django && \
    useradd -u 1000 -g django -d /home/django -m -s /bin/bash django

# Copia as dependências Python compiladas no estágio builder
COPY --from=builder /root/.local /home/django/.local

# Prepara diretórios para arquivos estáticos e media com permissões adequadas
RUN mkdir -p /app/staticfiles /app/media && \
    chown -R django:django /app /home/django/.local

# Copia o código da aplicação
COPY --chown=django:django . .

# Copia e configura o script de inicialização (Entrypoint)
COPY --chown=django:django docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Alterna para o utilizador sem privilégios
USER django

# Porta padrão de execução
EXPOSE 8000

# Verificação contínua de saúde do container
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health/ || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "app.asgi:application"]