"""
Provider de taxas de câmbio usando open.er-api.com (gratuita, sem chave).
Documentação: https://www.exchangerate-api.com/docs/free
"""
import logging
import requests
from django.conf import settings
from rates.domain.contracts import IRateProvider

logger = logging.getLogger(__name__)

# Timeout de segurança — não bloqueia a app se a API externa falhar
REQUEST_TIMEOUT = 10  # segundos


class ExchangeRateAPIProvider(IRateProvider):
    """
    Implementação concreta usando open.er-api.com.
    Não expõe erros internos — regista no log e devolve dict vazio.
    """

    def __init__(self):
        self.base_url = getattr(settings, 'EXCHANGE_RATE_BASE_URL', 'https://open.er-api.com/v6/latest')
        self.api_key  = getattr(settings, 'EXCHANGE_RATE_API_KEY', '')

    def fetch(self, base_currency: str = 'USD') -> dict:
        url = f'{self.base_url}/{base_currency}'
        if self.api_key:
            url += f'?apikey={self.api_key}'

        try:
            timeout = getattr(settings, 'EXCHANGE_RATE_TIMEOUT', 15)
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            data = response.json()
        except requests.Timeout:
            logger.warning('ExchangeRateAPI timeout para moeda base: %s', base_currency)
            return {}
        except requests.RequestException as exc:
            logger.error('ExchangeRateAPI erro HTTP: %s', exc)
            return {}
        except Exception as exc:
            logger.error('ExchangeRateAPI erro inesperado: %s', exc)
            return {}

        if data.get('result') != 'success':
            logger.warning(
                'ExchangeRateAPI retornou resultado não-success para %s: %s',
                base_currency, data.get('error-type', 'unknown')
            )
            return {}

        return data.get('rates', {})
