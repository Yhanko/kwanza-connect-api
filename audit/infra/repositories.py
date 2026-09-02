from typing import Optional, List
import uuid
from .models import AuditLog as DjangoAuditLog
from ..domain.entities import AuditLogEntity
from ..domain.interfaces import IAuditRepository

class DjangoAuditRepository(IAuditRepository):
    
    def _to_entity(self, django_log: DjangoAuditLog) -> AuditLogEntity:
        return AuditLogEntity(
            id=django_log.id,
            user_id=django_log.user_id,
            actor_email=django_log.actor_email,
            action=django_log.action,
            resource=django_log.resource,
            resource_id=django_log.resource_id,
            status=django_log.status,
            severity=django_log.severity,
            metadata=django_log.metadata,
            ip_address=django_log.ip_address,
            user_agent=django_log.user_agent,
            timestamp=django_log.timestamp
        )

    def save(self, audit_log: AuditLogEntity) -> AuditLogEntity:
        django_log = DjangoAuditLog.objects.create(
            id=audit_log.id,
            user_id=audit_log.user_id,
            actor_email=audit_log.actor_email,
            action=audit_log.action,
            resource=audit_log.resource,
            resource_id=audit_log.resource_id,
            status=audit_log.status,
            severity=audit_log.severity,
            metadata=audit_log.metadata,
            ip_address=audit_log.ip_address,
            user_agent=audit_log.user_agent
        )
        return self._to_entity(django_log)


    def get_by_user(self, user_id: uuid.UUID) -> List[AuditLogEntity]:
        logs = DjangoAuditLog.objects.filter(user_id=user_id)
        return [self._to_entity(log) for log in logs]

    def get_by_resource(self, resource: str, resource_id: Optional[str] = None) -> List[AuditLogEntity]:
        qs = DjangoAuditLog.objects.filter(resource=resource)
        if resource_id:
            qs = qs.filter(resource_id=resource_id)
        return [self._to_entity(log) for log in qs]
