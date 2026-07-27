from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Any
import uuid
from decimal import Decimal

@dataclass
class CurrencyEntity:
    id: uuid.UUID
    code: str
    name: str
    symbol: str
    flag_emoji: str = ""
    is_active: bool = True
    sort_order: int = 0

@dataclass
class ExchangeRateEntity:
    id: uuid.UUID
    from_currency_id: uuid.UUID
    to_currency_id: uuid.UUID
    rate: Decimal
    source: str = "api"
    fetched_at: Optional[datetime] = None

@dataclass
class OfferEntity:
    id: uuid.UUID
    owner_id: uuid.UUID
    give_currency_id: uuid.UUID
    give_amount: Decimal
    want_currency_id: uuid.UUID
    want_amount: Decimal
    exchange_rate_snapshot: Decimal
    offer_type: str = 'sell'
    status: str = 'active'
    payment_methods: List[str] = field(default_factory=list)
    notes: str = ""
    views_count: int = 0
    city: str = ""
    country_code: str = ""
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    implied_rate: Optional[Decimal] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    owner: Optional[Any] = None
    give_currency: Optional[Any] = None
    want_currency: Optional[Any] = None

    def __post_init__(self):
        if self.give_amount and self.want_amount and not self.implied_rate:
            self.implied_rate = round(self.give_amount / self.want_amount, 8)

    @property
    def is_active(self) -> bool:
        from django.utils import timezone
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return self.status == 'active'

    @property
    def spread_percentage(self) -> Optional[float]:
        if not self.exchange_rate_snapshot or not self.implied_rate:
            return None
        spread = ((self.implied_rate - self.exchange_rate_snapshot) 
                  / self.exchange_rate_snapshot) * 100
        return float(round(spread, 2))

@dataclass
class OfferInterestEntity:
    id: uuid.UUID
    offer_id: uuid.UUID
    buyer_id: uuid.UUID
    status: str = 'pending'
    message: str = ""
    room_id: Optional[uuid.UUID] = None
    created_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None
    buyer: Optional[Any] = None
    room: Optional[Any] = None

