from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from .infra.models import AuditLog

logger = logging.getLogger(__name__)

@shared_task
def cleanup_old_audit_logs():
    """
    Deleta registos de auditoria (AuditLog) mais antigos do que 7 dias.
    Executado como uma tarefa periódica via Celery Beat (configurado em settings.py).
    """
    cutoff_date = timezone.now() - timedelta(days=7)
    deleted_count, _ = AuditLog.objects.filter(timestamp__lt=cutoff_date).delete()
    
    logger.info(f"Limpeza de AuditLog: {deleted_count} registos apagados (anteriores a {cutoff_date}).")
    
    return f"Apagados {deleted_count} logs."
