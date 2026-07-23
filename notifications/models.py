import uuid
from django.db import models
from django.utils import timezone


# ─────────────────────────────────────────────
#  Tipos de notificação centralizados
# ─────────────────────────────────────────────

class NotificationType(models.TextChoices):
    # Ofertas
    NEW_INTEREST       = 'new_interest',       'Novo interesse na tua oferta'
    INTEREST_ACCEPTED  = 'interest_accepted',  'O teu interesse foi aceite'
    INTEREST_REJECTED  = 'interest_rejected',  'O teu interesse foi rejeitado'
    INTEREST_CANCELLED = 'interest_cancelled', 'Um interessado cancelou'
    OFFER_EXPIRED      = 'offer_expired',       'A tua oferta expirou'
    # Chat
    NEW_MESSAGE        = 'new_message',        'Nova mensagem'
    DEAL_ACCEPTED      = 'deal_accepted',      'Acordo aceite na conversa'
    DEAL_CANCELLED     = 'deal_cancelled',     'Acordo cancelado'
    # Câmbios
    RATE_ALERT         = 'rate_alert',         'Alerta de câmbio'
    # Sistema
    ACCOUNT_VERIFIED   = 'account_verified',   'Conta verificada'
    ACCOUNT_REJECTED   = 'account_rejected',   'Verificação rejeitada'
    ACCOUNT_SUSPENDED  = 'account_suspended',  'Conta Suspensa'
    SYSTEM             = 'system',             'Notificação do sistema'
    NEW_USER_REGISTRATION = 'new_user_registration', 'Novo Utilizador Registado'
    USER_PROFILE_UPDATED  = 'user_profile_updated',  'Perfil Atualizado'
    KYC_SUBMITTED         = 'kyc_submitted',         'Documento Submetido'
    USER_REPORTED         = 'user_reported',         'Utilizador Denunciado'



# ─────────────────────────────────────────────
#  Notificação
# ─────────────────────────────────────────────

class Notification(models.Model):
    """
    Registo persistente de cada notificação enviada a um utilizador.
    Serve ao mesmo tempo como histórico (in-app) e como base
    para o envio via WebSocket, email e push.
    """

    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    recipient = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    actor     = models.ForeignKey(
        'users.User',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='notifications_caused',
        help_text='Utilizador que desencadeou a notificação. Null = sistema.'
    )

    type      = models.CharField(
        max_length=30,
        choices=NotificationType.choices
    )
    title     = models.CharField(max_length=120)
    body      = models.CharField(max_length=300)

    # Dados extra para o frontend reconstruir a acção
    # ex: {'offer_id': '...', 'room_id': '...', 'redirect': '/offers/123'}
    payload   = models.JSONField(default=dict, blank=True)

    # Estado
    is_read      = models.BooleanField(default=False)
    read_at      = models.DateTimeField(null=True, blank=True)

    # Controlo de envio
    is_sent_ws   = models.BooleanField(default=False)  # enviado via WebSocket
    is_sent_email = models.BooleanField(default=False)
    is_sent_push  = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Notificação'
        verbose_name_plural = 'Notificações'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at']),
            models.Index(fields=['recipient', 'type']),
        ]

    def __str__(self):
        return f'[{self.type}] → {self.recipient.full_name}: {self.title}'

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

    def to_websocket_payload(self):
        """Payload serializado para enviar via WebSocket."""
        return {
            'id':         str(self.id),
            'type':       self.type,
            'title':      self.title,
            'body':       self.body,
            'payload':    self.payload,
            'is_read':    self.is_read,
            'created_at': self.created_at.isoformat(),
            'actor': {
                'id':       str(self.actor.id),
                'name':     self.actor.full_name,
                'avatar':   self.actor.avatar.url if self.actor.avatar else None,
            } if self.actor else None,
        }


# ─────────────────────────────────────────────
#  Preferências de notificação por utilizador
# ─────────────────────────────────────────────

class NotificationPreference(models.Model):
    """
    Cada utilizador escolhe quais notificações quer receber
    e por que canal. Criada automaticamente com o utilizador.
    """

    CHANNEL = [
        ('in_app', 'In-App'),
        ('email',  'Email'),
        ('push',   'Push'),
    ]

    id      = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user    = models.OneToOneField(
        'users.User',
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    channel = models.CharField(max_length=10, choices=CHANNEL, default='in_app')

    # Cada tipo tem um toggle independente
    new_interest       = models.BooleanField(default=True)
    interest_accepted  = models.BooleanField(default=True)
    interest_rejected  = models.BooleanField(default=True)
    interest_cancelled = models.BooleanField(default=True)
    offer_expired      = models.BooleanField(default=True)
    new_message        = models.BooleanField(default=True)
    deal_accepted      = models.BooleanField(default=True)
    deal_cancelled     = models.BooleanField(default=True)
    rate_alert         = models.BooleanField(default=False)  # off por defeito
    account_verified   = models.BooleanField(default=True)
    system             = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Preferências de notificação'

    def __str__(self):
        return f'Preferências de {self.user.full_name}'

    def allows(self, notification_type: str) -> bool:
        """Verifica se o utilizador quer receber este tipo de notificação."""
        return getattr(self, notification_type, True)


# ─────────────────────────────────────────────
#  Dispositivos para Push (FCM / APNs)
# ─────────────────────────────────────────────

class PushDevice(models.Model):
    """
    Token de dispositivo registado para push notifications.
    Um utilizador pode ter vários dispositivos (mobile + web).
    """

    PLATFORM = [
        ('android', 'Android (FCM)'),
        ('ios',     'iOS (APNs)'),
        ('web',     'Web (FCM Web)'),
    ]

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user          = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='push_devices'
    )
    platform      = models.CharField(max_length=10, choices=PLATFORM)
    token         = models.TextField(unique=True)
    device_name   = models.CharField(max_length=100, blank=True)  # ex: "iPhone 15"
    is_active     = models.BooleanField(default=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    last_used_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Dispositivo Push'
        verbose_name_plural = 'Dispositivos Push'

    def __str__(self):
        return f'{self.user.full_name} — {self.get_platform_display()}'