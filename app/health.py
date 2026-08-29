from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

def health_check(request):
    """
    Endpoint de Health Check para Docker, Kubernetes, Nginx e Load Balancers.
    Retorna 200 OK quando o serviço está operacional.
    """
    status = {
        "status": "healthy",
        "service": "kwanza-connect-api",
        "database": "unknown",
        "cache": "unknown",
    }
    status_code = 200

    # Teste de conexão com o banco de dados
    try:
        connection.ensure_connection()
        status["database"] = "connected"
    except Exception as exc:
        logger.error(f"Database health check failed: {exc}")
        status["database"] = "unreachable"
        status["status"] = "degraded"
        status_code = 503

    # Teste de conexão com o Redis/Cache
    try:
        cache.set("health_check_ping", "pong", timeout=5)
        if cache.get("health_check_ping") == "pong":
            status["cache"] = "connected"
        else:
            status["cache"] = "degraded"
    except Exception as exc:
        logger.warning(f"Cache health check warning: {exc}")
        status["cache"] = "unreachable"

    return JsonResponse(status, status=status_code)
