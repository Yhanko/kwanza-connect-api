"""
Módulo de Monitoramento de Spread Cambial & Banda Regulamentar do BNA.
Objetivo: Prevenir especulação predatória (Price Gouging) e operações de lavagem de capitais
disfarçadas de taxas cambiais irreais ou fictícias (Lei n.º 05/20 e Avisos Cambiais do BNA).
"""
from decimal import Decimal
from typing import Tuple, Dict, Any, Optional
from django.conf import settings
from django.utils import timezone


class BNASpreadMonitor:
    """
    Monitora a conformidade de cotações cambiais face às taxas de referência do BNA.
    Limites padrão de tolerância da Sandbox Regulatória:
    - Alerta Preventivo (SAR / Warning): Desvio > 30% da taxa de referência
    - Bloqueio Estrito (Block): Desvio > 60% da taxa de referência (Taxa Abusiva/Fraudulenta)
    """
    # Taxas de referência de fallback caso o serviço externo de taxas esteja temporariamente indisponível
    FALLBACK_REFERENCE_RATES: Dict[str, Decimal] = {
        'USD': Decimal('950.00'),
        'EUR': Decimal('1050.00'),
        'GBP': Decimal('1200.00'),
        'BRL': Decimal('170.00'),
        'ZAR': Decimal('52.00'),
        'CNY': Decimal('130.00'),
        'CAD': Decimal('700.00'),
        'CHF': Decimal('1080.00'),
        'AED': Decimal('258.00'),
    }

    # Percentuais de tolerância
    WARNING_DEVIATION_PERCENT: float = 30.0
    MAX_ALLOWED_DEVIATION_PERCENT: float = 60.0

    @classmethod
    def get_reference_rate(cls, from_currency: str, to_currency: str) -> Optional[Decimal]:
        """
        Obtém a taxa de câmbio de referência oficial ou de mercado.
        Normaliza para o par contra AOA (Kwanza).
        """
        from_code = (from_currency or '').upper().strip()
        to_code = (to_currency or '').upper().strip()

        if from_code == to_code:
            return Decimal('1.00')

        # Se for Moeda Estrangeira -> AOA
        if to_code == 'AOA' and from_code in cls.FALLBACK_REFERENCE_RATES:
            try:
                from rates.infra.repository import RatesRepository
                repo = RatesRepository()
                live_rate = repo.get_exchange_rate(from_code, to_code)
                if live_rate and live_rate > Decimal('0'):
                    return live_rate
            except Exception:
                pass
            return cls.FALLBACK_REFERENCE_RATES[from_code]

        # Se for AOA -> Moeda Estrangeira
        if from_code == 'AOA' and to_code in cls.FALLBACK_REFERENCE_RATES:
            try:
                from rates.infra.repository import RatesRepository
                repo = RatesRepository()
                live_rate = repo.get_exchange_rate(from_code, to_code)
                if live_rate and live_rate > Decimal('0'):
                    return live_rate
            except Exception:
                pass
            rate_aoa = cls.FALLBACK_REFERENCE_RATES[to_code]
            return Decimal('1.00') / rate_aoa

        return None

    @classmethod
    def check_exchange_rate_spread(
        cls,
        offered_rate: Decimal,
        from_currency: str,
        to_currency: str
    ) -> Tuple[bool, bool, float, str]:
        """
        Avalia se a taxa proposta pelo utilizador está dentro da banda permitida pelo BNA.
        
        Retorna:
        - is_valid (bool): Se a oferta pode ser criada (True) ou se deve ser bloqueada (False).
        - is_warning (bool): Se deve disparar alerta preventivo SAR de desvio cambial.
        - deviation_percent (float): Percentual absoluto de desvio da taxa de referência.
        - reason (str): Mensagem descritiva da análise.
        """
        if not offered_rate or offered_rate <= Decimal('0'):
            return False, True, 100.0, "Taxa de câmbio deve ser estritamente positiva."

        from_code = (from_currency or '').upper().strip()
        to_code = (to_currency or '').upper().strip()

        ref_rate = cls.get_reference_rate(from_code, to_code)
        if not ref_rate or ref_rate <= Decimal('0'):
            # Par sem taxa de referência oficial cadastrada -> aprova sem bloqueio
            return True, False, 0.0, "Par cambial sem taxa de referência estrita."

        comp_offered = offered_rate
        comp_ref = ref_rate

        # Calcula desvio percentual relativo
        diff = abs(comp_offered - comp_ref)
        deviation_percent = float((diff / comp_ref) * Decimal('100.0'))

        if deviation_percent > cls.MAX_ALLOWED_DEVIATION_PERCENT:
            msg = (
                f"Taxa de câmbio rejeitada: A cotação proposta ({comp_offered}) excede a banda máxima "
                f"de tolerância regulamentar do BNA ({cls.MAX_ALLOWED_DEVIATION_PERCENT}%). "
                f"Taxa de referência BNA: {comp_ref:.2f} (Desvio: {deviation_percent:.1f}%)."
            )
            return False, True, deviation_percent, msg

        if deviation_percent > cls.WARNING_DEVIATION_PERCENT:
            msg = (
                f"Alerta de desvio cambial: A cotação proposta apresenta desvio de {deviation_percent:.1f}% "
                f"face à taxa de referência do BNA ({comp_ref:.2f})."
            )
            return True, True, deviation_percent, msg

        return True, False, deviation_percent, "Taxa cambial em conformidade com a banda BNA."
