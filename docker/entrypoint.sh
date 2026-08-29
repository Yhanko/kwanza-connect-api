#!/bin/bash
set -e

# ==============================================================================
# 1. Verificação de Conexão com a Base de Dados
# ==============================================================================
if [ -n "$DB_HOST" ]; then
  DB_PORT="${DB_PORT:-5432}"
  echo "==> Aguardando PostgreSQL em $DB_HOST:$DB_PORT..."
  
  MAX_RETRIES=30
  COUNT=0
  until nc -z "$DB_HOST" "$DB_PORT" || [ $COUNT -eq $MAX_RETRIES ]; do
    sleep 1
    COUNT=$((COUNT + 1))
  done

  if [ $COUNT -eq $MAX_RETRIES ]; then
    echo "==> [ERRO] Tempo limite esgotado ao tentar conectar ao PostgreSQL."
    exit 1
  fi
  echo "==> PostgreSQL conectado com sucesso."
fi

# ==============================================================================
# 2. Verificação de Conexão com Redis (se REDIS_HOST estiver definido)
# ==============================================================================
if [ -n "$REDIS_HOST" ]; then
  REDIS_PORT="${REDIS_PORT:-6379}"
  echo "==> Aguardando Redis em $REDIS_HOST:$REDIS_PORT..."
  MAX_RETRIES=30
  COUNT=0
  until nc -z "$REDIS_HOST" "$REDIS_PORT" || [ $COUNT -eq $MAX_RETRIES ]; do
    sleep 1
    COUNT=$((COUNT + 1))
  done
  echo "==> Redis disponível."
fi

# ==============================================================================
# 3. Migrações, Estáticos e Setup Inicial (Apenas no Container Web Principal)
# ==============================================================================
IS_WEB_SERVICE=false
if [ "$1" = "daphne" ] || [ "$1" = "gunicorn" ] || [ "$1" = "python" -a "$2" = "manage.py" -a "$3" = "runserver" ]; then
  IS_WEB_SERVICE=true
fi

if [ "$IS_WEB_SERVICE" = true ]; then
  echo "==> [WEB SETUP] Aplicando migrações de base de dados..."
  python manage.py migrate --noinput

  echo "==> [WEB SETUP] Coletando arquivos estáticos..."
  python manage.py collectstatic --noinput --clear

  # Criação segura e condicional de Superuser
  if [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "==> [WEB SETUP] Verificando existência do Superuser..."
    python manage.py shell -c "
import os
from django.contrib.auth import get_user_model

User = get_user_model()
email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

if email and password:
    if not User.objects.filter(email=email).exists():
        User.objects.create_superuser(
            email=email,
            password=password,
            full_name='Admin'
        )
        print(f'==> Superuser {email} criado com sucesso.')
    else:
        print(f'==> Superuser {email} já existe.')
"
  fi
fi

# ==============================================================================
# 4. Execução do Comando Principal do Container
# ==============================================================================
echo "==> Iniciando comando: $@"
exec "$@"