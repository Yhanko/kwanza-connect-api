import uuid
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError


# ─────────────────────────────────────────────
#  Moedas
# ─────────────────────────────────────────────

class Currency(models.Model):
    """
    Tabela de moedas suportadas na plataforma.
    Populada via fixture ou management command.
    """
    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code      = models.CharField(max_length=10, unique=True)   # AOA, USD, EUR, GBP...
    name      = models.CharField(max_length=60)                # Kwanza, Dólar...
    symbol    = models.CharField(max_length=10)                # Kz, $, €...
    flag_emoji = models.CharField(max_length=10, blank=True)   # 🇦🇴, 🇺🇸...
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)   # AOA aparece primeiro

    class Meta:
        verbose_name = 'Moeda'
        verbose_name_plural = 'Moedas'
        ordering = ['sort_order', 'code']

    def __str__(self):
        return f'{self.flag_emoji} {self.code} — {self.name}'


# ─────────────────────────────────────────────
#  Taxas de câmbio (actualizadas pelo Celery)
# ─────────────────────────────────────────────

class ExchangeRate(models.Model):
    """
    Última taxa de câmbio conhecida entre dois pares de moedas.
    Actualizada a cada 5 minutos pela task Celery.
    """
    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_currency = models.ForeignKey(
        Currency, on_delete=models.CASCADE, related_name='rates_as_base'
    )
    to_currency   = models.ForeignKey(
        Currency, on_delete=models.CASCADE, related_name='rates_as_quote'
    )
    rate          = models.DecimalField(max_digits=24, decimal_places=8)
    source        = models.CharField(max_length=50, default='api')  # fonte da taxa
    fetched_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Taxa de câmbio'
        unique_together = [['from_currency', 'to_currency']]
        ordering = ['-fetched_at']

    def __str__(self):
        return f'1 {self.from_currency.code} = {self.rate} {self.to_currency.code}'


# ─────────────────────────────────────────────
#  Ofertas
# ─────────────────────────────────────────────

