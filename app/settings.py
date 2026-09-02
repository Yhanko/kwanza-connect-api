from pathlib import Path
from datetime import timedelta
from decouple import config

# ─────────────────────────────────────────────
#  Paths
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# ── Security & Hardening ───────────────────────────────────────────
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = [h.strip().split('#')[0].strip() for h in config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',') if h.strip().split('#')[0].strip()]

# Cabeçalhos HTTP de Segurança & Hardening:
# - SECURE_BROWSER_XSS_FILTER: Ativa o filtro XSS do navegador.
# - SECURE_CONTENT_TYPE_NOSNIFF: Evita vulnerabilidades de MIME-type sniffing.
# - X_FRAME_OPTIONS = 'DENY': Previne ataques de Clickjacking ao proibir a inclusão em iframes.
# - SECURE_REFERRER_POLICY: Restringe a exposição de dados sensíveis no cabeçalho Referer HTTP.
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'same-origin'

# Suporte a Proxy Reverso (Traefik / Nginx / Dokploy)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# Configuração de Sessão e CSRF Seguros (HTTPS em produção):
if not DEBUG:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# ─────────────────────────────────────────────
#  Applications
# ─────────────────────────────────────────────
INSTALLED_APPS = [
    # Django built-ins
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'django_extensions',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'drf_spectacular',
    'django_filters',
    'channels',
    'django_celery_beat',

    # Local apps
    'users',
    'offers',
    'chat',
    'notifications',
    'rates',
    'transactions',
    'security',
    'audit',
]

# ─────────────────────────────────────────────
#  Middleware (CorsMiddleware DEVE ser o primeiro para interceptar OPTIONS preflight)
# ─────────────────────────────────────────────
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ─────────────────────────────────────────────
#  CORS
# ─────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = config('CORS_ALLOW_ALL_ORIGINS', default=True, cast=bool)
CORS_ALLOWED_ORIGINS = [
    origin.strip().split('#')[0].strip()
    for origin in config(
        'CORS_ALLOWED_ORIGINS',
        default='http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,https://kwanza-connect-frontend.vercel.app'
    ).split(',')
    if origin.strip().split('#')[0].strip()
]
CORS_ALLOW_CREDENTIALS = True

# Cabeçalhos personalizados permitidos
from corsheaders.defaults import default_headers, default_methods
CORS_ALLOW_HEADERS = list(default_headers) + [
    'x-api-key',
    'x-request-id',
    'x-content-type-options',
]
CORS_ALLOW_METHODS = list(default_methods) + ['OPTIONS']
CORS_PREFLIGHT_MAX_AGE = 86400

# ─────────────────────────────────────────────
#  URLs & Templates
# ─────────────────────────────────────────────
ROOT_URLCONF = 'app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'app.wsgi.application'
ASGI_APPLICATION   = 'app.asgi.application'

import dj_database_url

# ─────────────────────────────────────────────
#  Database
# ─────────────────────────────────────────────
DATABASE_URL = config('DATABASE_URL', default='postgres://postgres:postgres@127.0.0.1:5432/kwanza_connect').split('#')[0].strip()

DATABASES = {
    'default': dj_database_url.config(
        default=DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# ─────────────────────────────────────────────
#  Cache (Redis)
# ─────────────────────────────────────────────
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0').split('#')[0].strip()

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
    }
}

# ─────────────────────────────────────────────
#  Django Channels (WebSocket)
# ─────────────────────────────────────────────
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {'hosts': [REDIS_URL]},
    }
}

