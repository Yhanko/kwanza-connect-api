"""
Classes avançadas de Rate Limiting (Throttling) para a KwanzaConnect API.
Conforme as exigências de Cibersegurança e Gestão de Riscos do BNA (Banco Nacional de Angola).
"""
from rest_framework.throttling import SimpleRateThrottle, AnonRateThrottle, UserRateThrottle
import logging

logger = logging.getLogger('security')

def get_client_ip(request) -> str:
    """
    Extrai o endereço IP real do cliente com suporte a proxies reversos (Traefik, Nginx, Cloudflare).
    Evita spoofing selecionando o primeiro IP legítimo do cabeçalho X-Forwarded-For.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


class ReliableAnonRateThrottle(AnonRateThrottle):
    """
    Throttling para visitantes não autenticados com resolução segura de IP.
    """
    scope = 'anon'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return None  # Não aplica a utilizadores autenticados

        ident = get_client_ip(request)
        if not ident:
            return None
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class KYCTieredUserRateThrottle(UserRateThrottle):
    """
    Throttling proporcional ao nível de risco e validação KYC do utilizador:
    - user_admin: 300 requisições/minuto (Operadores/Administradores)
    - user_verified: 180 requisições/minuto (Utilizadores com KYC aprovado)
    - user_unverified: 60 requisições/minuto (Utilizadores sem KYC ou pendentes)
    - user: 120 requisições/minuto (Fallback padrão)
    """
    scope = 'user'

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None

        # Determina o escopo com base no estado e privilégios da conta
        if getattr(request.user, 'is_staff', False) or getattr(request.user, 'is_superuser', False):
            self.scope = 'user_admin'
        elif getattr(request.user, 'is_verified', False):
            self.scope = 'user_verified'
        else:
            self.scope = 'user_unverified'

        # Recalcula dinamicamente a taxa e duração para o escopo atribuído
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)

        ident = str(request.user.pk)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class AuthBruteForceThrottle(SimpleRateThrottle):
    """
    Throttling específico para rotas de autenticação (Login, Registo, Password Reset).
    Limita as tentativas combinando IP + E-mail (quando fornecido no corpo do pedido)
    para mitigar ataques de força bruta direcionados ou distribuídos.
    """
    scope = 'auth_login'

    def get_cache_key(self, request, view):
        ip = get_client_ip(request)
        email = ''
        if hasattr(request, 'data') and isinstance(request.data, dict):
            email = str(request.data.get('email', '')).lower().strip()
        
        ident = f"{ip}_{email}" if email else ip
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }
