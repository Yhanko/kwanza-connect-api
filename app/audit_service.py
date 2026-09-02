from typing import Optional, Dict, Any
from audit.infra.repositories import DjangoAuditRepository
from audit.services.use_cases import RegisterAuditLogUseCase

# Singleton-like instance for global use
_audit_repo = DjangoAuditRepository()
_audit_use_case = RegisterAuditLogUseCase(_audit_repo)

def audit_log(
    action: str,
    resource: str,
    user_id=None,
    resource_id=None,
    metadata: Dict[str, Any] = None,
    request=None,
    status: str = 'SUCCESS',
    severity: str = 'INFO',
    actor_email: str = None
):
    """
    Helper global para registar auditoria em conformidade com o BNA.
    Extrai IP real (suporta proxy reverso), User-Agent, user_id e actor_email do request.
    """
    ip_address = None
    user_agent = None
    
    if request:
        # Tenta pegar o IP real se estiver atrás de um proxy (Traefik / Nginx)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR')
            
        user_agent = request.META.get('HTTP_USER_AGENT')
        
        # Se user_id não for passado mas o request tiver user autenticado
        if hasattr(request, 'user') and request.user.is_authenticated:
            if not user_id:
                user_id = request.user.id
            if not actor_email and hasattr(request.user, 'email'):
                actor_email = request.user.email

    # Se o email não foi passado pelo request, tenta pegar do metadata (ex: login/register)
    if not actor_email and metadata and 'email' in metadata:
        actor_email = str(metadata['email'])

    # Inferência inteligente de status e severidade para relatórios regulatórios
    upper_action = action.upper()
    if any(tag in upper_action for tag in ['FAILURE', 'FAIL', 'ERROR', 'REJECT', 'BLOCKED', 'CANCEL']):
        if status == 'SUCCESS':
            status = 'FAILURE'
        if severity == 'INFO':
            severity = 'WARNING'
    elif 'ATTEMPT' in upper_action:
        if status == 'SUCCESS':
            status = 'ATTEMPT'
    elif any(tag in upper_action for tag in ['SANCTION', 'DELETE', 'BAN', 'REVOKE', 'DISPUTE']):
        if severity == 'INFO':
            severity = 'CRITICAL'

    return _audit_use_case.execute(
        action=action,
        resource=resource,
        user_id=user_id,
        resource_id=resource_id,
        metadata=metadata,
        ip_address=ip_address,
        user_agent=user_agent,
        status=status,
        severity=severity,
        actor_email=actor_email
    )

