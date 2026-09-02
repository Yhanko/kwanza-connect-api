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

