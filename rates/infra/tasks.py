"""
Celery task para actualizar as taxas de câmbio a cada 5 minutos.
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def fetch_rates(self):
    """
    Busca taxas de câmbio da API externa e actualiza o modelo ExchangeRate
    para todos os pares de moedas activas na plataforma.
    """
    from offers.models import Currency, ExchangeRate
    from rates.infra.providers.exchangerate_api import ExchangeRateAPIProvider
    from django.core.cache import cache

    currencies = list(Currency.objects.filter(is_active=True).values_list('code', flat=True))
    if not currencies:
        return 'Nenhuma moeda activa encontrada.'

    provider = ExchangeRateAPIProvider()
    total    = 0

    for base_code in currencies:
        rates = provider.fetch(base_currency=base_code)
        if not rates:
            logger.warning('Sem taxas para moeda base: %s', base_code)
            continue

        try:
            base_currency = Currency.objects.get(code=base_code)
        except Currency.DoesNotExist:
            continue

        for target_code, rate_value in rates.items():
            if target_code == base_code:
                continue
            try:
                target_currency = Currency.objects.get(code=target_code)
            except Currency.DoesNotExist:
                continue  # Moeda não está na plataforma

            ExchangeRate.objects.update_or_create(
                from_currency=base_currency,
                to_currency=target_currency,
                defaults={'rate': rate_value, 'source': 'open.er-api.com'},
            )
            cache.delete(f"rate_{base_code}_{target_code}".lower())
            total += 1

    cache.delete('all_exchange_rates')
    logger.info('fetch_rates: %d pares de câmbio actualizados.', total)
    return f'{total} par(es) de câmbio actualizados.'
