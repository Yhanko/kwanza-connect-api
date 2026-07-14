from typing import Optional, List, Dict
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from offers.models import ExchangeRate, Currency, Offer, OfferInterest
from transactions.models import Transaction
from users.models import User
from ..domain.entities import PlatformStatsEntity
from ..domain.interfaces import IRatesRepository
from django.core.cache import cache

class DjangoRatesRepository(IRatesRepository):
    
    def get_exchange_rate(self, from_code: str, to_code: str) -> Optional[Decimal]:
        cache_key = f"rate_{from_code}_{to_code}".lower()
        cached_rate = cache.get(cache_key)
        if cached_rate is not None:
            return Decimal(str(cached_rate))
            
        try:
            rate = ExchangeRate.objects.get(
                from_currency__code__iexact=from_code,
                to_currency__code__iexact=to_code
            )
            cache.set(cache_key, str(rate.rate), timeout=60 * 60) # 1 hour timeout, updated by celery
            return rate.rate
        except ExchangeRate.DoesNotExist:
            return None

    def get_platform_stats(self) -> PlatformStatsEntity:
        active_offers = Offer.objects.filter(status='active').count()
        total_users = User.objects.filter(is_active=True).count()
        
        # Negócios fechados: transações com status completed
        successful_deals = Transaction.objects.filter(status='completed').count()
        
        # Traders ativos (todos os tempos): utilizadores que já criaram oferta ou completaram negócio
        offer_creators = set(Offer.objects.values_list('owner_id', flat=True))
        deal_buyers = set(Transaction.objects.filter(status='completed').values_list('buyer_id', flat=True))
        deal_sellers = set(Transaction.objects.filter(status='completed').values_list('seller_id', flat=True))
        daily_active_traders = len(offer_creators.union(deal_buyers).union(deal_sellers))
        
        # Top currencies by number of offers (either give or want)
        from django.db.models import Count
        top_qs = Currency.objects.filter(is_active=True).annotate(
            offer_count=Count('offers_give') + Count('offers_want')
        ).order_by('-offer_count')[:5]
        
        top_currencies = [
            {'code': c.code, 'name': c.name, 'count': c.offer_count} 
            for c in top_qs if c.offer_count > 0
        ]
        
        # If no offers exist yet, provide defaults for UI
        if not top_currencies:
            default_top = Currency.objects.filter(is_active=True)[:3]
            top_currencies = [{'code': c.code, 'name': c.name, 'count': 0} for c in default_top]

        # Available currencies
        available_currencies = list(Currency.objects.filter(is_active=True).values('code', 'name', 'symbol', 'flag_emoji'))
        
        return PlatformStatsEntity(
            active_offers=active_offers,
            total_users=total_users,
            successful_deals=successful_deals,
            top_currencies=top_currencies,
            daily_active_traders=daily_active_traders,
            available_currencies=available_currencies
        )

    def list_all_rates(self) -> List[Dict]:
        cache_key = "all_exchange_rates"
        cached_rates = cache.get(cache_key)
        
        if cached_rates is not None:
            return cached_rates
            
        rates = ExchangeRate.objects.select_related('from_currency', 'to_currency').all()
        result = [{
            'from': r.from_currency.code,
            'to': r.to_currency.code,
            'rate': r.rate,
            'fetched_at': r.fetched_at
        } for r in rates]
        
        cache.set(cache_key, result, timeout=60 * 60)
        return result
