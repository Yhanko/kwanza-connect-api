"""
Verificações de Segurança do Sistema Django (System Checks).
KwanzaConnect API — Diretrizes do BNA e Sandbox Regulatório.
"""

from django.core.checks import Error, Warning, register, Tags
from django.conf import settings


@register(Tags.security)
def check_infrastructure_security(app_configs, **kwargs):
    """
    Executa auditoria estática de conformidade e integridade das configurações de segurança do sistema.
    """
    errors = []

    # 1. Validação de SECRET_KEY
    secret_key = getattr(settings, 'SECRET_KEY', '')
    if not settings.DEBUG:
        if not secret_key or len(secret_key) < 32:
            errors.append(
                Error(
                    'SECRET_KEY é excessivamente curta ou insegura em produção (mínimo 32 caracteres exigidos pelo BNA).',
                    id='security.E001',
                    hint='Configure uma chave SECRET_KEY forte no arquivo de ambiente (.env).'
                )
            )
        if 'django-insecure' in secret_key:
            errors.append(
                Error(
                    'SECRET_KEY insegura padrão do Django detectada em ambiente de produção!',
                    id='security.E002',
                    hint='Gere uma SECRET_KEY criptograficamente aleatória com `secrets.token_urlsafe(50)`.'
                )
            )
    else:
        if not secret_key or len(secret_key) < 16:
            errors.append(
                Warning(
                    'SECRET_KEY é curta para desenvolvimento local (recomendado >= 32 caracteres).',
                    id='security.W003',
                    hint='Configure uma chave SECRET_KEY com pelo menos 32 caracteres.'
                )
            )

    # 2. Validação de FIELD_ENCRYPTION_KEY
    encryption_key = getattr(settings, 'FIELD_ENCRYPTION_KEY', None)
    if not settings.DEBUG and not encryption_key:
        errors.append(
            Warning(
                'FIELD_ENCRYPTION_KEY explícita não configurada no .env (utilizando derivação HKDF da SECRET_KEY).',
                id='security.W004',
                hint='Para isolamento criptográfico em produção, defina uma chave FIELD_ENCRYPTION_KEY dedicada de 32 bytes base64 no .env.'
            )
        )
    elif encryption_key and len(encryption_key) < 32:
        errors.append(
            Error(
                'FIELD_ENCRYPTION_KEY configurada é menor que 32 caracteres.',
                id='security.E003',
                hint='Gere uma chave segura de 32 bytes base64 no .env.'
            )
        )

    # 3. Validação do Algoritmo de Hashing de Senhas (Argon2)
    hashers = getattr(settings, 'PASSWORD_HASHERS', [])
    if not hashers or 'Argon2PasswordHasher' not in hashers[0]:
        errors.append(
            Warning(
                'Argon2id não está configurado como o hasher primário de senhas bancárias.',
                id='security.W001',
                hint="Configure PASSWORD_HASHERS = ['django.contrib.auth.hashers.Argon2PasswordHasher', ...]"
            )
        )

    # 4. Validação do Middleware de Cabeçalhos de Segurança
    middleware = getattr(settings, 'MIDDLEWARE', [])
    if 'security.middleware.FinancialSecurityHeadersMiddleware' not in middleware:
        errors.append(
            Error(
                'FinancialSecurityHeadersMiddleware não está registrado no MIDDLEWARE do Django.',
                id='security.E004',
                hint="Adicione 'security.middleware.FinancialSecurityHeadersMiddleware' aos settings."
            )
        )

    # 5. Validação de Cookies e CORS em Produção
    if not settings.DEBUG:
        if getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', False):
            errors.append(
                Error(
                    'CORS_ALLOW_ALL_ORIGINS está ativado em ambiente de produção!',
                    id='security.E005',
                    hint='Restrinja as origens CORS apenas aos domínios autorizados do KwanzaConnect.'
                )
            )

        if not getattr(settings, 'SESSION_COOKIE_SECURE', False):
            errors.append(
                Warning(
                    'SESSION_COOKIE_SECURE deve ser True em produção (HTTPS obrigatório).',
                    id='security.W002'
                )
            )

    return errors
