import logging
import uuid
from typing import Optional, Dict, Any
from ..domain.entities import AuditLogEntity
from ..domain.interfaces import IAuditRepository

logger = logging.getLogger('audit')

class RegisterAuditLogUseCase:
    def __init__(self, repository: IAuditRepository):
        self.repository = repository

    def execute(self, action: str, resource: str, user_id=None, resource_id=None, metadata=None, ip_address=None, user_agent=None) -> Optional[AuditLogEntity]:
        sensitive_fields = ['password', 'password_confirm', 'current_password', 'new_password', 'token', 'access', 'refresh']
        safe_metadata = {}
        if metadata:
            for k, v in metadata.items():
                if k in sensitive_fields:
                    safe_metadata[k] = '********'
                elif isinstance(v, uuid.UUID):
                    safe_metadata[k] = str(v)
                else:
                    safe_metadata[k] = v
        
        # Garantir que o resource_id é uma string para não falhar no CharField
        if resource_id is not None:
            resource_id = str(resource_id)

        # Criar a entidade
        audit_log = AuditLogEntity(
            id=None,
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            metadata=safe_metadata,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # 1. Terminal Logging (Auditoria em Tempo Real)
        user_info = f"User: {user_id}" if user_id else "Anonymous"
        terminal_msg = (
            f"\n[AUDIT LOG] {audit_log.timestamp:%Y-%m-%d %H:%M:%S}\n"
            f"  Action: {action}\n"
            f"  Resource: {resource} ({resource_id or 'N/A'})\n"
            f"  {user_info} | IP: {ip_address or 'Local'}\n"
        )
        print(terminal_msg)
        
        # Logs de ficheiro
        logger.info(f"{action} | {resource} | {user_info} | {safe_metadata}")

        # 2. Database Auditing (Persistência Fail-Safe)
        try:
            return self.repository.save(audit_log)
        except Exception as e:
            # Nunca bloquear o fluxo principal da aplicação por um erro de auditoria
            logger.error(f"FAIL-SAFE: Erro ao gravar auditoria: {str(e)}")
            return None