# ─────────────────────────────────────────────
#  Django REST Framework
# ─────────────────────────────────────────────
REST_FRAMEWORK = {
    # INTEGRAÇÃO JWT - CLASSE DE AUTENTICAÇÃO PADRÃO:
    # O Django REST Framework intercepta cada requisição HTTP recebida e valida o cabeçalho 'Authorization: Bearer <access_token>'.
    # Se o token JWT for válido e não estiver expirado, o utilizador é autenticado automaticamente em request.user.
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'security.permissions.HasAPIKey',
        'rest_framework.permissions.IsAuthenticated',
    ),
    # PROTEÇÃO DE RATE LIMITING (THROTTLING) AVANÇADO — CONFORMIDADE BNA:
    # Controla a frequência de requisições por cliente para evitar ataques DoS, força bruta e abusos.
    # - ReliableAnonRateThrottle: Limita visitantes não autenticados com resolução segura de IP contra spoofing.
    # - KYCTieredUserRateThrottle: Limita utilizadores autenticados com taxas dinâmicas e proporcionais ao nível de KYC.
    # - ScopedRateThrottle: Limita endpoints específicos conforme o 'throttle_scope' configurado na View.
    # Requisições que excedam estes limites recebem HTTP 429 (Too Many Requests), cabeçalho Retry-After e auditoria automática.
    'DEFAULT_THROTTLE_CLASSES': [
        'security.throttles.ReliableAnonRateThrottle',
        'security.throttles.KYCTieredUserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        # Limites globais por nível de conta e risco KYC (Sandbox BNA)
        'anon': '30/minute',
        'user_unverified': '60/minute',     # Utilizadores sem KYC aprovado
        'user_verified': '180/minute',      # Utilizadores com KYC aprovado
        'user_admin': '300/minute',         # Administradores do sistema
        'user': '120/minute',               # Fallback padrão

        # Limites específicos por escopo (Segurança & Requisitos BNA)
        'auth_login': '5/minute',             # Previne força bruta / credential stuffing no login
        'auth_2fa': '5/minute',               # Validação de segundo fator 2FA / Backup codes
        'auth_register': '5/minute',          # Previne criação em massa de contas falsas
        'auth_password_reset': '3/minute',    # Previne spam de redefinição de senhas / emails
        'auth_verify_email': '10/minute',     # Validação de token de email
        'admin_auth': '5/minute',             # Login e registo de administração com limite estrito
        'token_refresh': '30/minute',         # Renovação de access tokens JWT
        'kyc_upload': '5/minute',             # Upload de documentos pesados de identificação
        'offers_create': '20/minute',         # Criação de ofertas no livro de ordens P2P
        'offers_interest': '30/minute',       # Manifestação de interesse em ofertas
        'transactions': '20/minute',          # Confirmação e avaliação de transações
        'user_reports': '5/minute',           # Submissão de denúncias/moderação
        'rates_public': '60/minute',          # Consulta e conversão pública de taxas de câmbio
    },

    'DEFAULT_PAGINATION_CLASS': 'app.pagination.StandardPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'app.exceptions.handle_global_errors',
}

# ─────────────────────────────────────────────
#  JWT - PARÂMETROS E REGRAS DE SEGURANÇA DOS TOKENS
# ─────────────────────────────────────────────
# Configurações do SimpleJWT:
# - ACCESS_TOKEN_LIFETIME: Validade do token de acesso (60 minutos por padrão). Usado para autenticar requisições.
# - REFRESH_TOKEN_LIFETIME: Validade do token de renovação (7 dias). Usado para obter novo access token.
# - ROTATE_REFRESH_TOKENS: Quando True, ao renovar o access token, gera também um novo refresh token.
# - BLACKLIST_AFTER_ROTATION: Quando True, o refresh token antigo é invalidado na base de dados (tabela BlacklistedToken).
# - AUTH_HEADER_TYPES: Prefixo do cabeçalho de autorização. Requer 'Authorization: Bearer <token>'.
# - UPDATE_LAST_LOGIN: Atualiza o campo last_login do utilizador na BD ao emitir token.
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(minutes=config('JWT_ACCESS_MINUTES', default=60, cast=int)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=config('JWT_REFRESH_DAYS', default=7, cast=int)),
    'ROTATE_REFRESH_TOKENS':  True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'UPDATE_LAST_LOGIN': True,
}

# ─────────────────────────────────────────────
#  OpenAPI / Spectacular
# ─────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    'TITLE': 'KwanzaConnect API',
    'DESCRIPTION': 'Plataforma de troca de moedas entre utilizadores.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SERVE_PERMISSIONS': ['rest_framework.permissions.AllowAny'],
    'SERVE_AUTHENTICATION': [],
}

