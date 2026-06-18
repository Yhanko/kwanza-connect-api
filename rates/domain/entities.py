from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, Any, Optional
import uuid

@dataclass
class ConversionResultEntity:
    from_code: str
    to_code: str
    amount: Decimal
    rate: Decimal
    result: Decimal

@dataclass
class PlatformStatsEntity:
    active_offers: int
    total_users: int
    successful_deals: int
    top_currencies: list
    daily_active_traders: int = 0
    available_currencies: list = field(default_factory=list)
