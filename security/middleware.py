"""
Middleware de Cabeçalhos de Segurança Financeira e Proteção em Trânsito.
KwanzaConnect API — Diretrizes do BNA, OWASP API Security e Sandbox Regulatório.
"""

class FinancialSecurityHeadersMiddleware:
    """
    Injeta cabeçalhos HTTP de segurança de nível bancário em todas as respostas da API,
    garantindo proteção em trânsito contra MITM, Clickjacking, MIME-sniffing, XSS e vazamento de contexto.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # 1. HSTS (HTTP Strict Transport Security) - 1 ano com subdomínios e preload
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'

        # 2. Prevenção de MIME Sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'

        # 3. Prevenção de Clickjacking (Proibição total de iframes)
        response.headers['X-Frame-Options'] = 'DENY'

        # 4. Política de Referência Estrita (Não expõe parâmetros confidenciais no header Referer)
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # 5. Proteção XSS para navegadores legados
        response.headers['X-XSS-Protection'] = '1; mode=block'

        # 6. Permissions Policy (Restringe acesso a APIs do cliente)
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=(), payment=()'

        # 7. Isolamento de Contexto (Cross-Origin-Opener-Policy)
        response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'

        # 8. Content-Security-Policy estrito para APIs REST
        if 'Content-Security-Policy' not in response.headers:
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "frame-ancestors 'none'; "
                "object-src 'none'; "
                "base-uri 'self';"
            )

        return response
