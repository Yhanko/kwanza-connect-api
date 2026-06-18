"""
Use cases do módulo rates.
Orquestra repositórios e lógica de negócio operando sobre Entidades.
"""
from decimal import Decimal
from typing import Dict, Any
from rest_framework.exceptions import ValidationError, NotFound

from ..domain.entities import ConversionResultEntity, PlatformStatsEntity
from ..domain.interfaces import IRatesRepository

class GetLiveRateUseCase:
    def __init__(self, repository: IRatesRepository):
        self.repository = repository

    def execute(self, from_code: str, to_code: str) -> Decimal:
        rate = self.repository.get_exchange_rate(from_code, to_code)
        if rate is None:
            raise NotFound(f'Taxa de câmbio não disponível para {from_code}/{to_code}.')
        return rate

class ConvertAmountUseCase:
    def __init__(self, repository: IRatesRepository):
        self.repository = repository

    def execute(self, from_code: str, to_code: str, amount: Decimal) -> Dict[str, Any]:
        if amount <= 0:
            raise ValidationError('O valor deve ser positivo.')

        rate = self.repository.get_exchange_rate(from_code, to_code)
        if rate is None:
            raise NotFound(f'Taxa de câmbio não disponível para {from_code}/{to_code}.')

        result_amount = amount * rate

        return {
            'from_currency': from_code.upper(),
            'to_currency':   to_code.upper(),
            'amount':        amount,
            'rate':          rate,
            'converted_amount': result_amount
        }

class GetPlatformStatsUseCase:
    def __init__(self, repository: IRatesRepository):
        self.repository = repository

    def execute(self) -> Dict[str, Any]:
        stats = self.repository.get_platform_stats()
        return {
            'active_offers': stats.active_offers,
            'total_users': stats.total_users,
            'successful_deals': stats.successful_deals,
            'top_currencies': stats.top_currencies,
            'daily_active_traders': stats.daily_active_traders,
            'available_currencies': stats.available_currencies
        }
