from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from .infra.models import AuditLog

logger = logging.getLogger(__name__)

@shared_task
def cleanup_old_audit_logs():
    """
    Deleta registos de auditoria (AuditLog) mais antigos do que 6 anos.
    Em conformidade com os requisitos regulatórios do BNA e Lei n.º 40/20 (retenção mínima de 5 a 6 anos).
    Executado como uma tarefa periódica via Celery Beat (configurado em settings.py).
    """
    # 6 anos = 6 * 365 dias = 2190 dias
    cutoff_date = timezone.now() - timedelta(days=6 * 365)
    deleted_count, _ = AuditLog.objects.filter(timestamp__lt=cutoff_date).delete()
    
    logger.info(f"Limpeza de AuditLog: {deleted_count} registos apagados (anteriores a {cutoff_date}).")
    
    return f"Apagados {deleted_count} logs."


@shared_task
def log_audit_event(
    user_id=None,
    actor_email=None,
    action="",
    resource="",
    resource_id=None,
    status="SUCCESS",
    severity="INFO",
    metadata=None,
    ip_address=None,
    user_agent=None
):
    """
    Regista um evento de auditoria de forma assíncrona ou síncrona.
    """
    try:
        AuditLog.objects.create(
            user_id=user_id,
            actor_email=actor_email,
            action=action,
            resource=resource,
            resource_id=str(resource_id) if resource_id else None,
            status=status,
            severity=severity,
            metadata=metadata or {},
            ip_address=ip_address,
            user_agent=user_agent
        )
    except Exception as e:
        logger.error(f"Falha ao registar log de auditoria: {e}")


