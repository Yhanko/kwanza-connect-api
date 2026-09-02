from django.db import models
from django.conf import settings
import uuid

class AuditLog(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
        null=True, blank=True, related_name='audit_logs',
        db_index=True
    )
    actor_email = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    action      = models.CharField(max_length=255, db_index=True)
    resource    = models.CharField(max_length=255, db_index=True)
    resource_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    status      = models.CharField(max_length=50, default='SUCCESS', db_index=True)  # SUCCESS, FAILURE, ATTEMPT, BLOCKED
    severity    = models.CharField(max_length=20, default='INFO', db_index=True)     # INFO, WARNING, CRITICAL
    metadata    = models.JSONField(default=dict, blank=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    user_agent  = models.TextField(null=True, blank=True)
    timestamp   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Registo de Auditoria'
        verbose_name_plural = 'Registos de Auditoria'
        default_permissions = ('add', 'view')

    def save(self, *args, **kwargs):
        # Imutabilidade estrita conforme exigências de auditoria bancária / BNA (Append-Only)
        if self.pk and AuditLog.objects.filter(pk=self.pk).exists():
            raise PermissionError("Registos de auditoria são estritamente imutáveis e não podem ser alterados.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f'[{self.severity}] {self.action} on {self.resource} ({self.status}) by {self.actor_email or self.user}'