class Offer(models.Model):
    """
    Oferta publicada por um utilizador.

    O utilizador diz:
      - Tenho  [give_amount]  [give_currency]
      - Quero  [want_amount]  [want_currency]
      - A taxa de câmbio no momento da publicação fica guardada
        em [exchange_rate_snapshot] para histórico.

    A plataforma não executa a troca — serve apenas para
    conectar compradores e vendedores.
    """

    OFFER_TYPE = [
        ('sell', 'Vender'),   # tenho AOA, quero USD
        ('buy',  'Comprar'),  # tenho USD, quero AOA
    ]

    STATUS = [
        ('active',  'Activa'),     # visível e aberta a interesses
        ('paused',  'Pausada'),    # dono pausou temporariamente
        ('dealing', 'Em negócio'), # dono aceitou pelo menos um interesse
        ('closed',  'Fechada'),    # dono fechou manualmente
        ('expired', 'Expirada'),   # passou a data de expiração
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner       = models.ForeignKey(
        'users.User', on_delete=models.CASCADE, related_name='offers'
    )

    # Moedas e valores
    give_currency = models.ForeignKey(
        Currency, on_delete=models.PROTECT, related_name='offers_give'
    )
    give_amount   = models.DecimalField(max_digits=24, decimal_places=2)

    want_currency = models.ForeignKey(
        Currency, on_delete=models.PROTECT, related_name='offers_want'
    )
    want_amount   = models.DecimalField(max_digits=24, decimal_places=2)

    # Taxa de câmbio real no momento da publicação (read-only depois de criada)
    exchange_rate_snapshot = models.DecimalField(
        max_digits=24, decimal_places=8,
        help_text='Taxa de câmbio real no momento da publicação.'
    )

    # Taxa implícita da oferta: give_amount / want_amount
    # Calculada automaticamente, permite comparar com a taxa real
    implied_rate  = models.DecimalField(
        max_digits=24, decimal_places=8, null=True, blank=True
    )

    offer_type    = models.CharField(max_length=4, choices=OFFER_TYPE, default='sell')
    status        = models.CharField(max_length=10, choices=STATUS, default='active')
    
    payment_methods = models.JSONField(
        default=list, 
        blank=True,
        help_text='Ex: ["Multicaixa Express", "Wise", "PayPal"]'
    )
    
    notes         = models.TextField(
        max_length=500, blank=True,
        help_text='Observações visíveis a outros utilizadores.'
    )
    views_count   = models.PositiveIntegerField(default=0)

    # Localização (para filtros e KYC/Anti-fraude)
    city          = models.CharField(max_length=100, blank=True)
    country_code  = models.CharField(max_length=5, blank=True)
    latitude      = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude     = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)

    expires_at    = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Oferta'
        verbose_name_plural = 'Ofertas'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'give_currency', 'want_currency']),
            models.Index(fields=['owner', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return (
            f'{self.owner.full_name} | '
            f'{self.give_amount} {self.give_currency.code} → '
            f'{self.want_amount} {self.want_currency.code} '
            f'[{self.get_status_display()}]'
        )

    def clean(self):
        if self.give_currency == self.want_currency:
            raise ValidationError('As moedas de origem e destino não podem ser iguais.')
        if self.give_amount <= 0 or self.want_amount <= 0:
            raise ValidationError('Os valores têm de ser positivos.')

    def save(self, *args, **kwargs):
        # Calcula a taxa implícita da oferta automaticamente
        if self.give_amount and self.want_amount:
            self.implied_rate = round(self.give_amount / self.want_amount, 8)
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return self.status == 'active'

    @property
    def spread_percentage(self):
        """
        Diferença percentual entre a taxa da oferta e a taxa real de mercado.
        Útil para o utilizador perceber se a oferta é boa ou não.
        """
        if not self.exchange_rate_snapshot or not self.implied_rate:
            return None
        spread = ((self.implied_rate - self.exchange_rate_snapshot)
                  / self.exchange_rate_snapshot) * 100
        return round(spread, 2)

    def interests_pending(self):
        return self.interests.filter(status='pending')

    def pause(self):
        self.status = 'paused'
        self.save(update_fields=['status', 'updated_at'])

    def resume(self):
        self.status = 'active'
        self.save(update_fields=['status', 'updated_at'])

    def close(self):
        self.status = 'closed'
        self.save(update_fields=['status', 'updated_at'])


# ─────────────────────────────────────────────
#  Interesse numa oferta ("botão comprar")
# ─────────────────────────────────────────────

class OfferInterest(models.Model):
    """
    Quando um utilizador clica em "Tenho interesse" / "Comprar"
    numa oferta, é criado um OfferInterest.

    O dono da oferta vê a lista de interessados e pode:
      - Aceitar  → sala de chat criada automaticamente
      - Rejeitar → interessado notificado

    O interessado pode:
      - Cancelar antes de ser aceite/rejeitado
    """

    STATUS = [
        ('pending',   'Aguardando resposta'),
        ('accepted',  'Aceite'),
        ('rejected',  'Rejeitado'),
        ('cancelled', 'Cancelado pelo interessado'),
        ('chat_open', 'Chat aberto'),
    ]

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    offer      = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='interests')
    buyer      = models.ForeignKey(
        'users.User', on_delete=models.CASCADE, related_name='interests'
    )
    status     = models.CharField(max_length=12, choices=STATUS, default='pending')
    message    = models.TextField(
        max_length=300, blank=True,
        help_text='Mensagem opcional do interessado ao vendedor.'
    )

    # Referência à sala criada após aceitação
    room       = models.ForeignKey(
        'chat.Room', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='interests'
    )


    created_at   = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Interesse em oferta'
        verbose_name_plural = 'Interesses em ofertas'
        unique_together = [['offer', 'buyer']]   # 1 interesse por par oferta/comprador
        ordering = ['-created_at']

    def __str__(self):
        return (
            f'{self.buyer.full_name} interessado em '
            f'{self.offer} [{self.get_status_display()}]'
        )

    def accept(self, accepted_by):
        """
        Aceita o interesse:
        1. Muda estado para 'accepted' → 'chat_open'
        2. Muda oferta para 'dealing'
        3. Cria sala de chat entre dono e comprador
        4. Regista evento na sala
        5. Dispara notificações
        """
        from chat.models import Room, RoomMember, RoomEvent
        from notifications.models import Notification

        # Validações
        if self.status != 'pending':
            raise ValidationError('Só é possível aceitar interesses pendentes.')
        if accepted_by != self.offer.owner:
            raise ValidationError('Apenas o dono da oferta pode aceitar.')

        # Procura sala existente entre dono e comprador
        existing_room = Room.objects.filter(
            members__user=self.offer.owner
        ).filter(
            members__user=self.buyer
        ).exclude(status='closed').distinct().first()

        if existing_room:
            room = existing_room
            room.offer = self.offer
            room.save(update_fields=['offer'])
        else:
            # Cria nova sala de chat
            room = Room.objects.create(
                offer=self.offer,
                room_type='offer',
                status='active',
            )
            RoomMember.objects.create(room=room, user=self.offer.owner, is_admin=True)
            RoomMember.objects.create(room=room, user=self.buyer)


        RoomEvent.objects.create(
            room=room,
            actor=accepted_by,
            event_type='room_created',
            payload={
                'offer_id':   str(self.offer.id),
                'give':       f'{self.offer.give_amount} {self.offer.give_currency.code}',
                'want':       f'{self.offer.want_amount} {self.offer.want_currency.code}',
            }
        )

        # Actualiza estados
        self.status       = 'chat_open'
        self.room         = room
        self.responded_at = timezone.now()
        self.save(update_fields=['status', 'room', 'responded_at'])

        self.offer.status = 'dealing'
        self.offer.save(update_fields=['status', 'updated_at'])

        # Notificação para o comprador
        Notification.objects.create(
            user=self.buyer,
            type='interest_accepted',
            payload={
                'offer_id': str(self.offer.id),
                'room_id':  str(room.id),
                'message':  f'{self.offer.owner.full_name} aceitou o teu interesse.',
            }
        )

        return room

    def reject(self, rejected_by):
        if self.status != 'pending':
            raise ValidationError('Só é possível rejeitar interesses pendentes.')
        if rejected_by != self.offer.owner:
            raise ValidationError('Apenas o dono da oferta pode rejeitar.')

        from notifications.models import Notification


        self.status       = 'rejected'
        self.responded_at = timezone.now()
        self.save(update_fields=['status', 'responded_at'])

        Notification.objects.create(
            user=self.buyer,
            type='interest_rejected',
            payload={
                'offer_id': str(self.offer.id),
                'message':  f'O teu interesse foi rejeitado.',
            }
        )

    def cancel(self, cancelled_by):
        if self.status not in ('pending',):
            raise ValidationError('Só podes cancelar um interesse pendente.')
        if cancelled_by != self.buyer:
            raise ValidationError('Só o interessado pode cancelar.')

        self.status = 'cancelled'
        self.save(update_fields=['status'])


# ─────────────────────────────────────────────
#  Visualizações de oferta (analytics simples)
# ─────────────────────────────────────────────

class OfferView(models.Model):
    """
    Regista cada vez que um utilizador autenticado vê uma oferta.
    Permite ao dono da oferta ver quantas pessoas viram o anúncio.
    """
    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    offer     = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='views')
    user      = models.ForeignKey(
        'users.User', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='offer_views'
    )
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Visualização de oferta'
        indexes = [models.Index(fields=['offer', 'viewed_at'])]