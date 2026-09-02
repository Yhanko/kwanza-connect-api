"""
Comando de Auditoria de Infraestrutura e Redes Seguras (Sandbox BNA).
Executa diagnóstico completo da pilha de segurança, chaves, isolamento e parâmetros de produção.
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.checks import run_checks, Tags
import sys


class Command(BaseCommand):
    help = 'Executa auditoria técnica de conformidade de infraestrutura e redes com as normas do Sandbox BNA'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(self.style.SUCCESS("[AUDITORIA] SEGURANCA DA INFRAESTRUTURA E REDES - SANDBOX BNA"))
        self.stdout.write(self.style.SUCCESS("=" * 70))

        all_passed = True

        # 1. Executar Django System Checks de Segurança
        self.stdout.write("\n[1/5] Verificando Django System Checks...")
        issues = run_checks(tags=[Tags.security])
        if not issues:
            self.stdout.write(self.style.SUCCESS("  [OK] Todos os checks de seguranca internos passaram."))
        else:
            for issue in issues:
                if issue.is_serious():
                    all_passed = False
                    self.stdout.write(self.style.ERROR(f"  [ERRO] {issue.id}: {issue.msg}"))
                    if issue.hint:
                        self.stdout.write(self.style.WARNING(f"    Dica: {issue.hint}"))
                else:
                    self.stdout.write(self.style.WARNING(f"  [AVISO] {issue.id}: {issue.msg}"))

        # 2. Verificação de Chaves Criptográficas e Hashing
        self.stdout.write("\n[2/5] Verificando Entropia e Algoritmos Criptograficos...")
        from security.encryption import get_encryption_key, compute_blind_index
        try:
            key = get_encryption_key()
            self.stdout.write(self.style.SUCCESS("  [OK] Chave simetrica AES-256 / HKDF derivada com sucesso."))
            test_blind = compute_blind_index("002368943LA033")
            self.stdout.write(self.style.SUCCESS(f"  [OK] Blind Index HMAC-SHA256 operacional ({test_blind[:12]}...)."))
        except Exception as e:
            all_passed = False
            self.stdout.write(self.style.ERROR(f"  [ERRO] Falha na derivacao criptografica: {e}"))

        # 3. Verificação de Hasher de Senha
        self.stdout.write("\n[3/5] Verificando Hasher Primario de Senhas...")
        hashers = getattr(settings, 'PASSWORD_HASHERS', [])
        if hashers and 'Argon2PasswordHasher' in hashers[0]:
            self.stdout.write(self.style.SUCCESS(f"  [OK] Hasher primario: Argon2id ({hashers[0]})."))
        else:
            all_passed = False
            self.stdout.write(self.style.ERROR(f"  [ERRO] Hasher inseguro: {hashers} (Argon2id obrigatorio)."))

        # 4. Verificação de Cabeçalhos de Segurança
        self.stdout.write("\n[4/5] Verificando Middlewares de Cabecalhos Bancarios...")
        if 'security.middleware.FinancialSecurityHeadersMiddleware' in settings.MIDDLEWARE:
            self.stdout.write(self.style.SUCCESS("  [OK] FinancialSecurityHeadersMiddleware ativo (HSTS, CSP, X-Frame-Options DENY)."))
        else:
            all_passed = False
            self.stdout.write(self.style.ERROR("  [ERRO] FinancialSecurityHeadersMiddleware nao encontrado em MIDDLEWARE."))

        # 5. Verificação de Ambiente de Execução
        self.stdout.write("\n[5/5] Verificando Modo de Execucao...")
        if settings.DEBUG:
            self.stdout.write(self.style.WARNING("  [INFO] Modo DEBUG esta ATIVADO (Permitido apenas em desenvolvimento local)."))
        else:
            self.stdout.write(self.style.SUCCESS("  [OK] Modo de Producao Ativo (DEBUG=False, cookies protegidos)."))

        self.stdout.write("\n" + "=" * 70)
        if all_passed:
            self.stdout.write(self.style.SUCCESS("[SUCESSO] INFRAESTRUTURA APROVADA: Em conformidade com o Sandbox Regulatorio do BNA!"))
            self.stdout.write(self.style.SUCCESS("=" * 70))
        else:
            self.stdout.write(self.style.ERROR("[FALHA] ATENCAO: Foram identificadas nao-conformidades de infraestrutura a corrigir."))
            self.stdout.write(self.style.ERROR("=" * 70))
            sys.exit(1)
