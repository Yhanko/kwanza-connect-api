"""
Tarefas Assíncronas e Periódicas de Segurança, Backups e DRP (Celery).
KwanzaConnect API — Diretrizes do Sandbox BNA (RPO <= 15m).
"""

from celery import shared_task
import logging

from .services.backup_service import BackupService

logger = logging.getLogger('security')


@shared_task
def run_scheduled_backup_task():
    """
    Executa a rotina periódica de backup criptografado do banco de dados (RPO <= 15m).
    Agendado no Celery Beat.
    """
    try:
        logger.info("==> [BCP/DRP] Iniciando backup periódico agendado do PostgreSQL...")
        backup_log = BackupService.create_database_backup()
        logger.info(f"==> [BCP/DRP] Backup {backup_log.filename} criado com sucesso ({backup_log.file_size_bytes} bytes).")
        return f"Backup {backup_log.filename} criado."
    except Exception as exc:
        logger.error(f"==> [BCP/DRP ERRO] Falha ao criar backup periódico: {exc}")
        return f"Falha: {exc}"


@shared_task
def run_disaster_recovery_drill_task():
    """
    Executa a simulação periódica automatizada de recuperação de desastres (DRP Drill).
    """
    try:
        logger.info("==> [BCP/DRP] Executando simulado de Disaster Recovery (DRP Drill)...")
        success, rto_seconds, notes = BackupService.run_disaster_recovery_drill()
        logger.info(f"==> [BCP/DRP] DRP Drill concluído: Sucesso={success}, RTO={rto_seconds}s.")
        return notes
    except Exception as exc:
        logger.error(f"==> [BCP/DRP ERRO] Falha no simulado de recuperação de desastres: {exc}")
        return f"Falha: {exc}"