# ─────────────────────────────────────────────
#  Celery
# ─────────────────────────────────────────────
CELERY_BROKER_URL    = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TIMEZONE      = 'Africa/Luanda'
CELERY_TASK_SERIALIZER   = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT    = ['json']
CELERY_IMPORTS           = ['rates.infra.tasks']

from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'fetch-exchange-rates': {
        'task':     'rates.infra.tasks.fetch_rates',
        'schedule': crontab(minute='*/5'),
    },
    'expire-old-offers': {
        'task':     'offers.tasks.expire_old_offers',
        'schedule': crontab(minute=0),
    },
    'cleanup-old-audit-logs': {
        'task':     'audit.tasks.cleanup_old_audit_logs',
        'schedule': crontab(hour=2, minute=0),
    },
}

# ─────────────────────────────────────────────
#  Email
# ─────────────────────────────────────────────
EMAIL_BACKEND       = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST          = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT          = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS       = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_USE_SSL       = config('EMAIL_USE_SSL', default=False, cast=bool)
EMAIL_HOST_USER     = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL  = config('DEFAULT_FROM_EMAIL', default='KwanzaConnect <noreply@kwanzaconnect.ao>')

# ─────────────────────────────────────────────
#  Exchange Rate & Geolocation APIs
# ─────────────────────────────────────────────
EXCHANGE_RATE_API_KEY = config('EXCHANGE_RATE_API_KEY', default='')
EXCHANGE_RATE_BASE_URL = config(
    'EXCHANGE_RATE_BASE_URL',
    default='https://open.er-api.com/v6/latest'
)
EXCHANGE_RATE_TIMEOUT = config('EXCHANGE_RATE_TIMEOUT', default=15, cast=int)
GEOLOCATION_TIMEOUT    = config('GEOLOCATION_TIMEOUT', default=15, cast=int)


# ─────────────────────────────────────────────
#  Auth & i18n
# ─────────────────────────────────────────────
# ── Autenticação & Hashing ──────────────────────────────────────────
AUTH_USER_MODEL = 'users.User'

# ESTRATÉGIA DE CRIPTOGRAFIA E HASHING DE SENHAS DO UTILIZADOR:
# Configura os algoritmos de hashing de senhas. O Django utiliza o primeiro hasher (Argon2) para novas senhas.
# - Argon2PasswordHasher: Algoritmo vencedor da Password Hashing Competition (PHC), padrão ouro moderno
#   que utiliza Argon2id com alta resistência de memória, salt automático individual e parâmetros de custo de CPU.
# - PBKDF2 / BCrypt: Fornecidos como fallbacks seguros e para compatibilidade na verificação.
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'pt-pt'
TIME_ZONE     = 'Africa/Luanda'
USE_I18N      = True
USE_TZ        = True

# ─────────────────────────────────────────────
#  Static & Media
# ─────────────────────────────────────────────
STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL   = '/media/'
MEDIA_ROOT  = BASE_DIR / 'media'
SITE_URL    = config('SITE_URL', default='http://localhost:8000')

# ─────────────────────────────────────────────
#  Admin Secret Key
# ─────────────────────────────────────────────
ADMIN_SECRET_KEY = config('ADMIN_SECRET', default=config('ADMIN_SECRET_KEY', default='KWANZA_ADMIN_SECURE_2026'))


# ─────────────────────────────────────────────
#  Cloudinary (Media Storage)
# ─────────────────────────────────────────────
import cloudinary
import cloudinary.uploader
import cloudinary.api

cloudinary.config(
    cloud_name = config('CLOUDINARY_CLOUD_NAME', default='').split('#')[0].strip(),
    api_key    = config('CLOUDINARY_API_KEY', default='').split('#')[0].strip(),
    api_secret = config('CLOUDINARY_API_SECRET', default='').split('#')[0].strip(),
    secure     = True
)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
